package llm

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

	"log_rca_engine/internal/config"
	"log_rca_engine/internal/models"
)

type Explainer interface {
	Enabled() bool
	Explain(ctx context.Context, request models.ExplanationRequest) (*models.LLMExplanation, error)
}

type OpenAIConversationHandler struct {
	enabled         bool
	model           string
	maxOutputTokens int
	builder         PromptBuilder
	transport       ResponseTransport
	parser          ExplanationParser
	logger          *slog.Logger
}

func NewOpenAIConversationHandler(cfg config.OpenAIConfig, logger *slog.Logger) *OpenAIConversationHandler {
	return &OpenAIConversationHandler{
		enabled:         cfg.Enabled,
		model:           strings.TrimSpace(cfg.Model),
		maxOutputTokens: cfg.MaxOutputTokens,
		builder:         NewRCAPromptBuilder(),
		transport:       newResponsesTransport(cfg, logger),
		parser:          NewJSONExplanationParser(),
		logger:          logger,
	}
}

func (h *OpenAIConversationHandler) Enabled() bool {
	return h != nil && h.enabled && h.model != ""
}

func (h *OpenAIConversationHandler) Explain(ctx context.Context, request models.ExplanationRequest) (*models.LLMExplanation, error) {
	if !h.Enabled() {
		return nil, fmt.Errorf("openai conversation handler is disabled")
	}

	conversation, err := h.builder.BuildExplanationConversation(h.model, h.maxOutputTokens, request)
	if err != nil {
		return nil, err
	}

	raw, err := h.transport.CreateResponse(ctx, conversation)
	if err != nil {
		return nil, err
	}

	explanation, err := h.parser.Parse(raw, h.model)
	if err != nil {
		return nil, err
	}

	if h.logger != nil {
		h.logger.Debug(
			"generated structured RCA explanation",
			"model", h.model,
			"incident_id", request.Event.IncidentID,
			"affected_services", len(explanation.AffectedServices),
		)
	}
	return explanation, nil
}
