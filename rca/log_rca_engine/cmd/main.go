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

	"log_rca_engine/internal/autoscaling"
	"log_rca_engine/internal/checkpoint"
	"log_rca_engine/internal/config"
	"log_rca_engine/internal/configevents"
	"log_rca_engine/internal/elastic"
	"log_rca_engine/internal/llm"
	"log_rca_engine/internal/logger"
	"log_rca_engine/internal/models"
	"log_rca_engine/internal/mongoresults"
	"log_rca_engine/internal/mongosync"
	"log_rca_engine/internal/runtimeconfig"
	"log_rca_engine/internal/scheduler"
	"log_rca_engine/internal/scoring"
	"log_rca_engine/internal/service"
	"log_rca_engine/internal/storage"
	"log_rca_engine/internal/worker"
)

func main() {
	fmt.Println("=== Log RCA Engine ===")

	configPath := flag.String("config", filepath.Join(".", "config", "config.yml"), "Path to the YAML configuration file.")
	runOnce := flag.Bool("run-once", false, "Run one RCA cycle and exit.")
	flag.Parse()

	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "CRITICAL: failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	workerRuntime, err := worker.Resolve()
	if err != nil {
		fmt.Fprintf(os.Stderr, "CRITICAL: failed to resolve worker runtime: %v\n", err)
		os.Exit(1)
	}
	cfg.Storage.ResultsFile = workerRuntime.ScopedPath(cfg.Storage.ResultsFile)
	cfg.Storage.CheckpointFile = workerRuntime.ScopedPath(cfg.Storage.CheckpointFile)

	log := logger.New(cfg.Logging).With("service", cfg.ServiceName)
	log.Info(
		"service starting",
		"config_file", *configPath,
		"run_once", *runOnce,
		"worker_index", workerRuntime.Index,
		"worker_count", workerRuntime.Count,
		"results_file", cfg.Storage.ResultsFile,
		"checkpoint_file", cfg.Storage.CheckpointFile,
	)

	autoscaler := autoscaling.NewController(
		cfg.Autoscaling,
		autoscaling.SchedulerSettings{
			Interval:   cfg.Scheduler.Interval,
			RunTimeout: cfg.Scheduler.RunTimeout,
		},
		autoscaling.ReaderSettings{
			PageSize:         cfg.Elasticsearch.PageSize,
			MaxPagesPerCycle: cfg.Autoscaling.Reader.MaxPagesPerCycle,
		},
	)
	if autoscaler.Enabled() {
		log.Info(
			"runtime autoscaling enabled",
			"input_basis", cfg.Autoscaling.InputBasis,
			"reader_min_page_size", cfg.Autoscaling.Reader.MinPageSize,
			"reader_max_page_size", cfg.Autoscaling.Reader.MaxPageSize,
			"reader_max_pages_per_cycle", cfg.Autoscaling.Reader.MaxPagesPerCycle,
			"scheduler_min_interval", cfg.Autoscaling.Scheduler.MinInterval.String(),
			"scheduler_max_interval", cfg.Autoscaling.Scheduler.MaxInterval.String(),
			"scheduler_timeout_ratio", cfg.Autoscaling.Scheduler.TimeoutRatio,
			"scheduler_target_cycle_utilization", cfg.Autoscaling.Scheduler.TargetCycleUtilization,
			"scheduler_timeout_scale_up_multiplier", cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier,
		)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	esClient, err := elastic.NewClient(cfg.Elasticsearch, log.With("component", "elasticsearch"))
	if err != nil {
		log.Error("failed to create elasticsearch client", "error", err)
		os.Exit(1)
	}
	defer func() {
		if err := esClient.Close(); err != nil {
			log.Warn("failed to close elasticsearch client", "error", err)
		}
	}()

	var syncer *mongosync.Syncer
	var resultPublisher *mongoresults.Store
	resultsStore := service.ResultStore(storage.NewFileStore(cfg.Storage.ResultsFile, log.With("component", "results")))
	if cfg.MongoSync.Enabled {
		syncer = mongosync.New(cfg.MongoSync, cfg.Rules.File, cfg.Topology.File, log.With("component", "mongo_sync"))
		defer func() {
			closeCtx, cancel := context.WithTimeout(context.Background(), cfg.MongoSync.Timeout)
			defer cancel()
			if err := syncer.Close(closeCtx); err != nil {
				log.Warn("failed to close MongoDB sync client", "error", err)
			}
		}()
		if _, err := syncer.Sync(ctx); err != nil {
			log.Warn("initial MongoDB sync failed; using existing local JSON files", "error", err)
		}
	}
	if cfg.MongoSync.URI != "" && cfg.MongoSync.Database != "" && cfg.MongoSync.ResultsCollection != "" {
		resultPublisher = mongoresults.New(cfg.MongoSync, log.With("component", "mongo_results"))
		resultsStore = resultPublisher
		defer func() {
			closeCtx, cancel := context.WithTimeout(context.Background(), cfg.MongoSync.Timeout)
			defer cancel()
			if err := resultPublisher.Close(closeCtx); err != nil {
				log.Warn("failed to close MongoDB RCA result publisher", "error", err)
			}
		}()
	}

	rulesCache, err := runtimeconfig.NewRulesCache(ctx, cfg.Rules.File)
	if err != nil {
		log.Error("failed to load rules cache", "error", err)
		os.Exit(1)
	}
	topologyCache, err := runtimeconfig.NewTopologyCache(ctx, cfg.Topology.File)
	if err != nil {
		log.Error("failed to load topology cache", "error", err)
		os.Exit(1)
	}

	processor := service.NewProcessor(service.Dependencies{
		Reader:          esClient,
		Rules:           rulesCache,
		Topology:        topologyCache,
		Results:         resultsStore,
		ResultPublisher: nil,
		Checkpoints:     checkpoint.NewStore(cfg.Storage.CheckpointFile, log.With("component", "checkpoint")),
		Scorer: scoring.NewScorer(models.ScoreWeights{
			SequenceMatch:    cfg.Scoring.Weights.SequenceMatch,
			DependencyMatch:  cfg.Scoring.Weights.DependencyMatch,
			TimeProximity:    cfg.Scoring.Weights.TimeProximity,
			SignalSeverity:   cfg.Scoring.Weights.SignalSeverity,
			RuleCompleteness: cfg.Scoring.Weights.RuleCompleteness,
		}, cfg.Scoring.ConfidenceThreshold),
		Explainer:            llm.NewOpenAIConversationHandler(cfg.OpenAI, log.With("component", "openai")),
		NeighborhoodLogLimit: cfg.OpenAI.NeighborhoodLogLimit,
		NearbyLogTrigger:     cfg.Scoring.NearbyLogTriggerThreshold,
		ProbableCauseMin:     cfg.Scoring.ProbableCauseMinThreshold,
		WorkerIndex:          workerRuntime.Index,
		WorkerCount:          workerRuntime.Count,
		Autoscaler:           autoscaler,
		Logger:               log.With("component", "processor"),
	})

	var jobSyncer rcaSyncer
	if syncer != nil {
		jobSyncer = syncer
	}

	job := syncingJob{
		syncer:    jobSyncer,
		reloaders: []configReloader{rulesCache, topologyCache},
		watchers:  []configFileWatcher{rulesCache, topologyCache},
		next:      processor,
		logger:    log.With("component", "mongo_sync"),
	}
	if syncer != nil {
		closeConfigEvents := configevents.ListenRedis(ctx, cfg.MongoSync.RedisNotify, log.With("component", "config_events"), func(eventCtx context.Context, payload string) error {
			syncer.Invalidate()
			changed, err := syncer.Sync(eventCtx)
			if err != nil {
				return err
			}
			if !changed {
				return nil
			}
			if err := rulesCache.Reload(eventCtx); err != nil {
				return err
			}
			return topologyCache.Reload(eventCtx)
		})
		defer func() {
			if err := closeConfigEvents(); err != nil {
				log.Warn("failed to close config event listener", "error", err)
			}
		}()
	}

	if *runOnce {
		runCtx, cancel := context.WithTimeout(ctx, cfg.Scheduler.RunTimeout)
		defer cancel()
		if err := runJob(runCtx, job); err != nil {
			log.Error("RCA cycle failed", "error", err)
			os.Exit(1)
		}
		log.Info("single RCA cycle completed")
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

type rcaSyncer interface {
	Sync(ctx context.Context) (bool, error)
}

type configReloader interface {
	Reload(ctx context.Context) error
}

type configFileWatcher interface {
	ReloadIfChanged(ctx context.Context) (bool, error)
}

type syncingJob struct {
	syncer    rcaSyncer
	reloaders []configReloader
	watchers  []configFileWatcher
	next      scheduler.Job
	logger    *slog.Logger
}

func (j syncingJob) RunCycle(ctx context.Context) error {
	if j.syncer != nil {
		changed, err := j.syncer.Sync(ctx)
		if err != nil {
			if j.logger != nil {
				j.logger.Warn("MongoDB sync failed; using existing local JSON files", "error", err)
			}
		} else if changed {
			for _, reloader := range j.reloaders {
				if reloader == nil {
					continue
				}
				if err := reloader.Reload(ctx); err != nil {
					return fmt.Errorf("reload synced runtime config: %w", err)
				}
			}
			if j.logger != nil {
				j.logger.Info("local rules/topology JSON refreshed from MongoDB")
			}
		}
	}
	for _, watcher := range j.watchers {
		if watcher == nil {
			continue
		}
		changed, err := watcher.ReloadIfChanged(ctx)
		if err != nil {
			return fmt.Errorf("reload changed runtime config file: %w", err)
		}
		if changed && j.logger != nil {
			j.logger.Info("runtime config cache reloaded from changed JSON file")
		}
	}
	return j.next.RunCycle(ctx)
}

func runJob(ctx context.Context, job scheduler.Job) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("processor panic: %v\n%s", recovered, string(debug.Stack()))
		}
	}()
	return job.RunCycle(ctx)
}
