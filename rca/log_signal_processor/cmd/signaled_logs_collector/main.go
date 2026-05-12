// Package main is the entry point for the signaled logs collector service.
// This service polls Elasticsearch periodically, extracts signal-bearing documents,
// and stores them in Redis for later correlation and analysis.
//
// Operational Sequence:
//  1. Load configuration from YAML file
//  2. Initialize structured logger with configured level and format
//  3. Connect to Elasticsearch (source of raw event logs)
//  4. Connect to Redis (destination for signal storage)
//  5. Optionally set up distributed locking for multi-worker deployment
//  6. Start scheduler that runs collection cycle at configured intervals
//  7. On each cycle: fetch → normalize → deduplicate → retain → store
//  8. Gracefully shutdown on SIGINT or SIGTERM
//
// Command-line flags:
//
//	-config: Path to YAML configuration file (default: ./config.yml)
//	-run-once: Execute one collection cycle and exit (for testing/debugging)
//
// Exit Codes:
//
//	0 - Successful shutdown
//	1 - Configuration loading failed
//	1 - Elasticsearch connection failed
//	1 - Redis connection failed
//	1 - Collection cycle failed
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
	"strconv"
	"syscall"

	"log_signal_processor/internal/config"
	"log_signal_processor/internal/elasticsearch"
	"log_signal_processor/internal/logger"
	"log_signal_processor/internal/redisstore"
	"log_signal_processor/internal/scheduler"
	"log_signal_processor/internal/service"
)

// main initializes all components and orchestrates the signal collection workflow.
// Handles graceful shutdown and distributed locking for multi-worker deployments.
//
// Flow:
//  1. Parse command-line flags
//  2. Load configuration from file
//  3. Initialize structured logger
//  4. Create Elasticsearch repository (signal document source)
//  5. Create Redis store (signal data persistence)
//  6. Set up distributed lock if enabled
//  7. Create collector service
//  8. Run once (if -run-once) or start scheduler
//  9. Wait for SIGINT/SIGTERM for graceful shutdown
//
// Logging:
//   - INFO: Startup sequence, configuration loaded
//   - DEBUG: Component initialization details
//   - ERROR: Startup failures with context
//   - WARN: Non-fatal issues (lock failures, close errors)
func main() {
	fmt.Println("=== Signaled Logs Collector ===")
	fmt.Println("Initializing service components...")

	configPath := flag.String("config", filepath.Join(".", "config.yml"), "Path to the YAML or JSON configuration file.")
	runOnce := flag.Bool("run-once", false, "Run one collection cycle and exit.")
	flag.Parse()

	// Load configuration
	fmt.Printf("Loading configuration from: %s\n", *configPath)
	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "CRITICAL: Failed to load configuration: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Configuration loaded successfully")

	// Initialize structured logger
	log := logger.New(cfg.Logging).With("service", cfg.ServiceName)
	log.Info("service starting",
		"config_file", *configPath,
		"enabled", cfg.Enabled,
		"log_level", cfg.Logging.Level,
		"log_format", cfg.Logging.Format,
	)

	// Setup context with signal handling
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if !cfg.Enabled {
		log.Warn("collector disabled by configuration; legacy Elasticsearch to Redis bridge is inactive")
		if *runOnce {
			log.Info("run-once requested while collector is disabled; exiting without work")
			return
		}
		<-ctx.Done()
		log.Info("service shutdown complete")
		return
	}

	// Connect to Elasticsearch
	log.Info("connecting to Elasticsearch",
		"addresses", cfg.Elasticsearch.Addresses,
		"index", cfg.Elasticsearch.Index,
	)
	esClient, err := elasticsearch.NewClient(cfg.Elasticsearch)
	if err != nil {
		log.Error("failed to create Elasticsearch client",
			"error", err,
			"addresses", cfg.Elasticsearch.Addresses,
		)
		os.Exit(1)
	}
	log.Info("Elasticsearch client connected")

	esRepository := elasticsearch.NewRepository(esClient, cfg.Elasticsearch, cfg.Mappings, log.With("component", "elasticsearch"))

	// Connect to Redis
	log.Info("connecting to Redis",
		"address", cfg.Redis.Address,
		"key_prefix", cfg.Redis.KeyPrefix,
	)
	redisClient := redisstore.NewClient(cfg.Redis)
	defer func() {
		log.Info("closing Redis client")
		if err := redisClient.Close(); err != nil {
			log.Warn("Redis client close failed",
				"error", err,
			)
		}
	}()

	log.Info("Redis client connected")
	store := redisstore.NewStore(redisClient.Raw(), cfg.Redis, log.With("component", "redis"), cfg.Lock.Key)

	// Setup distributed locking if enabled
	var acquireLock service.AcquireLockFunc
	var acquireShardLease service.AcquireShardLeaseFunc
	if cfg.Lock.Enabled {
		lockBackend := redisstore.NewLockBackend(redisClient.Raw())
		lockLogger := log.With("component", "lock")
		identity := workerIdentity(cfg.ServiceName)
		if cfg.Lock.ShardCount > 1 {
			instanceID, instanceCount, instanceDriven := collectorInstancePlan(cfg)
			ownedShards := collectorOwnedShards(cfg.Lock.ShardCount, instanceID, instanceCount, instanceDriven)
			log.Info(
				"setting up shard-based distributed locks",
				"lock_key", cfg.Lock.Key,
				"ttl", cfg.Lock.TTL,
				"shard_count", cfg.Lock.ShardCount,
				"instance_id", instanceID,
				"instance_count", instanceCount,
				"owned_shards", ownedShards,
			)
			acquireShardLease = func(ctx context.Context) (service.ShardLease, bool, error) {
				return acquireCollectorShardLease(ctx, lockBackend, cfg.Lock, ownedShards, identity, lockLogger)
			}
			log.Info("shard-based distributed locks configured")
		} else {
			log.Info("setting up distributed lock",
				"lock_key", cfg.Lock.Key,
				"ttl", cfg.Lock.TTL,
			)
			locker := redisstore.NewLocker(
				lockBackend,
				cfg.Lock,
				identity,
				lockLogger,
			)
			acquireLock = func(ctx context.Context) (service.ReleaseFunc, bool, error) {
				lease, acquired, err := locker.Acquire(ctx)
				if err != nil || !acquired {
					return nil, acquired, err
				}
				return lease.Release, true, nil
			}
			log.Info("distributed lock configured")
		}
	}

	// Create collector service
	log.Info("initializing collector service",
		"signal_field", cfg.Mappings.SignalField,
		"organization_field", cfg.Mappings.OrganizationField,
	)
	collector := service.NewCollector(service.Dependencies{
		Config:            cfg,
		Source:            esRepository,
		Store:             store,
		AcquireLock:       acquireLock,
		AcquireShardLease: acquireShardLease,
		Logger:            log.With("component", "collector"),
	})
	log.Info("collector service initialized")

	// Run once mode (for testing/debugging)
	if *runOnce {
		log.Info("running in single-cycle mode")
		runCtx, cancel := context.WithTimeout(ctx, cfg.Scheduler.RunTimeout)
		defer cancel()

		if err := runCollector(runCtx, collector, log); err != nil {
			log.Error("single cycle failed",
				"error", err,
			)
			os.Exit(1)
		}
		log.Info("single cycle completed successfully")
		return
	}

	// Start scheduler for periodic collection
	log.Info("starting scheduler",
		"interval", cfg.Scheduler.Interval,
		"run_timeout", cfg.Scheduler.RunTimeout,
	)
	runner := scheduler.NewRunner(scheduler.Config{
		Interval:   cfg.Scheduler.Interval,
		RunTimeout: cfg.Scheduler.RunTimeout,
		Logger:     log.With("component", "scheduler"),
		Job:        collector,
	})

	if err := runner.Run(ctx); err != nil {
		log.Error("scheduler stopped with error",
			"error", err,
		)
		os.Exit(1)
	}

	log.Info("service shutdown complete")
}

// runCollector executes a single collection cycle with panic recovery.
// Catches panics and converts them to errors for proper error handling.
//
// Parameters:
//   - ctx: Context with timeout for cycle execution
//   - collector: Collector service performing the cycle
//   - log: Logger for recording cycle events
//
// Returns:
//   - error: Cycle error or recovered panic information
//
// Logging:
//   - DEBUG: Cycle start/end
//   - ERROR: Panics with full stack trace
func runCollector(ctx context.Context, collector *service.Collector, log *slog.Logger) (err error) {
	log.Debug("runCollector: starting collection cycle")
	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("collector panic: %v\n%s", recovered, string(debug.Stack()))
			log.Error("runCollector: panic recovered",
				"panic_value", recovered,
				"error", err,
			)
		}
		log.Debug("runCollector: collection cycle complete")
	}()

	return collector.RunCycle(ctx)
}

// workerIdentity constructs a unique identifier for this worker instance.
// Used for distributed lock ownership and operational tracing.
//
// Format: {serviceName}:{hostname}:{instance}:{pid}
//
// Defaults:
//   - hostname: "unknown-host" if unable to determine
//   - instance: "standalone" if not in multi-instance environment
//
// Environment Variables Checked:
//   - SLP_PM2_INSTANCE_ID
//   - NODE_APP_INSTANCE
//   - PM2_INSTANCE_ID
//   - pm_id
//
// Parameters:
//   - serviceName: Name of the service (from config)
//
// Returns:
//   - string: Unique worker identifier
func workerIdentity(serviceName string) string {
	// Get hostname
	host, err := os.Hostname()
	if err != nil || host == "" {
		host = "unknown-host"
	}

	// Get instance ID from environment
	instance := firstNonEmptyEnv("SLP_PM2_INSTANCE_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id")
	if instance == "" {
		instance = "standalone"
	}

	return fmt.Sprintf("%s:%s:%s:%d", serviceName, host, instance, os.Getpid())
}

// firstNonEmptyEnv returns the first non-empty value from environment variables.
// Checks in order provided; returns empty string if none are set.
//
// Parameters:
//   - keys: Environment variable names to check in order
//
// Returns:
//   - string: First non-empty environment variable value, or empty string
func firstNonEmptyEnv(keys ...string) string {
	for _, key := range keys {
		value := os.Getenv(key)
		if value != "" {
			return value
		}
	}
	return ""
}

func collectorInstancePlan(cfg config.Config) (int, int, bool) {
	instanceID, hasInstanceID := firstEnvInt("SLP_PM2_INSTANCE_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id")
	instanceCount, hasInstanceCount := firstEnvInt("SLP_PM2_INSTANCES")
	if !hasInstanceCount {
		instanceCount = cfg.PM2.Instances
	}
	if instanceCount < 1 {
		instanceCount = 1
	}
	if !hasInstanceID {
		return 0, 1, false
	}
	if instanceID < 0 {
		instanceID = 0
	}
	if instanceCount > 0 {
		instanceID = instanceID % instanceCount
	}
	return instanceID, instanceCount, true
}

func collectorOwnedShards(shardCount, instanceID, instanceCount int, instanceDriven bool) []int {
	if shardCount <= 1 {
		return []int{0}
	}
	if !instanceDriven || instanceCount <= 1 {
		return allCollectorShards(shardCount)
	}

	owned := make([]int, 0, shardCount)
	for shardID := 0; shardID < shardCount; shardID++ {
		if shardID%instanceCount == instanceID {
			owned = append(owned, shardID)
		}
	}
	return owned
}

func allCollectorShards(shardCount int) []int {
	if shardCount <= 0 {
		return nil
	}
	shards := make([]int, 0, shardCount)
	for shardID := 0; shardID < shardCount; shardID++ {
		shards = append(shards, shardID)
	}
	return shards
}

func acquireCollectorShardLease(
	ctx context.Context,
	backend redisstore.LockBackend,
	lockCfg config.LockConfig,
	ownedShards []int,
	workerID string,
	log *slog.Logger,
) (service.ShardLease, bool, error) {
	if len(ownedShards) == 0 {
		log.Info("collector cycle skipped because no shard is assigned to this instance")
		return service.ShardLease{}, false, nil
	}

	releases := make([]service.ReleaseFunc, 0, len(ownedShards))
	acquiredShards := make([]int, 0, len(ownedShards))
	for _, shardID := range ownedShards {
		shardCfg := lockCfg
		shardCfg.Key = collectorShardLockKey(lockCfg.Key, shardID)
		locker := redisstore.NewLocker(
			backend,
			shardCfg,
			workerID,
			log.With("lock_scope", "shard", "shard_id", shardID),
		)
		lease, acquired, err := locker.Acquire(ctx)
		if err != nil {
			releaseCollectorShardLocks(ctx, releases, log)
			return service.ShardLease{}, false, fmt.Errorf("acquire shard %d lock: %w", shardID, err)
		}
		if !acquired {
			continue
		}
		releases = append(releases, lease.Release)
		acquiredShards = append(acquiredShards, shardID)
	}

	if len(acquiredShards) == 0 {
		log.Info("collector cycle skipped because no shard lock was acquired", "owned_shards", ownedShards)
		return service.ShardLease{}, false, nil
	}

	return service.ShardLease{
		ShardCount:  lockCfg.ShardCount,
		OwnedShards: acquiredShards,
		Release: func(releaseCtx context.Context) (bool, error) {
			return releaseCollectorShardLocks(releaseCtx, releases, log)
		},
	}, true, nil
}

func releaseCollectorShardLocks(ctx context.Context, releases []service.ReleaseFunc, log *slog.Logger) (bool, error) {
	allReleased := true
	for _, release := range releases {
		if release == nil {
			continue
		}
		released, err := release(ctx)
		if err != nil {
			return false, err
		}
		if !released {
			allReleased = false
		}
	}
	if !allReleased && log != nil {
		log.Warn("one or more shard locks were not released because ownership changed or expired")
	}
	return allReleased, nil
}

func collectorShardLockKey(baseKey string, shardID int) string {
	return fmt.Sprintf("%s:shard:%d", baseKey, shardID)
}

func firstEnvInt(keys ...string) (int, bool) {
	value := firstNonEmptyEnv(keys...)
	if value == "" {
		return 0, false
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, false
	}
	return parsed, true
}
