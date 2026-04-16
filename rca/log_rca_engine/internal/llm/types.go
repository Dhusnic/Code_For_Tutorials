package llm

import (
	"context"

	"log_rca_engine/internal/models"
)

type ContentPart struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type ConversationMessage struct {
	Role    string        `json:"role"`
	Content []ContentPart `json:"content"`
}

type Conversation struct {
	Name            string
	Model           string
	Messages        []ConversationMessage
	ResponseSchema  map[string]any
	MaxOutputTokens int
}

type PromptBuilder interface {
	BuildExplanationConversation(model string, maxOutputTokens int, request models.ExplanationRequest) (Conversation, error)
}

type ResponseTransport interface {
	CreateResponse(ctx context.Context, conversation Conversation) (string, error)
}

type ExplanationParser interface {
	Parse(raw string, model string) (*models.LLMExplanation, error)
}
