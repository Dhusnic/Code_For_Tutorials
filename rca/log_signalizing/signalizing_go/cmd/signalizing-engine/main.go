package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"rca/internal/rca/checkpoints"
	"rca/internal/rca/config"
	"rca/internal/rca/enrichment"
	"rca/internal/rca/es"
	"rca/internal/rca/logging"
	"rca/internal/rca/signalstream"
)

func main() {
	configPath := flag.String("config", filepath.Join("..", "config.yml"), "Path to configuration YAML file.")
	runOnce := flag.Bool("run-once", false, "Process one cycle and exit.")
	flag.Parse()

	cfg, err := config.LoadAppConfig(*configPath)
	if err != nil {
		os.Exit(1)
	}
	logging.ConfigureLogging(cfg.Logging)
	logger := logging.GetLogger("main")

	esClient, err := es.NewClient(cfg.Elasticsearch)
	if err != nil {
		logger.Exception("Fatal error in enrichment loop", err)
		os.Exit(1)
	}

	checkpointStore, err := checkpoints.CreateStore(cfg.Checkpoints, esClient)
	if err != nil {
		logger.Exception("Fatal error in enrichment loop", err)
		os.Exit(1)
	}

	var streamPublisher *signalstream.Publisher
	if cfg.SignalStream.Enabled {
		streamPublisher, err = signalstream.NewPublisher(cfg.SignalStream)
		if err != nil {
			logger.Exception("Fatal error in enrichment loop", err)
			os.Exit(1)
		}
	}

	service, err := enrichment.NewSignalEnrichmentServiceWithPublisher(esClient, cfg, checkpointStore, streamPublisher)
	if err != nil {
		logger.Exception("Fatal error in enrichment loop", err)
		os.Exit(1)
	}
	defer service.Shutdown()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	for {
		select {
		case <-ctx.Done():
			logger.Info("Shutdown requested")
			return
		default:
		}

		processed, err := service.RunCycle()
		if err != nil {
			logger.Exception("Fatal error in enrichment loop", err)
			os.Exit(1)
		}
		logger.Info("Processing cycle completed", logging.F("processed", processed))
		if *runOnce {
			return
		}
		if cfg.Pipeline.PollIntervalSeconds > 0 {
			time.Sleep(time.Duration(cfg.Pipeline.PollIntervalSeconds) * time.Second)
		}
	}
}
