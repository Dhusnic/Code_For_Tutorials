package mongoresults

import (
	"testing"
	"time"

	"log_rca_engine/internal/models"

	"go.mongodb.org/mongo-driver/bson"
)

func TestLatestRecordsPipelineMatchesIncidentIDsAndLatestFirst(t *testing.T) {
	pipeline := latestRecordsPipeline([]string{"incident-2", "incident-1"})
	if len(pipeline) != 4 {
		t.Fatalf("expected 4 pipeline stages, got %d", len(pipeline))
	}

	match := pipeline[0].Map()
	matchBody, ok := match["$match"].(bson.D)
	if !ok {
		t.Fatalf("expected $match body to be bson.D, got %#v", match["$match"])
	}
	matchMap := matchBody.Map()
	if matchMap["managed_by"] != runtimeManagedBy {
		t.Fatalf("expected managed_by filter %q, got %#v", runtimeManagedBy, matchMap["managed_by"])
	}
	if matchMap["document_kind"] != resultDocumentKind {
		t.Fatalf("expected document_kind filter %q, got %#v", resultDocumentKind, matchMap["document_kind"])
	}
	incidentFilter, ok := matchMap["incident_id"].(bson.D)
	if !ok {
		t.Fatalf("expected incident_id filter to be bson.D, got %#v", matchMap["incident_id"])
	}
	inValues, ok := incidentFilter.Map()["$in"].([]string)
	if !ok {
		t.Fatalf("expected $in incident values to be []string, got %#v", incidentFilter.Map()["$in"])
	}
	if len(inValues) != 2 || inValues[0] != "incident-2" || inValues[1] != "incident-1" {
		t.Fatalf("unexpected incident filter values: %#v", inValues)
	}

	sortStage := pipeline[1].Map()
	sortBody, ok := sortStage["$sort"].(bson.D)
	if !ok {
		t.Fatalf("expected $sort body to be bson.D, got %#v", sortStage["$sort"])
	}
	sortMap := sortBody.Map()
	if sortMap["incident_id"] != 1 || sortMap["updated_at"] != -1 || sortMap["rca_generated_at"] != -1 {
		t.Fatalf("unexpected sort stage: %#v", sortMap)
	}
}

func TestRecordFromDocumentDecodesRCARecord(t *testing.T) {
	now := time.Date(2026, 5, 13, 10, 15, 0, 0, time.UTC)
	record, err := recordFromDocument(bson.M{
		"incident_id":                     "incident-42",
		"organization_id":                 "org-9",
		"rule_id":                         "rule-7",
		"status":                          "open",
		"classification":                  "probable_cause",
		"result_signature":                "sig-42",
		"last_processed_result_signature": "sig-41",
		"first_matched_at":                now.Add(-2 * time.Minute),
		"first_correlated_at":             now.Add(-time.Minute),
		"first_rca_generated_at":          now.Add(-30 * time.Second),
		"trigger_matched_doc_ids":         []any{"doc-1"},
		"updated_at":                      now,
		"matched_logs": []any{
			map[string]any{"id": "doc-1", "service_name": "api"},
		},
		"trigger_matched_logs": []any{
			map[string]any{"id": "doc-1", "service_name": "api"},
		},
		"managed_by": runtimeManagedBy,
	})
	if err != nil {
		t.Fatalf("recordFromDocument returned error: %v", err)
	}

	if record.IncidentID != "incident-42" || record.OrganizationID != "org-9" || record.RuleID != "rule-7" {
		t.Fatalf("unexpected record identity: %#v", record)
	}
	if record.ResultSignature != "sig-42" || record.LastProcessedResultSignature != "sig-41" {
		t.Fatalf("unexpected signatures: %#v", record)
	}
	if record.UpdatedAt != now {
		t.Fatalf("expected updated_at %v, got %v", now, record.UpdatedAt)
	}
	if len(record.MatchedLogs) != 1 || record.MatchedLogs[0].ID != "doc-1" {
		t.Fatalf("unexpected matched logs: %#v", record.MatchedLogs)
	}
	if len(record.TriggerMatchedLogs) != 1 || record.TriggerMatchedLogs[0].ID != "doc-1" {
		t.Fatalf("unexpected trigger matched logs: %#v", record.TriggerMatchedLogs)
	}
	if len(record.TriggerMatchedDocIDs) != 1 || record.TriggerMatchedDocIDs[0] != "doc-1" {
		t.Fatalf("unexpected trigger matched doc ids: %#v", record.TriggerMatchedDocIDs)
	}
	if record.FirstMatchedAt.IsZero() || record.FirstCorrelatedAt.IsZero() || record.FirstRCAGeneratedAt.IsZero() {
		t.Fatalf("expected first-cycle timestamps to decode, got %#v", record)
	}
}

func TestTrimUniqueStringsSortsAndDropsEmptyValues(t *testing.T) {
	values := trimUniqueStrings([]string{" incident-2 ", "", "incident-1", "incident-2", "incident-3"})
	expected := []string{"incident-1", "incident-2", "incident-3"}
	if len(values) != len(expected) {
		t.Fatalf("expected %d values, got %d (%#v)", len(expected), len(values), values)
	}
	for idx := range expected {
		if values[idx] != expected[idx] {
			t.Fatalf("expected value %q at position %d, got %#v", expected[idx], idx, values)
		}
	}
}

func TestUniqueLatestKeepsNewestRecordPerDocumentID(t *testing.T) {
	records := UniqueLatest([]models.RCARecord{
		{IncidentID: "incident-1", ResultSignature: "sig-1", ConfidenceScore: 1},
		{IncidentID: "incident-1", ResultSignature: "sig-1", ConfidenceScore: 2},
		{IncidentID: "incident-1", ResultSignature: "sig-2", ConfidenceScore: 3},
	})
	if len(records) != 2 {
		t.Fatalf("expected 2 unique records, got %d", len(records))
	}
	if records[0].ConfidenceScore != 2 || records[1].ConfidenceScore != 3 {
		t.Fatalf("unexpected unique-latest result: %#v", records)
	}
}
