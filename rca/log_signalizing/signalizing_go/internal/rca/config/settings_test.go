package config_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"rca/internal/rca/config"
)

func TestLoadConfigParsesSizeAndDurationUnits(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]
  request_timeout_seconds: "45s"

pipeline:
  batch_size: 100
  bulk_max_batch_bytes: "16MB"
  bulk_queue_enqueue_timeout_seconds: "250ms"
  bulk_spool_max_bytes: "2GB"
  bulk_spool_replay_interval_seconds: "1s"
  bulk_autoscaling_check_interval_seconds: "3s"
  bulk_autoscaling_cooldown_seconds: "12s"
  dynamic_batch_lookback_seconds: "30s"
  dynamic_batch_target_window_seconds: "1500ms"
  autoscaling_lag_scale_up_seconds: "2m"
  autoscaling_lag_scale_down_seconds: "15s"
  poll_interval_seconds: "10s"
  retry_initial_backoff_seconds: "500ms"
  start_time: "now-15m"
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	appConfig, err := config.LoadAppConfig(configFile)
	if err != nil {
		t.Fatal(err)
	}

	if appConfig.Elasticsearch.RequestTimeoutSeconds != 45 {
		t.Fatalf("expected request timeout 45, got %d", appConfig.Elasticsearch.RequestTimeoutSeconds)
	}
	if appConfig.Pipeline.BulkMaxBatchBytes != 16*1024*1024 {
		t.Fatalf("unexpected bulk max bytes: %d", appConfig.Pipeline.BulkMaxBatchBytes)
	}
	if appConfig.Pipeline.BulkQueueEnqueueTimeoutSeconds != 0.25 {
		t.Fatalf("unexpected enqueue timeout: %v", appConfig.Pipeline.BulkQueueEnqueueTimeoutSeconds)
	}
	if appConfig.Pipeline.BulkSpoolMaxBytes != 2*1024*1024*1024 {
		t.Fatalf("unexpected spool max bytes: %d", appConfig.Pipeline.BulkSpoolMaxBytes)
	}
	if appConfig.Pipeline.BulkSpoolReplayIntervalSeconds != 1.0 {
		t.Fatalf("unexpected spool replay interval: %v", appConfig.Pipeline.BulkSpoolReplayIntervalSeconds)
	}
	if appConfig.Pipeline.BulkAutoscalingCheckIntervalSeconds != 3.0 {
		t.Fatalf("unexpected autoscaling check interval: %v", appConfig.Pipeline.BulkAutoscalingCheckIntervalSeconds)
	}
	if appConfig.Pipeline.BulkAutoscalingCooldownSeconds != 12.0 {
		t.Fatalf("unexpected autoscaling cooldown: %v", appConfig.Pipeline.BulkAutoscalingCooldownSeconds)
	}
	if appConfig.Pipeline.DynamicBatchLookbackSeconds != 30 {
		t.Fatalf("unexpected lookback seconds: %d", appConfig.Pipeline.DynamicBatchLookbackSeconds)
	}
	if appConfig.Pipeline.DynamicBatchTargetWindowSeconds != 1.5 {
		t.Fatalf("unexpected target window seconds: %v", appConfig.Pipeline.DynamicBatchTargetWindowSeconds)
	}
	if appConfig.Pipeline.AutoscalingLagScaleUpSeconds != 120.0 {
		t.Fatalf("unexpected scale up lag: %v", appConfig.Pipeline.AutoscalingLagScaleUpSeconds)
	}
	if appConfig.Pipeline.AutoscalingLagScaleDownSeconds != 15.0 {
		t.Fatalf("unexpected scale down lag: %v", appConfig.Pipeline.AutoscalingLagScaleDownSeconds)
	}
	if appConfig.Pipeline.PollIntervalSeconds != 10 {
		t.Fatalf("unexpected poll interval: %d", appConfig.Pipeline.PollIntervalSeconds)
	}
	if appConfig.Pipeline.RetryInitialBackoffSeconds != 0.5 {
		t.Fatalf("unexpected retry initial backoff: %v", appConfig.Pipeline.RetryInitialBackoffSeconds)
	}
	if appConfig.Pipeline.StartTime != "now-15m" {
		t.Fatalf("expected start_time to remain raw, got %q", appConfig.Pipeline.StartTime)
	}
}

func TestLoadConfigRejectsInvalidSizeUnit(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config-invalid.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  bulk_max_batch_bytes: "8XB"
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err := config.LoadAppConfig(configFile)
	if err == nil || !strings.Contains(err.Error(), "pipeline.bulk_max_batch_bytes") {
		t.Fatalf("expected bulk_max_batch_bytes validation error, got %v", err)
	}
}

func TestLoadConfigFallsBackToYAMLHostsWithoutLegacySettings(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config.yml")
	configContents := `
elasticsearch:
  hosts:
    - "es-a:9200"
    - "http://es-b:9200"

pipeline:
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	previousPython, hadPython := os.LookupEnv("PYTHON")
	if err := os.Unsetenv("PYTHON"); err != nil {
		t.Fatal(err)
	}
	defer func() {
		if hadPython {
			_ = os.Setenv("PYTHON", previousPython)
		}
	}()

	appConfig, err := config.LoadAppConfig(configFile)
	if err != nil {
		t.Fatal(err)
	}

	expected := []string{"http://es-a:9200", "http://es-b:9200"}
	if len(appConfig.Elasticsearch.Hosts) != len(expected) {
		t.Fatalf("unexpected host count: %#v", appConfig.Elasticsearch.Hosts)
	}
	for index, value := range expected {
		if appConfig.Elasticsearch.Hosts[index] != value {
			t.Fatalf("unexpected host at %d: %#v", index, appConfig.Elasticsearch.Hosts)
		}
	}
}

func TestRulesDirectoryResolvedRelativeToConfigFile(t *testing.T) {
	tempDir := t.TempDir()
	configDir := filepath.Join(tempDir, "signalizing-engine")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatal(err)
	}
	configFile := filepath.Join(configDir, "config.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]

rules_directory: "rules"

pipeline:
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	appConfig, err := config.LoadAppConfig(configFile)
	if err != nil {
		t.Fatal(err)
	}

	expected, err := filepath.Abs(filepath.Join(configDir, "rules"))
	if err != nil {
		t.Fatal(err)
	}
	if appConfig.RulesDirectory != expected {
		t.Fatalf("expected rules dir %q, got %q", expected, appConfig.RulesDirectory)
	}
}

func TestWorkerRuntimeOverridesFromEnv(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  worker_count: 1
  worker_id: 0
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Setenv("RCA_WORKER_COUNT", "4")
	t.Setenv("RCA_WORKER_ID", "2")

	appConfig, err := config.LoadAppConfig(configFile)
	if err != nil {
		t.Fatal(err)
	}

	if appConfig.Pipeline.WorkerCount != 4 {
		t.Fatalf("expected worker count 4, got %d", appConfig.Pipeline.WorkerCount)
	}
	if appConfig.Pipeline.WorkerID != 2 {
		t.Fatalf("expected worker id 2, got %d", appConfig.Pipeline.WorkerID)
	}
}

func TestWorkerRuntimeFallsBackToNodeAppInstance(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  worker_count: 1
  worker_id: 0
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Setenv("RCA_WORKER_COUNT", "3")
	t.Setenv("NODE_APP_INSTANCE", "1")

	appConfig, err := config.LoadAppConfig(configFile)
	if err != nil {
		t.Fatal(err)
	}

	if appConfig.Pipeline.WorkerCount != 3 {
		t.Fatalf("expected worker count 3, got %d", appConfig.Pipeline.WorkerCount)
	}
	if appConfig.Pipeline.WorkerID != 1 {
		t.Fatalf("expected worker id 1, got %d", appConfig.Pipeline.WorkerID)
	}
}

func TestWorkerRuntimeRejectsInvalidEnvValue(t *testing.T) {
	tempDir := t.TempDir()
	configFile := filepath.Join(tempDir, "config.yml")
	configContents := `
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  worker_count: 1
  worker_id: 0
  services: []
`
	if err := os.WriteFile(configFile, []byte(configContents), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Setenv("RCA_WORKER_COUNT", "two")

	_, err := config.LoadAppConfig(configFile)
	if err == nil || !strings.Contains(err.Error(), "RCA_WORKER_COUNT must be an integer") {
		t.Fatalf("expected integer validation error, got %v", err)
	}
}
