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
	cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 999
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid fetcher min grouped lookup batch size to fail validation")
	}
}
