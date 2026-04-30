package service

import (
	"context"
	"fmt"
	"strings"
	"time"

	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/fetch"
	"log_correlation_engine/internal/models"
)

type processingScope struct {
	WorkloadKey     string
	CheckpointKey   string
	OrganizationID  string
	Payload         []byte
	ActiveIncidents []models.IncidentState
	Lease           *distributed.Lease
	Run             *distributed.WorkloadRun
	Shard           *distributed.ShardContract
	Finalization    *runFinalizationState
}

type runFinalizationState struct {
	claimed bool
}

func (p *Processor) processSignalWorkload(ctx context.Context, scope processingScope, rules []models.Rule) (CycleSummary, error) {
	signature := signalPayloadSignature(scope.Payload)
	orgRules := filterRulesByOrg(rules, scope.OrganizationID)
	rulesSignature := ruleSetSignature(orgRules)

	checkpointState, err := p.checkpoints.LoadCheckpoint(ctx, scope.CheckpointKey)
	if err != nil {
		return CycleSummary{CheckpointFailures: 1}, fmt.Errorf("load checkpoint for workload %s: %w", scope.WorkloadKey, err)
	}

	activeByID := make(map[string]models.IncidentState, len(scope.ActiveIncidents))
	for _, incident := range scope.ActiveIncidents {
		activeByID[incident.IncidentID] = incident
	}

	changed, _, rulesChanged := shouldProcessOrganization(signature, rulesSignature, checkpointState)
	now := p.now().UTC()
	checkpointInFuture := !checkpointState.Checkpoint.IsZero() && checkpointState.Checkpoint.After(now.Add(time.Minute))
	if checkpointInFuture {
		changed = true
	}

	saveCheckpointState := func(summary *CycleSummary, cursor signalCursor, signalCount int) error {
		if err := p.ensureMutationOwned(ctx, &scope); err != nil {
			summary.CheckpointFailures++
			return fmt.Errorf("verify mutation ownership before saving checkpoint for workload %s: %w", scope.WorkloadKey, err)
		}
		state := models.ProcessingCheckpoint{
			Checkpoint:             cursor.Timestamp.UTC(),
			CheckpointDocID:        strings.TrimSpace(cursor.DocID),
			SignalPayloadSignature: signature,
			RulesSignature:         rulesSignature,
			SignalCount:            signalCount,
		}
		if scope.Lease != nil {
			state.LeaseOwner = scope.Lease.Owner
			state.LeaseToken = scope.Lease.Token
		}
		if err := p.checkpoints.SaveCheckpoint(ctx, scope.CheckpointKey, state); err != nil {
			summary.CheckpointFailures++
			return fmt.Errorf("save checkpoint for workload %s: %w", scope.WorkloadKey, err)
		}
		return nil
	}

	if len(scope.Payload) == 0 {
		summary := CycleSummary{}
		if err := p.closeInactiveIncidents(ctx, &scope, activeByID, map[string]struct{}{}, now, &summary); err != nil {
			return summary, err
		}
		if err := saveCheckpointState(&summary, checkpointToCursor(checkpointState), 0); err != nil {
			return summary, err
		}
		return summary, nil
	}

	signalLogs, err := models.DecodeSignalLogsPayload(scope.Payload)
	if err != nil {
		return CycleSummary{}, fmt.Errorf("decode signal payload for workload %s: %w", scope.WorkloadKey, err)
	}
	sortSignalLogs(signalLogs)

	summary := CycleSummary{
		OrganizationsWithLogs: boolToInt(len(signalLogs) > 0),
		SignalLogsRead:        len(signalLogs),
	}
	if len(signalLogs) == 0 {
		if err := p.closeInactiveIncidents(ctx, &scope, activeByID, map[string]struct{}{}, now, &summary); err != nil {
			return summary, err
		}
		if err := saveCheckpointState(&summary, checkpointToCursor(checkpointState), 0); err != nil {
			return summary, err
		}
		return summary, nil
	}

	checkpointCursor := checkpointToCursor(checkpointState)
	maxCursor := signalLogToCursor(signalLogs[len(signalLogs)-1])
	checkpointCaughtUp := compareCheckpointToSignalCursor(checkpointState, maxCursor) >= 0
	if !changed && len(scope.ActiveIncidents) == 0 && checkpointCaughtUp {
		summary.OrganizationsSkipped = 1
		p.logger.Debug(
			"workload skipped because signal payload is unchanged, checkpoint is caught up, and no incidents are active",
			append(scopeLoggerFields(scope),
				"signal_logs", len(signalLogs),
				"checkpoint", checkpointCursor.Timestamp.Format(time.RFC3339Nano),
				"checkpoint_doc_id", checkpointCursor.DocID,
			)...,
		)
		return summary, nil
	}

	ruleBuckets := partitionRulesByExecutionMode(orgRules)
	ruleLookup := indexRulesByID(orgRules)

	lookback := p.lookbackWindow(ruleBuckets.incrementalLive)
	if candidate := p.lookbackWindow(ruleBuckets.incrementalShadow); candidate > lookback {
		lookback = candidate
	}

	rawNewLogs := selectNewSignalLogs(signalLogs, checkpointState)
	checkpointAheadOfSignals := isCheckpointAheadOfSignals(checkpointState, maxCursor)
	orgSettings := p.resolveOrganizationSettings(scope.WorkloadKey, len(rawNewLogs))
	capBypassed := false
	if orgSettings.MaxNewLogsPerCycle > 0 && len(rawNewLogs) > orgSettings.MaxNewLogsPerCycle &&
		(len(ruleBuckets.fullPayloadLive) > 0 || len(ruleBuckets.fullPayloadShadow) > 0) {
		capBypassed = true
		orgSettings.MaxNewLogsPerCycle = 0
		p.logger.Warn(
			"autoscaling cap bypassed because full-payload rules require complete workload replay",
			append(scopeLoggerFields(scope),
				"raw_incremental_signal_logs", len(rawNewLogs),
				"full_payload_rules", len(ruleBuckets.fullPayloadLive)+len(ruleBuckets.fullPayloadShadow),
			)...,
		)
	}

	selection := selectIncrementalSignalLogs(signalLogs, checkpointState, lookback, orgSettings.MaxNewLogsPerCycle)
	if len(rawNewLogs) == 0 && len(signalLogs) > 0 && (rulesChanged || checkpointAheadOfSignals) {
		selection = incrementalSelection{
			WorkingLogs:   append([]models.SignalLog(nil), signalLogs...),
			NewLogs:       append([]models.SignalLog(nil), signalLogs...),
			RawNewCount:   len(signalLogs),
			MaxCursor:     maxCursor,
			LastProcessed: maxCursor,
		}
	}
	summary.IncrementalSignalLogs = selection.RawNewCount
	p.logOrganizationAutoscaling(scope.WorkloadKey, summary.IncrementalSignalLogs, orgSettings, selection.Capped)

	if len(selection.NewLogs) == 0 {
		if err := p.closeInactiveIncidents(ctx, &scope, activeByID, map[string]struct{}{}, now, &summary); err != nil {
			return summary, err
		}
		if err := saveCheckpointState(&summary, maxSignalCursor(checkpointCursor, selection.MaxCursor), len(signalLogs)); err != nil {
			return summary, err
		}
		return summary, nil
	}

	cache := newEnrichmentCache()
	liveResults := make([]models.CorrelationResult, 0)
	shadowResults := make([]models.CorrelationResult, 0)
	var recoveryLogs []models.FullLog
	fetchOptions := fetch.BatchFetchOptions{
		GroupedLookupBatchSize: orgSettings.GroupedLookupBatchSize,
	}

	if len(ruleBuckets.fullPayloadLive) > 0 || len(ruleBuckets.fullPayloadShadow) > 0 {
		fullWorkingLogs, newFullLogs, fetchErrors, err := p.enrichSignalLogs(ctx, signalLogs, selection.NewLogs, cache, fetchOptions)
		if err != nil {
			return summary, fmt.Errorf("enrich full-payload signal logs for workload %s: %w", scope.WorkloadKey, err)
		}
		summary.FetchErrors += fetchErrors
		summary.EnrichedLogs += len(fullWorkingLogs)

		if len(ruleBuckets.fullPayloadLive) > 0 {
			fullResults, metrics, err := p.correlateRuleBucket(ctx, scope, fullWorkingLogs, ruleBuckets.fullPayloadLive, "full_payload_live")
			if err != nil {
				return summary, fmt.Errorf("correlate full-payload live rules for workload %s: %w", scope.WorkloadKey, err)
			}
			summary.mergeCorrelationMetrics(metrics)
			liveResults = append(liveResults, fullResults...)
		}
		if len(ruleBuckets.fullPayloadShadow) > 0 {
			fullShadowResults, metrics, err := p.correlateRuleBucket(ctx, scope, fullWorkingLogs, ruleBuckets.fullPayloadShadow, "full_payload_shadow")
			if err != nil {
				return summary, fmt.Errorf("correlate full-payload shadow rules for workload %s: %w", scope.WorkloadKey, err)
			}
			summary.mergeCorrelationMetrics(metrics)
			shadowResults = append(shadowResults, fullShadowResults...)
		}
		recoveryLogs = newFullLogs
	}

	if len(ruleBuckets.incrementalLive) > 0 || len(ruleBuckets.incrementalShadow) > 0 {
		workingFullLogs, newFullLogs, fetchErrors, err := p.enrichSignalLogs(ctx, selection.WorkingLogs, selection.NewLogs, cache, fetchOptions)
		if err != nil {
			return summary, fmt.Errorf("enrich incremental signal logs for workload %s: %w", scope.WorkloadKey, err)
		}
		summary.FetchErrors += fetchErrors
		summary.EnrichedLogs += len(workingFullLogs)

		if len(ruleBuckets.incrementalLive) > 0 {
			incrementalResults, metrics, err := p.correlateRuleBucket(ctx, scope, workingFullLogs, ruleBuckets.incrementalLive, "incremental_live")
			if err != nil {
				return summary, fmt.Errorf("correlate incremental live rules for workload %s: %w", scope.WorkloadKey, err)
			}
			summary.mergeCorrelationMetrics(metrics)
			liveResults = append(liveResults, incrementalResults...)
		}
		if len(ruleBuckets.incrementalShadow) > 0 {
			shadowIncrementalResults, metrics, err := p.correlateRuleBucket(ctx, scope, workingFullLogs, ruleBuckets.incrementalShadow, "incremental_shadow")
			if err != nil {
				return summary, fmt.Errorf("correlate incremental shadow rules for workload %s: %w", scope.WorkloadKey, err)
			}
			summary.mergeCorrelationMetrics(metrics)
			shadowResults = append(shadowResults, shadowIncrementalResults...)
		}
		if recoveryLogs == nil {
			recoveryLogs = newFullLogs
		}
	}

	results, _ := models.NormalizeCorrelationResults(liveResults)
	shadowResults, _ = models.NormalizeCorrelationResults(shadowResults)
	summary.ShadowMatches = len(shadowResults)
	p.logShadowMatches(scope.OrganizationID, shadowResults, ruleLookup)
	summary.CorrelationsFound = len(results)

	actions := make([]incidentAction, 0)
	matchedIncidentIDs := make(map[string]struct{})
	for idx := range results {
		result := &results[idx]
		action, shouldWrite, err := p.buildIncidentAction(scope.OrganizationID, result, activeByID)
		if err != nil {
			summary.IncidentStateFailures++
			p.logger.Warn(
				"failed to build incident action",
				append(scopeLoggerFields(scope),
					"rule_id", result.RuleID,
					"error", err,
				)...,
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
		p.logMatchAudit("correlation rule matched", scope.OrganizationID, action.result, ruleLookup[result.RuleID], false)
		actions = append(actions, action)
	}

	recoveryActions, err := p.buildRecoveryClosures(ctx, scope.OrganizationID, orgRules, recoveryLogs, activeByID)
	if err != nil {
		summary.IncidentStateFailures++
		return summary, err
	}
	for _, action := range recoveryActions {
		summary.IncidentsClosed++
		actions = append(actions, action)
	}

	if err := p.applyIncidentActions(ctx, &scope, activeByID, actions, &summary); err != nil {
		return summary, err
	}

	if !selection.Capped {
		if err := p.closeInactiveIncidents(ctx, &scope, activeByID, matchedIncidentIDs, now, &summary); err != nil {
			return summary, err
		}
	} else {
		p.logger.Debug(
			"skipping inactivity-based incident closure because incremental backlog is being drained in capped slices",
			append(scopeLoggerFields(scope),
				"raw_incremental_signal_logs", selection.RawNewCount,
				"processed_incremental_signal_logs", len(selection.NewLogs),
			)...,
		)
	}

	checkpointToSave := maxSignalCursor(checkpointCursor, selection.MaxCursor)
	if selection.Capped {
		checkpointToSave = maxSignalCursor(checkpointCursor, selection.LastProcessed)
	}
	if err := saveCheckpointState(&summary, checkpointToSave, len(signalLogs)); err != nil {
		return summary, err
	}

	p.logger.Info(
		"workload processed",
		append(scopeLoggerFields(scope),
			"signal_logs", len(signalLogs),
			"incremental_signal_logs", selection.RawNewCount,
			"processed_incremental_signal_logs", len(selection.NewLogs),
			"effective_grouped_lookup_batch_size", orgSettings.GroupedLookupBatchSize,
			"effective_max_new_logs_per_cycle", orgSettings.MaxNewLogsPerCycle,
			"incremental_backlog_capped", selection.Capped,
			"incremental_cap_bypassed_for_full_payload", capBypassed,
			"incremental_rules", len(ruleBuckets.incrementalLive)+len(ruleBuckets.incrementalShadow),
			"full_payload_rules", len(ruleBuckets.fullPayloadLive)+len(ruleBuckets.fullPayloadShadow),
			"enriched_logs", summary.EnrichedLogs,
			"results_found", len(results),
			"shadow_matches", summary.ShadowMatches,
			"incidents_opened", summary.IncidentsOpened,
			"incidents_updated", summary.IncidentsUpdated,
			"incidents_closed", summary.IncidentsClosed,
			"results_written", summary.ResultsWritten,
			"fetch_errors", summary.FetchErrors,
			"result_write_failures", summary.ResultWriteFailures,
			"result_publish_failures", summary.ResultPublishFailures,
			"results_suppressed", summary.ResultsSuppressed,
			"incident_state_failures", summary.IncidentStateFailures,
			"checkpoint_failures", summary.CheckpointFailures,
			"distributed_shards_planned", summary.DistributedShardsPlanned,
			"distributed_shards_completed", summary.DistributedShardsCompleted,
			"distributed_shard_retries", summary.DistributedShardRetries,
			"distributed_shard_queue_depth", summary.DistributedShardQueueDepth,
			"distributed_correlation_logs", summary.DistributedCorrelationLogs,
			"distributed_total_shard_duration", summary.DistributedTotalShardDuration.String(),
			"distributed_max_shard_duration", summary.DistributedMaxShardDuration.String(),
			"distributed_merge_duration", summary.DistributedMergeDuration.String(),
		)...,
	)

	return summary, nil
}

func (p *Processor) ensureLeaseOwned(ctx context.Context, lease *distributed.Lease) error {
	if lease == nil {
		return nil
	}
	if p.distributed == nil {
		return fmt.Errorf("distributed store is not configured")
	}
	owned, err := p.distributed.VerifyWorkloadLease(ctx, *lease)
	if err != nil {
		return err
	}
	if !owned {
		return fmt.Errorf("workload lease %s is no longer owned by worker %s", lease.Workload.DisplayKey(), lease.Owner)
	}
	return nil
}

func (p *Processor) ensureMutationOwned(ctx context.Context, scope *processingScope) error {
	if scope == nil {
		return nil
	}
	if err := p.ensureLeaseOwned(ctx, scope.Lease); err != nil {
		return err
	}
	if scope.Run == nil {
		return nil
	}
	if scope.Lease == nil {
		return fmt.Errorf("workload run %s is missing a workload lease", scope.Run.DisplayKey())
	}
	if scope.Finalization == nil || scope.Finalization.claimed {
		return nil
	}
	if p.distributed == nil {
		return fmt.Errorf("distributed store is not configured")
	}
	owned, err := p.distributed.ClaimWorkloadRunFinalization(ctx, *scope.Lease, *scope.Run, p.distributedMetadataTTL())
	if err != nil {
		return err
	}
	if !owned {
		return fmt.Errorf("workload run finalization is already owned by another worker for %s", scope.Run.DisplayKey())
	}
	scope.Finalization.claimed = true
	return nil
}

func scopeLoggerFields(scope processingScope) []any {
	fields := []any{
		"workload", scope.WorkloadKey,
		"organization", scope.OrganizationID,
	}
	if scope.Run != nil {
		fields = append(fields, "run_id", scope.Run.ID)
	}
	if scope.Shard != nil {
		fields = append(fields, "shard_id", scope.Shard.NormalizedShardID())
	}
	return fields
}
