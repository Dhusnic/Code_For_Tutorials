package writer

import "testing"

func TestBulkActionFactorySetsRuleLevelWhenMissing(t *testing.T) {
	factory := BulkActionFactory{}
	action := factory.Build(
		"linux-logs",
		"linux-logs-rca",
		"abc",
		map[string]any{"message": "sample"},
		map[string]any{"signal": "ssh_fail", "level": "warning"},
		false,
	)

	doc := action["doc"].(map[string]any)
	logValue := doc["log"].(map[string]any)
	if logValue["level"] != "warning" {
		t.Fatalf("expected warning, got %v", logValue["level"])
	}
	if doc["source_rca_id"] != "abc" {
		t.Fatalf("expected source_rca_id abc, got %v", doc["source_rca_id"])
	}
	if _, exists := doc["source_id"]; exists {
		t.Fatalf("expected legacy source_id to be absent, got %v", doc["source_id"])
	}
}

func TestBulkActionFactoryKeepsExistingValidShortForm(t *testing.T) {
	factory := BulkActionFactory{}
	action := factory.Build(
		"linux-logs",
		"linux-logs-rca",
		"abc",
		map[string]any{"message": "sample", "log": map[string]any{"level": "ERR"}},
		map[string]any{"signal": "ssh_fail", "level": "warning"},
		false,
	)

	doc := action["doc"].(map[string]any)
	logValue := doc["log"].(map[string]any)
	if logValue["level"] != "error" {
		t.Fatalf("expected error, got %v", logValue["level"])
	}
}

func TestBulkActionFactoryUsesSourceIDWhenRequested(t *testing.T) {
	factory := BulkActionFactory{}
	action := factory.Build(
		"linux-logs",
		"linux-logs",
		"abc",
		map[string]any{"message": "sample"},
		map[string]any{"signal": "ssh_fail", "level": "warning"},
		true,
	)

	if action["_id"] != "abc" {
		t.Fatalf("expected source id, got %v", action["_id"])
	}
}

func TestBulkActionFactorySetsRetryOnConflict(t *testing.T) {
	factory := BulkActionFactory{}
	action := factory.Build(
		"linux-logs",
		"linux-logs",
		"abc",
		map[string]any{"message": "sample"},
		map[string]any{"signal": "ssh_fail", "level": "warning"},
		true,
	)

	if action["retry_on_conflict"] != defaultRetryOnConflict {
		t.Fatalf("expected retry_on_conflict %d, got %v", defaultRetryOnConflict, action["retry_on_conflict"])
	}
}

func TestBuildMatchedSourceUpdateUsesResolvedSourceDocumentID(t *testing.T) {
	factory := BulkActionFactory{}
	action := factory.BuildMatchedSourceUpdate(
		"linux-2026.05.18",
		"linux-2026.05.18",
		"real-es-doc-id-123",
		map[string]any{
			"source_rca_id": "rca-123",
			"message":       "sample",
		},
		map[string]any{
			"signal":     "mongodb_host_unreachable",
			"level":      "critical",
			"matched_at": "2026-05-18T05:10:46Z",
		},
	)

	if action["_id"] != "real-es-doc-id-123" {
		t.Fatalf("expected matched source update to use resolved Elasticsearch _id, got %v", action["_id"])
	}
	if action["_index"] != "linux-2026.05.18" {
		t.Fatalf("expected matched source update to target source index, got %v", action["_index"])
	}
	if action["doc_as_upsert"] != false {
		t.Fatalf("expected matched source update to be update-only, got %v", action["doc_as_upsert"])
	}
}
