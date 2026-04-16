package rules

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFileLoaderSkipsDisabledRules(t *testing.T) {
	tempDir := t.TempDir()
	rulesPath := filepath.Join(tempDir, "rules.json")

	payload := `[
  {
    "id": "enabled-explicit",
    "is_enabled": true,
    "organization_id": "org-1",
    "rule_type": "ordered_signal_sequence",
    "window": "10m",
    "max_gap_between_steps": "2m",
    "group_by": ["event.organization"],
    "priority": 1,
    "sequence": [
      { "signal_key": "alpha", "min_count": 1, "within": "2m" }
    ],
    "not_sequence": [],
    "deduplication": { "key": ["signal_key"], "window": "1m" }
  },
  {
    "id": "disabled-rule",
    "is_enabled": false,
    "organization_id": "org-1",
    "rule_type": "ordered_signal_sequence",
    "window": "10m",
    "max_gap_between_steps": "2m",
    "group_by": ["event.organization"],
    "priority": 2,
    "sequence": [
      { "signal_key": "beta", "min_count": 1, "within": "2m" }
    ],
    "not_sequence": [],
    "deduplication": { "key": ["signal_key"], "window": "1m" }
  },
  {
    "id": "enabled-by-default",
    "organization_id": "org-1",
    "rule_type": "ordered_signal_sequence",
    "window": "10m",
    "max_gap_between_steps": "2m",
    "group_by": ["event.organization"],
    "priority": 3,
    "sequence": [
      { "signal_key": "gamma", "min_count": 1, "within": "2m" }
    ],
    "not_sequence": [],
    "deduplication": { "key": ["signal_key"], "window": "1m" }
  }
]`

	if err := os.WriteFile(rulesPath, []byte(payload), 0o600); err != nil {
		t.Fatalf("write rules file: %v", err)
	}

	loader, err := NewFileLoader(rulesPath, 0, nil)
	if err != nil {
		t.Fatalf("create loader: %v", err)
	}
	defer func() {
		if err := loader.Close(); err != nil {
			t.Fatalf("close loader: %v", err)
		}
	}()

	rules := loader.GetRules()
	if len(rules) != 2 {
		t.Fatalf("expected 2 enabled rules, got %d", len(rules))
	}
	if rules[0].ID != "enabled-explicit" {
		t.Fatalf("expected first enabled rule, got %q", rules[0].ID)
	}
	if rules[1].ID != "enabled-by-default" {
		t.Fatalf("expected default-enabled rule, got %q", rules[1].ID)
	}
	if !rules[0].IsEnabled || !rules[1].IsEnabled {
		t.Fatalf("expected returned rules to be enabled, got %#v", rules)
	}
}
