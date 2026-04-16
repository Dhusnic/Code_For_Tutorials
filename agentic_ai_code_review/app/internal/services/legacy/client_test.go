package legacy

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"agenticai/desktop/internal/contracts"
)

func TestRunFullReviewForwardsPayloadAndAsyncQuery(t *testing.T) {
	t.Parallel()

	var capturedPath string
	var capturedQuery string
	var capturedPayload map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		capturedQuery = r.URL.RawQuery
		defer r.Body.Close()
		_ = json.NewDecoder(r.Body).Decode(&capturedPayload)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"review":"ok","tokens_used":10}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, time.Second, nil, nil)
	_, err := client.RunFullReview(context.Background(), contracts.ConfigModel{
		RepoPath: "D:/repo",
		AIModel:  "gpt-4o-mini",
	}, true)
	if err != nil {
		t.Fatalf("RunFullReview returned error: %v", err)
	}

	if capturedPath != "/api/run-full-review" {
		t.Fatalf("unexpected path: %s", capturedPath)
	}
	if capturedQuery != "async_job=true" {
		t.Fatalf("unexpected query: %s", capturedQuery)
	}
	if capturedPayload["repo_path"] != "D:/repo" {
		t.Fatalf("expected repo_path to be forwarded")
	}
}

func TestBridgePropagatesErrorDetail(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"detail":"invalid request payload"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, time.Second, nil, nil)
	_, err := client.GetUsageMetrics(context.Background())
	if err == nil {
		t.Fatal("expected error but got nil")
	}
	if err.Error() == "" || err.Error() == "legacy_api_error" {
		t.Fatalf("expected detailed error message, got %v", err)
	}
}

func TestBridgeAutoStartsLegacyAPIOnTransportError(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"summary":{"request_count":2}}`)
	}))
	defer server.Close()

	ensureCalls := 0
	client := NewClient(server.URL, time.Second, nil, func(_ context.Context) error {
		ensureCalls++
		return nil
	})

	client.httpClient.Transport = &failFirstTransport{
		target: http.DefaultTransport,
	}

	_, err := client.GetUsageMetrics(context.Background())
	if err != nil {
		t.Fatalf("expected auto-start retry to recover request, got error: %v", err)
	}
	if ensureCalls != 1 {
		t.Fatalf("expected ensureRunning to be called once, got %d", ensureCalls)
	}
}

type failFirstTransport struct {
	mu     sync.Mutex
	failed bool
	target http.RoundTripper
}

func (f *failFirstTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if !f.failed {
		f.failed = true
		return nil, errors.New("dial tcp 127.0.0.1:8000: connectex: actively refused")
	}
	return f.target.RoundTrip(request)
}
