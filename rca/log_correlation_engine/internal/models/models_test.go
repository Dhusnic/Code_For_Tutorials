package models

import (
	"encoding/json"
	"testing"
	"time"
)

func TestSignalLogJSONRoundTrip(t *testing.T) {
	input := SignalLog{
		Signal:    "disk_failure",
		LogLevel:  "critical",
		DocID:     "doc-1",
		TimeStamp: time.Date(2026, 4, 8, 12, 30, 0, 123000000, time.UTC),
	}

	payload, err := json.Marshal(input)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var decoded SignalLog
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if decoded.DocID != input.DocID {
		t.Fatalf("expected doc id %s, got %s", input.DocID, decoded.DocID)
	}
	if !decoded.TimeStamp.Equal(input.TimeStamp) {
		t.Fatalf("expected timestamp %s, got %s", input.TimeStamp, decoded.TimeStamp)
	}
}

func TestCorrelationResultEnsureDocumentIDIsStable(t *testing.T) {
	first := &CorrelationResult{
		OrganizationID: "org-1",
		RuleID:         "rule-1",
		LogID: []ResultLog{
			{ID: "doc-2", Severity: "error"},
			{ID: "doc-1", Severity: "warning"},
		},
	}
	second := &CorrelationResult{
		OrganizationID: "org-1",
		RuleID:         "rule-1",
		LogID: []ResultLog{
			{ID: "doc-1", Severity: "warning"},
			{ID: "doc-2", Severity: "error"},
		},
	}

	if err := first.EnsureDocumentID(); err != nil {
		t.Fatalf("first EnsureDocumentID failed: %v", err)
	}
	if err := second.EnsureDocumentID(); err != nil {
		t.Fatalf("second EnsureDocumentID failed: %v", err)
	}

	if first.DocumentID == "" {
		t.Fatal("expected non-empty document id")
	}
	if first.DocumentID != second.DocumentID {
		t.Fatalf("expected stable document id, got %q and %q", first.DocumentID, second.DocumentID)
	}
}

func TestCorrelationResultUsesIncidentIDAsDocumentID(t *testing.T) {
	result := &CorrelationResult{
		IncidentID: "incident-123",
	}

	if err := result.EnsureDocumentID(); err != nil {
		t.Fatalf("EnsureDocumentID failed: %v", err)
	}
	if result.DocumentID != "incident-123" {
		t.Fatalf("expected document id incident-123, got %q", result.DocumentID)
	}
}

func TestBuildIncidentIDIsStable(t *testing.T) {
	first, err := BuildIncidentID("org-1", "rule-1", map[string]string{
		"host.name":    "host-1",
		"service.name": "api",
	})
	if err != nil {
		t.Fatalf("first BuildIncidentID failed: %v", err)
	}
	second, err := BuildIncidentID("org-1", "rule-1", map[string]string{
		"service.name": "api",
		"host.name":    "host-1",
	})
	if err != nil {
		t.Fatalf("second BuildIncidentID failed: %v", err)
	}

	if first == "" {
		t.Fatal("expected non-empty incident id")
	}
	if first != second {
		t.Fatalf("expected stable incident ids, got %q and %q", first, second)
	}
}

func TestBuildIncidentEpisodeIDIsStableForSameInputs(t *testing.T) {
	startedAt := time.Date(2026, 4, 16, 11, 0, 0, 0, time.UTC)
	first, err := BuildIncidentEpisodeID("incident-key-1", startedAt)
	if err != nil {
		t.Fatalf("first BuildIncidentEpisodeID failed: %v", err)
	}
	second, err := BuildIncidentEpisodeID("incident-key-1", startedAt)
	if err != nil {
		t.Fatalf("second BuildIncidentEpisodeID failed: %v", err)
	}

	if first == "" {
		t.Fatal("expected non-empty incident episode id")
	}
	if first != second {
		t.Fatalf("expected stable incident episode ids, got %q and %q", first, second)
	}
}

func TestBuildIncidentEpisodeIDChangesAcrossEpisodeStartTimes(t *testing.T) {
	incidentKey := "incident-key-1"
	first, err := BuildIncidentEpisodeID(incidentKey, time.Date(2026, 4, 16, 11, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("first BuildIncidentEpisodeID failed: %v", err)
	}
	second, err := BuildIncidentEpisodeID(incidentKey, time.Date(2026, 4, 16, 11, 31, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("second BuildIncidentEpisodeID failed: %v", err)
	}
	if first == second {
		t.Fatalf("expected different episode ids for different start times, got identical value %q", first)
	}
}

func TestBuildCorrelationEventDocumentIDIsStable(t *testing.T) {
	first, err := BuildCorrelationEventDocumentID("org-1", "incident-1", "updated", "signature-1")
	if err != nil {
		t.Fatalf("first BuildCorrelationEventDocumentID failed: %v", err)
	}
	second, err := BuildCorrelationEventDocumentID("org-1", "incident-1", "updated", "signature-1")
	if err != nil {
		t.Fatalf("second BuildCorrelationEventDocumentID failed: %v", err)
	}

	if first == "" {
		t.Fatal("expected non-empty event document id")
	}
	if first != second {
		t.Fatalf("expected stable event document ids, got %q and %q", first, second)
	}
}

func TestCorrelationResultIncludesSchemaV2FieldsInJSON(t *testing.T) {
	firstSeen := time.Date(2026, 4, 9, 10, 0, 0, 0, time.UTC)
	lastSeen := firstSeen.Add(5 * time.Minute)
	matchedAt := firstSeen.Add(2 * time.Minute)

	result := CorrelationResult{
		SchemaVersion:   2,
		IncidentID:      "incident-1",
		Status:          "open",
		FirstSeen:       &firstSeen,
		LastSeen:        &lastSeen,
		MatchedAt:       matchedAt,
		OrganizationID:  "org-1",
		ResultSignature: "sig-1",
		GroupByValues: map[string]string{
			"service.name": "api",
		},
		RuleID:         "rule-1",
		RuleCompletion: 0.5,
		SequenceMatch:  0.25,
		LogID: []ResultLog{
			{
				ID:          "doc-1",
				Severity:    "warning",
				SourceIndex: "linux-logs",
				Signal:      "nginx_access_5xx_any",
				Timestamp:   matchedAt,
				ServiceName: "api",
				HostName:    "host-1",
				HostIP:      "10.0.4.72",
				HostIPs:     []string{"10.0.4.72", "172.16.1.10"},
			},
		},
	}

	payload, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if decoded["schema_version"] != float64(2) {
		t.Fatalf("expected schema_version 2, got %v", decoded["schema_version"])
	}
	if decoded["status"] != "open" {
		t.Fatalf("expected status to be present, got %v", decoded["status"])
	}
	if decoded["organization_id"] != "org-1" {
		t.Fatalf("expected organization_id org-1, got %v", decoded["organization_id"])
	}
	if decoded["incident_id"] != "incident-1" {
		t.Fatalf("expected incident_id to remain present, got %v", decoded["incident_id"])
	}
	if decoded["matched_at"] == nil {
		t.Fatalf("expected matched_at to be present")
	}
	logs, ok := decoded["log_id"].([]any)
	if !ok || len(logs) != 1 {
		t.Fatalf("expected one log_id entry, got %#v", decoded["log_id"])
	}
	logEntry, ok := logs[0].(map[string]any)
	if !ok {
		t.Fatalf("expected log entry map, got %#v", logs[0])
	}
	if logEntry["source_index"] != "linux-logs" {
		t.Fatalf("expected source_index linux-logs, got %v", logEntry["source_index"])
	}
	if logEntry["service_name"] != "api" {
		t.Fatalf("expected service_name api, got %v", logEntry["service_name"])
	}
	if logEntry["host_ip"] != "10.0.4.72" {
		t.Fatalf("expected host_ip 10.0.4.72, got %v", logEntry["host_ip"])
	}
	hostIPs, ok := logEntry["host_ips"].([]any)
	if !ok || len(hostIPs) != 2 {
		t.Fatalf("expected host_ips array, got %#v", logEntry["host_ips"])
	}
}

func TestNormalizeCorrelationResultsSuppressesContainedWeakerMatches(t *testing.T) {
	results := []CorrelationResult{
		{
			OrganizationID: "org-1",
			RuleID:         "rule-weak",
			Priority:       2,
			RuleCompletion: 0.5,
			SequenceMatch:  0.5,
			LogID: []ResultLog{
				{ID: "doc-1", Severity: "warning"},
			},
		},
		{
			OrganizationID: "org-1",
			RuleID:         "rule-strong",
			Priority:       1,
			RuleCompletion: 1,
			SequenceMatch:  1,
			LogID: []ResultLog{
				{ID: "doc-1", Severity: "warning"},
				{ID: "doc-2", Severity: "error"},
			},
		},
	}

	normalized, suppressed := NormalizeCorrelationResults(results)
	if suppressed != 1 {
		t.Fatalf("expected 1 suppressed result, got %d", suppressed)
	}
	if len(normalized) != 1 {
		t.Fatalf("expected 1 normalized result, got %d", len(normalized))
	}
	if normalized[0].RuleID != "rule-strong" {
		t.Fatalf("expected strongest result to remain, got %s", normalized[0].RuleID)
	}
}
