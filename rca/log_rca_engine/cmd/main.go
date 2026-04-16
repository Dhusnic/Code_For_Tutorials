package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"runtime/debug"
	"syscall"

	"log_rca_engine/internal/checkpoint"
	"log_rca_engine/internal/config"
	"log_rca_engine/internal/elastic"
	"log_rca_engine/internal/llm"
	"log_rca_engine/internal/logger"
	"log_rca_engine/internal/models"
	"log_rca_engine/internal/rules"
	"log_rca_engine/internal/scheduler"
	"log_rca_engine/internal/scoring"
	"log_rca_engine/internal/service"
	"log_rca_engine/internal/storage"
	"log_rca_engine/internal/topology"
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

	log := logger.New(cfg.Logging).With("service", cfg.ServiceName)
	log.Info("service starting", "config_file", *configPath, "run_once", *runOnce)

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

	processor := service.NewProcessor(service.Dependencies{
		Reader:      esClient,
		Rules:       rules.NewFileLoader(cfg.Rules.File),
		Topology:    topology.NewFileRepository(cfg.Topology.File),
		Results:     storage.NewFileStore(cfg.Storage.ResultsFile, log.With("component", "results")),
		Checkpoints: checkpoint.NewStore(cfg.Storage.CheckpointFile, log.With("component", "checkpoint")),
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
		Logger:               log.With("component", "processor"),
	})

	if *runOnce {
		runCtx, cancel := context.WithTimeout(ctx, cfg.Scheduler.RunTimeout)
		defer cancel()
		if err := runProcessor(runCtx, processor); err != nil {
			log.Error("RCA cycle failed", "error", err)
			os.Exit(1)
		}
		log.Info("single RCA cycle completed")
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

func runProcessor(ctx context.Context, processor *service.Processor) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("processor panic: %v\n%s", recovered, string(debug.Stack()))
		}
	}()
	return processor.RunCycle(ctx)
}
