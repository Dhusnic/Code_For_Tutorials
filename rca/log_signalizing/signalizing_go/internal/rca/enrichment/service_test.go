package enrichment

import (
	"testing"
	"time"

	"rca/internal/rca/checkpoints"
	"rca/internal/rca/config"
)

type stubCountClient struct {
	countValue int
	fail       bool
	calls      []map[string]any
}

func (c *stubCountClient) Count(index string, body map[string]any) (map[string]any, error) {
	c.calls = append(c.calls, map[string]any{"index": index, "body": body})
	if c.fail {
		return nil, assertError("count failed")
	}
	return map[string]any{"count": c.countValue}, nil
}

type stubIndicesClient struct {
	patterns map[string][]string
	fail     bool
}

func (c *stubIndicesClient) IndicesGet(index string) (map[string]any, error) {
	if c.fail {
		return nil, assertError("boom")
	}
	response := make(map[string]any)
	for _, name := range c.patterns[index] {
		response[name] = map[string]any{}
	}
	return response, nil
}

type assertError string

func (e assertError) Error() string { return string(e) }

func buildServiceConfig() config.AppConfig {
	return config.AppConfig{
		Elasticsearch: config.ElasticsearchConfig{Hosts: []string{"http://localhost:9200"}},
		Checkpoints:   config.CheckpointConfig{Provider: "file", Path: "state/checkpoints.json"},
		Logging:       config.LoggingConfig{Level: "INFO", JSON: true, LogUnmatchedEvents: false},
		Pipeline: config.PipelineConfig{
			BatchSize:                         2000,
			BatchSizeMode:                     "static",
			DynamicBatchMinSize:               500,
			DynamicBatchMaxSize:               5000,
			DynamicBatchLookbackSeconds:       20,
			DynamicBatchTargetWindowSeconds:   2.0,
			DynamicBatchSmoothingAlpha:        1.0,
			WorkerID:                          0,
			WorkerCount:                       1,
			WriteToSourceIndex:                false,
			WriteToTargetIndex:                true,
			TargetSuffix:                      "-rca",
			BulkWorkerCount:                   1,
			BulkQueueSize:                     1,
			BulkQueueEnqueueTimeoutSeconds:    0.01,
			BulkSpoolEnabled:                  false,
			BulkAutoscalingMinWorkers:         1,
			BulkAutoscalingMaxWorkers:         1,
			BulkAutoscalingCPULimitPercent:    85,
			BulkAutoscalingMemoryLimitPercent: 85,
			PollIntervalSeconds:               1,
			TimestampField:                    "@timestamp",
			StartTime:                         "now-15m",
			BulkMaxBatchBytes:                 1024 * 1024,
		},
		RulesDirectory: "rules",
		RuleLearning: config.RuleLearningConfig{
			Enabled: false,
		},
	}
}

func TestResolveDestinationIndicesDoesNotAppendSuffixTwice(t *testing.T) {
	cfg := buildServiceConfig()
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(struct{}{}, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	destinations := service.resolveDestinationIndices("linux_logs-2026.02.19-rca")
	if len(destinations) != 1 || destinations[0] != "linux_logs-2026.02.19-rca" {
		t.Fatalf("unexpected destinations: %#v", destinations)
	}
}

func TestIsAlreadySignaledDocHandlesBoolAndString(t *testing.T) {
	if !isAlreadySignaledDoc(map[string]any{"signal_present": true}) {
		t.Fatal("expected bool true to be treated as signaled")
	}
	if !isAlreadySignaledDoc(map[string]any{"signal_present": "true"}) {
		t.Fatal("expected string true to be treated as signaled")
	}
	if !isAlreadySignaledDoc(map[string]any{"signal_present": 1}) {
		t.Fatal("expected numeric 1 to be treated as signaled")
	}
	if isAlreadySignaledDoc(map[string]any{"signal_present": false}) {
		t.Fatal("expected false to be untreated")
	}
}

func TestResolveBatchSizeStaticModeUsesConfiguredBatchSize(t *testing.T) {
	client := &stubCountClient{countValue: 50000}
	cfg := buildServiceConfig()
	cfg.Pipeline.BatchSizeMode = "static"
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(client, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	batch := service.resolveBatchSize(config.ServiceConfig{Name: "nginx", Query: map[string]any{"term": map[string]any{"event.module": "nginx"}}}, "linux-*")
	if batch != 2000 {
		t.Fatalf("expected static batch size 2000, got %d", batch)
	}
	if len(client.calls) != 0 {
		t.Fatalf("expected no count calls in static mode, got %#v", client.calls)
	}
}

func TestResolveBatchSizeDynamicModeUsesRecentEventsPerSecond(t *testing.T) {
	client := &stubCountClient{countValue: 30000}
	cfg := buildServiceConfig()
	cfg.Pipeline.BatchSizeMode = "dynamic"
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(client, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	batch := service.resolveBatchSize(config.ServiceConfig{Name: "nginx", Query: map[string]any{"term": map[string]any{"event.module": "nginx"}}}, "linux-*")
	if batch != 3000 {
		t.Fatalf("expected dynamic batch size 3000, got %d", batch)
	}
	if len(client.calls) != 1 {
		t.Fatalf("expected one count call, got %d", len(client.calls))
	}
}

func TestSelectOwnedWorkUnitsChangesByWorkerID(t *testing.T) {
	cfg0 := buildServiceConfig()
	cfg0.Pipeline.WorkerCount = 2
	cfg0.Pipeline.WorkerID = 0
	cfg1 := buildServiceConfig()
	cfg1.Pipeline.WorkerCount = 2
	cfg1.Pipeline.WorkerID = 1

	store0 := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	store1 := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service0, err := NewSignalEnrichmentService(struct{}{}, cfg0, store0)
	if err != nil {
		t.Fatalf("create service0: %v", err)
	}
	defer service0.Shutdown()
	service1, err := NewSignalEnrichmentService(struct{}{}, cfg1, store1)
	if err != nil {
		t.Fatalf("create service1: %v", err)
	}
	defer service1.Shutdown()

	allUnits := []workUnit{
		{serviceConfig: config.ServiceConfig{Name: "auth"}, indexName: "logs-auth"},
		{serviceConfig: config.ServiceConfig{Name: "nginx"}, indexName: "logs-nginx"},
	}
	owned0 := service0.selectOwnedWorkUnits(append([]workUnit{}, allUnits...))
	owned1 := service1.selectOwnedWorkUnits(append([]workUnit{}, allUnits...))
	if len(owned0) != 1 || len(owned1) != 1 {
		t.Fatalf("expected one unit per worker, got %d and %d", len(owned0), len(owned1))
	}
	if owned0[0].serviceConfig.Name == owned1[0].serviceConfig.Name && owned0[0].indexName == owned1[0].indexName {
		t.Fatalf("expected workers to receive different units, got %#v and %#v", owned0, owned1)
	}
}

func TestSelectOwnedWorkUnitsBalancesEvenlyAcrossFourWorkers(t *testing.T) {
	cfg := buildServiceConfig()
	cfg.Pipeline.WorkerCount = 4

	units := []workUnit{
		{serviceConfig: config.ServiceConfig{Name: "nginx"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "rabbitmq"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "mongodb"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "redis"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "kafka"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "postgres"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "auth"}, indexName: "*"},
		{serviceConfig: config.ServiceConfig{Name: "network"}, indexName: "network-*"},
	}

	counts := make([]int, 0, 4)
	for workerID := 0; workerID < 4; workerID++ {
		cfg.Pipeline.WorkerID = workerID
		store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
		service, err := NewSignalEnrichmentService(struct{}{}, cfg, store)
		if err != nil {
			t.Fatalf("create service: %v", err)
		}
		owned := service.selectOwnedWorkUnits(append([]workUnit{}, units...))
		counts = append(counts, len(owned))
		service.Shutdown()
	}

	for _, count := range counts {
		if count != 2 {
			t.Fatalf("expected balanced 2 units per worker, got %#v", counts)
		}
	}
}

func TestResolveSourceIndicesExpandsWildcards(t *testing.T) {
	cfg := buildServiceConfig()
	cfg.Pipeline.WorkerCount = 2
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(&stubIndicesClient{patterns: map[string][]string{"logs-*": []string{"logs-2026.02.22", "logs-2026.02.23"}}}, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	resolved := service.resolveSourceIndices("nginx", []string{"logs-*", "logs-2026.02.23"})
	if len(resolved) != 2 || resolved[0] != "logs-2026.02.22" || resolved[1] != "logs-2026.02.23" {
		t.Fatalf("unexpected resolved indices: %#v", resolved)
	}
}

func TestBuildSignalStreamEventUsesOrganizationAndNormalizedLevel(t *testing.T) {
	cfg := buildServiceConfig()
	cfg.SignalStream = config.SignalStreamConfig{
		Enabled:               true,
		StreamKey:             "Rca:signalized_log_events",
		OrganizationFieldPath: "event.organization",
	}
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(struct{}{}, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	event, ok := service.buildSignalStreamEvent(
		"linux-logs",
		"doc-1",
		map[string]any{
			"@timestamp": "2026-04-09T10:00:00Z",
			"host": map[string]any{
				"ip": []any{"10.0.0.12", "10.0.0.13"},
			},
			"log": map[string]any{
				"level": "ERR",
			},
			"event": map[string]any{
				"organization": "org-1",
			},
		},
		map[string]any{
			"signal": "mongodb_auth_failed",
			"level":  "warning",
		},
	)
	if !ok {
		t.Fatalf("expected stream event to be built")
	}
	if event.OrganizationID != "org-1" {
		t.Fatalf("expected organization org-1, got %q", event.OrganizationID)
	}
	if event.HostIdentity != "10.0.0.12" {
		t.Fatalf("expected host identity 10.0.0.12, got %q", event.HostIdentity)
	}
	if event.DocID != "doc-1" {
		t.Fatalf("expected doc id doc-1, got %q", event.DocID)
	}
	if event.Signal != "mongodb_auth_failed" {
		t.Fatalf("expected signal mongodb_auth_failed, got %q", event.Signal)
	}
	if event.LogLevel != "error" {
		t.Fatalf("expected normalized log level error, got %q", event.LogLevel)
	}
	if event.SourceIndex != "linux-logs" || event.SourceID != "doc-1" {
		t.Fatalf("unexpected source fields: %#v", event)
	}
	if !event.TimeStamp.Equal(time.Date(2026, 4, 9, 10, 0, 0, 0, time.UTC)) {
		t.Fatalf("unexpected event timestamp %s", event.TimeStamp)
	}
}

func TestBuildSignalStreamEventFallsBackToOrganizationInMessage(t *testing.T) {
	cfg := buildServiceConfig()
	cfg.SignalStream = config.SignalStreamConfig{
		Enabled:               true,
		StreamKey:             "Rca:signalized_log_events",
		OrganizationFieldPath: "event.organization",
	}
	store := checkpoints.NewFileStore(t.TempDir() + "\\checkpoints.json")
	service, err := NewSignalEnrichmentService(struct{}{}, cfg, store)
	if err != nil {
		t.Fatalf("create service: %v", err)
	}
	defer service.Shutdown()

	event, ok := service.buildSignalStreamEvent(
		"linux-logs",
		"doc-2",
		map[string]any{
			"@timestamp": "2026-04-09T10:05:00Z",
			"message":    `10.0.0.15 - - [09/Apr/2026:15:35:00 +0000] "GET /api/orders?rca_run_id=test&org=135098068173316952064 HTTP/1.1" 502 182 "-" "curl/8.5.0"`,
			"log": map[string]any{
				"level": "error",
			},
		},
		map[string]any{
			"signal": "nginx_access_5xx_any",
			"level":  "critical",
		},
	)
	if !ok {
		t.Fatalf("expected fallback stream event to be built")
	}
	if event.OrganizationID != "135098068173316952064" {
		t.Fatalf("expected fallback organization id, got %q", event.OrganizationID)
	}
	if event.Signal != "nginx_access_5xx_any" {
		t.Fatalf("expected nginx signal, got %q", event.Signal)
	}
	if event.HostIdentity != "" {
		t.Fatalf("expected empty host identity without host metadata, got %q", event.HostIdentity)
	}
}
