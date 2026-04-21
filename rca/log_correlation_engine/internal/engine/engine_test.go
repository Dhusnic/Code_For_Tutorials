package engine

import (
	"context"
	"math"
	"testing"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"
)

func newTestEngine(t *testing.T) *Engine {
	t.Helper()

	engine, err := NewEngine(config.EngineConfig{
		DefaultWindow: 10 * time.Minute,
		DefaultMaxGap: 2 * time.Minute,
	}, nil)
	if err != nil {
		t.Fatalf("failed to create engine: %v", err)
	}
	return engine
}

func approxEqual(got, want float64) bool {
	return math.Abs(got-want) < 0.000001
}

func mergeMetadata(base map[string]any, overlay map[string]any) map[string]any {
	merged := make(map[string]any, len(base)+len(overlay))
	for key, value := range base {
		merged[key] = value
	}
	for key, value := range overlay {
		merged[key] = value
	}
	return merged
}

func TestSlidingWindowMatchHonorsMinCount(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "rabbitmq_queue_depth_high", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(1 * time.Minute), Signal: "rabbitmq_queue_depth_high", Metadata: map[string]any{}},
		{DocID: "3", Timestamp: now.Add(2 * time.Minute), Signal: "rabbitmq_heartbeat_missed", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType:           "ordered_signal_sequence",
		Window:             "10m",
		MaxGapBetweenSteps: "2m",
		Sequence: []models.SequenceStep{
			{SignalKey: "rabbitmq_queue_depth_high", MinCount: 2, Within: "5m"},
			{SignalKey: "rabbitmq_heartbeat_missed", MinCount: 1, Within: "3m"},
		},
	})

	if match.matchedSteps != 2 {
		t.Fatalf("expected 2 matched steps, got %d", match.matchedSteps)
	}
	if len(match.logs) != 3 {
		t.Fatalf("expected 3 matched logs, got %d", len(match.logs))
	}
}

func TestSlidingWindowMatchReturnsPartialProgressWhenWithinFails(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "rabbitmq_queue_depth_high", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(6 * time.Minute), Signal: "rabbitmq_queue_depth_high", Metadata: map[string]any{}},
		{DocID: "3", Timestamp: now.Add(7 * time.Minute), Signal: "rabbitmq_heartbeat_missed", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType:           "ordered_signal_sequence",
		Window:             "15m",
		MaxGapBetweenSteps: "3m",
		Sequence: []models.SequenceStep{
			{SignalKey: "rabbitmq_queue_depth_high", MinCount: 2, Within: "5m"},
			{SignalKey: "rabbitmq_heartbeat_missed", MinCount: 1, Within: "3m"},
		},
	})

	if match.matchedSteps != 0 {
		t.Fatalf("expected 0 fully matched steps, got %d", match.matchedSteps)
	}
	if len(match.logs) != 1 {
		t.Fatalf("expected 1 partially matched log, got %d", len(match.logs))
	}
	if len(match.stepMatches) != 2 || match.stepMatches[0] != 1 {
		t.Fatalf("expected first step partial progress of 1, got %#v", match.stepMatches)
	}
}

func TestSlidingWindowMatchWithoutMaxGapSearchesAcrossWholeWindow(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "rabbitmq_queue_depth_high", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(7 * time.Minute), Signal: "rabbitmq_heartbeat_missed", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType: "ordered_signal_sequence",
		Window:   "15m",
		Sequence: []models.SequenceStep{
			{SignalKey: "rabbitmq_queue_depth_high", MinCount: 1, Within: "15m"},
			{SignalKey: "rabbitmq_heartbeat_missed", MinCount: 1, Within: "15m"},
		},
	})

	if match.matchedSteps != 2 {
		t.Fatalf("expected 2 matched steps without explicit max gap, got %d", match.matchedSteps)
	}
	if len(match.logs) != 2 {
		t.Fatalf("expected 2 matched logs without explicit max gap, got %d", len(match.logs))
	}
}

func TestSlidingWindowMatchSupportsSignalKeyAlternatives(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "kafka_broker_not_available", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(time.Minute), Signal: "data_collector_service_down", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType:           "ordered_signal_sequence",
		Window:             "10m",
		MaxGapBetweenSteps: "3m",
		Sequence: []models.SequenceStep{
			{
				SignalKeys: []string{
					"kafka_broker_not_available",
					"mongodb_host_unreachable",
					"postgres_conn_failed",
				},
				MinCount: 1,
				Within:   "5m",
			},
			{SignalKey: "data_collector_service_down", MinCount: 1, Within: "3m"},
		},
	})

	if match.matchedSteps != 2 {
		t.Fatalf("expected 2 matched steps, got %d", match.matchedSteps)
	}
	if len(match.logs) != 2 {
		t.Fatalf("expected 2 matched logs, got %d", len(match.logs))
	}
	if match.logs[0].Signal != "kafka_broker_not_available" {
		t.Fatalf("expected first step to match one alternative signal, got %#v", match.logs[0])
	}
}

func TestSlidingWindowMatchSupportsAnyOfBlocks(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "mongodb_host_unreachable", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(time.Minute), Signal: "data_collector_service_down", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType:           "ordered_signal_sequence",
		Window:             "10m",
		MaxGapBetweenSteps: "3m",
		Sequence: []models.SequenceStep{
			{
				AnyOf: []models.SignalSelector{
					{SignalKey: "kafka_broker_not_available"},
					{SignalKey: "mongodb_host_unreachable"},
					{SignalKey: "postgres_conn_failed"},
				},
				Within: "5m",
			},
			{
				AnyOf: []models.SignalSelector{
					{SignalKey: "data_collector_service_down"},
					{SignalKey: "systemd_unit_failed"},
				},
				Within: "3m",
			},
		},
	})

	if match.matchedSteps != 2 {
		t.Fatalf("expected 2 matched steps, got %d", match.matchedSteps)
	}
	if len(match.logs) != 2 {
		t.Fatalf("expected 2 matched logs, got %d", len(match.logs))
	}
}

func TestSlidingWindowMatchSupportsAllOfBlocksInAnyOrder(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{DocID: "1", Timestamp: now, Signal: "systemd_unit_failed", Metadata: map[string]any{}},
		{DocID: "2", Timestamp: now.Add(time.Minute), Signal: "data_collector_service_down", Metadata: map[string]any{}},
	}

	match := engine.slidingWindowMatch(logs, models.Rule{
		RuleType:           "ordered_signal_sequence",
		Window:             "10m",
		MaxGapBetweenSteps: "3m",
		Sequence: []models.SequenceStep{
			{
				AllOf: []models.SignalSelector{
					{SignalKey: "data_collector_service_down"},
					{SignalKeys: []string{"systemd_unit_failed", "systemd_watchdog_timeout"}},
				},
				Within: "5m",
			},
		},
	})

	if match.matchedSteps != 1 {
		t.Fatalf("expected 1 matched all_of step, got %d", match.matchedSteps)
	}
	if len(match.logs) != 2 {
		t.Fatalf("expected 2 matched logs for all_of step, got %d", len(match.logs))
	}
}

func TestCorrelateEmitsPartialResultForIncompleteAllOfStep(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "data_collector_service_down",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-allof-partial",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Sequence: []models.SequenceStep{
				{
					AllOf: []models.SignalSelector{
						{SignalKey: "data_collector_service_down"},
						{SignalKeys: []string{"systemd_unit_failed", "systemd_watchdog_timeout"}},
					},
					Within: "4m",
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 partial result, got %d", len(results))
	}
	if !approxEqual(results[0].RuleCompletion, 0.5) {
		t.Fatalf("expected rule completion 0.5, got %.6f", results[0].RuleCompletion)
	}
	if !approxEqual(results[0].SequenceMatch, 0.5) {
		t.Fatalf("expected sequence match 0.5, got %.6f", results[0].SequenceMatch)
	}
}

func TestCorrelateEmitsPartialResultForIncompleteSequence(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "rabbitmq_queue_depth_high",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
				"host.name":          "host-1",
				"service.name":       "api",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(1 * time.Minute),
			Signal:    "rabbitmq_queue_depth_high",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
				"host.name":          "host-1",
				"service.name":       "api",
			},
		},
		{
			DocID:     "3",
			Timestamp: now.Add(2 * time.Minute),
			Signal:    "rabbitmq_heartbeat_missed",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
				"host.name":          "host-1",
				"service.name":       "api",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "15m",
			MaxGapBetweenSteps: "3m",
			GroupBy:            []string{"event.organization", "host.name", "service.name"},
			Priority:           2,
			Sequence: []models.SequenceStep{
				{SignalKey: "rabbitmq_queue_depth_high", MinCount: 2, Within: "5m"},
				{SignalKey: "rabbitmq_heartbeat_missed", MinCount: 1, Within: "3m"},
				{SignalKey: "nginx_access_5xx_any", MinCount: 1, Within: "3m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 partial result, got %d", len(results))
	}

	result := results[0]
	if !approxEqual(result.RuleCompletion, 0.75) {
		t.Fatalf("expected rule completion 0.75, got %.6f", result.RuleCompletion)
	}
	if !approxEqual(result.SequenceMatch, 2.0/3.0) {
		t.Fatalf("expected sequence match %.6f, got %.6f", 2.0/3.0, result.SequenceMatch)
	}
	if len(result.LogID) != 3 {
		t.Fatalf("expected 3 matched logs in output, got %d", len(result.LogID))
	}
	if result.LogID[0].ID != "1" || result.LogID[0].Severity != "warning" {
		t.Fatalf("unexpected first compact log payload: %#v", result.LogID[0])
	}
}

func TestCorrelateIncludesSchemaV2EvidenceFields(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "doc-1",
			Timestamp: now,
			Signal:    "rabbitmq_queue_depth_high",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event": map[string]any{
					"organization": "org-1",
					"module":       "rabbitmq",
				},
				"host": map[string]any{
					"name": "host-1",
					"ip":   "172.16.1.10, 10.0.4.72",
				},
				"service": map[string]any{
					"name": "api",
				},
				"source_index": "linux-logs-2026.04.10",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Sequence: []models.SequenceStep{
				{SignalKey: "rabbitmq_queue_depth_high", MinCount: 1, Within: "5m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}

	result := results[0]
	if result.SchemaVersion != 2 {
		t.Fatalf("expected schema version 2, got %d", result.SchemaVersion)
	}
	if len(result.LogID) != 1 {
		t.Fatalf("expected 1 evidence log, got %d", len(result.LogID))
	}
	if result.LogID[0].SourceIndex != "linux-logs-2026.04.10" {
		t.Fatalf("expected source index, got %#v", result.LogID[0])
	}
	if result.LogID[0].ServiceName != "api" {
		t.Fatalf("expected service name api, got %#v", result.LogID[0])
	}
	if result.LogID[0].HostName != "host-1" {
		t.Fatalf("expected host name host-1, got %#v", result.LogID[0])
	}
	if result.LogID[0].HostIP != "172.16.1.10" {
		t.Fatalf("expected first extracted host ip, got %#v", result.LogID[0])
	}
	if len(result.LogID[0].HostIPs) != 2 || result.LogID[0].HostIPs[1] != "10.0.4.72" {
		t.Fatalf("expected all extracted host ips, got %#v", result.LogID[0])
	}
}

func TestCorrelateEmitsPartialResultForIncompleteMinCount(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "mongodb_auth_failed",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Sequence: []models.SequenceStep{
				{SignalKey: "mongodb_auth_failed", MinCount: 3, Within: "5m"},
				{SignalKey: "mongodb_host_unreachable", MinCount: 1, Within: "2m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 partial result, got %d", len(results))
	}

	result := results[0]
	if !approxEqual(result.RuleCompletion, 0.25) {
		t.Fatalf("expected rule completion 0.25, got %.6f", result.RuleCompletion)
	}
	if !approxEqual(result.SequenceMatch, 1.0/6.0) {
		t.Fatalf("expected sequence match %.6f, got %.6f", 1.0/6.0, result.SequenceMatch)
	}
}

func TestCorrelateZeroDedupWindowKeepsSameTimestampEvidence(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()
	commonMetadata := map[string]any{
		"event.organization": "org-1",
		"host.identity":      "10.0.4.72",
		"host.name":          "localhost.localdomain",
	}

	logs := []models.FullLog{
		{
			DocID:     "mongo-1",
			Timestamp: now,
			Signal:    "mongodb_user_not_found",
			LogLevel:  "warning",
			Metadata: mergeMetadata(commonMetadata, map[string]any{
				"service.name": "mongodb",
			}),
		},
		{
			DocID:     "mongo-2",
			Timestamp: now.Add(time.Second),
			Signal:    "mongodb_user_not_found",
			LogLevel:  "warning",
			Metadata: mergeMetadata(commonMetadata, map[string]any{
				"service.name": "mongodb",
			}),
		},
		{
			DocID:     "mongo-3",
			Timestamp: now.Add(2 * time.Second),
			Signal:    "mongodb_user_not_found",
			LogLevel:  "warning",
			Metadata: mergeMetadata(commonMetadata, map[string]any{
				"service.name": "mongodb",
			}),
		},
		{
			DocID:     "nginx-1",
			Timestamp: now.Add(10 * time.Second),
			Signal:    "nginx_access_502_bad_gateway",
			LogLevel:  "critical",
			Metadata: mergeMetadata(commonMetadata, map[string]any{
				"service.name": "nginx",
			}),
		},
		{
			DocID:     "nginx-2",
			Timestamp: now.Add(10 * time.Second),
			Signal:    "nginx_access_502_bad_gateway",
			LogLevel:  "critical",
			Metadata: mergeMetadata(commonMetadata, map[string]any{
				"service.name": "nginx",
			}),
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:             "mongo-to-nginx",
			OrganizationID: "org-1",
			RuleType:       "ordered_signal_sequence",
			Window:         "10m",
			GroupBy:        []string{"event.organization", "host.identity"},
			Sequence: []models.SequenceStep{
				{SignalKey: "mongodb_user_not_found", MinCount: 3, Within: "3m"},
				{SignalKey: "nginx_access_502_bad_gateway", MinCount: 3, Within: "3m"},
			},
			Deduplication: models.Deduplication{
				Key:    []string{"signal_key", "host.name", "service.name"},
				Window: "0s",
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 partial result, got %d", len(results))
	}
	if results[0].Audit == nil || len(results[0].Audit.Steps) != 2 {
		t.Fatalf("expected two audited steps, got %#v", results[0].Audit)
	}

	nginxStep := results[0].Audit.Steps[1]
	if nginxStep.MatchedCount != 2 {
		t.Fatalf("expected both same-timestamp nginx docs to be counted, got %d", nginxStep.MatchedCount)
	}
	if len(nginxStep.MatchedLogIDs) != 2 {
		t.Fatalf("expected both same-timestamp nginx doc ids, got %#v", nginxStep.MatchedLogIDs)
	}
}

func TestCorrelateSortsByPriorityThenCompletion(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "3",
			Timestamp: now.Add(2 * time.Minute),
			Signal:    "s3",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	rules := []models.Rule{
		{
			ID:                 "high-priority-partial",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Priority:           1,
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "missing", MinCount: 1, Within: "2m"},
			},
		},
		{
			ID:                 "low-priority-full",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Priority:           5,
			Sequence: []models.SequenceStep{
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
				{SignalKey: "s3", MinCount: 1, Within: "2m"},
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, rules)
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	if results[0].RuleID != "high-priority-partial" {
		t.Fatalf("expected highest priority result first, got %s", results[0].RuleID)
	}
}

func TestCorrelateRespectsNegativeSignals(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(30 * time.Second),
			Signal:    "recovered",
			LogLevel:  "info",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "3",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Priority:           1,
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
			},
			NotSequence: []models.NegativeStep{
				{SignalKey: "recovered"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results because negative signal cancels the rule, got %d", len(results))
	}
}

func TestCorrelateIgnoresRecoveryAfterSequenceCompletion(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "3",
			Timestamp: now.Add(2 * time.Minute),
			Signal:    "recovered",
			LogLevel:  "info",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
			},
			NotSequence: []models.NegativeStep{
				{SignalKey: "recovered"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected valid match before recovery to survive, got %d results", len(results))
	}
	if !approxEqual(results[0].RuleCompletion, 1) || !approxEqual(results[0].SequenceMatch, 1) {
		t.Fatalf("expected full match, got completion=%v sequence=%v", results[0].RuleCompletion, results[0].SequenceMatch)
	}
}

func TestCorrelateSuppressesWeakerContainedOverlap(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "full-match",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Priority:           5,
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
			},
		},
		{
			ID:                 "weaker-overlap",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization"},
			Priority:           1,
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
				{SignalKey: "missing", MinCount: 1, Within: "2m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected weaker overlapping result to be suppressed, got %d results", len(results))
	}
	if results[0].RuleID != "full-match" {
		t.Fatalf("expected strongest explanation to survive, got %s", results[0].RuleID)
	}
}

func TestCorrelateEmitsFullResultAsOne(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event.organization": "org-1",
				"host.name":          "host-1",
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event.organization": "org-1",
				"host.name":          "host-1",
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:                 "rule-1",
			OrganizationID:     "org-1",
			RuleType:           "ordered_signal_sequence",
			Window:             "10m",
			MaxGapBetweenSteps: "2m",
			GroupBy:            []string{"event.organization", "host.name"},
			Priority:           2,
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}

	result := results[0]
	if !approxEqual(result.RuleCompletion, 1) {
		t.Fatalf("expected rule completion 1, got %.6f", result.RuleCompletion)
	}
	if !approxEqual(result.SequenceMatch, 1) {
		t.Fatalf("expected sequence match 1, got %.6f", result.SequenceMatch)
	}
	if len(result.LogID) != 2 {
		t.Fatalf("expected 2 compact output logs, got %d", len(result.LogID))
	}
}

func TestCorrelateFiltersLogsByRequiredMetadata(t *testing.T) {
	engine := newTestEngine(t)
	now := time.Now().UTC()

	logs := []models.FullLog{
		{
			DocID:     "1",
			Timestamp: now,
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event": map[string]any{
					"organization": "org-1",
					"module":       "mongodb",
				},
			},
		},
		{
			DocID:     "2",
			Timestamp: now.Add(time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event": map[string]any{
					"organization": "org-1",
					"module":       "mongodb",
				},
			},
		},
		{
			DocID:     "3",
			Timestamp: now.Add(2 * time.Minute),
			Signal:    "s1",
			LogLevel:  "warning",
			Metadata: map[string]any{
				"event": map[string]any{
					"organization": "org-1",
					"module":       "nginx",
				},
			},
		},
		{
			DocID:     "4",
			Timestamp: now.Add(3 * time.Minute),
			Signal:    "s2",
			LogLevel:  "error",
			Metadata: map[string]any{
				"event": map[string]any{
					"organization": "org-1",
					"module":       "nginx",
				},
			},
		},
	}

	results, err := engine.Correlate(context.Background(), "org-1", logs, []models.Rule{
		{
			ID:             "mongodb-only",
			OrganizationID: "org-1",
			RuleType:       "ordered_signal_sequence",
			Window:         "10m",
			GroupBy:        []string{"event.organization"},
			RequiredMetadata: map[string]string{
				"event.module": "mongodb",
			},
			Sequence: []models.SequenceStep{
				{SignalKey: "s1", MinCount: 1, Within: "2m"},
				{SignalKey: "s2", MinCount: 1, Within: "2m"},
			},
		},
	})
	if err != nil {
		t.Fatalf("correlate returned error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 filtered result, got %d", len(results))
	}
	if len(results[0].LogID) != 2 {
		t.Fatalf("expected 2 matched logs after metadata filter, got %d", len(results[0].LogID))
	}
	if results[0].LogID[0].ID != "1" || results[0].LogID[1].ID != "2" {
		t.Fatalf("expected mongodb logs only, got %#v", results[0].LogID)
	}
	if results[0].Audit == nil {
		t.Fatalf("expected audit details to be populated")
	}
	if results[0].Audit.RequiredMetadata["event.module"] != "mongodb" {
		t.Fatalf("expected required metadata audit, got %#v", results[0].Audit.RequiredMetadata)
	}
	if len(results[0].Audit.Steps) != 2 || results[0].Audit.Steps[0].MatchedCount != 1 {
		t.Fatalf("unexpected audit step payload: %#v", results[0].Audit.Steps)
	}
}

func TestCalculateCompiledMatchStatsUsesOrderedPrefixForSequenceMatch(t *testing.T) {
	rule := compiledRule{
		steps: []compiledStep{
			{signalKey: "s1", minCount: 2},
			{signalKey: "s2", minCount: 1},
			{signalKey: "s3", minCount: 1},
		},
	}
	match := sequenceMatch{
		logs:        []models.FullLog{{DocID: "1"}, {DocID: "2"}},
		stepMatches: []int{1, 1, 0},
	}

	ruleCompletion, sequenceMatch := calculateCompiledMatchStats(match, rule)
	if !approxEqual(ruleCompletion, 0.5) {
		t.Fatalf("expected rule completion 0.5, got %.6f", ruleCompletion)
	}
	if !approxEqual(sequenceMatch, 1.0/6.0) {
		t.Fatalf("expected ordered-prefix sequence match %.6f, got %.6f", 1.0/6.0, sequenceMatch)
	}
}
