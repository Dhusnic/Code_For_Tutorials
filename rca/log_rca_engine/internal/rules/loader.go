package rules

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"log_rca_engine/internal/models"
)

type FileLoader struct {
	path string
}

func NewFileLoader(path string) *FileLoader {
	return &FileLoader{path: strings.TrimSpace(path)}
}

func (l *FileLoader) Load(ctx context.Context) (map[string]models.Rule, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	payload, err := os.ReadFile(l.path)
	if err != nil {
		return nil, fmt.Errorf("read rules file: %w", err)
	}

	var raw []models.Rule
	if err := json.Unmarshal(payload, &raw); err != nil {
		return nil, fmt.Errorf("decode rules file: %w", err)
	}

	result := make(map[string]models.Rule, len(raw))
	for _, rule := range raw {
		if strings.TrimSpace(rule.ID) == "" {
			continue
		}
		result[rule.ID] = rule
	}
	return result, nil
}
