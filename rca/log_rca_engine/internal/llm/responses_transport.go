package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"log_rca_engine/internal/config"
)

type responsesTransport struct {
	baseURL        string
	apiKey         string
	requestTimeout time.Duration
	httpClient     *http.Client
	logger         *slog.Logger
}

type responsesRequest struct {
	Model           string                `json:"model"`
	Input           []ConversationMessage `json:"input"`
	Text            responseText          `json:"text"`
	MaxOutputTokens int                   `json:"max_output_tokens,omitempty"`
}

type responseText struct {
	Format responseFormat `json:"format"`
}

type responseFormat struct {
	Type   string         `json:"type"`
	Name   string         `json:"name"`
	Strict bool           `json:"strict"`
	Schema map[string]any `json:"schema"`
}

type responsesResponse struct {
	OutputText string `json:"output_text"`
	Output     []struct {
		Content []struct {
			Type    string `json:"type"`
			Text    string `json:"text"`
			Refusal string `json:"refusal,omitempty"`
		} `json:"content"`
	} `json:"output"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func newResponsesTransport(cfg config.OpenAIConfig, logger *slog.Logger) *responsesTransport {
	timeout := cfg.RequestTimeout
	if timeout <= 0 {
		timeout = 30 * time.Second
	}

	return &responsesTransport{
		baseURL:        strings.TrimRight(strings.TrimSpace(cfg.BaseURL), "/"),
		apiKey:         strings.TrimSpace(cfg.APIKey),
		requestTimeout: timeout,
		httpClient:     &http.Client{Timeout: timeout},
		logger:         logger,
	}
}

func (t *responsesTransport) CreateResponse(ctx context.Context, conversation Conversation) (string, error) {
	requestBody := responsesRequest{
		Model: conversation.Model,
		Input: conversation.Messages,
		Text: responseText{
			Format: responseFormat{
				Type:   "json_schema",
				Name:   conversation.Name,
				Strict: true,
				Schema: conversation.ResponseSchema,
			},
		},
		MaxOutputTokens: conversation.MaxOutputTokens,
	}

	wireBody, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("marshal openai request body: %w", err)
	}

	requestCtx, cancel := context.WithTimeout(ctx, t.requestTimeout)
	defer cancel()

	httpRequest, err := http.NewRequestWithContext(requestCtx, http.MethodPost, t.baseURL+"/responses", bytes.NewReader(wireBody))
	if err != nil {
		return "", fmt.Errorf("create openai request: %w", err)
	}
	httpRequest.Header.Set("Authorization", "Bearer "+t.apiKey)
	httpRequest.Header.Set("Content-Type", "application/json")

	response, err := t.httpClient.Do(httpRequest)
	if err != nil {
		return "", fmt.Errorf("call openai responses api: %w", err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return "", fmt.Errorf("read openai response: %w", err)
	}
	if response.StatusCode >= http.StatusBadRequest {
		return "", fmt.Errorf("openai responses api returned %s: %s", response.Status, string(rawBody))
	}

	var parsed responsesResponse
	if err := json.Unmarshal(rawBody, &parsed); err != nil {
		return "", fmt.Errorf("decode openai response: %w", err)
	}
	if parsed.Error != nil && parsed.Error.Message != "" {
		return "", fmt.Errorf("openai error: %s", parsed.Error.Message)
	}

	text := strings.TrimSpace(parsed.OutputText)
	if text == "" {
		text = extractOutputText(parsed.Output)
	}
	if text == "" {
		return "", fmt.Errorf("openai response did not contain structured text")
	}
	return text, nil
}

func extractOutputText(output []struct {
	Content []struct {
		Type    string `json:"type"`
		Text    string `json:"text"`
		Refusal string `json:"refusal,omitempty"`
	} `json:"content"`
}) string {
	parts := make([]string, 0)
	for _, block := range output {
		for _, content := range block.Content {
			if text := strings.TrimSpace(content.Text); text != "" {
				parts = append(parts, text)
			}
		}
	}
	return strings.Join(parts, "\n")
}
