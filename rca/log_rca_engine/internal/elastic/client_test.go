package elastic

import (
	"encoding/json"
	"testing"
	"time"

	"log_rca_engine/internal/models"
)

func TestBuildCorrelationEventSearchBodyUsesSafeTiebreakers(t *testing.T) {
	replayStart := time.Date(2026, time.April, 10, 11, 0, 0, 0, time.UTC)
	body := buildCorrelationEventSearchBody(50, &replayStart, []any{
		"2026-04-10T11:19:26.6650837Z",
		"2026-04-10T11:19:21.0000000Z",
		"inc-123",
		"sig-123",
	})

	if got := body["size"]; got != 50 {
		t.Fatalf("expected size 50, got %#v", got)
	}
	query, ok := body["query"].(map[string]any)
	if !ok {
		t.Fatalf("expected query object, got %#v", body["query"])
	}
	boolQuery, ok := query["bool"].(map[string]any)
	if !ok {
		t.Fatalf("expected bool replay query, got %#v", query)
	}
	filters, ok := boolQuery["filter"].([]any)
	if !ok || len(filters) != 1 {
		t.Fatalf("expected one replay filter, got %#v", boolQuery["filter"])
	}

	sorts, ok := body["sort"].([]map[string]any)
	if !ok {
		t.Fatalf("expected typed sort definition, got %#v", body["sort"])
	}
	if len(sorts) != correlationEventSortFieldCount {
		t.Fatalf("expected %d sort fields, got %d", correlationEventSortFieldCount, len(sorts))
	}
	if _, ok := sorts[0]["last_seen"]; !ok {
		t.Fatalf("expected first sort field to be last_seen, got %#v", sorts[0])
	}
	if _, ok := sorts[1]["matched_at"]; !ok {
		t.Fatalf("expected second sort field to be matched_at, got %#v", sorts[1])
	}
	if _, ok := sorts[2]["incident_id.keyword"]; !ok {
		t.Fatalf("expected third sort field to be incident_id.keyword, got %#v", sorts[2])
	}
	if _, ok := sorts[3]["result_signature.keyword"]; !ok {
		t.Fatalf("expected fourth sort field to be result_signature.keyword, got %#v", sorts[3])
	}
	if _, ok := sorts[0]["_id"]; ok {
		t.Fatal("unexpected _id sort field in correlation query")
	}

	searchAfter, ok := body["search_after"].([]any)
	if !ok {
		t.Fatalf("expected search_after slice, got %#v", body["search_after"])
	}
	if len(searchAfter) != correlationEventSortFieldCount {
		t.Fatalf("expected %d search_after values, got %d", correlationEventSortFieldCount, len(searchAfter))
	}
}

func TestBuildCorrelationEventSearchBodyWithoutReplayWindowUsesMatchAll(t *testing.T) {
	body := buildCorrelationEventSearchBody(10, nil, nil)

	query, ok := body["query"].(map[string]any)
	if !ok {
		t.Fatalf("expected query object, got %#v", body["query"])
	}
	if _, ok := query["match_all"]; !ok {
		t.Fatalf("expected match_all query, got %#v", query)
	}
	if _, ok := body["search_after"]; ok {
		t.Fatalf("did not expect search_after, got %#v", body["search_after"])
	}
}

func TestNormalizeCorrelationSearchAfterRejectsLegacyCheckpoint(t *testing.T) {
	legacy := normalizeCorrelationSearchAfter([]any{"2026-04-10T11:19:26.6650837Z", "old-id"})
	if legacy != nil {
		t.Fatalf("expected legacy checkpoint values to be ignored, got %#v", legacy)
	}

	current := normalizeCorrelationSearchAfter([]any{
		"2026-04-10T11:19:26.6650837Z",
		"2026-04-10T11:19:21.0000000Z",
		"inc-123",
		"sig-123",
	})
	if len(current) != correlationEventSortFieldCount {
		t.Fatalf("expected %d values, got %d", correlationEventSortFieldCount, len(current))
	}
}

func TestReplayStartUsesCheckpointUpdatedAt(t *testing.T) {
	updatedAt := time.Date(2026, time.April, 10, 12, 7, 54, 0, time.UTC)
	client := &Client{replayWindow: time.Hour}

	start := client.replayStart(models.ReaderCheckpoint{UpdatedAt: updatedAt})
	if start == nil {
		t.Fatal("expected replay start")
	}
	expected := updatedAt.Add(-time.Hour)
	if !start.Equal(expected) {
		t.Fatalf("expected replay start %s, got %s", expected, *start)
	}
}

func TestParseRelatedLogExtractsHostIPs(t *testing.T) {
	source, err := json.Marshal(map[string]any{
		"event": map[string]any{
			"organization": "org-1",
			"module":       "mongodb",
		},
		"host": map[string]any{
			"name": "db-01",
			"ip":   "172.16.1.10,10.0.4.72",
		},
		"message": "@timestamp test",
	})
	if err != nil {
		t.Fatalf("marshal source: %v", err)
	}

	entry, err := parseRelatedLog("linux_logs", searchHit{
		ID:     "doc-1",
		Source: source,
	})
	if err != nil {
		t.Fatalf("parseRelatedLog returned error: %v", err)
	}
	if entry.HostIP != "172.16.1.10" {
		t.Fatalf("expected first host IP, got %#v", entry)
	}
	if len(entry.HostIPs) != 2 || entry.HostIPs[1] != "10.0.4.72" {
		t.Fatalf("expected both host IPs, got %#v", entry)
	}
}

func TestRankRelatedLogsPrioritizesSameIPAndContradictionSignals(t *testing.T) {
	event := models.CorrelationEvent{
		OrganizationID: "org-1",
		LogID: []models.EvidenceLog{
			{
				ID:          "match-1",
				Signal:      "mongodb_host_unreachable",
				ServiceName: "mongodb",
				HostName:    "db-01",
				HostIP:      "10.0.4.72",
			},
		},
		Audit: &models.MatchAudit{
			MatchedSignals:  []string{"mongodb_host_unreachable"},
			NegativeSignals: []string{"mongodb_primary_recovered"},
		},
	}

	logs := []models.RelatedLog{
		{
			DocID:       "same-ip-warning",
			ServiceName: "mongodb",
			HostName:    "db-01",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_auth_failed",
			Severity:    "warning",
		},
		{
			DocID:       "contradiction",
			ServiceName: "mongodb",
			HostName:    "db-01",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_primary_recovered",
			Severity:    "info",
			Message:     "primary recovered and healthy",
		},
		{
			DocID:       "different-host-critical",
			ServiceName: "redis",
			HostName:    "cache-01",
			HostIP:      "10.0.9.20",
			Signal:      "redis_latency_high",
			Severity:    "critical",
		},
	}

	ranked := rankRelatedLogs(event, logs)
	if len(ranked) != 3 {
		t.Fatalf("expected 3 ranked logs, got %d", len(ranked))
	}
	if ranked[0].DocID != "contradiction" {
		t.Fatalf("expected contradiction signal to rank first, got %s", ranked[0].DocID)
	}
	if ranked[1].DocID != "same-ip-warning" {
		t.Fatalf("expected same-ip correlated log to rank second, got %s", ranked[1].DocID)
	}
}
