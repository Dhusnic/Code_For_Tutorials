package service

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"

	"log_signal_processor/internal/config"
	"log_signal_processor/internal/elasticsearch"
	"log_signal_processor/internal/model"
)

type collectorTestSource struct {
	documents []elasticsearch.DocumentHit
}

func (s *collectorTestSource) SearchSignalDocuments(context.Context, time.Time, time.Time) ([]elasticsearch.DocumentHit, error) {
	return append([]elasticsearch.DocumentHit(nil), s.documents...), nil
}

type collectorTestStore struct {
	mu         sync.Mutex
	logs       map[string][]model.SignalLog
	saved      map[string][]model.SignalLog
	deleted    []string
	listedOrgs []string
}

func (s *collectorTestStore) ListOrganizations(context.Context) ([]string, error) {
	return append([]string(nil), s.listedOrgs...), nil
}

func (s *collectorTestStore) LoadLogs(_ context.Context, organization string) ([]model.SignalLog, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]model.SignalLog(nil), s.logs[organization]...), nil
}

func (s *collectorTestStore) SaveLogs(_ context.Context, organization string, logs []model.SignalLog) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.saved == nil {
		s.saved = make(map[string][]model.SignalLog)
	}
	s.saved[organization] = append([]model.SignalLog(nil), logs...)
	return nil
}

func (s *collectorTestStore) DeleteLogs(_ context.Context, organization string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.deleted = append(s.deleted, organization)
	return nil
}

func TestMapDocument(t *testing.T) {
	record, err := MapDocument(elasticsearch.DocumentHit{
		ID: "abc123",
		Source: map[string]any{
			"signal":     "disk_failure",
			"log_level":  "critical",
			"@timestamp": "2026-03-17T10:21:00Z",
			"event": map[string]any{
				"organization": "org123",
			},
		},
	}, config.FieldMappings{
		OrganizationField: "event.organization",
		SignalField:       "signal",
		LogLevelField:     "log_level",
		TimestampField:    "@timestamp",
		DocIDSource:       "_id",
	})
	if err != nil {
		t.Fatalf("unexpected map error: %v", err)
	}
	if record.Organization != "org123" {
		t.Fatalf("expected organization org123, got %s", record.Organization)
	}
	if record.Log.DocID != "abc123" {
		t.Fatalf("expected doc id abc123, got %s", record.Log.DocID)
	}
}

func TestGroupByOrganization(t *testing.T) {
	grouped := GroupByOrganization([]model.SignalRecord{
		{
			Organization: "org-a",
			Log: model.SignalLog{
				DocID:     "1",
				TimeStamp: time.Date(2026, 3, 17, 10, 0, 0, 0, time.UTC),
			},
		},
		{
			Organization: "org-a",
			Log: model.SignalLog{
				DocID:     "2",
				TimeStamp: time.Date(2026, 3, 17, 10, 1, 0, 0, time.UTC),
			},
		},
		{
			Organization: "org-b",
			Log: model.SignalLog{
				DocID:     "3",
				TimeStamp: time.Date(2026, 3, 17, 10, 2, 0, 0, time.UTC),
			},
		},
	})

	if len(grouped["org-a"]) != 2 {
		t.Fatalf("expected 2 records for org-a, got %d", len(grouped["org-a"]))
	}
	if len(grouped["org-b"]) != 1 {
		t.Fatalf("expected 1 record for org-b, got %d", len(grouped["org-b"]))
	}
}

func TestMergeLogsDedupesAndTrims(t *testing.T) {
	cutoff := time.Date(2026, 3, 17, 10, 0, 0, 0, time.UTC)
	existing := []model.SignalLog{
		{
			Signal:    "old-signal",
			LogLevel:  "warning",
			DocID:     "same",
			TimeStamp: time.Date(2026, 3, 17, 10, 5, 0, 0, time.UTC),
		},
		{
			Signal:    "expired",
			LogLevel:  "error",
			DocID:     "expired",
			TimeStamp: time.Date(2026, 3, 17, 9, 30, 0, 0, time.UTC),
		},
	}
	incoming := []model.SignalLog{
		{
			Signal:    "new-signal",
			LogLevel:  "critical",
			DocID:     "same",
			TimeStamp: time.Date(2026, 3, 17, 10, 6, 0, 0, time.UTC),
		},
		{
			Signal:    "fresh",
			LogLevel:  "info",
			DocID:     "fresh",
			TimeStamp: time.Date(2026, 3, 17, 10, 7, 0, 0, time.UTC),
		},
	}

	merged := MergeLogs(existing, incoming, cutoff)
	if len(merged) != 2 {
		t.Fatalf("expected 2 merged records, got %d", len(merged))
	}
	if merged[0].DocID != "same" || merged[0].Signal != "new-signal" {
		t.Fatalf("expected newest duplicate to win, got %+v", merged[0])
	}
	if merged[1].DocID != "fresh" {
		t.Fatalf("expected fresh record second, got %+v", merged[1])
	}
}

func TestSignalLogsEqual(t *testing.T) {
	now := time.Date(2026, 3, 17, 10, 0, 0, 0, time.UTC)
	left := []model.SignalLog{
		{Signal: "disk_failure", LogLevel: "critical", DocID: "doc-1", TimeStamp: now},
	}
	right := []model.SignalLog{
		{Signal: "disk_failure", LogLevel: "critical", DocID: "doc-1", TimeStamp: now},
	}
	if !signalLogsEqual(left, right) {
		t.Fatalf("expected logs to be equal")
	}

	right[0].LogLevel = "warning"
	if signalLogsEqual(left, right) {
		t.Fatalf("expected logs to be different when level changes")
	}
}

func TestCollectorRunCycleProcessesOrganizationsWithWorkerPool(t *testing.T) {
	now := time.Date(2026, 4, 9, 10, 0, 0, 0, time.UTC)
	source := &collectorTestSource{
		documents: []elasticsearch.DocumentHit{
			{
				ID: "doc-1",
				Source: map[string]any{
					"signal": "disk_failure",
					"log": map[string]any{
						"level": "critical",
					},
					"@timestamp": now.Format(time.RFC3339Nano),
					"event": map[string]any{
						"organization": "org-1",
					},
				},
			},
			{
				ID: "doc-2",
				Source: map[string]any{
					"signal": "cpu_high",
					"log": map[string]any{
						"level": "warning",
					},
					"@timestamp": now.Add(time.Second).Format(time.RFC3339Nano),
					"event": map[string]any{
						"organization": "org-2",
					},
				},
			},
		},
	}
	store := &collectorTestStore{
		logs: map[string][]model.SignalLog{
			"org-1": {
				{Signal: "disk_failure", LogLevel: "critical", DocID: "doc-1", TimeStamp: now},
			},
			"org-3": {
				{Signal: "stale", LogLevel: "info", DocID: "doc-3", TimeStamp: now.Add(-time.Hour)},
			},
		},
		listedOrgs: []string{"org-1", "org-3"},
	}

	cfg := config.Config{
		Elasticsearch: config.ElasticsearchConfig{
			Window: time.Minute,
		},
		Redis: config.RedisConfig{
			RetentionWindow: 30 * time.Minute,
		},
		Scheduler: config.SchedulerConfig{
			OrganizationWorkers: 2,
		},
		Mappings: config.FieldMappings{
			OrganizationField: "event.organization",
			SignalField:       "signal",
			LogLevelField:     "log.level",
			TimestampField:    "@timestamp",
			DocIDSource:       "_id",
		},
	}

	collector := NewCollector(Dependencies{
		Config: cfg,
		Source: source,
		Store:  store,
		Logger: slog.Default(),
	})
	collector.now = func() time.Time { return now }

	if err := collector.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}

	if len(store.saved) != 1 {
		t.Fatalf("expected 1 organization save due unchanged org-1, got %d", len(store.saved))
	}
	if _, ok := store.saved["org-2"]; !ok {
		t.Fatalf("expected org-2 to be saved, got %v", store.saved)
	}
	if len(store.deleted) != 1 || store.deleted[0] != "org-3" {
		t.Fatalf("expected org-3 to be deleted, got %v", store.deleted)
	}
	if _, ok := store.saved["org-1"]; ok {
		t.Fatalf("expected unchanged org-1 to skip save, got %v", store.saved["org-1"])
	}
}

func TestCollectorRunCycleProcessesOnlyOwnedShardOrganizations(t *testing.T) {
	now := time.Date(2026, 4, 9, 11, 0, 0, 0, time.UTC)
	shardCount := 8
	orgA := "org-alpha"
	orgB := "org-bravo"
	for organizationShard(orgA, shardCount) == organizationShard(orgB, shardCount) {
		orgB += "-x"
	}

	source := &collectorTestSource{
		documents: []elasticsearch.DocumentHit{
			{
				ID: "doc-a",
				Source: map[string]any{
					"signal": "disk_failure",
					"log": map[string]any{
						"level": "critical",
					},
					"@timestamp": now.Format(time.RFC3339Nano),
					"event": map[string]any{
						"organization": orgA,
					},
				},
			},
			{
				ID: "doc-b",
				Source: map[string]any{
					"signal": "cpu_high",
					"log": map[string]any{
						"level": "warning",
					},
					"@timestamp": now.Add(time.Second).Format(time.RFC3339Nano),
					"event": map[string]any{
						"organization": orgB,
					},
				},
			},
		},
	}
	store := &collectorTestStore{}
	released := false

	collector := NewCollector(Dependencies{
		Config: config.Config{
			Elasticsearch: config.ElasticsearchConfig{
				Window: time.Minute,
			},
			Redis: config.RedisConfig{
				RetentionWindow: 30 * time.Minute,
			},
			Scheduler: config.SchedulerConfig{
				OrganizationWorkers: 2,
			},
			Mappings: config.FieldMappings{
				OrganizationField: "event.organization",
				SignalField:       "signal",
				LogLevelField:     "log.level",
				TimestampField:    "@timestamp",
				DocIDSource:       "_id",
			},
		},
		Source: source,
		Store:  store,
		AcquireShardLease: func(context.Context) (ShardLease, bool, error) {
			return ShardLease{
				ShardCount:  shardCount,
				OwnedShards: []int{organizationShard(orgA, shardCount)},
				Release: func(context.Context) (bool, error) {
					released = true
					return true, nil
				},
			}, true, nil
		},
		Logger: slog.Default(),
	})
	collector.now = func() time.Time { return now }

	if err := collector.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}

	if !released {
		t.Fatalf("expected shard lease to be released")
	}
	if len(store.saved) != 1 {
		t.Fatalf("expected only one shard-owned organization save, got %d", len(store.saved))
	}
	if _, ok := store.saved[orgA]; !ok {
		t.Fatalf("expected %s to be saved, got %v", orgA, store.saved)
	}
	if _, ok := store.saved[orgB]; ok {
		t.Fatalf("did not expect %s to be saved, got %v", orgB, store.saved[orgB])
	}
}
