package scoring

import (
	"os"
	"path/filepath"
	"testing"

	"log_rca_engine/internal/models"
)

func TestLoadSignalSeverityCatalogFromYamlAndJSON(t *testing.T) {
	dir := t.TempDir()
	yamlPath := filepath.Join(dir, "mongodb.yml")
	jsonPath := filepath.Join(dir, "correlation.json")

	if err := os.WriteFile(yamlPath, []byte(`
service: mongodb
rules:
  - signal_key: mongodb_user_not_found
    level: warning
  - signal_key: mongodb_host_unreachable
    level: critical
`), 0o600); err != nil {
		t.Fatalf("write yaml catalog: %v", err)
	}
	if err := os.WriteFile(jsonPath, []byte(`{
  "rules": [
    {
      "signal_key": "rca_mongodb_auth_application_outage",
      "level": "critical",
      "sequence": [
        { "signal_key": "mongodb_auth_failed" }
      ]
    }
  ]
}`), 0o600); err != nil {
		t.Fatalf("write json catalog: %v", err)
	}

	catalog, err := LoadSignalSeverityCatalog([]string{filepath.Join(dir, "*.yml"), filepath.Join(dir, "*.json")})
	if err != nil {
		t.Fatalf("LoadSignalSeverityCatalog returned error: %v", err)
	}

	if got := catalog["mongodb_user_not_found"]; got != severityWeight("warning") {
		t.Fatalf("expected warning severity, got %v", got)
	}
	if got := catalog["mongodb_host_unreachable"]; got != severityWeight("critical") {
		t.Fatalf("expected critical severity, got %v", got)
	}
	if got := catalog["rca_mongodb_auth_application_outage"]; got != severityWeight("critical") {
		t.Fatalf("expected JSON critical severity, got %v", got)
	}
	if _, ok := catalog["mongodb_auth_failed"]; ok {
		t.Fatal("sequence entries without their own level should not become catalog entries")
	}
}

func TestComputeExpectedRuleSeverityUsesAverageCatalogSeverity(t *testing.T) {
	catalog := SignalSeverityCatalog{
		"warning_signal": severityWeight("warning"),
		"error_signal":   severityWeight("error"),
	}
	rule := &models.Rule{
		Sequence: []models.SequenceStep{
			{SignalKey: "warning_signal"},
			{SignalKeys: []string{"error_signal"}},
		},
	}

	got := computeExpectedRuleSeverity(rule, catalog)
	want := (severityWeight("warning") + severityWeight("error")) / 2
	if got != want {
		t.Fatalf("expected average severity %v, got %v", want, got)
	}
}
