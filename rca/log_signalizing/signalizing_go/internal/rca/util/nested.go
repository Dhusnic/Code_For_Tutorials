package util

import "strings"

// GetNested returns a nested field value using dot notation, or nil if missing.
func GetNested(data map[string]any, fieldPath string) any {
	current := any(data)
	for _, part := range strings.Split(fieldPath, ".") {
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
