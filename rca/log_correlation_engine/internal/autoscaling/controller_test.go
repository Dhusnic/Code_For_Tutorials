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
				MinInterval:  10 * time.Second,
				MaxInterval:  60 * time.Second,
				TimeoutRatio: 0.9,
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
				MinInterval:  10 * time.Second,
				MaxInterval:  60 * time.Second,
				TimeoutRatio: 0.9,
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
