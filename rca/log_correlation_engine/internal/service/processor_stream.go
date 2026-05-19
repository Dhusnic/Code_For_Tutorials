package service

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/models"
	"log_correlation_engine/internal/utils"
)

type signalWindowLoader interface {
	LoadSignalEventsWindowForSignals(ctx context.Context, since time.Time, signalKeys []string) ([]models.FullLog, error)
}

type signalStreamTrimmer interface {
	TrimSignalStreams(ctx context.Context, minID string, signalKeys []string) (int64, error)
}

type ruleOwnershipGroup struct {
	Key        string
	SignalKeys []string
	Rules      []models.Rule
}

type workerRuleAssignment struct {
	WorkerID   string
	Groups     []ruleOwnershipGroup
	RuleLoad   int
	SignalLoad int
}

func (p *Processor) runRedisStreamCycle(ctx context.Context, started time.Time, rules []models.Rule) error {
	if !p.config.Redis.SignalStreamEnabled {
		return fmt.Errorf("engine.input_mode redis_stream requires redis.signal_stream_enabled to be true")
	}
	requiredRetentionWindow := p.streamInputWindowForRules(rules)
	allRuleSignalKeys := uniqueSortedSignalKeys(flattenRuleSignalKeys(rules))
	if len(rules) == 0 {
		p.logger.Warn("no correlation rules loaded")
		p.trimRedisStreamWindow(ctx, requiredRetentionWindow, allRuleSignalKeys)
		return nil
	}

	workerIDs := []string{p.localWorkerID()}
	activeWorkers := 1

	if p.config.Distributed.Enabled {
		if p.distributed == nil {
			return fmt.Errorf("distributed mode is enabled but the configured store does not support distributed processing")
		}

		workers, err := p.distributed.ListActiveWorkers(ctx)
		if err != nil {
			return fmt.Errorf("list active distributed workers: %w", err)
		}
		workerIDs = normalizeWorkerIDs(workers, p.localWorkerID())
		activeWorkers = len(workerIDs)
	}

	groups := buildRuleOwnershipGroups(rules, len(workerIDs))
	groupActivity := p.estimateRuleGroupActivity(ctx, groups)
	assignments := assignRuleGroupsToWorkers(groups, workerIDs, groupActivity)
	ownedAssignment := assignments[p.localWorkerID()]
	if len(ownedAssignment.Groups) == 0 {
		p.trimRedisStreamWindow(ctx, requiredRetentionWindow, allRuleSignalKeys)
		p.logger.Info(
			"redis stream cycle skipped because no rules are assigned to this worker",
			"input_mode", p.config.Engine.InputMode,
			"worker_id", p.localWorkerID(),
			"active_workers", activeWorkers,
			"total_rules", len(rules),
		)
		return nil
	}

	ownedRules := flattenOwnershipRules(ownedAssignment.Groups)
	ownedSignalKeys := signalKeysForGroups(ownedAssignment.Groups)
	inputWindow := p.streamInputWindowForRules(ownedRules)
	inputSince := p.now().UTC().Add(-inputWindow)
	logs, err := p.loadRedisStreamLogs(ctx, inputSince, ownedSignalKeys)
	if err != nil {
		return fmt.Errorf("load redis signal events window: %w", err)
	}
	p.trimRedisStreamWindow(ctx, requiredRetentionWindow, allRuleSignalKeys)

	summary, err := p.processRedisStreamRules(ctx, logs, ownedAssignment.Groups)

	p.logger.Info(
		"correlation cycle completed",
		"started_at", started.Format(time.RFC3339Nano),
		"input_mode", p.config.Engine.InputMode,
		"input_window", inputWindow.String(),
		"active_workers", activeWorkers,
		"worker_id", p.localWorkerID(),
		"owned_rule_groups", len(ownedAssignment.Groups),
		"owned_rules", ownedAssignment.RuleLoad,
		"owned_signals", len(ownedSignalKeys),
		"owned_signal_load", ownedAssignment.SignalLoad,
		"organizations", summary.Organizations,
		"organizations_with_logs", summary.OrganizationsWithLogs,
		"organization_failures", summary.OrganizationFailures,
		"signal_logs_read", summary.SignalLogsRead,
		"incremental_signal_logs", summary.IncrementalSignalLogs,
		"enriched_logs", summary.EnrichedLogs,
		"fetch_errors", summary.FetchErrors,
		"correlations_found", summary.CorrelationsFound,
		"incidents_opened", summary.IncidentsOpened,
		"incidents_updated", summary.IncidentsUpdated,
		"incidents_closed", summary.IncidentsClosed,
		"results_written", summary.ResultsWritten,
		"result_write_failures", summary.ResultWriteFailures,
		"result_publish_failures", summary.ResultPublishFailures,
		"results_suppressed", summary.ResultsSuppressed,
		"shadow_matches", summary.ShadowMatches,
		"incident_state_failures", summary.IncidentStateFailures,
	)

	if p.autoscaler != nil && p.autoscaler.Enabled() {
		p.autoscaler.ObserveDistributedCycle(summary.IncrementalSignalLogs, activeWorkers)
	}

	if err != nil {
		return err
	}
	return ctx.Err()
}

func (p *Processor) processRedisStreamRules(
	ctx context.Context,
	logs []models.FullLog,
	groups []ruleOwnershipGroup,
) (CycleSummary, error) {
	allRules := flattenOwnershipRules(groups)
	rulesByID := indexRulesByID(allRules)
	logOrganizations := collectOrganizationsFromLogs(logs)
	organizations, activeByOrg, err := p.loadActiveIncidentsByOrganization(ctx, allRules, logOrganizations)
	if err != nil {
		return CycleSummary{}, err
	}

	summary := CycleSummary{
		Organizations:         len(organizations),
		OrganizationsWithLogs: len(logOrganizations),
		SignalLogsRead:        len(logs),
		IncrementalSignalLogs: len(logs),
		EnrichedLogs:          len(logs),
	}

	if len(groups) == 0 {
		return summary, nil
	}

	allResults := make([]models.CorrelationResult, 0)
	for _, group := range groups {
		if err := ctx.Err(); err != nil {
			return summary, err
		}

		groupLogs := filterLogsBySignalKeys(logs, group.SignalKeys)
		if len(groupLogs) == 0 {
			continue
		}

		results, err := p.engine.Correlate(ctx, "", groupLogs, group.Rules)
		if err != nil {
			return summary, fmt.Errorf("correlate redis stream rule group %s: %w", group.Key, err)
		}
		allResults = append(allResults, results...)
	}

	liveResults, shadowResults := splitResultsByShadowMode(allResults, rulesByID)
	liveResults, _ = models.NormalizeCorrelationResults(liveResults)
	shadowResults, _ = models.NormalizeCorrelationResults(shadowResults)

	summary.CorrelationsFound = len(liveResults)
	summary.ShadowMatches = len(shadowResults)

	shadowByOrg := groupResultsByOrganization(shadowResults)
	for organization, results := range shadowByOrg {
		p.logShadowMatches(organization, results, rulesByID)
	}

	liveByOrg := groupResultsByOrganization(liveResults)
	logsByOrg := groupLogsByOrganization(logs)
	allOrganizations := mergeOrganizationSets(organizations, sortedOrganizationKeys(liveByOrg), sortedOrganizationKeys(logsByOrg))
	if len(allOrganizations) == 0 {
		allOrganizations = mergeOrganizationSets(sortedOrganizationKeys(activeByOrg), sortedOrganizationKeys(liveByOrg), sortedOrganizationKeys(logsByOrg))
	}

	now := p.now().UTC()
	for _, organization := range allOrganizations {
		activeByID := activeByOrg[organization]
		if activeByID == nil {
			activeByID = make(map[string]models.IncidentState)
			activeByOrg[organization] = activeByID
		}

		scope := &processingScope{
			WorkloadKey:    organization,
			CheckpointKey:  organization,
			OrganizationID: organization,
		}

		results := liveByOrg[organization]
		actions := make([]incidentAction, 0, len(results))
		matchedIncidentIDs := make(map[string]struct{}, len(results))
		for idx := range results {
			result := &results[idx]
			action, shouldWrite, err := p.buildIncidentAction(organization, result, activeByID)
			if err != nil {
				summary.IncidentStateFailures++
				p.logger.Warn(
					"failed to build incident action",
					"organization", organization,
					"rule_id", result.RuleID,
					"error", err,
				)
				continue
			}
			if !shouldWrite {
				summary.ResultsSuppressed++
				continue
			}

			matchedIncidentIDs[result.IncidentID] = struct{}{}
			if result.Status == "open" {
				summary.IncidentsOpened++
			}
			if result.Status == "updated" {
				summary.IncidentsUpdated++
			}
			p.logMatchAudit("correlation rule matched", organization, action.result, rulesByID[result.RuleID], false)
			actions = append(actions, action)
		}

		recoveryActions, err := p.buildRecoveryClosures(ctx, organization, allRules, logsByOrg[organization], activeByID)
		if err != nil {
			summary.IncidentStateFailures++
			return summary, err
		}
		for _, action := range recoveryActions {
			summary.IncidentsClosed++
			actions = append(actions, action)
		}

		if err := p.applyIncidentActions(ctx, scope, activeByID, actions, &summary); err != nil {
			return summary, err
		}
		if err := p.closeInactiveIncidents(ctx, scope, activeByID, matchedIncidentIDs, now, &summary); err != nil {
			return summary, err
		}
	}

	return summary, nil
}

func (p *Processor) loadActiveIncidentsByOrganization(
	ctx context.Context,
	rules []models.Rule,
	logOrganizations []string,
) ([]string, map[string]map[string]models.IncidentState, error) {
	ownedRuleIDs := make(map[string]struct{}, len(rules))
	for _, rule := range rules {
		ownedRuleIDs[rule.ID] = struct{}{}
	}

	knownOrganizations, err := p.store.ListOrganizations(ctx)
	if err != nil {
		return nil, nil, fmt.Errorf("list organizations: %w", err)
	}
	allOrganizations := mergeOrganizationSets(knownOrganizations, logOrganizations)
	activeByOrg := make(map[string]map[string]models.IncidentState, len(allOrganizations))
	processed := make([]string, 0, len(allOrganizations))
	for _, organization := range allOrganizations {
		incidents, err := p.store.ListActiveIncidents(ctx, organization)
		if err != nil {
			return nil, nil, fmt.Errorf("list active incidents for organization %s: %w", organization, err)
		}

		activeByID := make(map[string]models.IncidentState)
		for _, incident := range incidents {
			if _, ok := ownedRuleIDs[incident.RuleID]; !ok {
				continue
			}
			activeByID[incident.IncidentID] = incident
		}

		if len(activeByID) == 0 {
			if containsString(logOrganizations, organization) {
				activeByOrg[organization] = activeByID
				processed = append(processed, organization)
			}
			continue
		}

		activeByOrg[organization] = activeByID
		processed = append(processed, organization)
	}
	return mergeOrganizationSets(processed, logOrganizations), activeByOrg, nil
}

func (p *Processor) loadRedisStreamLogs(ctx context.Context, since time.Time, signalKeys []string) ([]models.FullLog, error) {
	if loader, ok := p.store.(signalWindowLoader); ok && len(signalKeys) > 0 {
		return loader.LoadSignalEventsWindowForSignals(ctx, since, signalKeys)
	}
	return p.store.LoadSignalEventsWindow(ctx, since)
}

func (p *Processor) trimRedisStreamWindow(ctx context.Context, requiredWindow time.Duration, signalKeys []string) {
	retention := p.config.Redis.SignalStreamUnconsumedRetention
	if retention < requiredWindow {
		retention = requiredWindow
	}
	if retention <= 0 {
		return
	}

	trimMinID := streamTimeToID(p.now().UTC().Add(-retention))
	if trimMinID == "" {
		return
	}
	if trimmer, ok := p.store.(signalStreamTrimmer); ok && len(signalKeys) > 0 {
		if _, err := trimmer.TrimSignalStreams(ctx, trimMinID, signalKeys); err != nil {
			p.logger.Warn(
				"failed to trim redis signal streams window",
				"stream_key", p.config.Redis.SignalStreamKey,
				"trim_min_id", trimMinID,
				"signal_count", len(signalKeys),
				"error", err,
			)
		}
		return
	}
	if _, err := p.store.TrimSignalStream(ctx, trimMinID); err != nil {
		p.logger.Warn(
			"failed to trim redis signal stream window",
			"stream_key", p.config.Redis.SignalStreamKey,
			"trim_min_id", trimMinID,
			"error", err,
		)
	}
}

func (p *Processor) streamInputWindow() time.Duration {
	if p.config.Engine.InputWindow > 0 {
		return p.config.Engine.InputWindow
	}
	return 30 * time.Minute
}

func (p *Processor) localWorkerID() string {
	if strings.TrimSpace(p.workerID) != "" {
		return strings.TrimSpace(p.workerID)
	}
	return "local"
}

func normalizeWorkerIDs(workers []distributed.WorkerHeartbeat, self string) []string {
	seen := make(map[string]struct{}, len(workers)+1)
	ids := make([]string, 0, len(workers)+1)
	appendWorker := func(workerID string) {
		trimmed := strings.TrimSpace(workerID)
		if trimmed == "" {
			return
		}
		if _, exists := seen[trimmed]; exists {
			return
		}
		seen[trimmed] = struct{}{}
		ids = append(ids, trimmed)
	}

	for _, worker := range workers {
		appendWorker(worker.WorkerID)
	}
	appendWorker(self)
	sort.Strings(ids)
	if len(ids) == 0 {
		return []string{"local"}
	}
	return ids
}

func assignRulesToWorkers(rules []models.Rule, workerIDs []string) map[string]workerRuleAssignment {
	groups := buildRuleOwnershipGroups(rules, len(workerIDs))
	return assignRuleGroupsToWorkers(groups, workerIDs, nil)
}

func assignRuleGroupsToWorkers(
	groups []ruleOwnershipGroup,
	workerIDs []string,
	groupActivity map[string]int,
) map[string]workerRuleAssignment {
	normalizedWorkers := append([]string(nil), workerIDs...)
	sort.Strings(normalizedWorkers)
	if len(normalizedWorkers) == 0 {
		normalizedWorkers = []string{"local"}
	}

	assignments := make(map[string]workerRuleAssignment, len(normalizedWorkers))
	for _, workerID := range normalizedWorkers {
		assignments[workerID] = workerRuleAssignment{WorkerID: workerID}
	}

	sortedGroups := append([]ruleOwnershipGroup(nil), groups...)
	sort.Slice(sortedGroups, func(i, j int) bool {
		leftActivity := groupActivityValue(groupActivity, sortedGroups[i].Key)
		rightActivity := groupActivityValue(groupActivity, sortedGroups[j].Key)
		if leftActivity != rightActivity {
			return leftActivity > rightActivity
		}
		if len(sortedGroups[i].Rules) != len(sortedGroups[j].Rules) {
			return len(sortedGroups[i].Rules) > len(sortedGroups[j].Rules)
		}
		return sortedGroups[i].Key < sortedGroups[j].Key
	})

	for _, group := range sortedGroups {
		targetWorker := selectLeastLoadedWorker(assignments, normalizedWorkers)
		assignment := assignments[targetWorker]
		assignment.Groups = append(assignment.Groups, group)
		assignment.RuleLoad += len(group.Rules)
		assignment.SignalLoad += groupActivityValue(groupActivity, group.Key)
		assignments[targetWorker] = assignment
	}

	return assignments
}

func buildRuleOwnershipGroups(rules []models.Rule, workerCount int) []ruleOwnershipGroup {
	grouped := make(map[string]ruleOwnershipGroup)
	for _, rule := range rules {
		signals := extractRuleSignalKeys(rule)
		key := strings.Join(signals, "|")
		if key == "" {
			key = "rule:" + strings.TrimSpace(rule.ID)
		}

		group := grouped[key]
		group.Key = key
		group.SignalKeys = append([]string(nil), signals...)
		group.Rules = append(group.Rules, rule)
		grouped[key] = group
	}

	targetChunkSize := len(rules)
	if workerCount > 0 {
		targetChunkSize = (len(rules) + workerCount - 1) / workerCount
	}
	if targetChunkSize <= 0 {
		targetChunkSize = 1
	}

	keys := make([]string, 0, len(grouped))
	for key := range grouped {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		left := grouped[keys[i]]
		right := grouped[keys[j]]
		if len(left.Rules) != len(right.Rules) {
			return len(left.Rules) > len(right.Rules)
		}
		return keys[i] < keys[j]
	})

	result := make([]ruleOwnershipGroup, 0, len(grouped))
	for _, key := range keys {
		group := grouped[key]
		sort.Slice(group.Rules, func(i, j int) bool {
			return group.Rules[i].ID < group.Rules[j].ID
		})
		if len(group.Rules) <= targetChunkSize {
			result = append(result, group)
			continue
		}

		for start := 0; start < len(group.Rules); start += targetChunkSize {
			end := start + targetChunkSize
			if end > len(group.Rules) {
				end = len(group.Rules)
			}
			result = append(result, ruleOwnershipGroup{
				Key:        fmt.Sprintf("%s#%d", group.Key, len(result)),
				SignalKeys: append([]string(nil), group.SignalKeys...),
				Rules:      append([]models.Rule(nil), group.Rules[start:end]...),
			})
		}
	}
	return result
}

func selectLeastLoadedWorker(assignments map[string]workerRuleAssignment, workerIDs []string) string {
	bestWorker := workerIDs[0]
	bestSignalLoad := assignments[bestWorker].SignalLoad
	bestRuleLoad := assignments[bestWorker].RuleLoad
	for _, workerID := range workerIDs[1:] {
		signalLoad := assignments[workerID].SignalLoad
		ruleLoad := assignments[workerID].RuleLoad
		if signalLoad < bestSignalLoad || (signalLoad == bestSignalLoad && ruleLoad < bestRuleLoad) {
			bestWorker = workerID
			bestSignalLoad = signalLoad
			bestRuleLoad = ruleLoad
		}
	}
	return bestWorker
}

func groupActivityValue(groupActivity map[string]int, groupKey string) int {
	if len(groupActivity) == 0 {
		return 0
	}
	return groupActivity[strings.TrimSpace(groupKey)]
}

func (p *Processor) estimateRuleGroupActivity(ctx context.Context, groups []ruleOwnershipGroup) map[string]int {
	counter, ok := p.store.(SignalActivityStore)
	if !ok || len(groups) == 0 {
		return nil
	}

	activity := make(map[string]int, len(groups))
	cache := make(map[string]int, len(groups))
	for _, group := range groups {
		if len(group.SignalKeys) == 0 {
			activity[group.Key] = 0
			continue
		}

		since := p.now().UTC().Add(-p.streamInputWindowForRules(group.Rules))
		cacheKey := fmt.Sprintf("%s@%s", strings.Join(group.SignalKeys, "|"), since.Format(time.RFC3339Nano))
		if cached, ok := cache[cacheKey]; ok {
			activity[group.Key] = cached
			continue
		}

		counts, err := counter.CountSignalEventsWindowForSignals(ctx, since, group.SignalKeys)
		if err != nil {
			p.logger.Warn(
				"failed to estimate redis stream rule group activity; falling back to rule-count assignment",
				"error", err,
				"group", group.Key,
			)
			return nil
		}

		total := 0
		for _, signalKey := range group.SignalKeys {
			total += counts[strings.TrimSpace(signalKey)]
		}
		cache[cacheKey] = total
		activity[group.Key] = total
	}

	return activity
}

func signalKeysForGroups(groups []ruleOwnershipGroup) []string {
	keys := make([]string, 0)
	for _, group := range groups {
		keys = append(keys, group.SignalKeys...)
	}
	return uniqueSortedSignalKeys(keys)
}

func flattenRuleSignalKeys(rules []models.Rule) []string {
	keys := make([]string, 0)
	for _, rule := range rules {
		keys = append(keys, extractRuleSignalKeys(rule)...)
	}
	return keys
}

func uniqueSortedSignalKeys(signalKeys []string) []string {
	seen := make(map[string]struct{}, len(signalKeys))
	unique := make([]string, 0, len(signalKeys))
	for _, signalKey := range signalKeys {
		trimmed := strings.TrimSpace(signalKey)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		unique = append(unique, trimmed)
	}
	sort.Strings(unique)
	return unique
}

func (p *Processor) streamInputWindowForRules(rules []models.Rule) time.Duration {
	required := p.requiredStreamLookback(rules)
	configured := p.streamInputWindow()
	if configured > required {
		required = configured
	}
	if required <= 0 {
		return 30 * time.Minute
	}
	return required
}

func (p *Processor) requiredStreamLookback(rules []models.Rule) time.Duration {
	maxLookback := time.Duration(0)
	for _, rule := range rules {
		if candidate := p.ruleStreamLookback(rule); candidate > maxLookback {
			maxLookback = candidate
		}
	}
	return maxLookback
}

func (p *Processor) ruleStreamLookback(rule models.Rule) time.Duration {
	defaultWindow := p.config.Engine.DefaultWindow
	if defaultWindow <= 0 {
		defaultWindow = 30 * time.Minute
	}
	defaultMaxGap := p.config.Engine.DefaultMaxGap
	if defaultMaxGap <= 0 {
		defaultMaxGap = time.Minute
	}

	lookback := parseDurationWithFallback(rule.Window, defaultWindow)
	for _, step := range rule.Sequence {
		if within := parseDurationWithFallback(step.Within, defaultWindow); within > lookback {
			lookback = within
		}
	}
	if strings.TrimSpace(rule.MaxGapBetweenSteps) != "" {
		if gap := parseDurationWithFallback(rule.MaxGapBetweenSteps, defaultMaxGap); gap > lookback {
			lookback = gap
		}
	}
	if dedupWindow := parseDurationWithFallback(rule.Deduplication.Window, 0); dedupWindow > lookback {
		lookback = dedupWindow
	}
	return lookback
}

func parseDurationWithFallback(raw string, fallback time.Duration) time.Duration {
	if fallback < 0 {
		fallback = 0
	}
	parsed, err := utils.ParseDuration(raw)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}

func extractRuleSignalKeys(rule models.Rule) []string {
	seen := make(map[string]struct{})
	signals := make([]string, 0)
	appendSignal := func(value string) {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			return
		}
		if _, exists := seen[trimmed]; exists {
			return
		}
		seen[trimmed] = struct{}{}
		signals = append(signals, trimmed)
	}

	for _, step := range rule.Sequence {
		appendSignal(step.SignalKey)
		for _, signal := range step.SignalKeys {
			appendSignal(signal)
		}
		for _, selector := range step.AnyOf {
			appendSignal(selector.SignalKey)
			for _, signal := range selector.SignalKeys {
				appendSignal(signal)
			}
		}
		for _, selector := range step.AllOf {
			appendSignal(selector.SignalKey)
			for _, signal := range selector.SignalKeys {
				appendSignal(signal)
			}
		}
	}
	for _, step := range rule.NotSequence {
		appendSignal(step.SignalKey)
	}
	sort.Strings(signals)
	return signals
}

func flattenOwnershipRules(groups []ruleOwnershipGroup) []models.Rule {
	total := 0
	for _, group := range groups {
		total += len(group.Rules)
	}
	result := make([]models.Rule, 0, total)
	for _, group := range groups {
		result = append(result, group.Rules...)
	}
	return result
}

func filterLogsBySignalKeys(logs []models.FullLog, signalKeys []string) []models.FullLog {
	if len(signalKeys) == 0 {
		return append([]models.FullLog(nil), logs...)
	}

	allowed := make(map[string]struct{}, len(signalKeys))
	for _, signalKey := range signalKeys {
		allowed[signalKey] = struct{}{}
	}

	filtered := make([]models.FullLog, 0, len(logs))
	for _, log := range logs {
		if _, ok := allowed[log.Signal]; ok {
			filtered = append(filtered, log)
		}
	}
	return filtered
}

func splitResultsByShadowMode(results []models.CorrelationResult, rulesByID map[string]models.Rule) ([]models.CorrelationResult, []models.CorrelationResult) {
	live := make([]models.CorrelationResult, 0, len(results))
	shadow := make([]models.CorrelationResult, 0)
	for _, result := range results {
		rule, ok := rulesByID[result.RuleID]
		if ok && rule.ShadowMode {
			shadow = append(shadow, result)
			continue
		}
		live = append(live, result)
	}
	return live, shadow
}

func collectOrganizationsFromLogs(logs []models.FullLog) []string {
	seen := make(map[string]struct{})
	organizations := make([]string, 0)
	for _, log := range logs {
		organization := strings.TrimSpace(utils.ExtractGroupByValue(log.Metadata, "event.organization"))
		if organization == "" {
			continue
		}
		if _, exists := seen[organization]; exists {
			continue
		}
		seen[organization] = struct{}{}
		organizations = append(organizations, organization)
	}
	sort.Strings(organizations)
	return organizations
}

func groupLogsByOrganization(logs []models.FullLog) map[string][]models.FullLog {
	grouped := make(map[string][]models.FullLog)
	for _, log := range logs {
		organization := strings.TrimSpace(utils.ExtractGroupByValue(log.Metadata, "event.organization"))
		if organization == "" {
			continue
		}
		grouped[organization] = append(grouped[organization], log)
	}
	return grouped
}

func groupResultsByOrganization(results []models.CorrelationResult) map[string][]models.CorrelationResult {
	grouped := make(map[string][]models.CorrelationResult)
	for _, result := range results {
		organization := strings.TrimSpace(result.OrganizationID)
		if organization == "" {
			continue
		}
		grouped[organization] = append(grouped[organization], result)
	}
	return grouped
}

func mergeOrganizationSets(groups ...[]string) []string {
	seen := make(map[string]struct{})
	merged := make([]string, 0)
	for _, items := range groups {
		for _, item := range items {
			trimmed := strings.TrimSpace(item)
			if trimmed == "" {
				continue
			}
			if _, exists := seen[trimmed]; exists {
				continue
			}
			seen[trimmed] = struct{}{}
			merged = append(merged, trimmed)
		}
	}
	sort.Strings(merged)
	return merged
}

func sortedOrganizationKeys[V any](values map[string]V) []string {
	if len(values) == 0 {
		return nil
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		if strings.TrimSpace(key) == "" {
			continue
		}
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func parallelizeRuleGroups(
	ctx context.Context,
	workerCount int,
	groups []ruleOwnershipGroup,
	run func(context.Context, ruleOwnershipGroup) ([]models.CorrelationResult, error),
) ([]models.CorrelationResult, error) {
	if len(groups) == 0 {
		return nil, nil
	}
	if workerCount <= 1 || len(groups) == 1 {
		results := make([]models.CorrelationResult, 0)
		for _, group := range groups {
			groupResults, err := run(ctx, group)
			if err != nil {
				return nil, err
			}
			results = append(results, groupResults...)
		}
		return results, nil
	}

	type outcome struct {
		results []models.CorrelationResult
		err     error
	}

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	jobs := make(chan ruleOwnershipGroup, len(groups))
	outcomes := make(chan outcome, len(groups))
	for _, group := range groups {
		jobs <- group
	}
	close(jobs)

	var wg sync.WaitGroup
	for workerIndex := 0; workerIndex < workerCount; workerIndex++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for group := range jobs {
				if err := runCtx.Err(); err != nil {
					return
				}
				results, err := run(runCtx, group)
				if err != nil {
					select {
					case outcomes <- outcome{err: err}:
					default:
					}
					cancel()
					return
				}
				outcomes <- outcome{results: results}
			}
		}()
	}

	wg.Wait()
	close(outcomes)

	merged := make([]models.CorrelationResult, 0)
	for outcome := range outcomes {
		if outcome.err != nil {
			return nil, outcome.err
		}
		merged = append(merged, outcome.results...)
	}
	return merged, nil
}
