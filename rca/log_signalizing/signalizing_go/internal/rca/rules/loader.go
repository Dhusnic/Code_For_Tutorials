package rules

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"rca/internal/rca/logging"
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
	return &RuleSet{Service: rootService, Rules: rules}, nil
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
			Condition:   condition,
			Tags:        stringSlice(item["tags"]),
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
