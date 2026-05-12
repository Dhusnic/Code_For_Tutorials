package rules

import "testing"

func TestRuleEngineMatchesMultipleRules(t *testing.T) {
	engine := NewRuleEngine(true)
	ruleSet := &RuleSet{
		Service: "nginx",
		Rules: []SignalRule{
			{
				RuleID:      "A",
				SignalKey:   "upstream_timeout",
				Level:       "critical",
				Description: "contains timeout",
				Condition:   RuleCondition{Field: "message", Op: "contains", Value: "timeout"},
			},
			{
				RuleID:      "B",
				SignalKey:   "server_error",
				Level:       "warning",
				Description: "status high",
				Condition:   RuleCondition{Field: "http.response.status_code", Op: "gte", Value: 500},
			},
		},
	}

	event := map[string]any{
		"message": "upstream timeout while connecting",
		"http":    map[string]any{"response": map[string]any{"status_code": 502}},
	}

	signals := engine.Evaluate(event, ruleSet, 0, false)
	if len(signals) != 2 {
		t.Fatalf("expected 2 signals, got %d", len(signals))
	}
	if signals[0]["signal"] != "upstream_timeout" {
		t.Fatalf("expected upstream_timeout first, got %v", signals[0]["signal"])
	}
}

func TestRuleEngineSupportsNestedAndOrConditions(t *testing.T) {
	engine := NewRuleEngine(true)
	ruleSet := &RuleSet{
		Service: "rabbitmq",
		Rules: []SignalRule{
			{
				RuleID:      "C",
				SignalKey:   "memory_alarm",
				Level:       "critical",
				Description: "nested condition",
				Condition: RuleConditionGroup{
					Op: "and",
					Conditions: []ConditionNode{
						RuleCondition{Field: "message", Op: "contains", Value: "alarm"},
						RuleConditionGroup{
							Op: "or",
							Conditions: []ConditionNode{
								RuleCondition{Field: "log.level", Op: "equals", Value: "CRITICAL"},
								RuleCondition{Field: "rabbitmq.node.mem.alarm", Op: "equals", Value: true},
							},
						},
					},
				},
			},
		},
	}

	event := map[string]any{
		"message":  "queue memory alarm active",
		"log":      map[string]any{"level": "INFO"},
		"rabbitmq": map[string]any{"node": map[string]any{"mem": map[string]any{"alarm": true}}},
	}

	signals := engine.Evaluate(event, ruleSet, 0, false)
	if len(signals) != 1 {
		t.Fatalf("expected 1 signal, got %d", len(signals))
	}
}

func TestRuleEnginePrefersSpecificOverFallback(t *testing.T) {
	engine := NewRuleEngine(true)
	ruleSet := &RuleSet{
		Service: "nginx",
		Rules: []SignalRule{
			{
				RuleID:      "A_FALLBACK",
				SignalKey:   "nginx_unclassified_failure",
				Level:       "critical",
				Description: "fallback",
				Tags:        []string{"fallback", "unclassified", "critical"},
				Condition:   RuleCondition{Field: "log.level", Op: "equals", Value: "error"},
			},
			{
				RuleID:      "Z_SPECIFIC",
				SignalKey:   "nginx_upstream_timeout_connect",
				Level:       "critical",
				Description: "specific",
				Tags:        []string{"upstream", "timeout", "connect"},
				Condition:   RuleCondition{Field: "message", Op: "contains", Value: "upstream timed out"},
			},
		},
	}

	event := map[string]any{
		"log":     map[string]any{"level": "error"},
		"message": "upstream timed out while connecting",
	}

	signals := engine.Evaluate(event, ruleSet, 1, true)
	if len(signals) != 1 {
		t.Fatalf("expected 1 signal, got %d", len(signals))
	}
	if signals[0]["signal"] != "nginx_upstream_timeout_connect" {
		t.Fatalf("expected specific signal, got %v", signals[0]["signal"])
	}
}

func TestRuleEngineMatchesRawNginxAccessStatusMessage(t *testing.T) {
	engine := NewRuleEngine(true)
	ruleSet := &RuleSet{
		Service: "nginx",
		Rules: []SignalRule{
			{
				RuleID:      "NGINX_ACCESS_5XX_ANY",
				SignalKey:   "nginx_access_5xx_any",
				Level:       "warning",
				Description: "Any 5xx response in access logs.",
				Condition: RuleConditionGroup{
					Op: "or",
					Conditions: []ConditionNode{
						RuleCondition{Field: "http.response.status_code", Op: "gte", Value: 500},
						RuleCondition{Field: "status", Op: "gte", Value: 500},
						RuleCondition{Field: "status_code", Op: "regex", Value: "^5[0-9]{2}$"},
						RuleCondition{Field: "message", Op: "regex", Value: `(?:\s|")5[0-9]{2}(?:\s|")`},
						RuleConditionGroup{
							Op: "and",
							Conditions: []ConditionNode{
								RuleCondition{Field: "message", Op: "contains", Value: "rca_sim_nginx_access"},
								RuleCondition{Field: "message", Op: "regex", Value: `status=5[0-9]{2}`},
							},
						},
					},
				},
			},
			{
				RuleID:      "NGINX_ACCESS_502_BAD_GATEWAY",
				SignalKey:   "nginx_access_502_bad_gateway",
				Level:       "critical",
				Description: "Upstream gateway failure surfaced as 502.",
				Condition: RuleConditionGroup{
					Op: "or",
					Conditions: []ConditionNode{
						RuleCondition{Field: "http.response.status_code", Op: "equals", Value: 502},
						RuleCondition{Field: "status", Op: "equals", Value: 502},
						RuleCondition{Field: "status_code", Op: "regex", Value: "^502$"},
						RuleCondition{Field: "message", Op: "regex", Value: `(?:\s|")502(?:\s|")`},
						RuleConditionGroup{
							Op: "and",
							Conditions: []ConditionNode{
								RuleCondition{Field: "message", Op: "contains", Value: "rca_sim_nginx_access"},
								RuleCondition{Field: "message", Op: "contains", Value: "status=502"},
							},
						},
					},
				},
			},
		},
	}

	event := map[string]any{
		"message": `rca_sim_nginx_access ts="05/May/2026:10:55:51 +0530" client_ip=10.0.4.72 method=GET path=/api/orders status=502 bytes_sent=646 request_time=1.370 upstream_response_time=1.059`,
		"tags":    []any{"_grokparsefailure"},
	}

	signals := engine.Evaluate(event, ruleSet, 0, false)
	if len(signals) != 2 {
		t.Fatalf("expected 2 signals for raw access message, got %d", len(signals))
	}
	if signals[0]["signal"] != "nginx_access_502_bad_gateway" {
		t.Fatalf("expected 502 signal first, got %v", signals[0]["signal"])
	}
}
