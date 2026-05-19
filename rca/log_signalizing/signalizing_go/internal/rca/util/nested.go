package util

import "strings"

// GetNested returns a nested field value using dot notation, or nil if missing.
func GetNested(data map[string]any, fieldPath string) any {
	return GetNestedPath(data, strings.Split(fieldPath, "."))
}

// GetNestedPath returns a nested field value using pre-split path parts.
func GetNestedPath(data map[string]any, fieldParts []string) any {
	current := any(data)
	for _, part := range fieldParts {
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

// SetNested assigns a nested field value using dot notation, creating missing objects as needed.
func SetNested(data map[string]any, fieldPath string, value any) {
	if data == nil {
		return
	}

	parts := strings.Split(strings.TrimSpace(fieldPath), ".")
	if len(parts) == 0 {
		return
	}

	current := data
	for idx, part := range parts {
		if part == "" {
			return
		}
		if idx == len(parts)-1 {
			current[part] = value
			return
		}

		next, ok := current[part].(map[string]any)
		if !ok || next == nil {
			next = map[string]any{}
			current[part] = next
		}
		current = next
	}
}
