package rules

import (
	"fmt"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"rca/internal/rca/logging"
	"rca/internal/rca/util"
)

type scoredMatch struct {
	Severity     int
	MatchedCount int
	Signal       map[string]any
}

// RuleEngine evaluates events against a rule set.
type RuleEngine struct {
	vendorAnchorEnforcementEnabled bool
	logger                         logging.Logger
}

// NewRuleEngine builds a rule engine with optional vendor-anchor enforcement.
func NewRuleEngine(vendorAnchorEnforcementEnabled bool) *RuleEngine {
	return &RuleEngine{
		vendorAnchorEnforcementEnabled: vendorAnchorEnforcementEnabled,
		logger:                         logging.GetLogger("RuleEngine"),
	}
}

// Evaluate returns all matched signals for the event.
func (e *RuleEngine) Evaluate(event map[string]any, ruleSet *RuleSet, maxSignals int, highestOnly bool) []map[string]any {
	if ruleSet == nil {
		return []map[string]any{}
	}

	scoredMatches := make([]scoredMatch, 0)
	vendorSnapshot := e.buildVendorSnapshot(event)
	for _, rule := range ruleSet.Rules {
		matched, matchedCount := e.matchesRule(event, rule, vendorSnapshot)
		if !matched {
			continue
		}
		scoredMatches = append(scoredMatches, scoredMatch{
			Severity:     severityRank(rule.Level),
			MatchedCount: matchedCount,
			Signal: map[string]any{
				"rule_id":                 rule.RuleID,
				"signal":                  rule.SignalKey,
				"level":                   rule.Level,
				"description":             rule.Description,
				"service":                 ruleSet.Service,
				"tags":                    append([]string{}, rule.Tags...),
				"matched_at":              util.FormatUTCISO(time.Now().UTC()),
				"matched_condition_count": matchedCount,
			},
		})
	}

	if len(scoredMatches) == 0 {
		return []map[string]any{}
	}

	scoredMatches = preferSpecificMatches(scoredMatches)
	if highestOnly {
		bestSeverity := 0
		for _, item := range scoredMatches {
			if item.Severity > bestSeverity {
				bestSeverity = item.Severity
			}
		}

		filtered := make([]scoredMatch, 0, len(scoredMatches))
		for _, item := range scoredMatches {
			if item.Severity == bestSeverity {
				filtered = append(filtered, item)
			}
		}
		scoredMatches = filtered
	}

	sort.Slice(scoredMatches, func(i, j int) bool {
		left := scoredMatches[i]
		right := scoredMatches[j]
		if left.Severity != right.Severity {
			return left.Severity > right.Severity
		}
		if left.MatchedCount != right.MatchedCount {
			return left.MatchedCount > right.MatchedCount
		}
		return fmt.Sprint(left.Signal["rule_id"]) > fmt.Sprint(right.Signal["rule_id"])
	})

	signals := make([]map[string]any, 0, len(scoredMatches))
	for _, item := range scoredMatches {
		signals = append(signals, item.Signal)
	}
	if maxSignals > 0 && len(signals) > maxSignals {
		return signals[:maxSignals]
	}
	return signals
}

func (e *RuleEngine) buildVendorSnapshot(event map[string]any) (snapshot VendorAnchorSnapshot) {
	defer func() {
		if recovered := recover(); recovered != nil {
			e.logger.Exception(
				"Failed building vendor anchor snapshot; continuing without anchors",
				fmt.Errorf("%v", recovered),
			)
			snapshot = VendorAnchorSnapshot{}
		}
	}()
	return VendorAnchorSnapshotFromEvent(event)
}

func preferSpecificMatches(scoredMatches []scoredMatch) []scoredMatch {
	hasNonFallback := false
	for _, item := range scoredMatches {
		if !isFallbackSignal(item.Signal) {
			hasNonFallback = true
			break
		}
	}
	if !hasNonFallback {
		return scoredMatches
	}

	filtered := make([]scoredMatch, 0, len(scoredMatches))
	for _, item := range scoredMatches {
		if !isFallbackSignal(item.Signal) {
			filtered = append(filtered, item)
		}
	}
	return filtered
}

func isFallbackSignal(signal map[string]any) bool {
	switch tags := signal["tags"].(type) {
	case []string:
		if containsFallbackTag(tags) {
			return true
		}
	case []any:
		items := make([]string, 0, len(tags))
		for _, tag := range tags {
			items = append(items, fmt.Sprint(tag))
		}
		if containsFallbackTag(items) {
			return true
		}
	}

	signalKey := strings.TrimSpace(strings.ToLower(fmt.Sprint(signal["signal"])))
	return strings.HasSuffix(signalKey, "_unclassified_failure")
}

func containsFallbackTag(tags []string) bool {
	for _, rawTag := range tags {
		tag := strings.TrimSpace(strings.ToLower(rawTag))
		if tag == "fallback" || tag == "unclassified" {
			return true
		}
	}
	return false
}

func (e *RuleEngine) matchesRule(event map[string]any, rule SignalRule, vendorSnapshot VendorAnchorSnapshot) (bool, int) {
	if e.vendorAnchorEnforcementEnabled && vendorSnapshot.HasStrictHints() {
		vendor := InferRuleVendor(rule.Tags)
		if vendor != "" && !vendorSnapshot.MatchesVendor(vendor) {
			return false, 0
		}
	}
	if rule.Condition == nil {
		return false, 0
	}
	return e.matchesNode(event, rule.Condition)
}

func (e *RuleEngine) matchesNode(event map[string]any, node ConditionNode) (bool, int) {
	switch typed := node.(type) {
	case RuleConditionGroup:
		return e.matchesGroup(event, typed)
	case *RuleConditionGroup:
		return e.matchesGroup(event, *typed)
	case RuleCondition:
		matched := matchesCondition(event, typed)
		if matched {
			return true, 1
		}
		return false, 0
	case *RuleCondition:
		matched := matchesCondition(event, *typed)
		if matched {
			return true, 1
		}
		return false, 0
	default:
		return false, 0
	}
}

func (e *RuleEngine) matchesGroup(event map[string]any, group RuleConditionGroup) (bool, int) {
	if len(group.Conditions) == 0 {
		return false, 0
	}

	outcomes := make([][2]int, 0, len(group.Conditions))
	for _, child := range group.Conditions {
		matched, count := e.matchesNode(event, child)
		if matched {
			outcomes = append(outcomes, [2]int{1, count})
		} else {
			outcomes = append(outcomes, [2]int{0, count})
		}
	}

	if strings.EqualFold(group.Op, "or") {
		maxCount := 0
		hasMatch := false
		for _, outcome := range outcomes {
			if outcome[0] == 1 {
				hasMatch = true
				if outcome[1] > maxCount {
					maxCount = outcome[1]
				}
			}
		}
		if !hasMatch {
			return false, 0
		}
		return true, maxCount
	}

	total := 0
	for _, outcome := range outcomes {
		if outcome[0] != 1 {
			return false, 0
		}
		total += outcome[1]
	}
	return true, total
}

func matchesCondition(event map[string]any, condition RuleCondition) bool {
	value := util.GetNested(event, condition.Field)
	op := strings.ToLower(condition.Op)

	switch op {
	case "exists":
		return value != nil
	case "equals":
		return valuesEqual(value, condition.Value)
	case "not_equals":
		return !valuesEqual(value, condition.Value)
	case "contains":
		return contains(value, condition.Value, condition.CaseSensitive)
	case "not_contains":
		return !contains(value, condition.Value, condition.CaseSensitive)
	case "regex":
		return regexMatch(value, condition.Value, condition.CaseSensitive)
	case "not_regex":
		return !regexMatch(value, condition.Value, condition.CaseSensitive)
	case "in":
		return inList(value, condition.Value)
	case "not_in":
		return !inList(value, condition.Value)
	case "gt", "gte", "lt", "lte":
		return compareNumeric(value, condition.Value, op)
	default:
		return false
	}
}

func contains(left any, right any, caseSensitive bool) bool {
	if left == nil {
		return false
	}
	leftText := fmt.Sprint(left)
	rightText := fmt.Sprint(right)
	if caseSensitive {
		return strings.Contains(leftText, rightText)
	}
	return strings.Contains(strings.ToLower(leftText), strings.ToLower(rightText))
}

func regexMatch(left any, pattern any, caseSensitive bool) bool {
	if left == nil {
		return false
	}
	patternText := fmt.Sprint(pattern)
	if !caseSensitive {
		patternText = "(?i)" + patternText
	}
	re, err := regexp.Compile(patternText)
	if err != nil {
		return false
	}
	return re.FindStringIndex(fmt.Sprint(left)) != nil
}

func inList(value any, haystack any) bool {
	items, ok := haystack.([]any)
	if !ok {
		return false
	}
	for _, item := range items {
		if valuesEqual(value, item) {
			return true
		}
	}
	return false
}

func compareNumeric(left any, right any, op string) bool {
	leftFloat, ok := asFloat(left)
	if !ok {
		return false
	}
	rightFloat, ok := asFloat(right)
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
}

func valuesEqual(left any, right any) bool {
	leftFloat, leftNumeric := asFloat(left)
	rightFloat, rightNumeric := asFloat(right)
	if leftNumeric && rightNumeric {
		return leftFloat == rightFloat
	}
	return reflect.DeepEqual(left, right)
}

func asFloat(value any) (float64, bool) {
	switch typed := value.(type) {
	case int:
		return float64(typed), true
	case int8:
		return float64(typed), true
	case int16:
		return float64(typed), true
	case int32:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case uint:
		return float64(typed), true
	case uint8:
		return float64(typed), true
	case uint16:
		return float64(typed), true
	case uint32:
		return float64(typed), true
	case uint64:
		return float64(typed), true
	case float32:
		return float64(typed), true
	case float64:
		return typed, true
	case string:
		parsed, err := strconv.ParseFloat(typed, 64)
		if err != nil {
			return 0, false
		}
		return parsed, true
	default:
		return 0, false
	}
}

func severityRank(level string) int {
	switch strings.ToLower(level) {
	case "critical":
		return 3
	case "warning":
		return 2
	case "info":
		return 1
	default:
		return 0
	}
}
