package utils

import (
	"fmt"
	"net"
	"regexp"
	"sort"
	"strings"
	"time"
)

var ipv4Pattern = regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`)

func ExtractString(metadata map[string]any, path string) string {
	return normalizeString(extractValue(metadata, path))
}

func ExtractIPAddresses(metadata map[string]any, path string) []string {
	return parseIPv4Strings(extractValue(metadata, path))
}

func extractValue(metadata map[string]any, path string) any {
	if metadata == nil {
		return nil
	}
	if value, ok := metadata[path]; ok {
		return value
	}

	current := any(metadata)
	for _, part := range strings.Split(path, ".") {
		next, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		value, exists := next[part]
		if !exists {
			return nil
		}
		current = value
	}
	return current
}

func normalizeString(value any) string {
	switch typed := value.(type) {
	case []string:
		return strings.Join(typed, ",")
	case []any:
		parts := make([]string, 0, len(typed))
		for _, item := range typed {
			part := strings.TrimSpace(fmt.Sprint(item))
			if part != "" && part != "<nil>" {
				parts = append(parts, part)
			}
		}
		return strings.Join(parts, ",")
	}
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "<nil>" {
		return ""
	}
	return text
}

func parseIPv4Strings(value any) []string {
	text := normalizeString(value)
	if text == "" {
		return nil
	}

	matches := ipv4Pattern.FindAllString(text, -1)
	if len(matches) == 0 {
		return nil
	}

	seen := make(map[string]struct{}, len(matches))
	result := make([]string, 0, len(matches))
	for _, match := range matches {
		parsed := net.ParseIP(match)
		if parsed == nil || parsed.To4() == nil {
			continue
		}
		normalized := parsed.To4().String()
		if _, ok := seen[normalized]; ok {
			continue
		}
		seen[normalized] = struct{}{}
		result = append(result, normalized)
	}
	return result
}

func ParseTime(value string) (time.Time, error) {
	text := strings.TrimSpace(value)
	if text == "" {
		return time.Time{}, fmt.Errorf("empty time")
	}

	layouts := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999999",
		"2006-01-02 15:04:05",
	}
	for _, layout := range layouts {
		if parsed, err := time.Parse(layout, text); err == nil {
			return parsed.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported time format %q", value)
}

func UniqueStrings(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(values))
	result := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		result = append(result, trimmed)
	}
	return result
}

func SortedUniqueStrings(values []string) []string {
	result := UniqueStrings(values)
	sort.Strings(result)
	return result
}

func CloneStringMap(input map[string]string) map[string]string {
	if len(input) == 0 {
		return nil
	}
	cloned := make(map[string]string, len(input))
	for key, value := range input {
		cloned[key] = value
	}
	return cloned
}
