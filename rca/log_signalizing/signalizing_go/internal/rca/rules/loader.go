package rules

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"rca/internal/rca/logging"
	"rca/internal/rca/util"
)

type dependencyEntry struct {
	Path    string
	MTimeNS int64
}

type cachedRuleSet struct {
	Signature []dependencyEntry
	RuleSet   *RuleSet
}

// RuleLoader reads YAML files, validates them, and caches by dependency mtime.
type RuleLoader struct {
	rulesDirectory string
	validator      RuleSchemaValidator
	cache          map[string]cachedRuleSet
	logger         logging.Logger
}

// NewRuleLoader creates one rule loader rooted at a rules directory.
func NewRuleLoader(rulesDirectory string) *RuleLoader {
	return &RuleLoader{
		rulesDirectory: rulesDirectory,
		validator:      RuleSchemaValidator{},
		cache:          make(map[string]cachedRuleSet),
		logger:         logging.GetLogger("RuleLoader"),
	}
}

// Load reads one service rule file, using cache when dependencies are unchanged.
func (l *RuleLoader) Load(service string, fileName string) (*RuleSet, error) {
	path, err := l.resolveRulePath(filepath.Join(l.rulesDirectory, fileName))
	if err != nil {
		return nil, err
	}

	signature, err := l.dependencySignature(path, map[string]bool{}, nil)
	if err != nil {
		return nil, err
	}

	if cached, ok := l.cache[path]; ok && reflect.DeepEqual(cached.Signature, signature) {
		l.logger.Debug(
			"Using cached rules",
			logging.F("service", service),
			logging.F("rule_file", path),
		)
		return cached.RuleSet, nil
	}

	ruleSet, err := l.loadUncached(path, service)
	if err != nil {
		return nil, err
	}

	l.cache[path] = cachedRuleSet{Signature: signature, RuleSet: ruleSet}
	l.logger.Info(
		"Rule file loaded",
		logging.F("service", ruleSet.Service),
		logging.F("rule_file", path),
		logging.F("rule_count", len(ruleSet.Rules)),
		logging.F("from_cache", false),
		logging.F("dependency_count", len(signature)),
	)
	return ruleSet, nil
}

func (l *RuleLoader) loadUncached(path string, service string) (*RuleSet, error) {
	rawRoot, err := l.readPayload(path, service)
	if err != nil {
		return nil, err
	}

	rootService := service
	if rawService, ok := rawRoot["service"]; ok {
		rootService = fmt.Sprint(rawService)
	}

	rules, err := l.loadRulesRecursive(path, rootService, map[string]bool{}, nil)
	if err != nil {
		return nil, err
	}
	if err := validateDuplicateRuleIDs(rules, path); err != nil {
		return nil, err
	}
	return &RuleSet{
		Service:             rootService,
		Rules:               rules,
		HasVendorAwareRules: hasVendorAwareRules(rules),
	}, nil
}

func (l *RuleLoader) loadRulesRecursive(path string, service string, visiting map[string]bool, stack []string) ([]SignalRule, error) {
	if visiting[path] {
		chain := strings.Join(append(append([]string{}, stack...), path), " -> ")
		return nil, fmt.Errorf("Circular rule imports detected: %s", chain)
	}
	visiting[path] = true
	stack = append(stack, path)
	defer delete(visiting, path)

	raw, err := l.readPayload(path, service)
	if err != nil {
		return nil, err
	}

	serviceName := service
	if rawService, ok := raw["service"]; ok {
		serviceName = fmt.Sprint(rawService)
	}

	loadedRules := make([]SignalRule, 0)
	rulesRaw, _ := raw["rules"].([]any)
	for _, itemRaw := range rulesRaw {
		item, ok := itemRaw.(map[string]any)
		if !ok {
			continue
		}

		condition, err := l.parseRuleCondition(item)
		if err != nil {
			l.logger.Exception(
				"Rule parsing failed",
				err,
				logging.F("service", serviceName),
				logging.F("rule_file", path),
			)
			return nil, err
		}

		loadedRules = append(loadedRules, SignalRule{
			RuleID:      fmt.Sprint(item["id"]),
			SignalKey:   fmt.Sprint(item["signal_key"]),
			Level:       fmt.Sprint(item["level"]),
			Description: defaultString(item["description"], fmt.Sprint(item["id"])),
			Condition:   compileConditionNode(condition),
			Tags:        stringSlice(item["tags"]),
			Vendor:      InferRuleVendor(stringSlice(item["tags"])),
		})
	}

	if importsRaw, ok := raw["imports"]; ok {
		imports, ok := importsRaw.([]any)
		if !ok {
			return nil, fmt.Errorf("%s: imports must be a list of file paths", path)
		}
		for _, importEntry := range imports {
			importRef, ok := importEntry.(string)
			if !ok {
				return nil, fmt.Errorf("%s: imports must be a list of file paths", path)
			}
			importPath, err := l.resolveImportPath(path, importRef)
			if err != nil {
				return nil, err
			}
			childRules, err := l.loadRulesRecursive(importPath, serviceName, visiting, stack)
			if err != nil {
				return nil, err
			}
			loadedRules = append(loadedRules, childRules...)
		}
	}

	return loadedRules, nil
}

func (l *RuleLoader) readPayload(path string, service string) (map[string]any, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		l.logger.Exception(
			"Failed reading rule file",
			err,
			logging.F("service", service),
			logging.F("rule_file", path),
		)
		return nil, err
	}

	var raw map[string]any
	if err := yaml.Unmarshal(content, &raw); err != nil {
		l.logger.Exception(
			"Failed reading rule file",
			err,
			logging.F("service", service),
			logging.F("rule_file", path),
		)
		return nil, err
	}

	if raw == nil {
		return nil, fmt.Errorf("Rule file must contain mapping: %s", path)
	}

	if err := l.validator.Validate(raw, path); err != nil {
		l.logger.Exception(
			"Rule schema validation failed",
			err,
			logging.F("service", service),
			logging.F("rule_file", path),
		)
		return nil, err
	}
	return raw, nil
}

func (l *RuleLoader) dependencySignature(path string, visiting map[string]bool, stack []string) ([]dependencyEntry, error) {
	if visiting[path] {
		chain := strings.Join(append(append([]string{}, stack...), path), " -> ")
		return nil, fmt.Errorf("Circular rule imports detected: %s", chain)
	}
	visiting[path] = true
	stack = append(stack, path)
	defer delete(visiting, path)

	raw, err := l.readPayload(path, "dependency-scan")
	if err != nil {
		return nil, err
	}

	deps := map[string]int64{}
	mtimeNS, err := getMTimeNS(path)
	if err != nil {
		return nil, err
	}
	deps[path] = mtimeNS

	if importsRaw, ok := raw["imports"]; ok {
		imports, ok := importsRaw.([]any)
		if !ok {
			return nil, fmt.Errorf("%s: imports must be a list of file paths", path)
		}
		for _, importEntry := range imports {
			importRef, ok := importEntry.(string)
			if !ok {
				return nil, fmt.Errorf("%s: imports must be a list of file paths", path)
			}
			importPath, err := l.resolveImportPath(path, importRef)
			if err != nil {
				return nil, err
			}
			childSignature, err := l.dependencySignature(importPath, visiting, stack)
			if err != nil {
				return nil, err
			}
			for _, item := range childSignature {
				deps[item.Path] = item.MTimeNS
			}
		}
	}

	signature := make([]dependencyEntry, 0, len(deps))
	for depPath, depMTime := range deps {
		signature = append(signature, dependencyEntry{Path: depPath, MTimeNS: depMTime})
	}
	sort.Slice(signature, func(i, j int) bool {
		return signature[i].Path < signature[j].Path
	})
	return signature, nil
}

func getMTimeNS(path string) (int64, error) {
	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, fmt.Errorf("Rule file not found: %s", path)
		}
		return 0, err
	}
	return info.ModTime().UnixNano(), nil
}

func (l *RuleLoader) parseRuleCondition(ruleRaw map[string]any) (ConditionNode, error) {
	nodeRaw, ok := ruleRaw["condition"].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("rule condition must be an object")
	}
	return l.parseConditionNode(nodeRaw)
}

func (l *RuleLoader) resolveImportPath(parentPath string, importRef string) (string, error) {
	resolved, err := l.resolveRulePath(filepath.Join(filepath.Dir(parentPath), importRef))
	if err != nil {
		return "", err
	}
	if resolved == parentPath {
		return "", fmt.Errorf("%s: imports must not reference itself", parentPath)
	}
	return resolved, nil
}

func (l *RuleLoader) resolveRulePath(path string) (string, error) {
	resolved, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	rulesRoot, err := filepath.Abs(l.rulesDirectory)
	if err != nil {
		return "", err
	}
	rel, err := filepath.Rel(rulesRoot, resolved)
	if err != nil {
		return "", err
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return "", fmt.Errorf("Rule file path escapes rules directory: %s", path)
	}
	return resolved, nil
}

func validateDuplicateRuleIDs(rules []SignalRule, rootPath string) error {
	seen := map[string]bool{}
	duplicates := map[string]bool{}
	for _, rule := range rules {
		if seen[rule.RuleID] {
			duplicates[rule.RuleID] = true
		}
		seen[rule.RuleID] = true
	}
	if len(duplicates) == 0 {
		return nil
	}
	duplicateIDs := make([]string, 0, len(duplicates))
	for ruleID := range duplicates {
		duplicateIDs = append(duplicateIDs, ruleID)
	}
	sort.Strings(duplicateIDs)
	return fmt.Errorf("%s: duplicate rule id(s) detected: %s", rootPath, strings.Join(duplicateIDs, ", "))
}

func (l *RuleLoader) parseConditionNode(nodeRaw map[string]any) (ConditionNode, error) {
	if andRaw, ok := nodeRaw["and"]; ok {
		childrenRaw, _ := andRaw.([]any)
		children := make([]ConditionNode, 0, len(childrenRaw))
		for _, childRaw := range childrenRaw {
			childMap, ok := childRaw.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("condition child must be an object")
			}
			child, err := l.parseConditionNode(childMap)
			if err != nil {
				return nil, err
			}
			children = append(children, child)
		}
		return RuleConditionGroup{Op: "and", Conditions: children}, nil
	}
	if orRaw, ok := nodeRaw["or"]; ok {
		childrenRaw, _ := orRaw.([]any)
		children := make([]ConditionNode, 0, len(childrenRaw))
		for _, childRaw := range childrenRaw {
			childMap, ok := childRaw.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("condition child must be an object")
			}
			child, err := l.parseConditionNode(childMap)
			if err != nil {
				return nil, err
			}
			children = append(children, child)
		}
		return RuleConditionGroup{Op: "or", Conditions: children}, nil
	}
	return RuleCondition{
		Field:         fmt.Sprint(nodeRaw["field"]),
		Op:            fmt.Sprint(nodeRaw["op"]),
		Value:         nodeRaw["value"],
		CaseSensitive: boolValue(nodeRaw["case_sensitive"]),
	}, nil
}

func compileConditionNode(node ConditionNode) ConditionNode {
	switch typed := node.(type) {
	case RuleCondition:
		return compileLeafCondition(typed)
	case *RuleCondition:
		return compileLeafCondition(*typed)
	case RuleConditionGroup:
		children := make([]ConditionNode, 0, len(typed.Conditions))
		for _, child := range typed.Conditions {
			children = append(children, compileConditionNode(child))
		}
		group := compiledConditionGroup{
			Op:         strings.ToLower(strings.TrimSpace(typed.Op)),
			Conditions: children,
		}
		orderConditionGroup(&group)
		group.MaxMatchCount = maxMatchCountForGroup(group.Op, group.Conditions)
		group.Cost = estimatedCostForGroup(group.Op, group.Conditions)
		return group
	case *RuleConditionGroup:
		return compileConditionNode(*typed)
	default:
		return node
	}
}

func compileLeafCondition(condition RuleCondition) ConditionNode {
	matcher, cost := buildValueMatcher(
		strings.ToLower(strings.TrimSpace(condition.Op)),
		condition.Value,
		condition.CaseSensitive,
	)
	getter := buildFieldGetter(strings.TrimSpace(condition.Field))
	return compiledCondition{
		Field: strings.TrimSpace(condition.Field),
		Matches: func(event map[string]any) bool {
			return matcher(getter(event))
		},
		Cost: cost,
	}
}

func buildFieldGetter(field string) func(map[string]any) any {
	if field == "" {
		return func(map[string]any) any { return nil }
	}
	if !strings.Contains(field, ".") {
		return func(event map[string]any) any {
			if event == nil {
				return nil
			}
			return event[field]
		}
	}
	parts := strings.Split(field, ".")
	return func(event map[string]any) any {
		return util.GetNestedPath(event, parts)
	}
}

func buildValueMatcher(op string, value any, caseSensitive bool) (func(any) bool, int) {
	switch op {
	case "exists":
		return func(left any) bool { return left != nil }, 1
	case "equals":
		return func(left any) bool { return valuesEqual(left, value) }, 2
	case "not_equals":
		return func(left any) bool { return !valuesEqual(left, value) }, 2
	case "contains":
		return buildContainsMatcher(value, caseSensitive), 5
	case "not_contains":
		base := buildContainsMatcher(value, caseSensitive)
		return func(left any) bool { return !base(left) }, 5
	case "regex":
		return buildRegexValueMatcher(value, caseSensitive)
	case "not_regex":
		base, cost := buildRegexValueMatcher(value, caseSensitive)
		return func(left any) bool { return !base(left) }, cost
	case "in":
		return buildInListMatcher(value), 2
	case "not_in":
		base := buildInListMatcher(value)
		return func(left any) bool { return !base(left) }, 2
	case "gt", "gte", "lt", "lte":
		rightFloat, ok := asFloat(value)
		if !ok {
			return func(any) bool { return false }, 3
		}
		return func(left any) bool {
			leftFloat, ok := asFloat(left)
			if !ok {
				return false
			}
			switch op {
			case "gt":
				return leftFloat > rightFloat
			case "gte":
				return leftFloat >= rightFloat
			case "lt":
				return leftFloat < rightFloat
			default:
				return leftFloat <= rightFloat
			}
		}, 3
	default:
		return func(any) bool { return false }, 10
	}
}

func buildContainsMatcher(value any, caseSensitive bool) func(any) bool {
	rightText := fmt.Sprint(value)
	if caseSensitive {
		return func(left any) bool {
			if left == nil {
				return false
			}
			return strings.Contains(fmt.Sprint(left), rightText)
		}
	}
	needle := strings.ToLower(rightText)
	return func(left any) bool {
		if left == nil {
			return false
		}
		return strings.Contains(strings.ToLower(fmt.Sprint(left)), needle)
	}
}

func buildRegexValueMatcher(value any, caseSensitive bool) (func(any) bool, int) {
	pattern := fmt.Sprint(value)
	if exact, ok := exactRegexLiteral(pattern); ok {
		if caseSensitive {
			return func(left any) bool {
				if left == nil {
					return false
				}
				return fmt.Sprint(left) == exact
			}, 2
		}
		return func(left any) bool {
			if left == nil {
				return false
			}
			return strings.EqualFold(fmt.Sprint(left), exact)
		}, 2
	}

	if literals, ok := simpleAlternationLiterals(pattern); ok {
		return buildContainsAnyMatcher(literals, caseSensitive), 4
	}

	if literal, ok := plainRegexLiteral(pattern); ok {
		return buildContainsMatcher(literal, caseSensitive), 5
	}

	compiledPattern := pattern
	if !caseSensitive {
		compiledPattern = "(?i)" + compiledPattern
	}
	re, err := regexp.Compile(compiledPattern)
	if err != nil {
		return func(any) bool { return false }, 9
	}
	return func(left any) bool {
		if left == nil {
			return false
		}
		return re.FindStringIndex(fmt.Sprint(left)) != nil
	}, 9
}

func buildContainsAnyMatcher(literals []string, caseSensitive bool) func(any) bool {
	if caseSensitive {
		values := append([]string{}, literals...)
		return func(left any) bool {
			if left == nil {
				return false
			}
			text := fmt.Sprint(left)
			for _, literal := range values {
				if strings.Contains(text, literal) {
					return true
				}
			}
			return false
		}
	}
	values := make([]string, 0, len(literals))
	for _, literal := range literals {
		values = append(values, strings.ToLower(literal))
	}
	return func(left any) bool {
		if left == nil {
			return false
		}
		text := strings.ToLower(fmt.Sprint(left))
		for _, literal := range values {
			if strings.Contains(text, literal) {
				return true
			}
		}
		return false
	}
}

func buildInListMatcher(value any) func(any) bool {
	items, ok := value.([]any)
	if !ok {
		return func(any) bool { return false }
	}

	numericSet := make(map[float64]struct{})
	exactItems := make([]any, 0, len(items))
	for _, item := range items {
		if numericValue, ok := asFloat(item); ok {
			numericSet[numericValue] = struct{}{}
			continue
		}
		exactItems = append(exactItems, item)
	}

	return func(left any) bool {
		if len(numericSet) > 0 {
			if numericValue, ok := asFloat(left); ok {
				if _, exists := numericSet[numericValue]; exists {
					return true
				}
			}
		}
		for _, item := range exactItems {
			if valuesEqual(left, item) {
				return true
			}
		}
		return false
	}
}

func exactRegexLiteral(pattern string) (string, bool) {
	if len(pattern) < 2 || pattern[0] != '^' || pattern[len(pattern)-1] != '$' {
		return "", false
	}
	body := pattern[1 : len(pattern)-1]
	if body == "" || hasRegexMeta(body) {
		return "", false
	}
	return body, true
}

func plainRegexLiteral(pattern string) (string, bool) {
	if pattern == "" || hasRegexMeta(pattern) {
		return "", false
	}
	return pattern, true
}

func simpleAlternationLiterals(pattern string) ([]string, bool) {
	body := ""
	switch {
	case strings.HasPrefix(pattern, "(?:") && strings.HasSuffix(pattern, ")"):
		body = pattern[3 : len(pattern)-1]
	case strings.HasPrefix(pattern, "(") && strings.HasSuffix(pattern, ")"):
		body = pattern[1 : len(pattern)-1]
	default:
		return nil, false
	}

	parts := make([]string, 0)
	current := strings.Builder{}
	escaped := false
	for _, char := range body {
		switch {
		case escaped:
			return nil, false
		case char == '\\':
			escaped = true
		case char == '|':
			part := current.String()
			if part == "" || hasRegexMeta(part) {
				return nil, false
			}
			parts = append(parts, part)
			current.Reset()
		default:
			current.WriteRune(char)
		}
	}
	if escaped {
		return nil, false
	}
	part := current.String()
	if part == "" || hasRegexMeta(part) {
		return nil, false
	}
	parts = append(parts, part)
	return parts, true
}

func hasRegexMeta(value string) bool {
	return strings.ContainsAny(value, `.^$*+?()[]{}\|`)
}

func orderConditionGroup(group *compiledConditionGroup) {
	if len(group.Conditions) < 2 {
		return
	}
	if group.Op == "or" {
		sort.SliceStable(group.Conditions, func(i int, j int) bool {
			leftMax := maxMatchCountForNode(group.Conditions[i])
			rightMax := maxMatchCountForNode(group.Conditions[j])
			if leftMax != rightMax {
				return leftMax > rightMax
			}
			return estimatedCostForNode(group.Conditions[i]) < estimatedCostForNode(group.Conditions[j])
		})
		return
	}
	sort.SliceStable(group.Conditions, func(i int, j int) bool {
		leftCost := estimatedCostForNode(group.Conditions[i])
		rightCost := estimatedCostForNode(group.Conditions[j])
		if leftCost != rightCost {
			return leftCost < rightCost
		}
		return maxMatchCountForNode(group.Conditions[i]) < maxMatchCountForNode(group.Conditions[j])
	})
}

func estimatedCostForNode(node ConditionNode) int {
	switch typed := node.(type) {
	case compiledCondition:
		return typed.Cost
	case *compiledCondition:
		return typed.Cost
	case compiledConditionGroup:
		return typed.Cost
	case *compiledConditionGroup:
		return typed.Cost
	case RuleCondition:
		return fallbackLeafCost(strings.TrimSpace(typed.Field), strings.ToLower(strings.TrimSpace(typed.Op)))
	case *RuleCondition:
		return fallbackLeafCost(strings.TrimSpace(typed.Field), strings.ToLower(strings.TrimSpace(typed.Op)))
	case RuleConditionGroup:
		return estimatedCostForGroup(strings.ToLower(strings.TrimSpace(typed.Op)), typed.Conditions)
	case *RuleConditionGroup:
		return estimatedCostForGroup(strings.ToLower(strings.TrimSpace(typed.Op)), typed.Conditions)
	default:
		return 10
	}
}

func estimatedCostForGroup(op string, children []ConditionNode) int {
	if len(children) == 0 {
		return 10
	}
	if op == "or" {
		best := estimatedCostForNode(children[0])
		for _, child := range children[1:] {
			if cost := estimatedCostForNode(child); cost < best {
				best = cost
			}
		}
		return best + 1
	}
	total := 1
	for _, child := range children {
		total += estimatedCostForNode(child)
	}
	return total
}

func maxMatchCountForNode(node ConditionNode) int {
	switch typed := node.(type) {
	case compiledCondition, *compiledCondition, RuleCondition, *RuleCondition:
		return 1
	case compiledConditionGroup:
		return typed.MaxMatchCount
	case *compiledConditionGroup:
		return typed.MaxMatchCount
	case RuleConditionGroup:
		return maxMatchCountForGroup(strings.ToLower(strings.TrimSpace(typed.Op)), typed.Conditions)
	case *RuleConditionGroup:
		return maxMatchCountForGroup(strings.ToLower(strings.TrimSpace(typed.Op)), typed.Conditions)
	default:
		return 0
	}
}

func maxMatchCountForGroup(op string, children []ConditionNode) int {
	if len(children) == 0 {
		return 0
	}
	if op == "or" {
		best := 0
		for _, child := range children {
			if count := maxMatchCountForNode(child); count > best {
				best = count
			}
		}
		return best
	}
	total := 0
	for _, child := range children {
		total += maxMatchCountForNode(child)
	}
	return total
}

func fallbackLeafCost(field string, op string) int {
	cost := 5
	switch op {
	case "exists":
		cost = 1
	case "equals", "not_equals", "in", "not_in":
		cost = 2
	case "gt", "gte", "lt", "lte":
		cost = 3
	case "contains", "not_contains":
		cost = 5
	case "regex", "not_regex":
		cost = 9
	}
	normalizedField := strings.ToLower(field)
	if normalizedField == "message" || normalizedField == "msg" || strings.HasSuffix(normalizedField, ".message") || normalizedField == "event.original" {
		cost += 2
	}
	return cost
}

func hasVendorAwareRules(rules []SignalRule) bool {
	for _, rule := range rules {
		if rule.Vendor != "" || InferRuleVendor(rule.Tags) != "" {
			return true
		}
	}
	return false
}

func defaultString(value any, fallback string) string {
	if value == nil {
		return fallback
	}
	return fmt.Sprint(value)
}

func stringSlice(value any) []string {
	switch typed := value.(type) {
	case nil:
		return []string{}
	case []string:
		return append([]string{}, typed...)
	case []any:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			out = append(out, fmt.Sprint(item))
		}
		return out
	default:
		return []string{}
	}
}

func boolValue(value any) bool {
	typed, ok := value.(bool)
	return ok && typed
}
