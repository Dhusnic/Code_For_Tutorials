package llm

func explanationSchema() map[string]any {
	return map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"required": []string{
			"root_cause",
			"natural_language_summary",
			"affected_services",
			"evidence",
			"next_checks",
		},
		"properties": map[string]any{
			"root_cause": map[string]any{
				"type": "string",
			},
			"natural_language_summary": map[string]any{
				"type": "string",
			},
			"affected_services": map[string]any{
				"type":  "array",
				"items": map[string]any{"type": "string"},
			},
			"evidence": map[string]any{
				"type":  "array",
				"items": map[string]any{"type": "string"},
			},
			"next_checks": map[string]any{
				"type":  "array",
				"items": map[string]any{"type": "string"},
			},
		},
	}
}
