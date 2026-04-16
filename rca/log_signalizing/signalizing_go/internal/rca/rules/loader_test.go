package rules

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func writeRulesFile(t *testing.T, path string, rulesCount int) {
	t.Helper()

	content := `
service: nginx
rules:
  - id: RULE_A
    signal_key: nginx_timeout
    level: critical
    condition:
      field: message
      op: contains
      value: timeout
`
	if rulesCount == 2 {
		content += `
  - id: RULE_B
    signal_key: nginx_5xx
    level: warning
    condition:
      field: http.response.status_code
      op: gte
      value: 500
`
	}

	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write rules file: %v", err)
	}
}

func TestRuleLoaderUsesCacheWhenFileUnchanged(t *testing.T) {
	tempDir := t.TempDir()
	rulesFile := filepath.Join(tempDir, "nginx.yml")
	writeRulesFile(t, rulesFile, 1)

	loader := NewRuleLoader(tempDir)
	first, err := loader.Load("nginx", "nginx.yml")
	if err != nil {
		t.Fatalf("first load: %v", err)
	}
	second, err := loader.Load("nginx", "nginx.yml")
	if err != nil {
		t.Fatalf("second load: %v", err)
	}

	if first != second {
		t.Fatal("expected cached ruleset pointer reuse")
	}
	if len(second.Rules) != 1 {
		t.Fatalf("expected 1 rule, got %d", len(second.Rules))
	}
}

func TestRuleLoaderReloadsWhenFileChanges(t *testing.T) {
	tempDir := t.TempDir()
	rulesFile := filepath.Join(tempDir, "nginx.yml")
	writeRulesFile(t, rulesFile, 1)

	loader := NewRuleLoader(tempDir)
	first, err := loader.Load("nginx", "nginx.yml")
	if err != nil {
		t.Fatalf("first load: %v", err)
	}

	time.Sleep(20 * time.Millisecond)
	writeRulesFile(t, rulesFile, 2)

	second, err := loader.Load("nginx", "nginx.yml")
	if err != nil {
		t.Fatalf("second load: %v", err)
	}

	if first == second {
		t.Fatal("expected cache invalidation after file change")
	}
	if len(second.Rules) != 2 {
		t.Fatalf("expected 2 rules, got %d", len(second.Rules))
	}
}

func TestRuleLoaderLoadsImportedRuleFiles(t *testing.T) {
	tempDir := t.TempDir()

	basePath := filepath.Join(tempDir, "network.yml")
	vendorPath := filepath.Join(tempDir, "vendor.yml")

	baseContent := `
service: network
imports:
  - vendor.yml
rules:
  - id: BASE_RULE
    signal_key: network_base_rule
    level: warning
    condition:
      field: message
      op: contains
      value: base
`
	vendorContent := `
service: network
rules:
  - id: VENDOR_RULE
    signal_key: network_vendor_rule
    level: critical
    condition:
      field: message
      op: contains
      value: vendor
`

	if err := os.WriteFile(basePath, []byte(baseContent), 0o644); err != nil {
		t.Fatalf("write base file: %v", err)
	}
	if err := os.WriteFile(vendorPath, []byte(vendorContent), 0o644); err != nil {
		t.Fatalf("write vendor file: %v", err)
	}

	loader := NewRuleLoader(tempDir)
	loaded, err := loader.Load("network", "network.yml")
	if err != nil {
		t.Fatalf("load rules: %v", err)
	}

	if len(loaded.Rules) != 2 {
		t.Fatalf("expected 2 rules, got %d", len(loaded.Rules))
	}
}
