package config

import "testing"

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
}
