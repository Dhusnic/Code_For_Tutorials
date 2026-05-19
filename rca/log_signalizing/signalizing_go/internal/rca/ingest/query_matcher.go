package ingest

import (
	"fmt"
	"path"
	"strconv"
	"strings"

	"rca/internal/rca/util"
)

// EventMatchesQuery evaluates a small Elasticsearch-like query subset against an event payload.
func EventMatchesQuery(event map[string]any, query map[string]any) bool {
	if len(query) == 0 {
		return true
	}
	return matchClause(event, query)
}

func matchClause(event map[string]any, clause map[string]any) bool {
	if len(clause) == 0 {
		return true
	}

	for operator, payload := range clause {
		switch operator {
		case "term":
			return matchTerm(event, payload)
		case "terms":
			return matchTerms(event, payload)
		case "exists":
			return matchExists(event, payload)
		case "wildcard":
			return matchWildcard(event, payload)
		case "range":
			return matchRange(event, payload)
		case "bool":
			return matchBool(event, payload)
		default:
			return false
		}
	}
	return false
}

func matchTerm(event map[string]any, payload any) bool {
	fields, ok := payload.(map[string]any)
	if !ok || len(fields) == 0 {
		return false
	}
	for fieldPath, expected := range fields {
		return valuesEqual(util.GetNested(event, fieldPath), expected)
	}
	return false
}

func matchTerms(event map[string]any, payload any) bool {
	fields, ok := payload.(map[string]any)
	if !ok || len(fields) == 0 {
		return false
	}
	for fieldPath, expectedRaw := range fields {
		expectedList, ok := expectedRaw.([]any)
		if !ok {
			return false
		}
		actual := util.GetNested(event, fieldPath)
		for _, expected := range expectedList {
			if valuesEqual(actual, expected) {
				return true
			}
		}
		return false
	}
	return false
}

func matchExists(event map[string]any, payload any) bool {
	fields, ok := payload.(map[string]any)
	if !ok {
		return false
	}
	fieldName := strings.TrimSpace(fmt.Sprint(fields["field"]))
	if fieldName == "" {
		return false
	}
	return util.GetNested(event, fieldName) != nil
}

func matchWildcard(event map[string]any, payload any) bool {
	fields, ok := payload.(map[string]any)
	if !ok || len(fields) == 0 {
		return false
	}
	for fieldPath, expected := range fields {
		actualText := strings.TrimSpace(fmt.Sprint(util.GetNested(event, fieldPath)))
		pattern := strings.TrimSpace(fmt.Sprint(expected))
		if actualText == "<nil>" || pattern == "" {
			return false
		}
		matched, err := path.Match(pattern, actualText)
		return err == nil && matched
	}
	return false
}

func matchRange(event map[string]any, payload any) bool {
	fields, ok := payload.(map[string]any)
	if !ok || len(fields) == 0 {
		return false
	}
	for fieldPath, boundsRaw := range fields {
		bounds, ok := boundsRaw.(map[string]any)
		if !ok {
			return false
		}
		actualNumber, ok := toFloat(util.GetNested(event, fieldPath))
		if !ok {
			return false
		}
		for bound, value := range bounds {
			limit, ok := toFloat(value)
			if !ok {
				return false
			}
			switch bound {
			case "gt":
				if !(actualNumber > limit) {
					return false
				}
			case "gte":
				if !(actualNumber >= limit) {
					return false
				}
			case "lt":
				if !(actualNumber < limit) {
					return false
				}
			case "lte":
				if !(actualNumber <= limit) {
					return false
				}
			default:
				return false
			}
		}
		return true
	}
	return false
}

func matchBool(event map[string]any, payload any) bool {
	body, ok := payload.(map[string]any)
	if !ok {
		return false
	}

	for _, key := range []string{"filter", "must"} {
		items := clauseList(body[key])
		for _, item := range items {
			if !matchClause(event, item) {
				return false
			}
		}
	}

	for _, item := range clauseList(body["must_not"]) {
		if matchClause(event, item) {
			return false
		}
	}

	shouldClauses := clauseList(body["should"])
	if len(shouldClauses) == 0 {
		return true
	}

	matches := 0
	for _, item := range shouldClauses {
		if matchClause(event, item) {
			matches++
		}
	}

	minimumShouldMatch := 1
	switch value := body["minimum_should_match"].(type) {
	case int:
		minimumShouldMatch = value
	case int64:
		minimumShouldMatch = int(value)
	case float64:
		minimumShouldMatch = int(value)
	case string:
		if parsed, err := strconv.Atoi(strings.TrimSpace(value)); err == nil {
			minimumShouldMatch = parsed
		}
	}
	if minimumShouldMatch < 0 {
		minimumShouldMatch = 0
	}
	return matches >= minimumShouldMatch
}

func clauseList(value any) []map[string]any {
	switch typed := value.(type) {
	case []any:
		result := make([]map[string]any, 0, len(typed))
		for _, item := range typed {
			if clause, ok := item.(map[string]any); ok {
				result = append(result, clause)
			}
		}
		return result
	case map[string]any:
		return []map[string]any{typed}
	default:
		return nil
	}
}

func valuesEqual(actual any, expected any) bool {
	switch actualTyped := actual.(type) {
	case []any:
		for _, item := range actualTyped {
			if valuesEqual(item, expected) {
				return true
			}
		}
		return false
	case []string:
		for _, item := range actualTyped {
			if valuesEqual(item, expected) {
				return true
			}
		}
		return false
	}

	actualText := strings.TrimSpace(fmt.Sprint(actual))
	expectedText := strings.TrimSpace(fmt.Sprint(expected))
	if actualText == "<nil>" || expectedText == "<nil>" {
		return false
	}
	return strings.EqualFold(actualText, expectedText)
}

func toFloat(value any) (float64, bool) {
	switch typed := value.(type) {
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case float64:
		return typed, true
	case string:
		number, err := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		if err != nil {
			return 0, false
		}
		return number, true
	default:
		return 0, false
	}
}
