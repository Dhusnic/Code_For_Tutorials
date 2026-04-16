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

	"log_correlation_engine/internal/checkpoint"
	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/elastic"
	"log_correlation_engine/internal/engine"
	"log_correlation_engine/internal/loader"
	"log_correlation_engine/internal/logger"
	"log_correlation_engine/internal/redis"
	"log_correlation_engine/internal/rules"
	"log_correlation_engine/internal/scheduler"
	"log_correlation_engine/internal/service"
)

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
		Logger:      log.With("component", "processor"),
	})

	if *runOnce {
		runCtx, cancel := context.WithTimeout(ctx, cfg.Scheduler.RunTimeout)
		defer cancel()

		if err := runProcessor(runCtx, processor, log); err != nil {
			log.Error("correlation cycle failed", "error", err)
			os.Exit(1)
		}
		log.Info("single correlation cycle completed")
		return
	}

	runner := scheduler.NewRunner(scheduler.Config{
		Interval:   cfg.Scheduler.Interval,
		RunTimeout: cfg.Scheduler.RunTimeout,
		Logger:     log.With("component", "scheduler"),
		Job:        processor,
	})

	if err := runner.Run(ctx); err != nil {
		log.Error("scheduler stopped with error", "error", err)
		os.Exit(1)
	}
}

func runProcessor(ctx context.Context, processor *service.Processor, log *slog.Logger) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("processor panic: %v\n%s", recovered, string(debug.Stack()))
			log.Error("panic recovered during processor run", "panic", recovered, "error", err)
		}
	}()
	return processor.RunCycle(ctx)
}

func buildFetcher(cfg config.Config, log *slog.Logger) (loader.LogFetcher, error) {
	switch cfg.Fetcher.Mode {
	case "mock":
		return loader.NewMockLogFetcher(log.With("component", "fetcher")), nil
	case "elasticsearch":
		return loader.NewElasticsearchLogFetcher(
			cfg.FetcherElasticsearchConfig(),
			cfg.Fetcher.TimestampField,
			cfg.Fetcher.LogLevelField,
			log.With("component", "fetcher", "mode", "elasticsearch"),
		)
	default:
		return nil, fmt.Errorf("unsupported fetcher mode %q", cfg.Fetcher.Mode)
	}
}
