package rules

import "testing"

func buildCiscoRuleSet() *RuleSet {
	return &RuleSet{
		Service: "network",
		Rules: []SignalRule{
			{
				RuleID:      "CISCO_LINK",
				SignalKey:   "network_cisco_ios_link_updown",
				Level:       "critical",
				Description: "Cisco-like link down signature",
				Tags:        []string{"vendor", "cisco", "ios"},
				Condition:   RuleCondition{Field: "message", Op: "contains", Value: "line protocol is down"},
			},
		},
	}
}

func TestVendorAnchorBlocksMismatchedVendorWhenHintsPresent(t *testing.T) {
	engine := NewRuleEngine(true)
	event := map[string]any{
		"message":  "GigabitEthernet0/1 line protocol is down",
		"observer": map[string]any{"vendor": "juniper"},
	}

	signals := engine.Evaluate(event, buildCiscoRuleSet(), 1, true)
	if len(signals) != 0 {
		t.Fatalf("expected no signals, got %d", len(signals))
	}
}

func TestVendorAnchorAllowsMatchingVendorWhenHintsPresent(t *testing.T) {
	engine := NewRuleEngine(true)
	event := map[string]any{
		"message":  "GigabitEthernet0/1 line protocol is down",
		"observer": map[string]any{"vendor": "cisco"},
	}

	signals := engine.Evaluate(event, buildCiscoRuleSet(), 1, true)
	if len(signals) != 1 {
		t.Fatalf("expected 1 signal, got %d", len(signals))
	}
	if signals[0]["signal"] != "network_cisco_ios_link_updown" {
		t.Fatalf("unexpected signal: %v", signals[0]["signal"])
	}
}
