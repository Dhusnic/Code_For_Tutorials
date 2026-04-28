package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"runtime/debug"
	"syscall"

	"log_correlation_engine/internal/autoscaling"
	"log_correlation_engine/internal/checkpoint"
	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/configevents"
	"log_correlation_engine/internal/elastic"
	"log_correlation_engine/internal/engine"
	"log_correlation_engine/internal/loader"
	"log_correlation_engine/internal/logger"
	"log_correlation_engine/internal/mongosync"
	"log_correlation_engine/internal/redis"
	"log_correlation_engine/internal/rules"
	"log_correlation_engine/internal/scheduler"
	"log_correlation_engine/internal/service"
)

type ruleSyncer interface {
	Sync(ctx context.Context) (bool, error)
}

type ruleReloader interface {
	LoadRules() error
}

type syncingJob struct {
	syncer ruleSyncer
	rules  ruleReloader
	next   scheduler.Job
	logger *slog.Logger
}

func (j *syncingJob) RunCycle(ctx context.Context) error {
	if j.syncer != nil {
		changed, err := j.syncer.Sync(ctx)
		if err != nil {
			if j.logger != nil {
				j.logger.Warn("MongoDB rule sync failed; continuing with last local rules JSON", "error", err)
			}
		} else if changed && j.rules != nil {
			if err := j.rules.LoadRules(); err != nil {
				return fmt.Errorf("reload synced rules: %w", err)
			}
		}
	}
	return j.next.RunCycle(ctx)
}

func main() {
	fmt.Println("=== Log Correlation Engine ===")

	configPath := flag.String("config", filepath.Join(".", "config", "config.yml"), "Path to the YAML configuration file.")
	runOnce := flag.Bool("run-once", false, "Run one correlation cycle and exit.")
	flag.Parse()

	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "CRITICAL: failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	log := logger.New(cfg.Logging).With("service", cfg.ServiceName)
	log.Info("service starting", "config_file", *configPath, "run_once", *runOnce)

	autoscaler := autoscaling.NewController(
		cfg.Autoscaling,
		autoscaling.SchedulerSettings{
			Interval:   cfg.Scheduler.Interval,
			RunTimeout: cfg.Scheduler.RunTimeout,
		},
		cfg.Fetcher.GroupedLookupBatchSize,
	)
	if autoscaler.Enabled() {
		log.Info(
			"runtime autoscaling enabled",
			"input_basis", cfg.Autoscaling.InputBasis,
			"fetcher_min_grouped_lookup_batch_size", cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize,
			"fetcher_max_grouped_lookup_batch_size", cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize,
			"scheduler_min_interval", cfg.Autoscaling.Scheduler.MinInterval.String(),
			"scheduler_max_interval", cfg.Autoscaling.Scheduler.MaxInterval.String(),
			"scheduler_timeout_ratio", cfg.Autoscaling.Scheduler.TimeoutRatio,
			"scheduler_target_cycle_utilization", cfg.Autoscaling.Scheduler.TargetCycleUtilization,
			"scheduler_timeout_scale_up_multiplier", cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier,
		)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	redisClient := redis.NewClient(cfg.Redis)
	defer func() {
		if err := redisClient.Close(); err != nil {
			log.Warn("failed to close Redis client", "error", err)
		}
	}()

	pingCtx, cancelPing := context.WithTimeout(ctx, cfg.Redis.DialTimeout)
	defer cancelPing()
	if err := redisClient.Raw().Ping(pingCtx).Err(); err != nil {
		log.Error("failed to connect to Redis", "address", cfg.Redis.Address, "error", err)
		os.Exit(1)
	}

	store := redis.NewStore(redisClient.Raw(), cfg.Redis, log.With("component", "redis"))
	checkpointStore := checkpoint.NewStore(
		cfg.Engine.CheckpointDirectory,
		cfg.Redis.KeyPrefix,
		log.With("component", "checkpoint"),
	)

	writer, err := elastic.NewWriter(cfg.Elasticsearch, log.With("component", "elasticsearch"))
	if err != nil {
		log.Error("failed to create Elasticsearch writer", "error", err)
		os.Exit(1)
	}
	defer func() {
		if err := writer.Close(); err != nil {
			log.Warn("failed to close Elasticsearch writer", "error", err)
		}
	}()

	var mongoRuleSyncer *mongosync.RuleSyncer
	if cfg.MongoSync.Enabled {
		mongoRuleSyncer = mongosync.NewRuleSyncer(cfg.MongoSync, cfg.Engine.RulesFile, log.With("component", "mongo_sync"))
		defer func() {
			closeCtx, cancel := context.WithTimeout(context.Background(), cfg.MongoSync.Timeout)
			defer cancel()
			if err := mongoRuleSyncer.Close(closeCtx); err != nil {
				log.Warn("failed to close MongoDB rule syncer", "error", err)
			}
		}()
		if _, err := mongoRuleSyncer.Sync(ctx); err != nil {
			log.Warn("initial MongoDB rule sync failed; using existing local rules JSON", "error", err)
		}
	}

	ruleLoader, err := rules.NewFileLoader(cfg.Engine.RulesFile, cfg.Engine.HotReloadInterval, log.With("component", "rules"))
	if err != nil {
		log.Error("failed to load rules", "error", err)
		os.Exit(1)
	}
	defer func() {
		if err := ruleLoader.Close(); err != nil {
			log.Warn("failed to close rule loader", "error", err)
		}
	}()

	if err := ruleLoader.HotReload(); err != nil {
		log.Warn("failed to enable rule hot reload", "error", err)
	}

	correlationEngine, err := engine.NewEngine(cfg.Engine, log.With("component", "engine"))
	if err != nil {
		log.Error("failed to initialize correlation engine", "error", err)
		os.Exit(1)
	}

	logFetcher, err := buildFetcher(cfg, log)
	if err != nil {
		log.Error("failed to initialize log fetcher", "error", err)
		os.Exit(1)
	}

	processor := service.NewProcessor(service.Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: checkpointStore,
		Fetcher:     logFetcher,
		Engine:      correlationEngine,
		Rules:       ruleLoader,
		Writer:      writer,
		Autoscaler:  autoscaler,
		Logger:      log.With("component", "processor"),
	})

	job := scheduler.Job(processor)
	if mongoRuleSyncer != nil {
		job = &syncingJob{
			syncer: mongoRuleSyncer,
			rules:  ruleLoader,
			next:   processor,
			logger: log.With("component", "mongo_sync"),
		}
		configevents.ListenRedis(ctx, redisClient.Raw(), cfg.MongoSync.RedisNotify, log.With("component", "config_events"), func(eventCtx context.Context, payload string) error {
			mongoRuleSyncer.Invalidate()
			changed, err := mongoRuleSyncer.Sync(eventCtx)
			if err != nil {
				return err
			}
			if changed {
				return ruleLoader.LoadRules()
			}
			return nil
		})
	}

	if *runOnce {
		runCtx, cancel := context.WithTimeout(ctx, cfg.Scheduler.RunTimeout)
		defer cancel()

		if err := runJob(runCtx, job, log); err != nil {
			log.Error("correlation cycle failed", "error", err)
			os.Exit(1)
		}
		log.Info("single correlation cycle completed")
		return
	}

	runner := scheduler.NewRunner(scheduler.Config{
		Interval:         cfg.Scheduler.Interval,
		RunTimeout:       cfg.Scheduler.RunTimeout,
		Logger:           log.With("component", "scheduler"),
		Job:              job,
		SettingsProvider: autoscaler,
	})

	if err := runner.Run(ctx); err != nil {
		log.Error("scheduler stopped with error", "error", err)
		os.Exit(1)
	}
}

func runJob(ctx context.Context, job scheduler.Job, log *slog.Logger) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("scheduled job panic: %v\n%s", recovered, string(debug.Stack()))
			log.Error("panic recovered during processor run", "panic", recovered, "error", err)
		}
	}()
	return job.RunCycle(ctx)
}

func buildFetcher(cfg config.Config, log *slog.Logger) (loader.LogFetcher, error) {
	switch cfg.Fetcher.Mode {
	case "mock":
		return loader.NewMockLogFetcher(log.With("component", "fetcher")), nil
	case "elasticsearch":
		fetcher, err := loader.NewElasticsearchLogFetcher(
			cfg.FetcherElasticsearchConfig(),
			cfg.Fetcher.TimestampField,
			cfg.Fetcher.LogLevelField,
			log.With("component", "fetcher", "mode", "elasticsearch"),
		)
		if err != nil {
			return nil, err
		}
		fetcher.SetGroupedLookupBatchSize(cfg.Fetcher.GroupedLookupBatchSize)
		return fetcher, nil
	default:
		return nil, fmt.Errorf("unsupported fetcher mode %q", cfg.Fetcher.Mode)
	}
}
