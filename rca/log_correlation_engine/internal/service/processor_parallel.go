package service

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/autoscaling"
	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/models"
)

type correlationShard struct {
	index        int
	logs         []models.FullLog
	primaryStart time.Time
	primaryEnd   time.Time
}

type shardOutcome struct {
	results []models.CorrelationResult
	err     error
}

type correlationRunMetrics struct {
	ShardsPlanned      int
	ShardsCompleted    int
	ShardRetryCount    int
	ShardQueueDepth    int
	CorrelationLogs    int
	TotalShardDuration time.Duration
	MaxShardDuration   time.Duration
	MergeDuration      time.Duration
}

type distributedShardPlanDetails struct {
	Plan                         autoscaling.DistributedShardPlan
	RemainingRunBudget           time.Duration
	ReservedRunBudget            time.Duration
	AvailableCorrelationBudget   time.Duration
	EffectiveTargetShardDuration time.Duration
}

func (p *Processor) correlateRuleBucket(
	ctx context.Context,
	scope processingScope,
	logs []models.FullLog,
	rules []models.Rule,
	mode string,
) ([]models.CorrelationResult, correlationRunMetrics, error) {
	if p.shouldUseDistributedShardCorrelation(scope, logs, rules, mode) {
		return p.correlateRuleBucketDistributed(ctx, scope, logs, rules, mode)
	}
	if !p.shouldUseParallelCorrelation(logs, rules) {
		results, err := p.engine.Correlate(ctx, scope.OrganizationID, logs, rules)
		return results, correlationRunMetrics{}, err
	}
	return p.correlateRuleBucketLocal(ctx, scope, logs, rules, mode)
}

func (p *Processor) correlateRuleBucketLocal(
	ctx context.Context,
	scope processingScope,
	logs []models.FullLog,
	rules []models.Rule,
	mode string,
) ([]models.CorrelationResult, correlationRunMetrics, error) {
	overlap := p.lookbackWindow(rules)
	shards := buildCorrelationShards(logs, p.config.Engine.ParallelCorrelation.TargetLogsPerShard, overlap)
	if len(shards) <= 1 {
		results, err := p.engine.Correlate(ctx, scope.OrganizationID, logs, rules)
		return results, correlationRunMetrics{}, err
	}

	workerCount := p.config.Engine.ParallelCorrelation.MaxWorkers
	if workerCount > len(shards) {
		workerCount = len(shards)
	}

	p.logger.Info(
		"parallel correlation enabled",
		append(scopeLoggerFields(scope),
			"mode", mode,
			"logs", len(logs),
			"rules", len(rules),
			"shards", len(shards),
			"workers", workerCount,
			"overlap", overlap.String(),
			"target_logs_per_shard", p.config.Engine.ParallelCorrelation.TargetLogsPerShard,
			"distributed_parallelism", false,
		)...,
	)

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	jobs := make(chan correlationShard, len(shards))
	outcomes := make(chan shardOutcome, len(shards))
	for _, shard := range shards {
		jobs <- shard
	}
	close(jobs)

	var wg sync.WaitGroup
	for workerID := 0; workerID < workerCount; workerID++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for shard := range jobs {
				if err := runCtx.Err(); err != nil {
					return
				}

				results, err := p.engine.Correlate(runCtx, scope.OrganizationID, shard.logs, rules)
				if err != nil {
					select {
					case outcomes <- shardOutcome{err: fmt.Errorf("correlate shard %d: %w", shard.index, err)}:
					default:
					}
					cancel()
					return
				}
				outcomes <- shardOutcome{
					results: filterCorrelationResultsByShard(results, shard),
				}
			}
		}()
	}

	wg.Wait()
	close(outcomes)

	merged := make([]models.CorrelationResult, 0)
	var firstErr error
	for outcome := range outcomes {
		if outcome.err != nil {
			if firstErr == nil {
				firstErr = outcome.err
			}
			continue
		}
		merged = append(merged, outcome.results...)
	}
	if firstErr != nil {
		return nil, correlationRunMetrics{}, firstErr
	}
	return merged, correlationRunMetrics{}, nil
}

func (p *Processor) correlateRuleBucketDistributed(
	ctx context.Context,
	scope processingScope,
	logs []models.FullLog,
	rules []models.Rule,
	mode string,
) ([]models.CorrelationResult, correlationRunMetrics, error) {
	activeWorkers := p.activeDistributedWorkerCount(ctx)
	if activeWorkers <= 1 {
		return p.correlateRuleBucketLocal(ctx, scope, logs, rules, mode)
	}

	overlap := p.lookbackWindow(rules)
	shardPlanDetails, err := p.resolveDistributedShardPlan(ctx, len(logs), activeWorkers)
	if err != nil {
		return nil, correlationRunMetrics{}, fmt.Errorf("plan distributed shard correlation for workload %s mode %s: %w", scope.WorkloadKey, mode, err)
	}
	shards := buildCorrelationShards(logs, shardPlanDetails.Plan.TargetLogsPerShard, overlap)
	if len(shards) <= 1 {
		results, err := p.engine.Correlate(ctx, scope.OrganizationID, logs, rules)
		return results, correlationRunMetrics{}, err
	}

	payloads := make([]distributed.ShardExecutionPayload, 0, len(shards))
	correlationWorkUnits := 0
	for _, shard := range shards {
		correlationWorkUnits += len(shard.logs)
		payloads = append(payloads, distributed.ShardExecutionPayload{
			Workload:     scope.Run.Workload,
			RunID:        scope.Run.ID,
			ShardID:      fmt.Sprintf("%s-%04d", mode, shard.index),
			Mode:         mode,
			PrimaryStart: shard.primaryStart.UTC(),
			PrimaryEnd:   shard.primaryEnd.UTC(),
			Logs:         append([]models.FullLog(nil), shard.logs...),
			Rules:        append([]models.Rule(nil), rules...),
		})
	}

	p.logger.Info(
		"distributed shard correlation enabled",
		append(scopeLoggerFields(scope),
			"mode", mode,
			"logs", len(logs),
			"rules", len(rules),
			"shards", len(payloads),
			"active_workers", activeWorkers,
			"queue_depth", shardPlanDetails.Plan.QueueDepth,
			"correlation_work_units", correlationWorkUnits,
			"overlap", overlap.String(),
			"target_logs_per_shard", shardPlanDetails.Plan.TargetLogsPerShard,
			"estimated_cluster_duration", shardPlanDetails.Plan.EstimatedClusterDuration.String(),
			"remaining_run_budget", formatDurationOrUnbounded(shardPlanDetails.RemainingRunBudget),
			"distributed_run_reserve", shardPlanDetails.ReservedRunBudget.String(),
			"available_correlation_budget", formatDurationOrUnbounded(shardPlanDetails.AvailableCorrelationBudget),
			"effective_target_shard_duration", shardPlanDetails.EffectiveTargetShardDuration.String(),
			"distributed_parallelism", true,
		)...,
	)

	if err := p.distributed.StoreWorkloadShards(ctx, *scope.Lease, *scope.Run, payloads, p.distributedMetadataTTL()); err != nil {
		return nil, correlationRunMetrics{}, fmt.Errorf("store distributed shard plan for workload %s mode %s: %w", scope.WorkloadKey, mode, err)
	}

	return p.collectDistributedShardResults(
		ctx,
		scope,
		mode,
		correlationRunMetrics{
			ShardsPlanned:   len(payloads),
			ShardQueueDepth: shardPlanDetails.Plan.QueueDepth,
			CorrelationLogs: correlationWorkUnits,
		},
	)
}

func (p *Processor) assistDistributedShardWork(ctx context.Context) (int, error) {
	if p.distributed == nil || !p.config.Distributed.Enabled || !p.config.Engine.ParallelCorrelation.Enabled {
		return 0, nil
	}

	processed := 0
	waitUntil := time.Now().UTC().Add(2 * time.Second)
	for {
		claimed, err := p.processOneDistributedShard(ctx, nil)
		if err != nil {
			return processed, err
		}
		if claimed {
			processed++
			continue
		}
		if processed > 0 || time.Now().UTC().After(waitUntil) {
			return processed, nil
		}

		select {
		case <-ctx.Done():
			return processed, ctx.Err()
		case <-time.After(p.distributedShardPollInterval()):
		}
	}
}

func (p *Processor) processOneDistributedShard(ctx context.Context, run *distributed.WorkloadRun) (bool, error) {
	if p.distributed == nil {
		return false, nil
	}

	if remainingBudget, ok := p.remainingRunBudget(ctx); ok && remainingBudget <= p.distributedRunReserve() {
		p.logger.Debug(
			"skipping distributed shard claim because remaining run budget is at or below reserve",
			"worker_id", p.workerID,
			"remaining_run_budget", remainingBudget.String(),
			"distributed_run_reserve", p.distributedRunReserve().String(),
		)
		return false, nil
	}

	payload, lease, err := p.distributed.ClaimWorkloadShard(ctx, p.workerID, p.config.Distributed.LeaseTTL, run)
	if err != nil {
		return false, err
	}
	if payload == nil || lease == nil {
		return false, nil
	}

	heartbeatCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	heartbeatErr := make(chan error, 1)
	if p.config.Distributed.LeaseHeartbeatInterval > 0 {
		go p.runShardLeaseHeartbeat(heartbeatCtx, *lease, heartbeatErr)
	}

	shardTimeout, remainingBudget, budgetErr := p.distributedShardExecutionBudget(ctx)
	if budgetErr != nil {
		retryAfter := p.distributedShardRetryAfter()
		if failErr := p.failDistributedShard(*lease, budgetErr, true, retryAfter); failErr != nil {
			return true, fmt.Errorf("fail distributed shard %s: %w", lease.Contract.StateKey(), failErr)
		}
		p.logger.Warn(
			"distributed shard skipped because execution budget is exhausted",
			"workload", payload.Workload.DisplayKey(),
			"run_id", payload.RunID,
			"shard_id", payload.NormalizedShardID(),
			"mode", payload.NormalizedMode(),
			"log_count", len(payload.Logs),
			"worker_id", p.workerID,
			"remaining_run_budget", formatDurationOrUnbounded(remainingBudget),
			"distributed_run_reserve", p.distributedRunReserve().String(),
			"configured_shard_timeout", p.distributedShardTimeout().String(),
			"retry_after", retryAfter.Format(time.RFC3339Nano),
			"error", budgetErr,
		)
		return true, nil
	}

	shardCtx, shardCancel := context.WithTimeout(heartbeatCtx, shardTimeout)
	defer shardCancel()

	started := time.Now()
	results, err := p.engine.Correlate(shardCtx, payload.Workload.OrganizationID, payload.Logs, payload.Rules)
	cancel()
	duration := time.Since(started)

	select {
	case hbErr := <-heartbeatErr:
		if hbErr != nil && err == nil {
			err = hbErr
		}
	default:
	}

	if err != nil {
		retryable := false
		retryAfter := time.Time{}
		if errors.Is(err, context.DeadlineExceeded) && ctx.Err() == nil {
			retryable = true
			retryAfter = p.distributedShardRetryAfter()
		}
		if failErr := p.failDistributedShard(*lease, err, true, retryAfter); failErr != nil {
			return true, fmt.Errorf("fail distributed shard %s: %w", lease.Contract.StateKey(), failErr)
		}
		if retryable {
			p.logger.Warn(
				"distributed shard exceeded execution budget",
				"workload", payload.Workload.DisplayKey(),
				"run_id", payload.RunID,
				"shard_id", payload.NormalizedShardID(),
				"mode", payload.NormalizedMode(),
				"log_count", len(payload.Logs),
				"worker_id", p.workerID,
				"shard_timeout", shardTimeout.String(),
				"remaining_run_budget", formatDurationOrUnbounded(remainingBudget),
				"distributed_run_reserve", p.distributedRunReserve().String(),
				"retry_after", retryAfter.Format(time.RFC3339Nano),
				"error", err,
			)
			return true, nil
		}
		return true, fmt.Errorf("correlate distributed shard %s: %w", lease.Contract.StateKey(), err)
	}

	filtered := filterCorrelationResultsByShard(results, correlationShard{
		primaryStart: payload.PrimaryStart.UTC(),
		primaryEnd:   payload.PrimaryEnd.UTC(),
	})

	completeCtx, completeCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
	defer completeCancel()
	if err := p.distributed.CompleteWorkloadShard(completeCtx, *lease, distributed.ShardExecutionResult{
		Workload:    payload.Workload,
		RunID:       payload.RunID,
		ShardID:     payload.ShardID,
		Mode:        payload.Mode,
		WorkerID:    p.workerID,
		LogCount:    len(payload.Logs),
		Duration:    duration,
		Status:      distributed.ShardStateCompleted,
		Results:     filtered,
		CompletedAt: p.now().UTC(),
	}, p.distributedMetadataTTL()); err != nil {
		return true, fmt.Errorf("complete distributed shard %s: %w", lease.Contract.StateKey(), err)
	}

	return true, nil
}

func (p *Processor) runShardLeaseHeartbeat(ctx context.Context, lease distributed.ShardLease, errCh chan<- error) {
	ticker := time.NewTicker(p.config.Distributed.LeaseHeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			ok, err := p.distributed.RenewWorkloadShardLease(ctx, lease, p.config.Distributed.LeaseTTL)
			if err != nil {
				select {
				case errCh <- err:
				default:
				}
				return
			}
			if !ok {
				select {
				case errCh <- fmt.Errorf("lost distributed shard lease %s during heartbeat", lease.Contract.StateKey()):
				default:
				}
				return
			}
		}
	}
}

func (p *Processor) collectDistributedShardResults(
	ctx context.Context,
	scope processingScope,
	mode string,
	metrics correlationRunMetrics,
) ([]models.CorrelationResult, correlationRunMetrics, error) {
	if metrics.ShardsPlanned <= 0 {
		return nil, metrics, nil
	}

	for {
		if err := ctx.Err(); err != nil {
			return nil, metrics, err
		}

		claimed, err := p.processOneDistributedShard(ctx, scope.Run)
		if err != nil {
			return nil, metrics, err
		}

		results, contracts, err := p.distributed.LoadWorkloadShardResults(ctx, *scope.Run, mode)
		if err != nil {
			return nil, metrics, err
		}

		completed := 0
		retries := 0
		for _, contract := range contracts {
			if contract.Attempt > 1 {
				retries += contract.Attempt - 1
			}
			switch contract.State {
			case distributed.ShardStateCompleted:
				completed++
			case distributed.ShardStateFailed:
				if !contract.Retryable {
					return nil, metrics, fmt.Errorf("distributed shard %s failed without retry", contract.StateKey())
				}
			}
		}
		metrics.ShardsCompleted = completed
		metrics.ShardRetryCount = retries

		if completed >= metrics.ShardsPlanned {
			for _, shardResult := range results {
				metrics.TotalShardDuration += shardResult.Duration
				if shardResult.Duration > metrics.MaxShardDuration {
					metrics.MaxShardDuration = shardResult.Duration
				}
			}
			mergeStarted := time.Now()
			merged := make([]models.CorrelationResult, 0)
			sort.Slice(results, func(i, j int) bool {
				if results[i].ShardID == results[j].ShardID {
					return results[i].WorkerID < results[j].WorkerID
				}
				return results[i].ShardID < results[j].ShardID
			})
			for _, shardResult := range results {
				merged = append(merged, shardResult.Results...)
			}
			metrics.MergeDuration += time.Since(mergeStarted)
			return merged, metrics, nil
		}

		if !claimed {
			select {
			case <-ctx.Done():
				return nil, metrics, ctx.Err()
			case <-time.After(p.distributedShardPollInterval()):
			}
		}
	}
}

func (p *Processor) shouldUseParallelCorrelation(logs []models.FullLog, rules []models.Rule) bool {
	cfg := p.config.Engine.ParallelCorrelation
	return cfg.Enabled &&
		len(logs) >= cfg.MinLogs &&
		cfg.TargetLogsPerShard > 0 &&
		len(rules) > 0
}

func (p *Processor) shouldUseDistributedShardCorrelation(
	scope processingScope,
	logs []models.FullLog,
	rules []models.Rule,
	mode string,
) bool {
	if !p.shouldUseParallelCorrelation(logs, rules) {
		return false
	}
	if !p.config.Distributed.Enabled || p.distributed == nil {
		return false
	}
	if scope.Run == nil || scope.Lease == nil {
		return false
	}
	return strings.HasPrefix(strings.TrimSpace(mode), "incremental_")
}

func (p *Processor) activeDistributedWorkerCount(ctx context.Context) int {
	if p.distributed == nil {
		return 1
	}
	workers, err := p.distributed.ListActiveWorkers(ctx)
	if err != nil {
		p.logger.Warn("failed to list active distributed workers for shard planning", "error", err)
		return 1
	}
	if len(workers) == 0 {
		return 1
	}
	return len(workers)
}

func (p *Processor) resolveDistributedShardPlan(
	ctx context.Context,
	logCount int,
	activeWorkers int,
) (distributedShardPlanDetails, error) {
	baselineTargetDuration := p.distributedTargetShardDuration()
	details := distributedShardPlanDetails{
		ReservedRunBudget:            p.distributedRunReserve(),
		EffectiveTargetShardDuration: baselineTargetDuration,
	}

	defaultTargetLogsPerShard := maxInt(1, p.config.Engine.ParallelCorrelation.TargetLogsPerShard)
	if remaining, ok := p.remainingRunBudget(ctx); ok {
		details.RemainingRunBudget = remaining
		available := remaining - details.ReservedRunBudget
		if available <= 0 {
			return distributedShardPlanDetails{}, fmt.Errorf(
				"insufficient remaining run budget for distributed shard correlation: remaining=%s reserve=%s",
				remaining.String(),
				details.ReservedRunBudget.String(),
			)
		}
		details.AvailableCorrelationBudget = available

		effectiveTarget := minDuration(baselineTargetDuration, available/2)
		minTarget := maxDuration(500*time.Millisecond, baselineTargetDuration/4)
		if effectiveTarget < minTarget {
			effectiveTarget = minTarget
		}
		if effectiveTarget > available {
			effectiveTarget = available
		}
		if effectiveTarget <= 0 {
			return distributedShardPlanDetails{}, fmt.Errorf(
				"insufficient remaining run budget for distributed shard correlation after reserve: remaining=%s reserve=%s",
				remaining.String(),
				details.ReservedRunBudget.String(),
			)
		}
		details.EffectiveTargetShardDuration = effectiveTarget
		defaultTargetLogsPerShard = scaleTargetLogsForDuration(defaultTargetLogsPerShard, baselineTargetDuration, effectiveTarget)
	}

	hints := autoscaling.DistributedShardHints{
		DefaultTargetLogsPerShard: defaultTargetLogsPerShard,
		MinShardsPerWorker:        p.config.Engine.ParallelCorrelation.DistributedMinShardsPerWorker,
		MaxShardsPerWorker:        p.config.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker,
		TargetShardDuration:       details.EffectiveTargetShardDuration,
	}

	if p.autoscaler != nil && p.autoscaler.Enabled() {
		details.Plan = p.autoscaler.ResolveDistributedShardPlan(logCount, activeWorkers, hints)
	} else {
		targetLogsPerShard := maxInt(1, hints.DefaultTargetLogsPerShard)
		if logCount <= 0 {
			details.Plan = autoscaling.DistributedShardPlan{
				ActiveWorkers:      maxInt(1, activeWorkers),
				DesiredShards:      0,
				TargetLogsPerShard: targetLogsPerShard,
			}
		} else {
			activeWorkers = maxInt(1, activeWorkers)
			desiredShards := (logCount + targetLogsPerShard - 1) / targetLogsPerShard
			minShards := activeWorkers * maxInt(1, hints.MinShardsPerWorker)
			maxShards := activeWorkers * maxInt(maxInt(1, hints.MinShardsPerWorker), hints.MaxShardsPerWorker)
			if desiredShards < minShards {
				desiredShards = minShards
			}
			if desiredShards > maxShards {
				desiredShards = maxShards
			}
			if desiredShards > logCount {
				desiredShards = logCount
			}
			if desiredShards <= 0 {
				desiredShards = 1
			}
			details.Plan = autoscaling.DistributedShardPlan{
				ActiveWorkers:      activeWorkers,
				DesiredShards:      desiredShards,
				TargetLogsPerShard: (logCount + desiredShards - 1) / desiredShards,
				QueueDepth:         maxInt(0, desiredShards-activeWorkers),
			}
		}
	}

	if details.AvailableCorrelationBudget > 0 &&
		details.Plan.EstimatedClusterDuration > 0 &&
		details.Plan.EstimatedClusterDuration > details.AvailableCorrelationBudget {
		return distributedShardPlanDetails{}, fmt.Errorf(
			"insufficient remaining run budget for distributed shard correlation: available=%s estimated=%s",
			details.AvailableCorrelationBudget.String(),
			details.Plan.EstimatedClusterDuration.String(),
		)
	}

	return details, nil
}

func (p *Processor) distributedShardPollInterval() time.Duration {
	if p.config.Engine.ParallelCorrelation.ShardPollInterval > 0 {
		return p.config.Engine.ParallelCorrelation.ShardPollInterval
	}
	return 20 * time.Millisecond
}

func (p *Processor) distributedTargetShardDuration() time.Duration {
	if p.config.Engine.ParallelCorrelation.DistributedTargetShardDuration > 0 {
		return p.config.Engine.ParallelCorrelation.DistributedTargetShardDuration
	}
	return time.Second
}

func (p *Processor) distributedShardTimeout() time.Duration {
	if p.config.Engine.ParallelCorrelation.DistributedShardTimeout > 0 {
		return p.config.Engine.ParallelCorrelation.DistributedShardTimeout
	}
	return 5 * time.Second
}

func (p *Processor) distributedRunReserve() time.Duration {
	if p.config.Engine.ParallelCorrelation.DistributedRunReserve > 0 {
		return p.config.Engine.ParallelCorrelation.DistributedRunReserve
	}
	return 5 * time.Second
}

func (p *Processor) remainingRunBudget(ctx context.Context) (time.Duration, bool) {
	deadline, ok := ctx.Deadline()
	if !ok {
		return 0, false
	}
	remaining := time.Until(deadline)
	if remaining < 0 {
		remaining = 0
	}
	return remaining, true
}

func (p *Processor) distributedShardExecutionBudget(ctx context.Context) (time.Duration, time.Duration, error) {
	budget := p.distributedShardTimeout()
	remaining, ok := p.remainingRunBudget(ctx)
	if !ok {
		return budget, 0, nil
	}

	available := remaining - p.distributedRunReserve()
	if available <= 0 {
		return 0, remaining, fmt.Errorf(
			"insufficient remaining run budget for distributed shard execution: remaining=%s reserve=%s",
			remaining.String(),
			p.distributedRunReserve().String(),
		)
	}
	if budget <= 0 || available < budget {
		budget = available
	}
	if budget <= 0 {
		return 0, remaining, fmt.Errorf(
			"insufficient remaining run budget for distributed shard execution after reserve: remaining=%s reserve=%s",
			remaining.String(),
			p.distributedRunReserve().String(),
		)
	}
	return budget, remaining, nil
}

func (p *Processor) distributedShardRetryAfter() time.Time {
	retryDelay := p.distributedShardPollInterval()
	if p.config.Distributed.LeaseHeartbeatInterval > 0 && p.config.Distributed.LeaseHeartbeatInterval > retryDelay {
		retryDelay = p.config.Distributed.LeaseHeartbeatInterval
	}
	if retryDelay <= 0 {
		retryDelay = time.Second
	}
	return p.now().UTC().Add(retryDelay)
}

func (p *Processor) failDistributedShard(lease distributed.ShardLease, execErr error, retryable bool, retryAfter time.Time) error {
	failCtx, failCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
	defer failCancel()
	return p.distributed.FailWorkloadShard(failCtx, lease, execErr.Error(), retryable, retryAfter, p.distributedMetadataTTL())
}

func scaleTargetLogsForDuration(defaultTarget int, baseline time.Duration, effective time.Duration) int {
	defaultTarget = maxInt(1, defaultTarget)
	if baseline <= 0 || effective <= 0 || effective >= baseline {
		return defaultTarget
	}
	scaled := int(float64(defaultTarget)*float64(effective)/float64(baseline) + 0.5)
	return maxInt(1, scaled)
}

func minDuration(left time.Duration, right time.Duration) time.Duration {
	if left <= 0 {
		return right
	}
	if right <= 0 {
		return left
	}
	if left < right {
		return left
	}
	return right
}

func maxDuration(left time.Duration, right time.Duration) time.Duration {
	if left > right {
		return left
	}
	return right
}

func formatDurationOrUnbounded(value time.Duration) string {
	if value <= 0 {
		return "unbounded"
	}
	return value.String()
}

func buildCorrelationShards(logs []models.FullLog, targetLogsPerShard int, overlap time.Duration) []correlationShard {
	if len(logs) == 0 {
		return nil
	}

	sortedLogs := append([]models.FullLog(nil), logs...)
	sort.Slice(sortedLogs, func(i, j int) bool {
		if sortedLogs[i].Timestamp.Equal(sortedLogs[j].Timestamp) {
			return sortedLogs[i].DocID < sortedLogs[j].DocID
		}
		return sortedLogs[i].Timestamp.Before(sortedLogs[j].Timestamp)
	})

	if targetLogsPerShard <= 0 || len(sortedLogs) <= targetLogsPerShard {
		return []correlationShard{{
			index:        0,
			logs:         sortedLogs,
			primaryStart: sortedLogs[0].Timestamp.UTC(),
			primaryEnd:   sortedLogs[len(sortedLogs)-1].Timestamp.UTC(),
		}}
	}

	shards := make([]correlationShard, 0, maxInt(1, len(sortedLogs)/targetLogsPerShard))
	for start := 0; start < len(sortedLogs); {
		end := start + targetLogsPerShard
		if end > len(sortedLogs) {
			end = len(sortedLogs)
		}
		if end < len(sortedLogs) {
			boundary := sortedLogs[end-1].Timestamp.UTC()
			for end < len(sortedLogs) && sortedLogs[end].Timestamp.UTC().Equal(boundary) {
				end++
			}
		}

		primaryStart := sortedLogs[start].Timestamp.UTC()
		primaryEnd := sortedLogs[end-1].Timestamp.UTC()
		overlapStart := start
		if overlap > 0 {
			cutoff := primaryStart.Add(-overlap)
			overlapStart = sort.Search(len(sortedLogs), func(i int) bool {
				return !sortedLogs[i].Timestamp.Before(cutoff)
			})
			if overlapStart > start {
				overlapStart = start
			}
		}

		shards = append(shards, correlationShard{
			index:        len(shards),
			logs:         append([]models.FullLog(nil), sortedLogs[overlapStart:end]...),
			primaryStart: primaryStart,
			primaryEnd:   primaryEnd,
		})
		start = end
	}

	return shards
}

func filterCorrelationResultsByShard(results []models.CorrelationResult, shard correlationShard) []models.CorrelationResult {
	if len(results) == 0 {
		return nil
	}

	filtered := make([]models.CorrelationResult, 0, len(results))
	for _, result := range results {
		matchedAt := correlationResultMatchedAt(result)
		if matchedAt.IsZero() {
			continue
		}
		if matchedAt.Before(shard.primaryStart) || matchedAt.After(shard.primaryEnd) {
			continue
		}
		filtered = append(filtered, result)
	}
	return filtered
}

func correlationResultMatchedAt(result models.CorrelationResult) time.Time {
	if !result.MatchedAt.IsZero() {
		return result.MatchedAt.UTC()
	}
	latest := time.Time{}
	for _, entry := range result.LogID {
		if entry.Timestamp.After(latest) {
			latest = entry.Timestamp.UTC()
		}
	}
	return latest
}
