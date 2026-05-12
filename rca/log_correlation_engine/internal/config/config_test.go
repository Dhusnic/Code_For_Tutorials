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
	if cfg.Autoscaling.Scheduler.MinInterval != 20*time.Second {
		t.Fatalf("expected autoscaling min interval 20s, got %s", cfg.Autoscaling.Scheduler.MinInterval)
	}
	if cfg.Autoscaling.Scheduler.MaxInterval != 90*time.Second {
		t.Fatalf("expected autoscaling max interval 90s, got %s", cfg.Autoscaling.Scheduler.MaxInterval)
	}
	if cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize != 250 {
		t.Fatalf("expected min grouped lookup batch size 250, got %d", cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize)
	}
	if cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize != 2000 {
		t.Fatalf("expected max grouped lookup batch size 2000, got %d", cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize)
	}
	if cfg.Autoscaling.Fetcher.MaxBatchesPerCycle != 4 {
		t.Fatalf("expected max batches per cycle 4, got %d", cfg.Autoscaling.Fetcher.MaxBatchesPerCycle)
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
	if !cfg.Distributed.SingleStreamIngestLeader {
		t.Fatalf("expected distributed single_stream_ingest_leader to be enabled by default")
	}
	if cfg.Distributed.PrefetchFullLogs {
		t.Fatalf("expected distributed prefetch_full_logs to be disabled by default")
	}
	if cfg.Distributed.PrefetchTimeout != 5*time.Second {
		t.Fatalf("expected distributed prefetch timeout 5s, got %s", cfg.Distributed.PrefetchTimeout)
	}
	if cfg.Distributed.PrefetchMaxDocIDs != 1000 {
		t.Fatalf("expected distributed prefetch max doc ids 1000, got %d", cfg.Distributed.PrefetchMaxDocIDs)
	}
	if cfg.Redis.SignalStreamBatchSize != 250 {
		t.Fatalf("expected redis signal stream batch size 250, got %d", cfg.Redis.SignalStreamBatchSize)
	}
	if cfg.Fetcher.GroupedLookupBatchSize != 100 {
		t.Fatalf("expected fetcher grouped lookup batch size 100, got %d", cfg.Fetcher.GroupedLookupBatchSize)
	}
	if cfg.Engine.ParallelCorrelation.Enabled {
		t.Fatalf("expected engine parallel correlation to be disabled by default")
	}
	if cfg.Engine.ParallelCorrelation.MinLogs != 5000 {
		t.Fatalf("expected parallel correlation min_logs 5000, got %d", cfg.Engine.ParallelCorrelation.MinLogs)
	}
	if cfg.Engine.ParallelCorrelation.TargetLogsPerShard != 1500 {
		t.Fatalf("expected parallel correlation target_logs_per_shard 1500, got %d", cfg.Engine.ParallelCorrelation.TargetLogsPerShard)
	}
	if cfg.Engine.ParallelCorrelation.MaxWorkers != 8 {
		t.Fatalf("expected parallel correlation max_workers 8, got %d", cfg.Engine.ParallelCorrelation.MaxWorkers)
	}
	if cfg.Engine.ParallelCorrelation.DistributedTargetShardDuration != 750*time.Millisecond {
		t.Fatalf("expected distributed target shard duration 750ms, got %s", cfg.Engine.ParallelCorrelation.DistributedTargetShardDuration)
	}
	if cfg.Engine.ParallelCorrelation.DistributedShardTimeout != 5*time.Second {
		t.Fatalf("expected distributed shard timeout 5s, got %s", cfg.Engine.ParallelCorrelation.DistributedShardTimeout)
	}
	if cfg.Engine.ParallelCorrelation.DistributedRunReserve != 3*time.Second {
		t.Fatalf("expected distributed run reserve 3s, got %s", cfg.Engine.ParallelCorrelation.DistributedRunReserve)
	}
	if cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker != 1 {
		t.Fatalf("expected distributed min shards per worker 1, got %d", cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker)
	}
	if cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker != 10 {
		t.Fatalf("expected distributed max shards per worker 10, got %d", cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker)
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
	cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 99
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
	cfg.Distributed.PrefetchFullLogs = true
	cfg.Distributed.PrefetchTimeout = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed prefetch timeout to fail validation")
	}

	cfg.Distributed.PrefetchTimeout = 5 * time.Second
	cfg.Distributed.PrefetchMaxDocIDs = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed prefetch max doc ids to fail validation")
	}

	cfg.Distributed.PrefetchMaxDocIDs = 1000
	cfg.Distributed.PrefetchFullLogs = false
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

	cfg.Engine.ParallelCorrelation.MaxWorkers = 8
	cfg.Engine.ParallelCorrelation.DistributedShardTimeout = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed shard timeout to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedShardTimeout = 5 * time.Second
	cfg.Engine.ParallelCorrelation.DistributedRunReserve = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed run reserve to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedRunReserve = 3 * time.Second
	cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed min shards per worker to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedMinShardsPerWorker = 2
	cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker = 1
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid distributed max shards per worker to fail validation")
	}

	cfg.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker = 10
	cfg.Engine.ParallelCorrelation.ShardPollInterval = 0
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid shard poll interval to fail validation")
	}
}
