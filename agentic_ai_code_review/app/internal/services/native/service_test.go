package native

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"agenticai/desktop/internal/contracts"
)

func TestNativeServiceBridgesAndAddsExecutionMetadata(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/usage-metrics" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"summary":{"request_count":1}}`))
	}))
	defer server.Close()

	service := NewService(server.URL, time.Second, nil, nil)
	result, err := service.GetUsageMetrics(context.Background())
	if err != nil {
		t.Fatalf("GetUsageMetrics returned error: %v", err)
	}

	mode, _ := result["desktop_execution_mode"].(string)
	if mode != "native_bridge" {
		t.Fatalf("expected desktop_execution_mode=native_bridge, got %q", mode)
	}
	op, _ := result["desktop_operation"].(string)
	if op != "GetUsageMetrics" {
		t.Fatalf("expected desktop_operation metadata")
	}
}

func TestNativeServicePropagatesBridgeErrors(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"detail":"bad request from baseline"}`))
	}))
	defer server.Close()

	service := NewService(server.URL, time.Second, nil, nil)
	_, err := service.RunFullReview(context.Background(), contracts.ConfigModel{RepoPath: "D:/repo"}, false)
	if err == nil {
		t.Fatal("expected error but got nil")
	}
	if !strings.Contains(strings.ToLower(err.Error()), "bad request") {
		t.Fatalf("expected propagated detail error, got %v", err)
	}
}
