package llm

import (
	"encoding/json"
	"fmt"
	"strings"

	"log_rca_engine/internal/models"
)

type JSONExplanationParser struct{}

func NewJSONExplanationParser() *JSONExplanationParser {
	return &JSONExplanationParser{}
}

func (p *JSONExplanationParser) Parse(raw string, model string) (*models.LLMExplanation, error) {
	text := strings.TrimSpace(raw)
	if text == "" {
		return nil, fmt.Errorf("empty LLM response")
	}

	var explanation models.LLMExplanation
	if err := json.Unmarshal([]byte(text), &explanation); err != nil {
		return nil, fmt.Errorf("decode structured LLM output: %w", err)
	}
	explanation.Provider = "openai"
	explanation.Model = strings.TrimSpace(model)
	return &explanation, nil
}
