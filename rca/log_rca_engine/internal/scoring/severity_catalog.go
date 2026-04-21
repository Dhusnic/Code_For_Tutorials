package scoring

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

type SignalSeverityCatalog map[string]float64

func LoadSignalSeverityCatalog(patterns []string) (SignalSeverityCatalog, error) {
	catalog := make(SignalSeverityCatalog)
	for _, pattern := range patterns {
		matches, err := expandCatalogPattern(pattern)
		if err != nil {
			return nil, err
		}
		for _, path := range matches {
			payload, err := os.ReadFile(filepath.Clean(path))
			if err != nil {
				return nil, fmt.Errorf("read signal severity catalog %s: %w", path, err)
			}
			var document any
			if err := yaml.Unmarshal(payload, &document); err != nil {
				return nil, fmt.Errorf("parse signal severity catalog %s: %w", path, err)
			}
			collectSignalSeverities(document, catalog)
		}
	}
	return catalog, nil
}

func expandCatalogPattern(pattern string) ([]string, error) {
	pattern = strings.TrimSpace(pattern)
	if pattern == "" {
		return nil, nil
	}
	if !strings.ContainsAny(pattern, "*?[") {
		return []string{pattern}, nil
	}
	matches, err := filepath.Glob(pattern)
	if err != nil {
		return nil, fmt.Errorf("expand signal severity catalog pattern %q: %w", pattern, err)
	}
	return matches, nil
}

func collectSignalSeverities(value any, catalog SignalSeverityCatalog) {
	switch typed := value.(type) {
	case map[string]any:
		signal := strings.ToLower(strings.TrimSpace(stringValue(typed["signal_key"])))
		level := strings.TrimSpace(stringValue(typed["level"]))
		if signal != "" && level != "" {
			catalog[signal] = severityWeight(level)
		}
		for _, nested := range typed {
			collectSignalSeverities(nested, catalog)
		}
	case []any:
		for _, nested := range typed {
			collectSignalSeverities(nested, catalog)
		}
	}
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	default:
		return ""
	}
}
