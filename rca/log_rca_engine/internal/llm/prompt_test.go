package llm

import (
	"strings"
	"testing"
	"time"

	"log_rca_engine/internal/models"
)

func TestRCAPromptBuilderBuildExplanationConversation(t *testing.T) {
	builder := NewRCAPromptBuilder()
	matchedAt := time.Date(2026, time.April, 10, 9, 30, 0, 0, time.UTC)

	conversation, err := builder.BuildExplanationConversation("gpt-4o-mini", 900, models.ExplanationRequest{
		Event: models.CorrelationEvent{
			IncidentID:     "inc-123",
			OrganizationID: "org-123",
			RuleID:         "rule-latency",
			Status:         "open",
			MatchedAt:      matchedAt,
			LogID: []models.EvidenceLog{
				{ID: "doc-1", ServiceName: "checkout-api", Severity: "error"},
			},
		},
		Score: models.ScoreResult{
			Classification:  "confirmed_rca",
			ConfidenceScore: 8.4,
			Breakdown: models.ScoreBreakdown{
				SequenceMatch:   0.95,
				DependencyMatch: 0.80,
			},
		},
	})
	if err != nil {
		t.Fatalf("BuildExplanationConversation() error = %v", err)
	}

	if conversation.Name != "rca_summary" {
		t.Fatalf("expected conversation name rca_summary, got %q", conversation.Name)
	}
	if conversation.Model != "gpt-4o-mini" {
		t.Fatalf("expected model gpt-4o-mini, got %q", conversation.Model)
	}
	if conversation.MaxOutputTokens != 900 {
		t.Fatalf("expected max output tokens 900, got %d", conversation.MaxOutputTokens)
	}
	if len(conversation.Messages) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(conversation.Messages))
	}

	systemPrompt := conversation.Messages[0].Content[0].Text
	if !strings.Contains(systemPrompt, "Return only valid JSON") {
		t.Fatalf("expected system prompt to require JSON-only output, got %q", systemPrompt)
	}

	userPrompt := conversation.Messages[1].Content[0].Text
	if !strings.Contains(userPrompt, `"incident_id": "inc-123"`) {
		t.Fatalf("expected incident payload in user prompt, got %q", userPrompt)
	}
	if !strings.Contains(userPrompt, `"confidence_score": 8.4`) {
		t.Fatalf("expected score payload in user prompt, got %q", userPrompt)
	}

	properties, ok := conversation.ResponseSchema["properties"].(map[string]any)
	if !ok {
		t.Fatalf("expected schema properties map, got %#v", conversation.ResponseSchema["properties"])
	}
	if _, ok := properties["root_cause"]; !ok {
		t.Fatalf("expected root_cause property in schema")
	}
	if _, ok := properties["next_checks"]; !ok {
		t.Fatalf("expected next_checks property in schema")
	}
}
