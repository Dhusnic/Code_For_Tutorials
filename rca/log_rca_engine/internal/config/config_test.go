package config

import "testing"

func TestDefaultConfigAutoscalingDefaults(t *testing.T) {
	cfg := defaultConfig()
	cfg.normalize()

	if cfg.Autoscaling.InputBasis != "correlation_events" {
		t.Fatalf("expected autoscaling input basis correlation_events, got %q", cfg.Autoscaling.InputBasis)
	}
	if cfg.Autoscaling.Reader.MinPageSize != 100 {
		t.Fatalf("expected min page size 100, got %d", cfg.Autoscaling.Reader.MinPageSize)
	}
	if cfg.Autoscaling.Reader.MaxPageSize != 1000 {
		t.Fatalf("expected max page size 1000, got %d", cfg.Autoscaling.Reader.MaxPageSize)
	}
	if cfg.Autoscaling.Reader.MaxPagesPerCycle != 10 {
		t.Fatalf("expected max pages per cycle 10, got %d", cfg.Autoscaling.Reader.MaxPagesPerCycle)
	}
}

func TestValidateRejectsInvalidAutoscalingReaderBounds(t *testing.T) {
	cfg := defaultConfig()
	cfg.normalize()
	cfg.Autoscaling.Reader.MinPageSize = 2000
	cfg.Autoscaling.Reader.MaxPageSize = 1000

	if err := cfg.Validate(); err == nil {
		t.Fatal("expected invalid autoscaling reader bounds to fail validation")
	}
}
