package llm

import "testing"

func TestJSONExplanationParserParse(t *testing.T) {
	parser := NewJSONExplanationParser()

	explanation, err := parser.Parse(`{
		"root_cause": "Database latency increased after a dependency slowdown.",
		"natural_language_summary": "Checkout latency rose because the orders database slowed down.",
		"affected_services": ["checkout-api", "orders-db"],
		"evidence": ["error logs show DB timeout", "topology links checkout-api to orders-db"],
		"next_checks": ["check database saturation", "review recent deploys"]
	}`, "gpt-4o-mini")
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}

	if explanation.Provider != "openai" {
		t.Fatalf("expected provider openai, got %q", explanation.Provider)
	}
	if explanation.Model != "gpt-4o-mini" {
		t.Fatalf("expected model gpt-4o-mini, got %q", explanation.Model)
	}
	if explanation.RootCause == "" {
		t.Fatal("expected root cause to be populated")
	}
	if len(explanation.AffectedServices) != 2 {
		t.Fatalf("expected 2 affected services, got %d", len(explanation.AffectedServices))
	}
}

func TestJSONExplanationParserParseInvalidJSON(t *testing.T) {
	parser := NewJSONExplanationParser()

	if _, err := parser.Parse(`not-json`, "gpt-4o-mini"); err == nil {
		t.Fatal("expected invalid JSON to return an error")
	}
}
