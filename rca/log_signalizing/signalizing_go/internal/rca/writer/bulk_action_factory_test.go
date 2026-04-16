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
