package autoscaling

import (
	"testing"
	"time"

	"log_rca_engine/internal/config"
)

func TestCurrentReaderSettingsScaleWithObservedWorkload(t *testing.T) {
	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "correlation_events",
			InputLowWatermark:       100,
			InputHighWatermark:      1000,
			ScaleDownCooldownCycles: 1,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              20 * time.Second,
				MaxInterval:              90 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Reader: config.AutoscalingReaderConfig{
				MinPageSize:      100,
				MaxPageSize:      1000,
				MaxPagesPerCycle: 12,
			},
		},
		SchedulerSettings{Interval: 30 * time.Second, RunTimeout: 27 * time.Second},
		ReaderSettings{PageSize: 100, MaxPagesPerCycle: 12},
	)

	initial := controller.CurrentReaderSettings()
	if initial.PageSize != 100 || initial.MaxPagesPerCycle != 12 {
		t.Fatalf("unexpected initial reader settings: %#v", initial)
	}

	controller.ObserveCycle(1000)
	scaled := controller.CurrentReaderSettings()
	if scaled.PageSize != 1000 {
		t.Fatalf("expected reader page size to scale to 1000, got %#v", scaled)
	}
	if scaled.MaxPagesPerCycle != 12 {
		t.Fatalf("expected page cap to stay at 12, got %#v", scaled)
	}
}

func TestObserveExecutionScalesSchedulerAfterTimeout(t *testing.T) {
	controller := NewController(
		config.AutoscalingConfig{
			Enabled:                 true,
			InputBasis:              "correlation_events",
			InputLowWatermark:       100,
			InputHighWatermark:      1000,
			ScaleDownCooldownCycles: 1,
			Scheduler: config.AutoscalingSchedulerConfig{
				MinInterval:              20 * time.Second,
				MaxInterval:              90 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Reader: config.AutoscalingReaderConfig{
				MinPageSize:      100,
				MaxPageSize:      1000,
				MaxPagesPerCycle: 10,
			},
		},
		SchedulerSettings{Interval: 30 * time.Second, RunTimeout: 27 * time.Second},
		ReaderSettings{PageSize: 100, MaxPagesPerCycle: 10},
	)

	controller.ObserveExecution(ExecutionObservation{
		Interval:   30 * time.Second,
		RunTimeout: 27 * time.Second,
		Duration:   27 * time.Second,
		Failed:     true,
		TimedOut:   true,
	})

	settings := controller.CurrentSchedulerSettings()
	if settings.Interval <= 30*time.Second {
		t.Fatalf("expected timeout feedback to increase interval, got %#v", settings)
	}
	if settings.RunTimeout >= settings.Interval {
		t.Fatalf("expected run timeout to remain below interval, got %#v", settings)
	}
}
