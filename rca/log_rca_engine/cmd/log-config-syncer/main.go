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
	"time"

	"log_rca_engine/internal/config"
	"log_rca_engine/internal/configevents"
	"log_rca_engine/internal/logger"
	"log_rca_engine/internal/mongosync"
)

func main() {
	fmt.Println("=== Log Config Syncer ===")

	configPath := flag.String("config", filepath.Join(".", "config", "config.yml"), "Path to the YAML configuration file.")
	runOnce := flag.Bool("run-once", false, "Run one config sync and exit.")
	interval := flag.Duration("interval", 30*time.Second, "Polling interval for Mongo sync-state checks.")
	flag.Parse()

	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "CRITICAL: failed to load configuration: %v\n", err)
		os.Exit(1)
	}
	if !cfg.MongoSync.Enabled {
		fmt.Fprintln(os.Stderr, "CRITICAL: mongo_sync.enabled must be true for log-config-syncer")
		os.Exit(1)
	}
	if *interval <= 0 {
		fmt.Fprintln(os.Stderr, "CRITICAL: interval must be greater than zero")
		os.Exit(1)
	}

	log := logger.New(cfg.Logging).With("service", "log-config-syncer")
	log.Info("service starting", "config_file", *configPath, "run_once", *runOnce, "interval", interval.String())

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	syncer := mongosync.New(cfg.MongoSync, cfg.Rules.File, cfg.Topology.File, log.With("component", "mongo_sync"))
	defer func() {
		closeCtx, cancel := context.WithTimeout(context.Background(), cfg.MongoSync.Timeout)
		defer cancel()
		if err := syncer.Close(closeCtx); err != nil {
			log.Warn("failed to close MongoDB sync client", "error", err)
		}
	}()

	closeEvents := configevents.ListenRedis(ctx, cfg.MongoSync.RedisNotify, log.With("component", "config_events"), func(eventCtx context.Context, payload string) error {
		syncer.Invalidate()
		_, err := runSync(eventCtx, syncer, log)
		return err
	})
	defer func() {
		if err := closeEvents(); err != nil {
			log.Warn("failed to close config event listener", "error", err)
		}
	}()

	runCtx, cancel := context.WithTimeout(ctx, cfg.MongoSync.Timeout)
	_, err = runSync(runCtx, syncer, log)
	cancel()
	if err != nil {
		log.Warn("initial config sync failed; retrying on next interval", "error", err)
	}

	if *runOnce {
		if err != nil {
			os.Exit(1)
		}
		return
	}

	ticker := time.NewTicker(*interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Info("service stopped", "reason", ctx.Err())
			return
		case <-ticker.C:
			runCtx, cancel := context.WithTimeout(ctx, cfg.MongoSync.Timeout)
			if _, err := runSync(runCtx, syncer, log); err != nil {
				log.Warn("config sync failed", "error", err)
			}
			cancel()
		}
	}
}

type syncer interface {
	Sync(ctx context.Context) (bool, error)
}

func runSync(ctx context.Context, syncer syncer, log *slog.Logger) (changed bool, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("config sync panic: %v\n%s", recovered, string(debug.Stack()))
		}
	}()
	changed, err = syncer.Sync(ctx)
	if err == nil && log != nil {
		log.Info("config sync completed", "changed", changed)
	}
	return changed, err
}
