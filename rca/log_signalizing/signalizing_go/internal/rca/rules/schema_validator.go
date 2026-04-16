package rules

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	supportedOps = map[string]struct{}{
		"exists":       {},
		"equals":       {},
		"not_equals":   {},
		"contains":     {},
		"not_contains": {},
		"regex":        {},
		"not_regex":    {},
		"in":           {},
		"not_in":       {},
		"gt":           {},
		"gte":          {},
		"lt":           {},
		"lte":          {},
	}
	supportedLevels = map[string]struct{}{
		"critical": {},
		"warning":  {},
		"info":     {},
	}
	signalKeyPattern = regexp.MustCompile(`^[a-z0-9]+(?:_[a-z0-9]+)*$`)
)

// RuleSchemaValidator validates rule-file shape and supported operators.
type RuleSchemaValidator struct{}

// Validate fails when the payload does not conform to the rule schema.
func (RuleSchemaValidator) Validate(payload map[string]any, fileName string) error {
	rulesRaw, ok := payload["rules"]
	if !ok {
		return fmt.Errorf("%s: 'rules' must be a list", fileName)
	}
	rulesList, ok := rulesRaw.([]any)
	if !ok {
		return fmt.Errorf("%s: 'rules' must be a list", fileName)
	}
	for idx, ruleRaw := range rulesList {
		if err := validateRule(ruleRaw, fileName, idx); err != nil {
			return err
		}
	}
	return nil
}

func validateRule(ruleRaw any, fileName string, idx int) error {
	prefix := fmt.Sprintf("%s: rules[%d]", fileName, idx)
	rule, ok := ruleRaw.(map[string]any)
	if !ok {
		return fmt.Errorf("%s must be an object", prefix)
	}

	if err := requireString(rule, "id", prefix); err != nil {
		return err
	}
	if err := requireString(rule, "signal_key", prefix); err != nil {
		return err
	}
	if err := requireString(rule, "level", prefix); err != nil {
		return err
	}

	level := strings.ToLower(fmt.Sprint(rule["level"]))
	if _, ok := supportedLevels[level]; !ok {
		return fmt.Errorf("%s.level unsupported: %v", prefix, rule["level"])
	}
	if !signalKeyPattern.MatchString(fmt.Sprint(rule["signal_key"])) {
		return fmt.Errorf("%s.signal_key must be lowercase snake_case (example: nginx_upstream_timeout)", prefix)
	}

	if tagsRaw, ok := rule["tags"]; ok {
		tags, ok := tagsRaw.([]any)
		if !ok {
			return fmt.Errorf("%s.tags must be a list of strings", prefix)
		}
		for _, tag := range tags {
			if _, ok := tag.(string); !ok {
				return fmt.Errorf("%s.tags must be a list of strings", prefix)
			}
		}
	}

	conditionRaw, ok := rule["condition"]
	if !ok {
		return fmt.Errorf("%s.condition is required", prefix)
	}
	if _, ok := rule["conditions"]; ok {
		return fmt.Errorf("%s must not use legacy 'conditions'/'match'; use nested 'condition' only", prefix)
	}
	if _, ok := rule["match"]; ok {
		return fmt.Errorf("%s must not use legacy 'conditions'/'match'; use nested 'condition' only", prefix)
	}

	return validateConditionNode(conditionRaw, prefix+".condition")
}

func validateConditionNode(nodeRaw any, prefix string) error {
	node, ok := nodeRaw.(map[string]any)
	if !ok {
		return fmt.Errorf("%s must be an object", prefix)
	}

	if andRaw, ok := node["and"]; ok {
		return validateLogicalGroup(andRaw, prefix+".and")
	}
	if orRaw, ok := node["or"]; ok {
		return validateLogicalGroup(orRaw, prefix+".or")
	}
	return validateConditionLeaf(node, prefix)
}

func validateLogicalGroup(nodesRaw any, prefix string) error {
	nodes, ok := nodesRaw.([]any)
	if !ok || len(nodes) < 1 {
		return fmt.Errorf("%s must be a list with at least 1 condition", prefix)
	}
	for idx, child := range nodes {
		if err := validateConditionNode(child, fmt.Sprintf("%s[%d]", prefix, idx)); err != nil {
			return err
		}
	}
	return nil
}

func validateConditionLeaf(cond map[string]any, prefix string) error {
	if err := requireString(cond, "field", prefix); err != nil {
		return err
	}
	if err := requireString(cond, "op", prefix); err != nil {
		return err
	}

	op := strings.ToLower(fmt.Sprint(cond["op"]))
	if _, ok := supportedOps[op]; !ok {
		return fmt.Errorf("%s.op unsupported: %s", prefix, op)
	}

	_, hasValue := cond["value"]
	if op == "exists" {
		if hasValue {
			return fmt.Errorf("%s.value must not be present for op='exists'", prefix)
		}
	} else if !hasValue {
		return fmt.Errorf("%s.value is required for op='%s'", prefix, op)
	}

	if caseSensitiveRaw, ok := cond["case_sensitive"]; ok {
		if _, ok := caseSensitiveRaw.(bool); !ok {
			return fmt.Errorf("%s.case_sensitive must be boolean", prefix)
		}
	}

	if requiresScalar(op) && hasValue && !isScalar(cond["value"]) {
		return fmt.Errorf("%s.value must be scalar for op='%s'", prefix, op)
	}

	if op == "regex" || op == "not_regex" {
		pattern, ok := cond["value"].(string)
		if !ok {
			return fmt.Errorf("%s.value must be string for op='%s'", prefix, op)
		}
		if _, err := regexp.Compile(pattern); err != nil {
			return fmt.Errorf("%s.value invalid regex: %s", prefix, err)
		}
	}

	if op == "in" || op == "not_in" {
		values, ok := cond["value"].([]any)
		if !ok || len(values) == 0 {
			return fmt.Errorf("%s.value must be non-empty list for op='%s'", prefix, op)
		}
	}

	if (op == "gt" || op == "gte" || op == "lt" || op == "lte") && !isNumeric(cond["value"]) {
		return fmt.Errorf("%s.value must be numeric for op='%s'", prefix, op)
	}

	return nil
}

func requireString(data map[string]any, key string, prefix string) error {
	value, ok := data[key]
	if !ok {
		return fmt.Errorf("%s.%s is required", prefix, key)
	}
	if _, ok := value.(string); !ok {
		return fmt.Errorf("%s.%s must be str", prefix, key)
	}
	return nil
}

func requiresScalar(op string) bool {
	switch op {
	case "contains", "not_contains", "regex", "not_regex", "equals", "not_equals":
		return true
	default:
		return false
	}
}

func isScalar(value any) bool {
	switch value.(type) {
	case string, int, int8, int16, int32, int64, float32, float64, bool:
		return true
	default:
		return false
	}
}

func isNumeric(value any) bool {
	switch value.(type) {
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, float32, float64:
		return true
	default:
		return false
	}
}
