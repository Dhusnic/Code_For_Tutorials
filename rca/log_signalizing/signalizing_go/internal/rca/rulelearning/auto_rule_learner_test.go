package rulelearning

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"

	"rca/internal/rca/config"
)

func fallbackSignal() map[string]any {
	return map[string]any{
		"signal": "nginx_unclassified_failure",
		"level":  "critical",
		"tags":   []string{"fallback", "unclassified", "critical"},
	}
}

func TestAutoRuleLearnerWritesSuggestionsToSeparateFolder(t *testing.T) {
	tempDir := t.TempDir()
	rulesDir := filepath.Join(tempDir, "rules")
	suggestionsDir := filepath.Join(rulesDir, "suggestions")

	learner := NewAutoRuleLearner(
		config.RuleLearningConfig{
			Enabled:                 true,
			Mode:                    "suggest",
			OutputDirectory:         suggestionsDir,
			MinOccurrences:          2,
			MaxCandidatesPerService: 10,
			MinKeywordCount:         2,
			MaxKeywordsPerSignal:    4,
			ConditionField:          "message",
			ConditionOp:             "contains",
			Level:                   "critical",
		},
		rulesDir,
		map[string]string{"nginx": "nginx.yml"},
	)

	learner.Observe("nginx", map[string]any{"message": "upstream sent no valid HTTP/1.0 header while reading response header from upstream"}, fallbackSignal())
	learner.Observe("nginx", map[string]any{"message": "upstream sent no valid HTTP/1.0 header while reading response header from upstream, client: 10.0.0.5"}, fallbackSignal())

	written := learner.Flush()
	if written["nginx"] != 1 {
		t.Fatalf("expected nginx write count 1, got %#v", written)
	}

	path := filepath.Join(suggestionsDir, "nginx.yml")
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read suggestions file: %v", err)
	}

	var payload map[string]any
	if err := yaml.Unmarshal(content, &payload); err != nil {
		t.Fatalf("unmarshal yaml: %v", err)
	}
	if payload["service"] != "nginx" {
		t.Fatalf("unexpected service: %v", payload["service"])
	}
	rules := payload["rules"].([]any)
	if len(rules) != 1 {
		t.Fatalf("expected 1 rule, got %d", len(rules))
	}
	rule := rules[0].(map[string]any)
	if !strings.HasPrefix(rule["signal_key"].(string), "nginx_auto_") {
		t.Fatalf("unexpected signal_key: %v", rule["signal_key"])
	}
}

func TestAutoRuleLearnerAppendModeWritesToMainRuleFile(t *testing.T) {
	tempDir := t.TempDir()
	rulesDir := filepath.Join(tempDir, "rules")
	if err := os.MkdirAll(rulesDir, 0o755); err != nil {
		t.Fatalf("mkdir rules: %v", err)
	}

	mainRulePath := filepath.Join(rulesDir, "auth.yml")
	initialPayload := map[string]any{
		"service": "auth",
		"rules": []any{
			map[string]any{
				"id":          "A_AUTH_UNCLASSIFIED_FAILURE",
				"signal_key":  "auth_unclassified_failure",
				"level":       "critical",
				"description": "fallback",
				"tags":        []any{"fallback", "unclassified", "critical"},
				"condition":   map[string]any{"field": "message", "op": "contains", "value": "authentication failure"},
			},
		},
	}
	content, _ := yaml.Marshal(initialPayload)
	if err := os.WriteFile(mainRulePath, content, 0o644); err != nil {
		t.Fatalf("write main rule file: %v", err)
	}

	learner := NewAutoRuleLearner(
		config.RuleLearningConfig{
			Enabled:                 true,
			Mode:                    "append",
			OutputDirectory:         filepath.Join(tempDir, "unused"),
			MinOccurrences:          2,
			MaxCandidatesPerService: 10,
			MinKeywordCount:         2,
			MaxKeywordsPerSignal:    4,
			ConditionField:          "message",
			ConditionOp:             "contains",
			Level:                   "critical",
		},
		rulesDir,
		map[string]string{"auth": "auth.yml"},
	)

	learner.Observe("auth", map[string]any{"message": "authentication timeout for invalid user admin from 10.0.0.10"}, fallbackSignal())
	learner.Observe("auth", map[string]any{"message": "authentication timeout for invalid user root from 10.0.0.11"}, fallbackSignal())

	written := learner.Flush()
	if written["auth"] != 1 {
		t.Fatalf("expected auth write count 1, got %#v", written)
	}

	updatedContent, err := os.ReadFile(mainRulePath)
	if err != nil {
		t.Fatalf("read main rule file: %v", err)
	}
	var payload map[string]any
	if err := yaml.Unmarshal(updatedContent, &payload); err != nil {
		t.Fatalf("unmarshal updated yaml: %v", err)
	}
	rules := payload["rules"].([]any)
	if len(rules) != 2 {
		t.Fatalf("expected 2 rules, got %d", len(rules))
	}
	lastRule := rules[len(rules)-1].(map[string]any)
	if !strings.HasPrefix(lastRule["signal_key"].(string), "auth_auto_") {
		t.Fatalf("unexpected signal key: %v", lastRule["signal_key"])
	}
}

func TestAutoRuleLearnerExtractsEmbeddedMessageForConditionFilter(t *testing.T) {
	tempDir := t.TempDir()
	rulesDir := filepath.Join(tempDir, "rules")
	suggestionsDir := filepath.Join(rulesDir, "suggestions")

	learner := NewAutoRuleLearner(
		config.RuleLearningConfig{
			Enabled:                 true,
			Mode:                    "suggest",
			OutputDirectory:         suggestionsDir,
			MinOccurrences:          2,
			MaxCandidatesPerService: 10,
			MinKeywordCount:         2,
			MaxKeywordsPerSignal:    4,
			ConditionField:          "message",
			ConditionOp:             "contains",
			Level:                   "critical",
		},
		rulesDir,
		map[string]string{"network": "network.yml"},
	)

	eventMessage := `<187>Feb 20 12:16:41 FGT-EDGE-1 date=2026-02-20 time=12:16:41 logid="0100022920" type="utm" subtype="app-ctrl" level="error" devid="FGT60E3X19000001" vd="root" eventtime=1771570001785 tz="+0000" srcip=10.34.195.36 srcport=40308 dstip=8.8.8.8 dstport=161 proto=17 service="web-browsing" action="blocked" msg="Application control blocked"`

	learner.Observe("network", map[string]any{"message": eventMessage}, fallbackSignal())
	learner.Observe("network", map[string]any{"message": eventMessage}, fallbackSignal())
	written := learner.Flush()

	if written["network"] != 1 {
		t.Fatalf("expected network write count 1, got %#v", written)
	}
	content, err := os.ReadFile(filepath.Join(suggestionsDir, "network.yml"))
	if err != nil {
		t.Fatalf("read network suggestions: %v", err)
	}
	var payload map[string]any
	if err := yaml.Unmarshal(content, &payload); err != nil {
		t.Fatalf("unmarshal yaml: %v", err)
	}
	rules := payload["rules"].([]any)
	rule := rules[0].(map[string]any)
	condition := rule["condition"].(map[string]any)
	if condition["value"] != "application control blocked" {
		t.Fatalf("unexpected condition value: %v", condition["value"])
	}
}
