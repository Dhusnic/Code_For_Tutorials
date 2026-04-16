package rules

import (
	"strings"
	"testing"
)

func TestRuleSchemaValidatorAcceptsNestedConditionTree(t *testing.T) {
	validator := RuleSchemaValidator{}
	payload := map[string]any{
		"service": "nginx",
		"rules": []any{
			map[string]any{
				"id":         "RULE_A",
				"signal_key": "upstream_timeout",
				"level":      "critical",
				"condition": map[string]any{
					"and": []any{
						map[string]any{"field": "message", "op": "contains", "value": "timeout"},
						map[string]any{
							"or": []any{
								map[string]any{"field": "http.response.status_code", "op": "gte", "value": 500},
								map[string]any{"field": "status", "op": "gte", "value": 500},
							},
						},
					},
				},
			},
		},
	}

	if err := validator.Validate(payload, "rules/test.yml"); err != nil {
		t.Fatalf("expected valid payload, got %v", err)
	}
}

func TestRuleSchemaValidatorRejectsMissingValueForNonExists(t *testing.T) {
	validator := RuleSchemaValidator{}
	payload := map[string]any{
		"service": "rabbitmq",
		"rules": []any{
			map[string]any{
				"id":         "RULE_B",
				"signal_key": "auth_failed",
				"level":      "warning",
				"condition":  map[string]any{"field": "message", "op": "contains"},
			},
		},
	}

	err := validator.Validate(payload, "rules/test.yml")
	if err == nil {
		t.Fatal("expected validation error")
	}
	if !strings.Contains(err.Error(), ".value is required") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestRuleSchemaValidatorRejectsEmptyConditionGroup(t *testing.T) {
	validator := RuleSchemaValidator{}
	payload := map[string]any{
		"service": "nginx",
		"rules": []any{
			map[string]any{
				"id":         "RULE_C",
				"signal_key": "invalid_req",
				"level":      "warning",
				"condition": map[string]any{
					"and": []any{},
				},
			},
		},
	}

	err := validator.Validate(payload, "rules/test.yml")
	if err == nil {
		t.Fatal("expected validation error")
	}
	if !strings.Contains(err.Error(), "at least 1 condition") {
		t.Fatalf("unexpected error: %v", err)
	}
}
