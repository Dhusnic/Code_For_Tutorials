package engine

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log/slog"
	"sort"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"
	"log_correlation_engine/internal/utils"
)

type Correlator interface {
	Correlate(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error)
}

type Engine struct {
	logger        *slog.Logger
	defaultWindow time.Duration
	defaultMaxGap time.Duration

	metricsMu sync.Mutex
	metrics   *EngineMetrics

	compiledMu sync.RWMutex
	compiled   map[string]compiledRule
}

type EngineMetrics struct {
	TotalLogsProcessed int64
	TotalRulesMatched  int64
	ProcessingTimeMS   int64
}

type sequenceMatch struct {
	logs         []models.FullLog
	stepLogs     [][]models.FullLog
	stepMatches  []int
	matchedSteps int
}

type stepMode int

const (
	stepModeAllOf stepMode = iota
	stepModeAnyOf
)

type compiledRule struct {
	cacheKey         string
	rule             models.Rule
	groupByCacheKey  string
	window           time.Duration
	maxGap           time.Duration
	maxGapEnabled    bool
	requiredMetadata map[string]string
	steps            []compiledStep
	firstSignalKeys  []string
	negativeSignals  map[string]struct{}
	dedupWindow      time.Duration
}

type compiledSelector struct {
	signalKey  string
	signalKeys map[string]struct{}
	minCount   int
}

type compiledStep struct {
	signalKey string
	mode      stepMode
	selectors []compiledSelector
	minCount  int
	within    time.Duration
}

type stepMatchResult struct {
	logs          []models.FullLog
	matchedCount  int
	complete      bool
	nextIndex     int
	lastMatchedAt time.Time
	canceled      bool
}

const correlationSchemaVersion = 2

type signalIndex map[string][]int

type logGroup struct {
	groupByValues map[string]string
	logs          []models.FullLog
}

func NewEngine(cfg config.EngineConfig, logger *slog.Logger) (*Engine, error) {
	if cfg.DefaultWindow <= 0 {
		return nil, fmt.Errorf("default window must be greater than zero")
	}
	if cfg.DefaultMaxGap <= 0 {
		return nil, fmt.Errorf("default max gap must be greater than zero")
	}

	return &Engine{
		logger:        logger,
		defaultWindow: cfg.DefaultWindow,
		defaultMaxGap: cfg.DefaultMaxGap,
		metrics:       &EngineMetrics{},
		compiled:      make(map[string]compiledRule),
	}, nil
}

func (e *Engine) Correlate(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error) {
	started := time.Now()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if len(logs) == 0 || len(rules) == 0 {
		return []models.CorrelationResult{}, nil
	}

	compiledRules := e.compileRulesForOrg(orgID, rules)
	if len(compiledRules) == 0 {
		return []models.CorrelationResult{}, nil
	}

	sortedLogs := append([]models.FullLog(nil), logs...)
	sort.Slice(sortedLogs, func(i, j int) bool {
		return sortedLogs[i].Timestamp.Before(sortedLogs[j].Timestamp)
	})

	results := make([]models.CorrelationResult, 0)
	groupCount := 0
	groupCache := make(map[string][]*logGroup)

	for _, rule := range compiledRules {
		logGroups, ok := groupCache[rule.groupByCacheKey]
		if !ok {
			filteredLogs := e.filterLogsForRule(sortedLogs, rule)
			logGroups = e.groupLogs(filteredLogs, rule.rule.GroupBy)
			groupCache[rule.groupByCacheKey] = logGroups
			groupCount += len(logGroups)
		}

		for _, group := range logGroups {
			if err := ctx.Err(); err != nil {
				return nil, err
			}

			result, err := e.correlateGroup(ctx, rule, group)
			if err != nil {
				if e.logger != nil {
					e.logger.Warn("failed to correlate rule against group", "rule_id", rule.rule.ID, "error", err)
				}
				continue
			}
			if result != nil {
				results = append(results, *result)
			}
		}
	}

	results, suppressedOverlaps := resolveResultConflicts(results)
	sortResults(results)
	e.recordMetrics(len(logs), len(results), time.Since(started))

	if e.logger != nil {
		e.logger.Info(
			"correlation completed",
			"organization", orgID,
			"logs", len(logs),
			"rules", len(compiledRules),
			"groups", groupCount,
			"results", len(results),
			"suppressed_overlaps", suppressedOverlaps,
			"processing_time_ms", time.Since(started).Milliseconds(),
		)
	}

	return results, nil
}

func (e *Engine) correlateGroup(ctx context.Context, rule compiledRule, group *logGroup) (*models.CorrelationResult, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	deduped := e.deduplicate(group.logs, rule.rule.Deduplication.Key, rule.dedupWindow)
	if len(deduped) == 0 {
		return nil, nil
	}

	match := e.slidingWindowMatchCompiled(deduped, buildSignalIndex(deduped), rule)
	if len(match.logs) == 0 {
		return nil, nil
	}

	ruleCompletion, sequenceMatch := calculateCompiledMatchStats(match, rule)
	return &models.CorrelationResult{
		SchemaVersion:  correlationSchemaVersion,
		LogID:          extractResultLogs(match.logs),
		RuleCompletion: ruleCompletion,
		RuleID:         rule.rule.ID,
		SequenceMatch:  sequenceMatch,
		OrganizationID: rule.rule.OrganizationID,
		Priority:       rule.rule.Priority,
		GroupByValues:  cloneGroupByValues(group.groupByValues),
		MatchedAt:      latestMatchTime(match.logs),
		Audit:          buildMatchAudit(rule, group.groupByValues, match),
	}, nil
}

func (e *Engine) slidingWindowMatch(logs []models.FullLog, rule models.Rule) sequenceMatch {
	compiled, ok := e.compileRule(rule)
	if !ok {
		return sequenceMatch{}
	}

	sortedLogs := append([]models.FullLog(nil), logs...)
	sort.Slice(sortedLogs, func(i, j int) bool {
		return sortedLogs[i].Timestamp.Before(sortedLogs[j].Timestamp)
	})

	return e.slidingWindowMatchCompiled(sortedLogs, buildSignalIndex(sortedLogs), compiled)
}

func (e *Engine) slidingWindowMatchCompiled(logs []models.FullLog, index signalIndex, rule compiledRule) sequenceMatch {
	if len(rule.steps) == 0 {
		return sequenceMatch{}
	}

	firstSignalPositions := collectFirstSignalPositions(index, rule.firstSignalKeys)
	if len(firstSignalPositions) == 0 {
		return sequenceMatch{}
	}

	best := sequenceMatch{}
	for _, startIndex := range firstSignalPositions {
		windowStart := logs[startIndex].Timestamp
		windowEnd := windowStart.Add(rule.window)
		endIndex := upperBoundTimestamp(logs, windowEnd) - 1
		if endIndex < startIndex {
			continue
		}

		candidate := e.matchSequence(logs, startIndex, endIndex, windowStart, windowEnd, rule)
		if candidate.matchedSteps == len(rule.steps) {
			return candidate
		}
		if betterCompiledMatch(rule, candidate, best) {
			best = candidate
		}
	}

	return best
}

func (e *Engine) matchSequence(
	logs []models.FullLog,
	startIndex, endIndex int,
	windowStart, windowEnd time.Time,
	rule compiledRule,
) sequenceMatch {
	matchedLogs := make([]models.FullLog, 0)
	stepLogs := make([][]models.FullLog, len(rule.steps))
	stepMatches := make([]int, len(rule.steps))
	matchedSteps := 0
	searchIndex := startIndex
	lastMatchedTime := windowStart

	for stepIndex, step := range rule.steps {
		deadlineCandidates := []time.Time{
			windowEnd,
			windowStart.Add(step.within),
		}
		if stepIndex > 0 {
			deadlineCandidates = []time.Time{
				windowEnd,
				lastMatchedTime.Add(step.within),
			}
			if rule.maxGapEnabled {
				deadlineCandidates = append(deadlineCandidates, lastMatchedTime.Add(rule.maxGap))
			}
		}
		stepDeadline := minTime(deadlineCandidates...)

		stepMatch := e.matchCompiledStep(logs, searchIndex, endIndex, stepDeadline, rule.negativeSignals, step)
		if stepMatch.canceled {
			return sequenceMatch{}
		}
		matchedLogs = append(matchedLogs, stepMatch.logs...)
		stepLogs[stepIndex] = append(stepLogs[stepIndex], stepMatch.logs...)
		stepMatches[stepIndex] = stepMatch.matchedCount

		if !stepMatch.complete {
			return sequenceMatch{
				logs:         matchedLogs,
				stepLogs:     stepLogs,
				stepMatches:  stepMatches,
				matchedSteps: matchedSteps,
			}
		}

		matchedSteps++
		searchIndex = stepMatch.nextIndex
		lastMatchedTime = stepMatch.lastMatchedAt
	}

	return sequenceMatch{
		logs:         matchedLogs,
		stepLogs:     stepLogs,
		stepMatches:  stepMatches,
		matchedSteps: matchedSteps,
	}
}

func (e *Engine) deduplicate(logs []models.FullLog, keys []string, window time.Duration) []models.FullLog {
	if len(keys) == 0 || window <= 0 {
		return logs
	}

	seen := make(map[string]time.Time, len(logs))
	result := make([]models.FullLog, 0, len(logs))

	for _, log := range logs {
		key := e.buildDedupKey(log, keys)
		if lastTime, exists := seen[key]; exists && log.Timestamp.Sub(lastTime) <= window {
			continue
		}

		result = append(result, log)
		seen[key] = log.Timestamp
	}

	return result
}

func (e *Engine) buildDedupKey(log models.FullLog, keys []string) string {
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		if key == "signal_key" {
			parts = append(parts, log.Signal)
			continue
		}

		parts = append(parts, utils.ExtractGroupByValue(log.Metadata, key))
	}
	return strings.Join(parts, "|")
}

func (e *Engine) groupLogs(logs []models.FullLog, groupBy []string) []*logGroup {
	groups := make(map[string]*logGroup)

	for _, log := range logs {
		values := utils.ExtractGroupByValues(log.Metadata, groupBy)
		key := utils.GroupByKey(values)
		group, exists := groups[key]
		if !exists {
			group = &logGroup{
				groupByValues: values,
				logs:          make([]models.FullLog, 0),
			}
			groups[key] = group
		}
		group.logs = append(group.logs, log)
	}

	result := make([]*logGroup, 0, len(groups))
	for _, group := range groups {
		result = append(result, group)
	}
	return result
}

func sortResults(results []models.CorrelationResult) {
	sort.Slice(results, func(i, j int) bool {
		if results[i].Priority != results[j].Priority {
			return results[i].Priority < results[j].Priority
		}
		if results[i].RuleCompletion != results[j].RuleCompletion {
			return results[i].RuleCompletion > results[j].RuleCompletion
		}
		if results[i].SequenceMatch != results[j].SequenceMatch {
			return results[i].SequenceMatch > results[j].SequenceMatch
		}
		return results[i].RuleID < results[j].RuleID
	})
}

func resolveResultConflicts(results []models.CorrelationResult) ([]models.CorrelationResult, int) {
	if len(results) < 2 {
		return results, 0
	}

	candidates := append([]models.CorrelationResult(nil), results...)
	sort.Slice(candidates, func(i, j int) bool {
		return strongerConflictResult(candidates[i], candidates[j])
	})

	resolved := make([]models.CorrelationResult, 0, len(candidates))
	suppressed := 0
	for _, candidate := range candidates {
		if isContainedByAccepted(candidate, resolved) {
			suppressed++
			continue
		}
		resolved = append(resolved, candidate)
	}

	return resolved, suppressed
}

func strongerConflictResult(left, right models.CorrelationResult) bool {
	if left.RuleCompletion != right.RuleCompletion {
		return left.RuleCompletion > right.RuleCompletion
	}
	if left.SequenceMatch != right.SequenceMatch {
		return left.SequenceMatch > right.SequenceMatch
	}
	if len(left.LogID) != len(right.LogID) {
		return len(left.LogID) > len(right.LogID)
	}
	if left.Priority != right.Priority {
		return left.Priority < right.Priority
	}
	return left.RuleID < right.RuleID
}

func isContainedByAccepted(candidate models.CorrelationResult, accepted []models.CorrelationResult) bool {
	if len(candidate.LogID) == 0 {
		return false
	}
	for _, current := range accepted {
		if sameOrganization(candidate, current) && resultLogSubset(candidate.LogID, current.LogID) {
			return true
		}
	}
	return false
}

func sameOrganization(left, right models.CorrelationResult) bool {
	if left.OrganizationID == "" || right.OrganizationID == "" {
		return true
	}
	return left.OrganizationID == right.OrganizationID
}

func resultLogSubset(candidate, accepted []models.ResultLog) bool {
	acceptedIDs := make(map[string]struct{}, len(accepted))
	for _, entry := range accepted {
		acceptedIDs[entry.ID] = struct{}{}
	}
	for _, entry := range candidate {
		if _, ok := acceptedIDs[entry.ID]; !ok {
			return false
		}
	}
	return true
}

func extractResultLogs(logs []models.FullLog) []models.ResultLog {
	result := make([]models.ResultLog, 0, len(logs))
	for _, log := range logs {
		hostIPs := utils.ExtractIPAddresses(log.Metadata, "host.ip")
		result = append(result, models.ResultLog{
			ID:          log.DocID,
			Severity:    log.LogLevel,
			SourceIndex: utils.ExtractGroupByValue(log.Metadata, "source_index"),
			Signal:      log.Signal,
			Timestamp:   log.Timestamp.UTC(),
			ServiceName: resolveServiceName(log.Metadata),
			HostName:    utils.ExtractGroupByValue(log.Metadata, "host.name"),
			HostIP:      firstIP(hostIPs),
			HostIPs:     append([]string(nil), hostIPs...),
		})
	}
	return result
}

func resolveServiceName(metadata map[string]any) string {
	for _, field := range []string{"service.name", "event.module", "host.name"} {
		if value := utils.ExtractGroupByValue(metadata, field); value != "" {
			return value
		}
	}
	return ""
}

func firstIP(values []string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func latestMatchTime(logs []models.FullLog) time.Time {
	if len(logs) == 0 {
		return time.Time{}
	}

	latest := logs[0].Timestamp
	for _, log := range logs[1:] {
		if log.Timestamp.After(latest) {
			latest = log.Timestamp
		}
	}
	return latest
}

func cloneGroupByValues(values map[string]string) map[string]string {
	if len(values) == 0 {
		return nil
	}

	cloned := make(map[string]string, len(values))
	for key, value := range values {
		cloned[key] = value
	}
	return cloned
}

func (e *Engine) GetMetrics() *EngineMetrics {
	e.metricsMu.Lock()
	defer e.metricsMu.Unlock()

	metrics := *e.metrics
	return &metrics
}

func normalizeMinCount(value int) int {
	if value <= 0 {
		return 1
	}
	return value
}

func betterCompiledMatch(rule compiledRule, candidate, current sequenceMatch) bool {
	if len(candidate.logs) == 0 {
		return false
	}
	if len(current.logs) == 0 {
		return true
	}

	candidateCompletion, candidateSequenceMatch := calculateCompiledMatchStats(candidate, rule)
	currentCompletion, currentSequenceMatch := calculateCompiledMatchStats(current, rule)

	if candidateCompletion != currentCompletion {
		return candidateCompletion > currentCompletion
	}
	if candidateSequenceMatch != currentSequenceMatch {
		return candidateSequenceMatch > currentSequenceMatch
	}
	if len(candidate.logs) != len(current.logs) {
		return len(candidate.logs) > len(current.logs)
	}
	return candidate.logs[0].Timestamp.Before(current.logs[0].Timestamp)
}

func calculateCompiledMatchStats(match sequenceMatch, rule compiledRule) (float64, float64) {
	if len(match.logs) == 0 || len(rule.steps) == 0 {
		return 0, 0
	}

	totalRequired := 0
	matchedRequired := 0
	completedPrefixSteps := 0
	partialNextStepProgress := 0.0
	encounteredIncompleteStep := false

	for idx, step := range rule.steps {
		totalRequired += step.minCount

		matchedCount := 0
		if idx < len(match.stepMatches) {
			matchedCount = match.stepMatches[idx]
		}
		if matchedCount > step.minCount {
			matchedCount = step.minCount
		}

		matchedRequired += matchedCount
		if encounteredIncompleteStep {
			continue
		}
		if matchedCount >= step.minCount {
			completedPrefixSteps++
			continue
		}
		encounteredIncompleteStep = true
		partialNextStepProgress = float64(matchedCount) / float64(step.minCount)
	}

	if totalRequired == 0 {
		return 0, 0
	}

	ruleCompletion := float64(matchedRequired) / float64(totalRequired)
	sequenceMatch := (float64(completedPrefixSteps) + partialNextStepProgress) / float64(len(rule.steps))
	return ruleCompletion, sequenceMatch
}

func minTime(values ...time.Time) time.Time {
	result := values[0]
	for _, value := range values[1:] {
		if value.Before(result) {
			result = value
		}
	}
	return result
}

func (e *Engine) matchCompiledStep(
	logs []models.FullLog,
	startIndex, endIndex int,
	stepDeadline time.Time,
	negativeSignals map[string]struct{},
	step compiledStep,
) stepMatchResult {
	switch step.mode {
	case stepModeAnyOf:
		return e.matchAnyOfStep(logs, startIndex, endIndex, stepDeadline, negativeSignals, step)
	default:
		return e.matchAllOfStep(logs, startIndex, endIndex, stepDeadline, negativeSignals, step)
	}
}

func (e *Engine) matchAnyOfStep(
	logs []models.FullLog,
	startIndex, endIndex int,
	stepDeadline time.Time,
	negativeSignals map[string]struct{},
	step compiledStep,
) stepMatchResult {
	counts := make([]int, len(step.selectors))
	selectorLogs := make([][]models.FullLog, len(step.selectors))

	for idx := startIndex; idx <= endIndex; idx++ {
		log := logs[idx]
		if _, blocked := negativeSignals[log.Signal]; blocked {
			return stepMatchResult{canceled: true}
		}
		if log.Timestamp.After(stepDeadline) {
			break
		}

		for selectorIdx, selector := range step.selectors {
			if counts[selectorIdx] >= selector.minCount {
				continue
			}
			if selector.matchesSignal(log.Signal) {
				counts[selectorIdx]++
				selectorLogs[selectorIdx] = append(selectorLogs[selectorIdx], log)
			}
		}

		for selectorIdx, selector := range step.selectors {
			if counts[selectorIdx] >= selector.minCount {
				return stepMatchResult{
					logs:          selectorLogs[selectorIdx],
					matchedCount:  1,
					complete:      true,
					nextIndex:     idx + 1,
					lastMatchedAt: selectorLogs[selectorIdx][len(selectorLogs[selectorIdx])-1].Timestamp,
				}
			}
		}
	}

	bestIdx := bestSelectorProgressIndex(counts, step.selectors)
	if bestIdx < 0 {
		return stepMatchResult{}
	}
	return stepMatchResult{
		logs:         selectorLogs[bestIdx],
		matchedCount: 0,
	}
}

func (e *Engine) matchAllOfStep(
	logs []models.FullLog,
	startIndex, endIndex int,
	stepDeadline time.Time,
	negativeSignals map[string]struct{},
	step compiledStep,
) stepMatchResult {
	counts := make([]int, len(step.selectors))
	selectorLogs := make([][]models.FullLog, len(step.selectors))
	matchedLogs := make([]models.FullLog, 0)

	for idx := startIndex; idx <= endIndex; idx++ {
		log := logs[idx]
		if _, blocked := negativeSignals[log.Signal]; blocked {
			return stepMatchResult{canceled: true}
		}
		if log.Timestamp.After(stepDeadline) {
			break
		}

		for selectorIdx, selector := range step.selectors {
			if counts[selectorIdx] >= selector.minCount {
				continue
			}
			if !selector.matchesSignal(log.Signal) {
				continue
			}

			counts[selectorIdx]++
			selectorLogs[selectorIdx] = append(selectorLogs[selectorIdx], log)
			matchedLogs = append(matchedLogs, log)
			if allSelectorsSatisfied(counts, step.selectors) {
				return stepMatchResult{
					logs:          matchedLogs,
					matchedCount:  matchedSelectorUnits(counts, step.selectors),
					complete:      true,
					nextIndex:     idx + 1,
					lastMatchedAt: log.Timestamp,
				}
			}
			break
		}
	}

	return stepMatchResult{
		logs:         matchedLogs,
		matchedCount: matchedSelectorUnits(counts, step.selectors),
	}
}

func buildSignalIndex(logs []models.FullLog) signalIndex {
	index := make(signalIndex, len(logs))
	for idx, log := range logs {
		index[log.Signal] = append(index[log.Signal], idx)
	}
	return index
}

func normalizeSelectorSignalKeys(signalKey string, signalKeys []string) []string {
	seen := make(map[string]struct{}, 1+len(signalKeys))
	result := make([]string, 0, 1+len(signalKeys))
	appendSignal := func(raw string) {
		trimmed := strings.TrimSpace(raw)
		if trimmed == "" {
			return
		}
		if _, exists := seen[trimmed]; exists {
			return
		}
		seen[trimmed] = struct{}{}
		result = append(result, trimmed)
	}

	appendSignal(signalKey)
	for _, signal := range signalKeys {
		appendSignal(signal)
	}
	return result
}

func collectFirstSignalPositions(index signalIndex, signalKeys []string) []int {
	if len(signalKeys) == 0 {
		return nil
	}
	if len(signalKeys) == 1 {
		return append([]int(nil), index[signalKeys[0]]...)
	}

	positions := make([]int, 0)
	seen := make(map[int]struct{})
	for _, signal := range signalKeys {
		for _, idx := range index[signal] {
			if _, exists := seen[idx]; exists {
				continue
			}
			seen[idx] = struct{}{}
			positions = append(positions, idx)
		}
	}
	sort.Ints(positions)
	return positions
}

func (s compiledSelector) matchesSignal(signal string) bool {
	_, ok := s.signalKeys[signal]
	return ok
}

func upperBoundTimestamp(logs []models.FullLog, target time.Time) int {
	return sort.Search(len(logs), func(i int) bool {
		return logs[i].Timestamp.After(target)
	})
}

func (e *Engine) compileRulesForOrg(orgID string, rules []models.Rule) []compiledRule {
	result := make([]compiledRule, 0)
	for _, rule := range rules {
		if rule.OrganizationID != orgID {
			continue
		}

		compiled, ok := e.compileRule(rule)
		if !ok {
			continue
		}
		result = append(result, compiled)
	}
	return result
}

func (e *Engine) compileRule(rule models.Rule) (compiledRule, bool) {
	cacheKey, err := ruleCacheKey(rule)
	if err != nil {
		if e.logger != nil {
			e.logger.Warn("failed to derive rule cache key", "rule_id", rule.ID, "error", err)
		}
		return compiledRule{}, false
	}

	e.compiledMu.RLock()
	cached, ok := e.compiled[cacheKey]
	e.compiledMu.RUnlock()
	if ok {
		return cached, true
	}

	compiled := compiledRule{
		cacheKey:         cacheKey,
		rule:             rule,
		groupByCacheKey:  groupCacheKey(rule.GroupBy, rule.RequiredMetadata),
		window:           e.parseDurationOrDefault(rule.Window, e.defaultWindow),
		steps:            make([]compiledStep, 0, len(rule.Sequence)),
		negativeSignals:  make(map[string]struct{}, len(rule.NotSequence)),
		requiredMetadata: normalizeRequiredMetadata(rule.RequiredMetadata),
		dedupWindow:      e.parseDurationOrDefault(rule.Deduplication.Window, 0),
	}
	if strings.TrimSpace(rule.MaxGapBetweenSteps) != "" {
		compiled.maxGap = e.parseDurationOrDefault(rule.MaxGapBetweenSteps, e.defaultMaxGap)
		compiled.maxGapEnabled = true
	}

	for idx, step := range rule.Sequence {
		compiledStep, firstSignalKeys, ok := e.compileStep(rule, idx, step)
		if !ok {
			return compiledRule{}, false
		}
		compiled.steps = append(compiled.steps, compiledStep)
		if idx == 0 {
			compiled.firstSignalKeys = append([]string(nil), firstSignalKeys...)
		}
	}
	if len(compiled.steps) == 0 || len(compiled.firstSignalKeys) == 0 {
		return compiledRule{}, false
	}
	for _, step := range rule.NotSequence {
		compiled.negativeSignals[step.SignalKey] = struct{}{}
	}

	e.compiledMu.Lock()
	e.compiled[cacheKey] = compiled
	e.compiledMu.Unlock()
	return compiled, true
}

func (e *Engine) parseDurationOrDefault(value string, fallback time.Duration) time.Duration {
	if fallback < 0 {
		fallback = 0
	}
	parsed, err := utils.ParseDuration(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}

func (e *Engine) compileStep(rule models.Rule, stepIndex int, step models.SequenceStep) (compiledStep, []string, bool) {
	hasLegacySignals := len(normalizeSelectorSignalKeys(step.SignalKey, step.SignalKeys)) > 0
	hasAnyOf := len(step.AnyOf) > 0
	hasAllOf := len(step.AllOf) > 0

	modeCount := 0
	if hasLegacySignals {
		modeCount++
	}
	if hasAnyOf {
		modeCount++
	}
	if hasAllOf {
		modeCount++
	}
	if modeCount != 1 {
		if e.logger != nil {
			e.logger.Warn(
				"rule step must use exactly one selector mode",
				"rule_id", rule.ID,
				"step_index", stepIndex,
			)
		}
		return compiledStep{}, nil, false
	}

	within := e.parseDurationOrDefault(step.Within, e.defaultWindow)
	if hasLegacySignals {
		selector, signalKeys, ok := compileSelector(step.SignalKey, step.SignalKeys, normalizeMinCount(step.MinCount))
		if !ok {
			if e.logger != nil {
				e.logger.Warn("rule step has no signal selectors", "rule_id", rule.ID, "step_index", stepIndex)
			}
			return compiledStep{}, nil, false
		}
		return compiledStep{
			signalKey: selector.signalKey,
			mode:      stepModeAllOf,
			selectors: []compiledSelector{selector},
			minCount:  selector.minCount,
			within:    within,
		}, signalKeys, true
	}

	if normalizeMinCount(step.MinCount) > 1 {
		if e.logger != nil {
			e.logger.Warn(
				"grouped rule steps do not support step min_count > 1",
				"rule_id", rule.ID,
				"step_index", stepIndex,
				"min_count", step.MinCount,
			)
		}
		return compiledStep{}, nil, false
	}

	rawSelectors := step.AnyOf
	mode := stepModeAnyOf
	if hasAllOf {
		rawSelectors = step.AllOf
		mode = stepModeAllOf
	}

	selectors := make([]compiledSelector, 0, len(rawSelectors))
	firstSignalKeys := make([]string, 0)
	firstSignalSeen := make(map[string]struct{})
	for selectorIndex, raw := range rawSelectors {
		selector, signalKeys, ok := compileSelector(raw.SignalKey, raw.SignalKeys, 1)
		if !ok {
			if e.logger != nil {
				e.logger.Warn(
					"grouped rule selector has no signals",
					"rule_id", rule.ID,
					"step_index", stepIndex,
					"selector_index", selectorIndex,
				)
			}
			return compiledStep{}, nil, false
		}
		selectors = append(selectors, selector)
		for _, signalKey := range signalKeys {
			if _, exists := firstSignalSeen[signalKey]; exists {
				continue
			}
			firstSignalSeen[signalKey] = struct{}{}
			firstSignalKeys = append(firstSignalKeys, signalKey)
		}
	}

	stepSummary := renderStepSummary(mode, selectors)
	requiredCount := 1
	if mode == stepModeAllOf {
		requiredCount = len(selectors)
	}
	return compiledStep{
		signalKey: stepSummary,
		mode:      mode,
		selectors: selectors,
		minCount:  requiredCount,
		within:    within,
	}, firstSignalKeys, true
}

func compileSelector(signalKey string, signalKeys []string, minCount int) (compiledSelector, []string, bool) {
	normalizedSignals := normalizeSelectorSignalKeys(signalKey, signalKeys)
	if len(normalizedSignals) == 0 {
		return compiledSelector{}, nil, false
	}

	signalSet := make(map[string]struct{}, len(normalizedSignals))
	for _, signal := range normalizedSignals {
		signalSet[signal] = struct{}{}
	}

	return compiledSelector{
		signalKey:  strings.Join(normalizedSignals, "|"),
		signalKeys: signalSet,
		minCount:   normalizeMinCount(minCount),
	}, normalizedSignals, true
}

func renderStepSummary(mode stepMode, selectors []compiledSelector) string {
	parts := make([]string, 0, len(selectors))
	for _, selector := range selectors {
		parts = append(parts, selector.signalKey)
	}
	switch mode {
	case stepModeAnyOf:
		return "any_of(" + strings.Join(parts, "; ") + ")"
	default:
		return "all_of(" + strings.Join(parts, "; ") + ")"
	}
}

func bestSelectorProgressIndex(counts []int, selectors []compiledSelector) int {
	bestIdx := -1
	bestProgress := -1.0
	bestMatched := -1
	for idx, selector := range selectors {
		progress := float64(minInt(counts[idx], selector.minCount)) / float64(selector.minCount)
		if progress > bestProgress {
			bestIdx = idx
			bestProgress = progress
			bestMatched = counts[idx]
			continue
		}
		if progress == bestProgress && counts[idx] > bestMatched {
			bestIdx = idx
			bestMatched = counts[idx]
		}
	}
	return bestIdx
}

func allSelectorsSatisfied(counts []int, selectors []compiledSelector) bool {
	for idx, selector := range selectors {
		if counts[idx] < selector.minCount {
			return false
		}
	}
	return true
}

func matchedSelectorUnits(counts []int, selectors []compiledSelector) int {
	matched := 0
	for idx, selector := range selectors {
		matched += minInt(counts[idx], selector.minCount)
	}
	return matched
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}

func (e *Engine) recordMetrics(logCount, resultCount int, duration time.Duration) {
	e.metricsMu.Lock()
	defer e.metricsMu.Unlock()

	e.metrics.TotalLogsProcessed += int64(logCount)
	e.metrics.TotalRulesMatched += int64(resultCount)
	e.metrics.ProcessingTimeMS = duration.Milliseconds()
}

func ruleCacheKey(rule models.Rule) (string, error) {
	payload, err := json.Marshal(rule)
	if err != nil {
		return "", fmt.Errorf("marshal rule: %w", err)
	}

	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func buildMatchAudit(rule compiledRule, groupByValues map[string]string, match sequenceMatch) *models.MatchAudit {
	audit := &models.MatchAudit{
		RuleType:           rule.rule.RuleType,
		Window:             durationOrFallback(rule.rule.Window, rule.window),
		MaxGapBetweenSteps: durationOrFallback(rule.rule.MaxGapBetweenSteps, rule.maxGap),
		GroupBy:            append([]string(nil), rule.rule.GroupBy...),
		GroupByValues:      cloneGroupByValues(groupByValues),
		RequiredMetadata:   cloneGroupByValues(rule.requiredMetadata),
		NegativeSignals:    sortedKeys(rule.negativeSignals),
		MatchedLogIDs:      extractMatchedLogIDs(match.logs),
		MatchedSignals:     extractMatchedSignals(match.logs),
	}
	if len(rule.rule.Deduplication.Key) > 0 {
		audit.DeduplicationKey = append([]string(nil), rule.rule.Deduplication.Key...)
	}
	if duration := durationOrFallback(rule.rule.Deduplication.Window, rule.dedupWindow); duration != "" {
		audit.DeduplicationWindow = duration
	}

	steps := make([]models.MatchStepAudit, 0, len(rule.steps))
	for idx, step := range rule.steps {
		matchedCount := 0
		if idx < len(match.stepMatches) {
			matchedCount = match.stepMatches[idx]
		}
		var matchedLogs []models.FullLog
		if idx < len(match.stepLogs) {
			matchedLogs = match.stepLogs[idx]
		}
		steps = append(steps, models.MatchStepAudit{
			StepIndex:     idx,
			SignalKey:     step.signalKey,
			RequiredCount: step.minCount,
			MatchedCount:  matchedCount,
			Within:        durationOrFallback(rule.rule.Sequence[idx].Within, step.within),
			MatchedLogIDs: extractMatchedLogIDs(matchedLogs),
		})
	}
	audit.Steps = steps
	return audit
}

func durationOrFallback(raw string, fallback time.Duration) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed != "" {
		return trimmed
	}
	if fallback <= 0 {
		return ""
	}
	return fallback.String()
}

func sortedKeys(values map[string]struct{}) []string {
	if len(values) == 0 {
		return nil
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func extractMatchedLogIDs(logs []models.FullLog) []string {
	if len(logs) == 0 {
		return nil
	}
	ids := make([]string, 0, len(logs))
	for _, log := range logs {
		ids = append(ids, log.DocID)
	}
	return ids
}

func extractMatchedSignals(logs []models.FullLog) []string {
	if len(logs) == 0 {
		return nil
	}
	signals := make([]string, 0, len(logs))
	for _, log := range logs {
		signals = append(signals, log.Signal)
	}
	return signals
}

func (e *Engine) filterLogsForRule(logs []models.FullLog, rule compiledRule) []models.FullLog {
	if len(rule.requiredMetadata) == 0 {
		return logs
	}

	filtered := make([]models.FullLog, 0, len(logs))
	for _, log := range logs {
		if matchesRequiredMetadata(log, rule.requiredMetadata) {
			filtered = append(filtered, log)
		}
	}
	return filtered
}

func matchesRequiredMetadata(log models.FullLog, required map[string]string) bool {
	for field, expected := range required {
		if utils.ExtractGroupByValue(log.Metadata, field) != expected {
			return false
		}
	}
	return true
}

func groupCacheKey(groupBy []string, requiredMetadata map[string]string) string {
	parts := []string{strings.Join(groupBy, "\x1f")}
	if len(requiredMetadata) == 0 {
		return strings.Join(parts, "\x1e")
	}

	keys := make([]string, 0, len(requiredMetadata))
	for key := range requiredMetadata {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		parts = append(parts, key+"="+requiredMetadata[key])
	}
	return strings.Join(parts, "\x1e")
}

func normalizeRequiredMetadata(values map[string]string) map[string]string {
	if len(values) == 0 {
		return nil
	}

	normalized := make(map[string]string, len(values))
	for key, value := range values {
		trimmedKey := strings.TrimSpace(key)
		trimmedValue := strings.TrimSpace(value)
		if trimmedKey == "" || trimmedValue == "" {
			continue
		}
		normalized[trimmedKey] = trimmedValue
	}
	if len(normalized) == 0 {
		return nil
	}
	return normalized
}
