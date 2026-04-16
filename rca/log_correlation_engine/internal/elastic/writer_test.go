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
		CurrentIndex:   "rca_correlated_incidents_current",
		RequestTimeout: time.Second,
		BulkBatchSize:  10,
	}, nil)
	if err != nil {
		t.Fatalf("failed to create writer: %v", err)
	}

	now := time.Date(2026, time.April, 12, 9, 0, 0, 0, time.UTC)
	result := &models.CorrelationResult{
		SchemaVersion:   2,
		DocumentID:      "history-doc-1",
		IncidentID:      "incident-1",
		OrganizationID:  "org-1",
		RuleID:          "rule-1",
		Status:          "open",
		ResultSignature: "sig-1",
		MatchedAt:       now,
		LogID:           []models.ResultLog{{ID: "doc-1"}},
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
	if !strings.Contains(calls[1].path, "/rca_correlated_incidents_current/_bulk") {
		t.Fatalf("expected current bulk request second, got %s", calls[1].path)
	}
	if !strings.Contains(calls[1].body, `"incident-1"`) {
		t.Fatalf("expected incident id in current bulk body, got %s", calls[1].body)
	}
}
