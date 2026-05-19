package elastic

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"
)

func TestWriterWriteResultsAlsoIndexesCurrentIncidentDocument(t *testing.T) {
	type bulkCall struct {
		path string
		body string
	}

	calls := make([]bulkCall, 0, 2)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_bulk"):
			payload, _ := io.ReadAll(r.Body)
			calls = append(calls, bulkCall{
				path: r.URL.Path,
				body: string(payload),
			})
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"errors":false,"items":[{"index":{"_id":"ok","status":201}}]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	writer, err := NewWriter(config.ElasticsearchConfig{
		Addresses:      []string{server.URL},
		Index:          "rca_correlated_events",
		WriteHistory:   true,
		CurrentIndex:   "rca_correlated_incidents_current",
		RequestTimeout: time.Second,
		BulkBatchSize:  10,
	}, nil)
	if err != nil {
		t.Fatalf("failed to create writer: %v", err)
	}

	now := time.Date(2026, time.April, 12, 9, 0, 0, 0, time.UTC)
	firstSeen := now.Add(-2 * time.Minute)
	lastSeen := now.Add(-time.Minute)
	correlatedAt := now.Add(30 * time.Second)
	result := &models.CorrelationResult{
		SchemaVersion:   2,
		DocumentID:      "history-doc-1",
		IncidentID:      "incident-1",
		OrganizationID:  "org-1",
		RuleID:          "rule-1",
		Status:          "open",
		FirstSeen:       &firstSeen,
		LastSeen:        &lastSeen,
		GroupByValues:   map[string]string{"host.ip": "10.0.4.72"},
		ResultSignature: "sig-1",
		MatchedAt:       now,
		CorrelatedAt:    correlatedAt,
		LogID: []models.ResultLog{{
			ID:           "doc-1",
			SourceIndex:  "logs-a",
			SignalizedAt: now.Add(-15 * time.Second),
		}},
		Audit: &models.MatchAudit{
			RuleType:            "sequence",
			Window:              "30m",
			MaxGapBetweenSteps:  "5m",
			GroupBy:             []string{"host.ip"},
			GroupByValues:       map[string]string{"host.ip": "10.0.4.72"},
			RequiredMetadata:    map[string]string{"event.module": "system"},
			NegativeSignals:     []string{"signal-clear"},
			DeduplicationKey:    []string{"host.ip"},
			DeduplicationWindow: "10m",
			MatchedLogIDs:       []string{"doc-1"},
			MatchedSignals:      []string{"signal-a"},
			Steps: []models.MatchStepAudit{{
				StepIndex:     0,
				SignalKey:     "signal-a",
				RequiredCount: 1,
				MatchedCount:  1,
				Within:        "5m",
				MatchedLogIDs: []string{"doc-1"},
			}},
		},
	}

	errorsByIndex := writer.WriteResults(context.Background(), []*models.CorrelationResult{result})
	if len(errorsByIndex) != 1 || errorsByIndex[0] != nil {
		t.Fatalf("expected successful write, got %#v", errorsByIndex)
	}
	if len(calls) != 2 {
		t.Fatalf("expected two bulk calls, got %d", len(calls))
	}
	if !strings.Contains(calls[0].path, "/rca_correlated_events/_bulk") {
		t.Fatalf("expected history bulk request first, got %s", calls[0].path)
	}
	if !strings.Contains(calls[0].body, `"history-doc-1"`) {
		t.Fatalf("expected history document id in first bulk body, got %s", calls[0].body)
	}
	if !strings.Contains(calls[0].body, `"is_processed":0`) {
		t.Fatalf("expected history document to be marked unprocessed, got %s", calls[0].body)
	}
	if strings.Contains(calls[0].body, `"schema_version"`) {
		t.Fatalf("expected compact history payload without schema_version, got %s", calls[0].body)
	}
	if strings.Contains(calls[0].body, `"rule_type"`) || strings.Contains(calls[0].body, `"group_by"`) || strings.Contains(calls[0].body, `"required_metadata"`) || strings.Contains(calls[0].body, `"deduplication_key"`) || strings.Contains(calls[0].body, `"deduplication_window"`) || strings.Contains(calls[0].body, `"step_index"`) || strings.Contains(calls[0].body, `"signal_key"`) {
		t.Fatalf("expected unused audit fields to be removed from history payload, got %s", calls[0].body)
	}
	if !strings.Contains(calls[0].body, `"correlated_at":"2026-04-12T09:00:30Z"`) {
		t.Fatalf("expected correlated_at in history payload, got %s", calls[0].body)
	}
	if strings.Contains(calls[0].body, `"signalized_at"`) {
		t.Fatalf("expected signalized_at to be removed from history payload, got %s", calls[0].body)
	}
	if !strings.Contains(calls[1].path, "/rca_correlated_incidents_current/_bulk") {
		t.Fatalf("expected current bulk request second, got %s", calls[1].path)
	}
	if !strings.Contains(calls[1].body, `"incident-1"`) {
		t.Fatalf("expected incident id in current bulk body, got %s", calls[1].body)
	}
	if !strings.Contains(calls[1].body, `"is_processed":0`) {
		t.Fatalf("expected current document to be marked unprocessed, got %s", calls[1].body)
	}
	if strings.Contains(calls[1].body, `"schema_version"`) || strings.Contains(calls[1].body, `"rule_type"`) || strings.Contains(calls[1].body, `"group_by"`) || strings.Contains(calls[1].body, `"required_metadata"`) || strings.Contains(calls[1].body, `"deduplication_key"`) || strings.Contains(calls[1].body, `"deduplication_window"`) || strings.Contains(calls[1].body, `"step_index"`) || strings.Contains(calls[1].body, `"signal_key"`) {
		t.Fatalf("expected compact current payload without removed fields, got %s", calls[1].body)
	}
	if !strings.Contains(calls[1].body, `"correlated_at":"2026-04-12T09:00:30Z"`) {
		t.Fatalf("expected correlated_at in current payload, got %s", calls[1].body)
	}
	if strings.Contains(calls[1].body, `"signalized_at"`) {
		t.Fatalf("expected signalized_at to be removed from current payload, got %s", calls[1].body)
	}
}

func TestWriterWriteResultsCanSkipHistoryIndexAndOnlyWriteCurrent(t *testing.T) {
	type bulkCall struct {
		path string
		body string
	}

	calls := make([]bulkCall, 0, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Elastic-Product", "Elasticsearch")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"version":{"number":"8.11.0"}}`))
		case strings.HasSuffix(r.URL.Path, "/_bulk"):
			payload, _ := io.ReadAll(r.Body)
			calls = append(calls, bulkCall{
				path: r.URL.Path,
				body: string(payload),
			})
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"errors":false,"items":[{"index":{"_id":"ok","status":201}}]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	writer, err := NewWriter(config.ElasticsearchConfig{
		Addresses:      []string{server.URL},
		Index:          "rca_correlated_events",
		WriteHistory:   false,
		CurrentIndex:   "rca_correlated_incidents_current",
		RequestTimeout: time.Second,
		BulkBatchSize:  10,
	}, nil)
	if err != nil {
		t.Fatalf("failed to create writer: %v", err)
	}

	now := time.Date(2026, time.April, 12, 9, 0, 0, 0, time.UTC)
	correlatedAt := now.Add(45 * time.Second)
	result := &models.CorrelationResult{
		SchemaVersion:   2,
		DocumentID:      "history-doc-1",
		IncidentID:      "incident-1",
		OrganizationID:  "org-1",
		RuleID:          "rule-1",
		Status:          "open",
		ResultSignature: "sig-1",
		MatchedAt:       now,
		CorrelatedAt:    correlatedAt,
		LogID:           []models.ResultLog{{ID: "doc-1", SignalizedAt: now.Add(-time.Second)}},
	}

	errorsByIndex := writer.WriteResults(context.Background(), []*models.CorrelationResult{result})
	if len(errorsByIndex) != 1 || errorsByIndex[0] != nil {
		t.Fatalf("expected successful write, got %#v", errorsByIndex)
	}
	if len(calls) != 1 {
		t.Fatalf("expected one bulk call when history write is disabled, got %d", len(calls))
	}
	if !strings.Contains(calls[0].path, "/rca_correlated_incidents_current/_bulk") {
		t.Fatalf("expected only current bulk request, got %s", calls[0].path)
	}
	if !strings.Contains(calls[0].body, `"incident-1"`) {
		t.Fatalf("expected incident id in current bulk body, got %s", calls[0].body)
	}
	if !strings.Contains(calls[0].body, `"is_processed":0`) {
		t.Fatalf("expected current document to be marked unprocessed, got %s", calls[0].body)
	}
	if strings.Contains(calls[0].body, `"schema_version"`) || strings.Contains(calls[0].body, `"rule_type"`) || strings.Contains(calls[0].body, `"group_by"`) {
		t.Fatalf("expected compact current payload without removed fields, got %s", calls[0].body)
	}
	if !strings.Contains(calls[0].body, `"correlated_at":"2026-04-12T09:00:45Z"`) {
		t.Fatalf("expected correlated_at in current payload, got %s", calls[0].body)
	}
	if strings.Contains(calls[0].body, `"signalized_at"`) {
		t.Fatalf("expected signalized_at to be removed from current payload, got %s", calls[0].body)
	}
}
