package autoscaling

import (
	"testing"
	"time"

	"log_correlation_engine/internal/config"
)

func TestControllerUsesStaticDefaultsBeforeWarmup(t *testing.T) {
	t.Parallel()

	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "incremental_logs",
			InputLowWatermark:       1000,
			InputHighWatermark:      100000,
			ScaleDownCooldownCycles: 3,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              10 * time.Second,
				MaxInterval:              60 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Fetcher: config.AutoscalingFetcherConfig{
				MinGroupedLookupBatchSize: 1000,
				MaxGroupedLookupBatchSize: 10000,
				MaxBatchesPerCycle:        10,
			},
		},
		SchedulerSettings{Interval: 5 * time.Second, RunTimeout: 5 * time.Second},
		250,
	)

	schedulerSettings := controller.CurrentSchedulerSettings()
	if schedulerSettings.Interval != 5*time.Second || schedulerSettings.RunTimeout != 5*time.Second {
		t.Fatalf("expected static scheduler settings before warmup, got %#v", schedulerSettings)
	}

	orgSettings := controller.ResolveOrganization("org-1", 50000)
	if orgSettings.GroupedLookupBatchSize != 250 {
		t.Fatalf("expected static batch size before warmup, got %d", orgSettings.GroupedLookupBatchSize)
	}
	if orgSettings.MaxNewLogsPerCycle != 2500 {
		t.Fatalf("expected static cap before warmup, got %d", orgSettings.MaxNewLogsPerCycle)
	}
}

func TestControllerScalesTimeoutWithIntervalAndAppliesCooldownOnScaleDown(t *testing.T) {
	t.Parallel()

	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "incremental_logs",
			InputLowWatermark:       1000,
			InputHighWatermark:      100000,
			ScaleDownCooldownCycles: 3,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              10 * time.Second,
				MaxInterval:              60 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Fetcher: config.AutoscalingFetcherConfig{
				MinGroupedLookupBatchSize: 1000,
				MaxGroupedLookupBatchSize: 10000,
				MaxBatchesPerCycle:        10,
			},
		},
		SchedulerSettings{Interval: 5 * time.Second, RunTimeout: 5 * time.Second},
		250,
	)

	controller.ObserveCycle(100000)
	settings := controller.CurrentSchedulerSettings()
	if settings.Interval != 10*time.Second {
		t.Fatalf("expected interval to stay at 10s while batch scaling can still cope, got %s", settings.Interval)
	}
	if settings.RunTimeout != 9*time.Second {
		t.Fatalf("expected timeout to be 90%% of 10s, got %s", settings.RunTimeout)
	}

	controller.ObserveCycle(600000)
	if scaledUp := controller.CurrentSchedulerSettings(); scaledUp.Interval != 60*time.Second || scaledUp.RunTimeout != 54*time.Second {
		t.Fatalf("expected interval to scale up only after max batch capacity is exceeded, got %#v", scaledUp)
	}

	controller.ObserveCycle(1000)
	if stillScaled := controller.CurrentSchedulerSettings(); stillScaled.Interval != 60*time.Second {
		t.Fatalf("expected first low cycle to remain at 60s due to cooldown, got %s", stillScaled.Interval)
	}
	controller.ObserveCycle(1000)
	if stillScaled := controller.CurrentSchedulerSettings(); stillScaled.Interval != 60*time.Second {
		t.Fatalf("expected second low cycle to remain at 60s due to cooldown, got %s", stillScaled.Interval)
	}
	controller.ObserveCycle(1000)
	if scaledDown := controller.CurrentSchedulerSettings(); scaledDown.Interval != 10*time.Second || scaledDown.RunTimeout != 9*time.Second {
		t.Fatalf("expected cooldown to scale down to 10s/9s, got %#v", scaledDown)
	}
}

func TestControllerScalesSchedulerFromExecutionTimeWhenWorkloadOnlyWouldStayAtMinInterval(t *testing.T) {
	t.Parallel()

	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "incremental_logs",
			InputLowWatermark:       1000,
			InputHighWatermark:      100000,
			ScaleDownCooldownCycles: 3,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              10 * time.Second,
				MaxInterval:              60 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Fetcher: config.AutoscalingFetcherConfig{
				MinGroupedLookupBatchSize: 1000,
				MaxGroupedLookupBatchSize: 10000,
				MaxBatchesPerCycle:        10,
			},
		},
		SchedulerSettings{Interval: 5 * time.Second, RunTimeout: 5 * time.Second},
		250,
	)

	controller.ObserveCycle(98279)
	if settings := controller.CurrentSchedulerSettings(); settings.Interval != 10*time.Second || settings.RunTimeout != 9*time.Second {
		t.Fatalf("expected workload-only scaling to stay at 10s/9s, got %#v", settings)
	}

	controller.ObserveExecution(ExecutionObservation{
		Interval:   10 * time.Second,
		RunTimeout: 9 * time.Second,
		Duration:   9 * time.Second,
		Failed:     true,
		TimedOut:   true,
	})

	scaled := controller.CurrentSchedulerSettings()
	if scaled.Interval <= 10*time.Second {
		t.Fatalf("expected execution timeout feedback to increase interval beyond 10s, got %#v", scaled)
	}
	if scaled.Interval != 18750*time.Millisecond || scaled.RunTimeout != 16875*time.Millisecond {
		t.Fatalf("expected interval to scale to 18.75s/16.875s from timeout feedback, got %#v", scaled)
	}
}

func TestControllerUsesDistributedThroughputForShardPlanningAndSchedulerScaling(t *testing.T) {
	t.Parallel()

	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "incremental_logs",
			InputLowWatermark:       1000,
			InputHighWatermark:      100000,
			ScaleDownCooldownCycles: 3,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              10 * time.Second,
				MaxInterval:              60 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Fetcher: config.AutoscalingFetcherConfig{
				MinGroupedLookupBatchSize: 1000,
				MaxGroupedLookupBatchSize: 10000,
				MaxBatchesPerCycle:        10,
			},
		},
		SchedulerSettings{Interval: 5 * time.Second, RunTimeout: 5 * time.Second},
		250,
	)

	controller.ObserveDistributedCycle(60000, 3)
	controller.ObserveDistributedObservation(DistributedObservation{
		ActiveWorkers:        3,
		CorrelationWorkUnits: 60000,
		PlannedShards:        6,
		CompletedShards:      6,
		QueueDepth:           3,
		TotalShardDuration:   60 * time.Second,
		MaxShardDuration:     6 * time.Second,
		MergeDuration:        500 * time.Millisecond,
	})

	settings := controller.CurrentSchedulerSettings()
	if settings.Interval <= 10*time.Second {
		t.Fatalf("expected distributed throughput feedback to increase interval beyond 10s, got %#v", settings)
	}

	plan := controller.ResolveDistributedShardPlan(12000, 3, DistributedShardHints{
		DefaultTargetLogsPerShard: 5000,
		MinShardsPerWorker:        1,
		MaxShardsPerWorker:        4,
		TargetShardDuration:       2 * time.Second,
	})
	if plan.DesiredShards != 6 {
		t.Fatalf("expected 6 desired shards from distributed throughput plan, got %#v", plan)
	}
	if plan.TargetLogsPerShard != 2000 {
		t.Fatalf("expected 2000 target logs per shard, got %#v", plan)
	}
	if plan.QueueDepth != 3 {
		t.Fatalf("expected queue depth 3, got %#v", plan)
	}
	if plan.EstimatedClusterDuration != 4*time.Second {
		t.Fatalf("expected estimated cluster duration 4s, got %#v", plan)
	}
}
