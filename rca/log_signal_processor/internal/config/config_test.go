package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestLoadParsesDurationsAndDefaults(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "config.yml")
	contents := []byte(`
service_name: signaled-logs-collector
logging:
  level: debug
  format: json
scheduler:
  interval: 1m
  run_timeout: 50s
elasticsearch:
  addresses:
    - http://localhost:9200
  index: logs-*
  page_size: 250
  request_timeout: 15s
  query_timeout: 10s
  window: 10m
  use_point_in_time: true
  pit_keep_alive: 2m
redis:
  address: localhost:6379
  key_prefix: Rca
  hash_field: signaled_logs
  retention_window: 30m
  dial_timeout: 5s
  read_timeout: 3s
  write_timeout: 3s
lock:
  enabled: true
  ttl: 90s
  acquire_timeout: 2s
mappings:
  organization_field: event.organization
  signal_field: signal
  log_level_field: log_level
  timestamp_field: "@timestamp"
  doc_id_source: _id
pm2:
  app_name: signaled-logs-collector
  instances: 2
`)
	if err := os.WriteFile(configPath, contents, 0o600); err != nil {
		t.Fatalf("write config file: %v", err)
	}

	cfg, err := Load(configPath)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	if cfg.Scheduler.Interval != time.Minute {
		t.Fatalf("expected 1m interval, got %s", cfg.Scheduler.Interval)
	}
	if cfg.Elasticsearch.Window != 10*time.Minute {
		t.Fatalf("expected 10m elasticsearch window, got %s", cfg.Elasticsearch.Window)
	}
	if !cfg.Elasticsearch.UsePointInTime {
		t.Fatalf("expected point-in-time pagination to be enabled")
	}
	if cfg.Elasticsearch.PITKeepAlive != 2*time.Minute {
		t.Fatalf("expected 2m pit keep alive, got %s", cfg.Elasticsearch.PITKeepAlive)
	}
	if cfg.Redis.RetentionWindow != 30*time.Minute {
		t.Fatalf("expected 30m retention, got %s", cfg.Redis.RetentionWindow)
	}
	if cfg.Lock.Key != "Rca:collector_lock" {
		t.Fatalf("expected default lock key, got %s", cfg.Lock.Key)
	}
}
