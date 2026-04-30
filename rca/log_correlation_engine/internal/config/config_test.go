package config

import (
	"testing"
	"time"
)

func TestLoadDefaultsIncludesAutoscalingDefaults(t *testing.T) {
	t.Parallel()

	cfg := defaultConfig()

	if cfg.Autoscaling.Enabled {
		t.Fatalf("expected autoscaling to be disabled by default")
	}
	if cfg.Autoscaling.InputBasis != "incremental_logs" {
		t.Fatalf("expected incremental_logs input basis, got %q", cfg.Autoscaling.InputBasis)
	}
	if cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize != 1000 {
		t.Fatalf("expected min grouped lookup batch size 1000, got %d", cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize)
	}
	if cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize != 10000 {
		t.Fatalf("expected max grouped lookup batch size 10000, got %d", cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize)
	}
	if cfg.Autoscaling.Scheduler.TargetCycleUtilization != 0.8 {
		t.Fatalf("expected target cycle utilization 0.8, got %v", cfg.Autoscaling.Scheduler.TargetCycleUtilization)
	}
	if cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier != 1.5 {
		t.Fatalf("expected timeout scale up multiplier 1.5, got %v", cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier)
	}
	if cfg.Distributed.Enabled {
		t.Fatalf("expected distributed mode to be disabled by default")
	}
	if cfg.Distributed.WorkerIDEnv != "RCA_WORKER_ID" {
		t.Fatalf("expected distributed worker env RCA_WORKER_ID, got %q", cfg.Distributed.WorkerIDEnv)
	}
	if cfg.Distributed.StreamConsumerGroup != "rca-correlation" {
		t.Fatalf("expected distributed stream consumer group rca-correlation, got %q", cfg.Distributed.StreamConsumerGroup)
	}
	if !cfg.Distributed.PrefetchFullLogs {
		t.Fatalf("expected distributed prefetch_full_logs to be enabled by default")
	}
	if cfg.Engine.ParallelCorrelation.Enabled {
		t.Fatalf("expected engine parallel correlation to be disabled by default")
	}
	if cfg.Engine.ParallelCorrelation.MinLogs != 5000 {
		t.Fatalf("expected parallel correlation min_logs 5000, got %d", cfg.Engine.ParallelCorrelation.MinLogs)
	}
	if cfg.Engine.ParallelCorrelation.TargetLogsPerShard != 5000 {
		t.Fatalf("expected parallel correlation target_logs_per_shard 5000, got %d", cfg.Engine.ParallelCorrelation.TargetLogsPerShard)
	}
	if cfg.Engine.ParallelCorrelation.MaxWorkers != 4 {
		t.Fatalf("expected parallel correlation max_workers 4, got %d", cfg.Engine.ParallelCorrelation.MaxWorkers)
	}
	if cfg.Engine.ParallelCorrelation.DistributedTargetShardDuration != 2*time.Second {
		t.Fatalf("expected distributed target shard duration 2s, got %s", cfg.Engine.ParallelCorrelation.DistributedTargetShardDuration)
	}
	if cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker != 1 {
		t.Fatalf("expected distributed min shards per worker 1, got %d", cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker)
	}
	if cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker != 4 {
		t.Fatalf("expected distributed max shards per worker 4, got %d", cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker)
	}
	if cfg.Engine.ParallelCorrelation.ShardPollInterval != 20*time.Millisecond {
		t.Fatalf("expected shard poll interval 20ms, got %s", cfg.Engine.ParallelCorrelation.ShardPollInterval)
	}
}

func TestValidateRejectsInvalidAutoscalingBounds(t *testing.T) {
	t.Parallel()

	cfg := defaultConfig()
	cfg.Redis.Address = "localhost:6379"

	cfg.Autoscaling.InputLowWatermark = 2000
	cfg.Autoscaling.InputHighWatermark = 1000
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid watermarks to fail validation")
	}

	cfg.Autoscaling.InputLowWatermark = 1000
	cfg.Autoscaling.InputHighWatermark = 2000
	cfg.Autoscaling.Scheduler.TimeoutRatio = 1
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid timeout ratio to fail validation")
	}

	cfg.Autoscaling.Scheduler.TimeoutRatio = 0.9
	cfg.Autoscaling.Scheduler.TargetCycleUtilization = 1
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid target cycle utilization to fail validation")
	}

	cfg.Autoscaling.Scheduler.TargetCycleUtilization = 0.8
	cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier = 0.5
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid timeout scale up multiplier to fail validation")
	}

	cfg.Autoscaling.Scheduler.TimeoutScaleUpMultiplier = 1.5
	cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 999
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid fetcher min grouped lookup batch size to fail validation")
	}

	cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 1000
	cfg.Distributed.Enabled = true
	cfg.Distributed.LeaseHeartbeatInterval = cfg.Distributed.LeaseTTL
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed lease heartbeat interval to fail validation")
	}

	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.StreamConsumerGroup = ""
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected missing distributed stream consumer group to fail validation")
	}

	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.FullLogCacheTTL = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed full log cache ttl to fail validation")
	}

	cfg.Distributed.FullLogCacheTTL = 2 * time.Hour
	cfg.Engine.ParallelCorrelation.Enabled = true
	cfg.Engine.ParallelCorrelation.MaxWorkers = 1
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid parallel correlation max_workers to fail validation")
	}

	cfg.Engine.ParallelCorrelation.MaxWorkers = 4
	cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed min shards per worker to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker = 2
	cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker = 1
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed max shards per worker to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker = 4
	cfg.Engine.ParallelCorrelation.ShardPollInterval = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid shard poll interval to fail validation")
	}
}
