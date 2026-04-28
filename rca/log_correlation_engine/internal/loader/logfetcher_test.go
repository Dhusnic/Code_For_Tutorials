package loader

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/fetch"
)

func TestElasticsearchLogFetcherFetchLog(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_search"):
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{
				"hits": {
					"hits": [
						{
							"_id": "doc-1",
							"_source": {
								"@timestamp": "2026-04-08T12:00:00Z",
								"signal": "rabbitmq_queue_depth_high",
								"event": {
									"organization": "org-1",
									"module": "rabbitmq"
								},
								"host": {
									"name": "host-1"
								},
								"service": {
									"name": "api"
								},
								"log": {
									"level": "warning"
								}
							}
						}
					]
				}
			}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	fetcher, err := NewElasticsearchLogFetcher(
		config.ElasticsearchConfig{
			Addresses:      []string{server.URL},
			Index:          "source-*",
			RequestTimeout: time.Second,
		},
		"@timestamp",
		"log.level",
		nil,
	)
	if err != nil {
		t.Fatalf("failed to create fetcher: %v", err)
	}

	logEntry, err := fetcher.FetchLog(context.Background(), "doc-1")
	if err != nil {
		t.Fatalf("fetch log returned error: %v", err)
	}

	if logEntry.DocID != "doc-1" {
		t.Fatalf("expected doc id doc-1, got %s", logEntry.DocID)
	}
	if logEntry.Signal != "rabbitmq_queue_depth_high" {
		t.Fatalf("expected signal from source, got %s", logEntry.Signal)
	}
	if logEntry.LogLevel != "warning" {
		t.Fatalf("expected log level warning, got %s", logEntry.LogLevel)
	}
	if got := logEntry.Metadata["event"].(map[string]any)["organization"]; got != "org-1" {
		t.Fatalf("expected event.organization org-1, got %#v", got)
	}
	if got := logEntry.Metadata["host"].(map[string]any)["name"]; got != "host-1" {
		t.Fatalf("expected host.name host-1, got %#v", got)
	}
	if logEntry.Timestamp.IsZero() {
		t.Fatalf("expected parsed source timestamp")
	}
}

func TestElasticsearchLogFetcherReturnsNotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_search"):
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"hits": map[string]any{
					"hits": []any{},
				},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	fetcher, err := NewElasticsearchLogFetcher(
		config.ElasticsearchConfig{
			Addresses:      []string{server.URL},
			Index:          "source-*",
			RequestTimeout: time.Second,
		},
		"@timestamp",
		"log.level",
		nil,
	)
	if err != nil {
		t.Fatalf("failed to create fetcher: %v", err)
	}

	if _, err := fetcher.FetchLog(context.Background(), "missing-doc"); err == nil {
		t.Fatalf("expected not found error")
	}
}

func TestElasticsearchLogFetcherFetchLogsBatch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_search"):
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{
				"hits": {
					"hits": [
						{
							"_id": "doc-2",
							"_source": {
								"@timestamp": "2026-04-08T12:01:00Z",
								"signal": "rabbitmq_heartbeat_missed",
								"log": {"level": "error"},
								"event": {"organization": "org-1"}
							}
						},
						{
							"_id": "doc-1",
							"_source": {
								"@timestamp": "2026-04-08T12:00:00Z",
								"signal": "rabbitmq_queue_depth_high",
								"log": {"level": "warning"},
								"event": {"organization": "org-1"}
							}
						},
						{
							"_id": "doc-1",
							"_source": {
								"@timestamp": "2026-04-08T11:59:00Z",
								"signal": "older_duplicate_should_be_ignored",
								"log": {"level": "info"},
								"event": {"organization": "org-1"}
							}
						}
					]
				}
			}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	fetcher, err := NewElasticsearchLogFetcher(
		config.ElasticsearchConfig{
			Addresses:      []string{server.URL},
			Index:          "source-*",
			RequestTimeout: time.Second,
		},
		"@timestamp",
		"log.level",
		nil,
	)
	if err != nil {
		t.Fatalf("failed to create fetcher: %v", err)
	}

	logs, err := fetcher.FetchLogs(context.Background(), []string{"doc-1", "doc-2", "doc-1"})
	if err != nil {
		t.Fatalf("fetch logs returned error: %v", err)
	}
	if len(logs) != 2 {
		t.Fatalf("expected 2 fetched logs, got %d", len(logs))
	}
	if logs["doc-1"] == nil || logs["doc-1"].Signal != "rabbitmq_queue_depth_high" {
		t.Fatalf("unexpected doc-1 payload: %#v", logs["doc-1"])
	}
	if logs["doc-2"] == nil || logs["doc-2"].LogLevel != "error" {
		t.Fatalf("unexpected doc-2 payload: %#v", logs["doc-2"])
	}
}

func TestElasticsearchLogFetcherFetchLogsWithOptionsOverridesBatchSize(t *testing.T) {
	t.Parallel()

	var searchRequests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_search"):
			searchRequests.Add(1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{
				"hits": {
					"hits": [
						{"_id": "doc-1", "_source": {"@timestamp": "2026-04-08T12:00:00Z", "log": {"level": "warning"}}},
						{"_id": "doc-2", "_source": {"@timestamp": "2026-04-08T12:01:00Z", "log": {"level": "error"}}},
						{"_id": "doc-3", "_source": {"@timestamp": "2026-04-08T12:02:00Z", "log": {"level": "critical"}}}
					]
				}
			}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	fetcher, err := NewElasticsearchLogFetcher(
		config.ElasticsearchConfig{
			Addresses:      []string{server.URL},
			Index:          "source-*",
			RequestTimeout: time.Second,
		},
		"@timestamp",
		"log.level",
		nil,
	)
	if err != nil {
		t.Fatalf("failed to create fetcher: %v", err)
	}
	fetcher.SetGroupedLookupBatchSize(10)

	logs, err := fetcher.FetchLogsWithOptions(
		context.Background(),
		[]string{"doc-1", "doc-2", "doc-3"},
		fetch.BatchFetchOptions{GroupedLookupBatchSize: 1},
	)
	if err != nil {
		t.Fatalf("fetch logs returned error: %v", err)
	}
	if len(logs) != 3 {
		t.Fatalf("expected 3 fetched logs, got %d", len(logs))
	}
	if searchRequests.Load() != 3 {
		t.Fatalf("expected batch size override to create 3 search requests, got %d", searchRequests.Load())
	}
}
