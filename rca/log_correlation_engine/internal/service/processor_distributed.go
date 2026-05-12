package service

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/autoscaling"
	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/fetch"
	"log_correlation_engine/internal/models"
)

type claimedWorkload struct {
	workload distributed.Workload
	lease    distributed.Lease
}

func (p *Processor) runDistributedCycle(ctx context.Context, started time.Time, rules []models.Rule) error {
	if p.distributed == nil {
		return fmt.Errorf("distributed mode is enabled but the configured store does not support distributed processing")
	}

	if err := p.heartbeatDistributedWorker(ctx); err != nil {
		return fmt.Errorf("heartbeat distributed worker %s: %w", p.workerID, err)
	}
	activeWorkers, err := p.distributed.ListActiveWorkers(ctx)
	if err != nil {
		return fmt.Errorf("list active distributed workers: %w", err)
	}

	if p.config.Redis.SignalStreamEnabled {
		if err := p.ingestSignalStreamDistributedAsLeader(ctx, rules); err != nil {
			return fmt.Errorf("ingest distributed signal stream: %w", err)
		}
	}

	organizations, err := p.store.ListOrganizations(ctx)
	if err != nil {
		return fmt.Errorf("list organizations: %w", err)
	}
	if len(organizations) == 0 {
		p.logger.Debug("no organizations found for distributed processing")
		return nil
	}
	if len(rules) == 0 {
		p.logger.Warn("no correlation rules loaded")
		return nil
	}

	workloads, err := p.claimDistributedWorkloads(ctx, organizations, rules)
	if err != nil {
		return err
	}
	if len(workloads) == 0 {
		assisted, assistErr := p.assistDistributedShardWork(ctx)
		if assistErr != nil {
			return fmt.Errorf("assist distributed shard work: %w", assistErr)
		}
		if assisted > 0 {
			p.logger.Info(
				"distributed shard assistance completed",
				"assisted_shards", assisted,
				"active_workers", len(activeWorkers),
				"worker_id", p.workerID,
			)
			return nil
		}
		p.logger.Debug(
			"no distributed workloads claimed for this cycle",
			"organizations", len(organizations),
			"active_workers", len(activeWorkers),
			"worker_id", p.workerID,
		)
		return nil
	}

	workerHeartbeatCtx, workerHeartbeatCancel := context.WithCancel(ctx)
	defer workerHeartbeatCancel()
	workerHeartbeatErr := make(chan error, 1)
	if p.config.Distributed.LeaseHeartbeatInterval > 0 {
		go p.runDistributedWorkerHeartbeat(workerHeartbeatCtx, workerHeartbeatErr)
	}

	workerCount := p.config.Scheduler.OrganizationWorkers
	if workerCount > len(workloads) {
		workerCount = len(workloads)
	}

	summary := CycleSummary{
		Organizations: len(organizations),
	}
	outcomes := make(chan organizationOutcome, len(workloads))
	jobs := make(chan claimedWorkload, len(workloads))
	for _, workload := range workloads {
		jobs <- workload
	}
	close(jobs)

	var wg sync.WaitGroup
	for workerID := 0; workerID < workerCount; workerID++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for workload := range jobs {
				if err := ctx.Err(); err != nil {
					return
				}

				workloadSummary, err := p.processClaimedWorkload(ctx, workload, rules)
				outcomes <- organizationOutcome{
					organization: workload.workload.DisplayKey(),
					summary:      workloadSummary,
					err:          err,
				}
			}
		}()
	}

	wg.Wait()
	close(outcomes)

	var firstErr error
	for outcome := range outcomes {
		if outcome.err != nil {
			summary.OrganizationFailures++
			if firstErr == nil {
				firstErr = fmt.Errorf("process workload %s: %w", outcome.organization, outcome.err)
			}
			p.logger.Error(
				"distributed workload processing failed",
				"workload", outcome.organization,
				"error", outcome.err,
			)
		}

		summary.OrganizationsWithLogs += outcome.summary.OrganizationsWithLogs
		summary.OrganizationsSkipped += outcome.summary.OrganizationsSkipped
		summary.SignalLogsRead += outcome.summary.SignalLogsRead
		summary.IncrementalSignalLogs += outcome.summary.IncrementalSignalLogs
		summary.EnrichedLogs += outcome.summary.EnrichedLogs
		summary.FetchErrors += outcome.summary.FetchErrors
		summary.CorrelationsFound += outcome.summary.CorrelationsFound
		summary.IncidentsOpened += outcome.summary.IncidentsOpened
		summary.IncidentsUpdated += outcome.summary.IncidentsUpdated
		summary.IncidentsClosed += outcome.summary.IncidentsClosed
		summary.ResultsWritten += outcome.summary.ResultsWritten
		summary.ResultWriteFailures += outcome.summary.ResultWriteFailures
		summary.ResultPublishFailures += outcome.summary.ResultPublishFailures
		summary.ResultsSuppressed += outcome.summary.ResultsSuppressed
		summary.ShadowMatches += outcome.summary.ShadowMatches
		summary.IncidentStateFailures += outcome.summary.IncidentStateFailures
		summary.CheckpointFailures += outcome.summary.CheckpointFailures
		summary.DistributedShardsPlanned += outcome.summary.DistributedShardsPlanned
		summary.DistributedShardsCompleted += outcome.summary.DistributedShardsCompleted
		summary.DistributedShardRetries += outcome.summary.DistributedShardRetries
		if outcome.summary.DistributedShardQueueDepth > summary.DistributedShardQueueDepth {
			summary.DistributedShardQueueDepth = outcome.summary.DistributedShardQueueDepth
		}
		summary.DistributedCorrelationLogs += outcome.summary.DistributedCorrelationLogs
		summary.DistributedTotalShardDuration += outcome.summary.DistributedTotalShardDuration
		if outcome.summary.DistributedMaxShardDuration > summary.DistributedMaxShardDuration {
			summary.DistributedMaxShardDuration = outcome.summary.DistributedMaxShardDuration
		}
		summary.DistributedMergeDuration += outcome.summary.DistributedMergeDuration
	}

	p.logger.Info(
		"correlation cycle completed",
		"started_at", started.Format(time.RFC3339Nano),
		"organizations", summary.Organizations,
		"claimed_workloads", len(workloads),
		"organization_workers", workerCount,
		"active_workers", len(activeWorkers),
		"organizations_with_logs", summary.OrganizationsWithLogs,
		"organizations_skipped", summary.OrganizationsSkipped,
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
		"checkpoint_failures", summary.CheckpointFailures,
		"distributed_shards_planned", summary.DistributedShardsPlanned,
		"distributed_shards_completed", summary.DistributedShardsCompleted,
		"distributed_shard_retries", summary.DistributedShardRetries,
		"distributed_shard_queue_depth", summary.DistributedShardQueueDepth,
		"distributed_correlation_logs", summary.DistributedCorrelationLogs,
		"distributed_total_shard_duration", summary.DistributedTotalShardDuration.String(),
		"distributed_max_shard_duration", summary.DistributedMaxShardDuration.String(),
		"distributed_merge_duration", summary.DistributedMergeDuration.String(),
		"distributed_mode", true,
		"worker_id", p.workerID,
	)

	if p.autoscaler != nil && p.autoscaler.Enabled() {
		p.autoscaler.ObserveDistributedCycle(summary.IncrementalSignalLogs, len(activeWorkers))
		if summary.DistributedShardsPlanned > 0 {
			p.autoscaler.ObserveDistributedObservation(autoscaling.DistributedObservation{
				ActiveWorkers:        len(activeWorkers),
				CorrelationWorkUnits: summary.DistributedCorrelationLogs,
				PlannedShards:        summary.DistributedShardsPlanned,
				CompletedShards:      summary.DistributedShardsCompleted,
				RetryCount:           summary.DistributedShardRetries,
				QueueDepth:           summary.DistributedShardQueueDepth,
				TotalShardDuration:   summary.DistributedTotalShardDuration,
				MaxShardDuration:     summary.DistributedMaxShardDuration,
				MergeDuration:        summary.DistributedMergeDuration,
			})
		}
		p.logger.Info(
			"autoscaling workload observed",
			"incremental_signal_logs", summary.IncrementalSignalLogs,
			"active_workers", len(activeWorkers),
			"distributed_shards_planned", summary.DistributedShardsPlanned,
			"distributed_shard_queue_depth", summary.DistributedShardQueueDepth,
			"distributed_total_shard_duration", summary.DistributedTotalShardDuration.String(),
			"distributed_merge_duration", summary.DistributedMergeDuration.String(),
		)
	}

	workerHeartbeatCancel()
	select {
	case heartbeatErr := <-workerHeartbeatErr:
		if heartbeatErr != nil && firstErr == nil {
			firstErr = fmt.Errorf("heartbeat distributed worker %s: %w", p.workerID, heartbeatErr)
		}
	default:
	}

	if firstErr != nil {
		return firstErr
	}
	return ctx.Err()
}

func (p *Processor) claimDistributedWorkloads(ctx context.Context, organizations []string, rules []models.Rule) ([]claimedWorkload, error) {
	remainingClaims := p.config.Distributed.ClaimLimitPerCycle
	workloads := make([]claimedWorkload, 0, remainingClaims)

	for _, organization := range organizations {
		if remainingClaims <= 0 {
			break
		}
		if len(filterRulesByOrg(rules, organization)) == 0 {
			continue
		}

		lease, ok, err := p.tryClaimWorkload(ctx, distributed.OrganizationWorkload(organization))
		if err != nil {
			return nil, err
		}
		if !ok {
			continue
		}

		workloads = append(workloads, claimedWorkload{workload: lease.Workload, lease: lease})
		remainingClaims--
	}

	return workloads, nil
}

func (p *Processor) tryClaimWorkload(ctx context.Context, workload distributed.Workload) (distributed.Lease, bool, error) {
	lease := distributed.NewLease(workload, p.workerID)
	ok, err := p.distributed.ClaimWorkloadLease(ctx, lease, p.config.Distributed.LeaseTTL)
	if err != nil {
		return distributed.Lease{}, false, fmt.Errorf("claim workload lease %s: %w", workload.DisplayKey(), err)
	}
	return lease, ok, nil
}

func (p *Processor) processClaimedWorkload(ctx context.Context, workload claimedWorkload, rules []models.Rule) (CycleSummary, error) {
	run := distributed.NewWorkloadRunAt(workload.lease.Workload, p.workerID, p.now().UTC())
	rootShard := distributed.RootShardContract(run)
	metadataTTL := p.distributedMetadataTTL()
	if err := p.distributed.StartWorkloadRun(ctx, workload.lease, run, rootShard, metadataTTL); err != nil {
		releaseCtx, releaseCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
		defer releaseCancel()
		if releaseErr := p.distributed.ReleaseWorkloadLease(releaseCtx, workload.lease); releaseErr != nil {
			p.logger.Warn(
				"failed to release workload lease after run start error",
				"workload", workload.workload.DisplayKey(),
				"run_id", run.ID,
				"error", releaseErr,
			)
		}
		return CycleSummary{}, fmt.Errorf("start workload run %s: %w", run.DisplayKey(), err)
	}

	heartbeatCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	heartbeatErr := make(chan error, 1)
	if p.config.Distributed.LeaseHeartbeatInterval > 0 {
		go p.runLeaseHeartbeat(heartbeatCtx, workload.lease, heartbeatErr)
	}

	finalization := &runFinalizationState{}
	summary, err := p.loadAndProcessClaimedWorkload(heartbeatCtx, workload, run, rootShard, finalization, rules)
	cancel()

	select {
	case hbErr := <-heartbeatErr:
		if hbErr != nil && err == nil {
			err = hbErr
		}
	default:
	}

	status := distributed.ShardStateCompleted
	message := ""
	if err != nil {
		status = distributed.ShardStateFailed
		message = err.Error()
		rootShard.Retryable = true
		if retryDelay := p.config.Distributed.LeaseHeartbeatInterval; retryDelay > 0 {
			rootShard.RetryAfter = p.now().UTC().Add(retryDelay)
		}
	}

	finishCtx, finishCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
	defer finishCancel()
	if finishErr := p.distributed.FinishWorkloadRun(finishCtx, workload.lease, run, rootShard, status, metadataTTL, message); finishErr != nil {
		if err == nil {
			err = finishErr
		} else {
			p.logger.Warn(
				"failed to finish distributed workload run",
				"workload", workload.workload.DisplayKey(),
				"run_id", run.ID,
				"error", finishErr,
			)
		}
	}

	releaseCtx, releaseCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
	defer releaseCancel()
	if releaseErr := p.distributed.ReleaseWorkloadLease(releaseCtx, workload.lease); releaseErr != nil && err == nil {
		err = releaseErr
	}
	return summary, err
}

func (p *Processor) heartbeatDistributedWorker(ctx context.Context) error {
	return p.distributed.HeartbeatWorker(ctx, distributed.WorkerHeartbeat{
		WorkerID:  p.workerID,
		UpdatedAt: p.now().UTC(),
	}, p.config.Distributed.LeaseTTL)
}

func (p *Processor) runDistributedWorkerHeartbeat(ctx context.Context, errCh chan<- error) {
	ticker := time.NewTicker(p.config.Distributed.LeaseHeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := p.heartbeatDistributedWorker(ctx); err != nil {
				select {
				case errCh <- err:
				default:
				}
				return
			}
		}
	}
}

func (p *Processor) runLeaseHeartbeat(ctx context.Context, lease distributed.Lease, errCh chan<- error) {
	ticker := time.NewTicker(p.config.Distributed.LeaseHeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			ok, err := p.distributed.RenewWorkloadLease(ctx, lease, p.config.Distributed.LeaseTTL)
			if err != nil {
				select {
				case errCh <- err:
				default:
				}
				return
			}
			if !ok {
				select {
				case errCh <- fmt.Errorf("lost workload lease %s during heartbeat", lease.Workload.DisplayKey()):
				default:
				}
				return
			}
		}
	}
}

func (p *Processor) loadAndProcessClaimedWorkload(
	ctx context.Context,
	claimed claimedWorkload,
	run distributed.WorkloadRun,
	shard distributed.ShardContract,
	finalization *runFinalizationState,
	rules []models.Rule,
) (CycleSummary, error) {
	payload, err := p.store.LoadSignalPayload(ctx, claimed.workload.OrganizationID)
	if err != nil {
		return CycleSummary{}, fmt.Errorf("load organization signal payload for workload %s: %w", claimed.workload.DisplayKey(), err)
	}
	incidents, err := p.store.ListActiveIncidents(ctx, claimed.workload.OrganizationID)
	if err != nil {
		return CycleSummary{}, fmt.Errorf("list organization active incidents for workload %s: %w", claimed.workload.DisplayKey(), err)
	}

	return p.processSignalWorkload(ctx, processingScope{
		WorkloadKey:     claimed.workload.DisplayKey(),
		CheckpointKey:   claimed.workload.CheckpointKey(),
		OrganizationID:  claimed.workload.OrganizationID,
		Payload:         payload,
		ActiveIncidents: incidents,
		Lease:           &claimed.lease,
		Run:             &run,
		Shard:           &shard,
		Finalization:    finalization,
	}, rules)
}

func (p *Processor) ingestSignalStreamDistributedAsLeader(ctx context.Context, rules []models.Rule) error {
	if !p.config.Distributed.SingleStreamIngestLeader {
		return p.ingestSignalStreamDistributed(ctx, rules)
	}

	lease, ok, err := p.tryClaimWorkload(ctx, distributed.SignalStreamIngestWorkload())
	if err != nil {
		return fmt.Errorf("claim stream ingest leader lease: %w", err)
	}
	if !ok {
		p.logger.Debug(
			"skipping distributed signal stream ingest because another worker owns the ingest lease",
			"worker_id", p.workerID,
		)
		return nil
	}

	heartbeatCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	heartbeatErr := make(chan error, 1)
	if p.config.Distributed.LeaseHeartbeatInterval > 0 {
		go p.runLeaseHeartbeat(heartbeatCtx, lease, heartbeatErr)
	}

	err = p.ingestSignalStreamDistributed(heartbeatCtx, rules)
	cancel()

	select {
	case hbErr := <-heartbeatErr:
		if hbErr != nil && err == nil {
			err = hbErr
		}
	default:
	}

	releaseCtx, releaseCancel := context.WithTimeout(context.Background(), p.config.Redis.WriteTimeout)
	defer releaseCancel()
	if releaseErr := p.distributed.ReleaseWorkloadLease(releaseCtx, lease); releaseErr != nil && err == nil {
		err = releaseErr
	}
	return err
}

func (p *Processor) ingestSignalStreamDistributed(ctx context.Context, rules []models.Rule) error {
	if err := p.distributed.EnsureSignalStreamConsumerGroup(ctx, p.config.Distributed.StreamConsumerGroup); err != nil {
		return err
	}

	events, ids, err := p.distributed.ReadSignalStreamConsumerGroup(
		ctx,
		p.config.Distributed.StreamConsumerGroup,
		p.consumer,
		p.config.Distributed.LeaseTTL,
	)
	if err != nil {
		return err
	}
	if len(events) == 0 {
		p.trimDistributedSignalStream(ctx)
		return nil
	}

	retentionCutoff := p.now().UTC().Add(-p.signalRetentionWindow(rules))
	grouped := make(map[string][]models.SignalLog)
	skipped := 0
	uniqueDocIDs := make([]string, 0, len(events))
	seenDocIDs := make(map[string]struct{}, len(events))
	for _, event := range events {
		organizationID := strings.TrimSpace(event.OrganizationID)
		docID := strings.TrimSpace(event.DocID)
		signal := strings.TrimSpace(event.Signal)
		if organizationID == "" || docID == "" || signal == "" ||
			(event.TimeStamp.IsZero() && event.SignalizedAt.IsZero()) {
			skipped++
			continue
		}
		eventTimestamp := event.TimeStamp
		if eventTimestamp.IsZero() {
			eventTimestamp = event.SignalizedAt
		}
		grouped[organizationID] = append(grouped[organizationID], models.SignalLog{
			HostIdentity: strings.TrimSpace(event.HostIdentity),
			Signal:       event.Signal,
			LogLevel:     event.LogLevel,
			DocID:        docID,
			TimeStamp:    eventTimestamp.UTC(),
			SignalizedAt: event.SignalizedAt.UTC(),
		})
		if _, ok := seenDocIDs[docID]; ok {
			continue
		}
		seenDocIDs[docID] = struct{}{}
		uniqueDocIDs = append(uniqueDocIDs, docID)
	}

	updatedOrganizations := 0
	deletedOrganizations := 0
	unchangedOrganizations := 0
	for organization, incoming := range grouped {
		updated, deleted, err := p.distributed.MergeSignalLogs(ctx, organization, incoming, retentionCutoff)
		if err != nil {
			return fmt.Errorf("merge signal payload for organization %s: %w", organization, err)
		}
		switch {
		case deleted:
			deletedOrganizations++
		case updated:
			updatedOrganizations++
		default:
			unchangedOrganizations++
		}
	}

	if err := p.distributed.AckSignalStream(ctx, p.config.Distributed.StreamConsumerGroup, ids); err != nil {
		return err
	}
	p.trimDistributedSignalStream(ctx)

	prefetchedDocIDs, skippedPrefetchDocIDs, prefetchStatus := p.scheduleDistributedFullLogPrefetch(uniqueDocIDs)

	p.logger.Info(
		"ingested compact signal stream",
		"stream_key", p.config.Redis.SignalStreamKey,
		"stream_events", len(events),
		"skipped_events", skipped,
		"organizations_updated", updatedOrganizations,
		"organizations_deleted", deletedOrganizations,
		"organizations_unchanged", unchangedOrganizations,
		"prefetch_candidate_doc_ids", len(uniqueDocIDs),
		"prefetched_doc_ids", prefetchedDocIDs,
		"prefetch_skipped_doc_ids", skippedPrefetchDocIDs,
		"prefetch_status", prefetchStatus,
		"distributed_mode", true,
		"worker_id", p.workerID,
		"consumer_group", p.config.Distributed.StreamConsumerGroup,
	)
	return nil
}

func (p *Processor) trimDistributedSignalStream(ctx context.Context) {
	trimMinID := streamTimeToID(p.now().UTC().Add(-p.config.Redis.SignalStreamUnconsumedRetention))
	if trimMinID == "" {
		return
	}
	if _, err := p.store.TrimSignalStream(ctx, trimMinID); err != nil {
		p.logger.Warn(
			"failed to trim distributed compact signal stream",
			"stream_key", p.config.Redis.SignalStreamKey,
			"trim_min_id", trimMinID,
			"error", err,
		)
	}
}

func (p *Processor) scheduleDistributedFullLogPrefetch(docIDs []string) (int, int, string) {
	if p.distributed == nil || !p.config.Distributed.PrefetchFullLogs || len(docIDs) == 0 {
		return 0, len(docIDs), "disabled"
	}

	maxDocIDs := p.distributedPrefetchMaxDocIDs()
	if maxDocIDs > 0 && len(docIDs) > maxDocIDs {
		p.logger.Info(
			"skipping distributed full log prefetch because acknowledged stream batch is too large",
			"candidate_doc_ids", len(docIDs),
			"max_doc_ids", maxDocIDs,
		)
		return 0, len(docIDs), "max_doc_ids_exceeded"
	}

	if !p.tryStartDistributedPrefetch() {
		p.logger.Debug(
			"skipping distributed full log prefetch because a previous prefetch is still running",
			"candidate_doc_ids", len(docIDs),
		)
		return 0, len(docIDs), "already_in_flight"
	}

	clonedDocIDs := append([]string(nil), docIDs...)
	go func() {
		defer p.finishDistributedPrefetch()

		prefetchCtx, cancel := context.WithTimeout(context.Background(), p.distributedPrefetchTimeout())
		defer cancel()

		p.prefetchDistributedFullLogs(prefetchCtx, clonedDocIDs)
	}()

	return len(docIDs), 0, "scheduled"
}

func (p *Processor) tryStartDistributedPrefetch() bool {
	p.prefetchMu.Lock()
	defer p.prefetchMu.Unlock()
	if p.prefetching {
		return false
	}
	p.prefetching = true
	return true
}

func (p *Processor) finishDistributedPrefetch() {
	p.prefetchMu.Lock()
	defer p.prefetchMu.Unlock()
	p.prefetching = false
}

func (p *Processor) distributedPrefetchTimeout() time.Duration {
	if p.config.Distributed.PrefetchTimeout > 0 {
		return p.config.Distributed.PrefetchTimeout
	}
	return 5 * time.Second
}

func (p *Processor) distributedPrefetchMaxDocIDs() int {
	if p.config.Distributed.PrefetchMaxDocIDs > 0 {
		return p.config.Distributed.PrefetchMaxDocIDs
	}
	return 1000
}

func (p *Processor) prefetchDistributedFullLogs(ctx context.Context, docIDs []string) {
	if p.distributed == nil || !p.config.Distributed.PrefetchFullLogs || len(docIDs) == 0 {
		return
	}

	missingDocIDs := append([]string(nil), docIDs...)
	if cached, err := p.distributed.LoadCachedFullLogs(ctx, docIDs); err == nil && len(cached) > 0 {
		missingDocIDs = missingDocIDs[:0]
		for _, docID := range docIDs {
			if _, ok := cached[docID]; ok {
				continue
			}
			missingDocIDs = append(missingDocIDs, docID)
		}
	} else if err != nil {
		p.logger.Warn("failed to load distributed full log cache during prefetch", "error", err)
	}

	if len(missingDocIDs) == 0 {
		return
	}

	options := fetch.BatchFetchOptions{
		GroupedLookupBatchSize: maxInt(1, p.config.Fetcher.GroupedLookupBatchSize),
	}
	fetched := p.fetchBatchLogsBestEffort(ctx, missingDocIDs, options)
	if len(fetched) == 0 {
		return
	}
	if err := p.distributed.SaveCachedFullLogs(ctx, fetched, p.config.Distributed.FullLogCacheTTL); err != nil {
		p.logger.Warn("failed to save distributed full log cache during prefetch", "error", err, "doc_ids", len(fetched))
	}
}

func (p *Processor) fetchBatchLogsBestEffort(
	ctx context.Context,
	docIDs []string,
	options fetch.BatchFetchOptions,
) map[string]*models.FullLog {
	switch batchFetcher := p.fetcher.(type) {
	case BatchLogFetcherWithOptions:
		fetched, err := batchFetcher.FetchLogsWithOptions(ctx, docIDs, options)
		if err != nil {
			p.logger.Warn("distributed full log prefetch batch failed", "error", err, "doc_ids", len(docIDs))
			return nil
		}
		return fetched
	case BatchLogFetcher:
		fetched, err := batchFetcher.FetchLogs(ctx, docIDs)
		if err != nil {
			p.logger.Warn("distributed full log prefetch batch failed", "error", err, "doc_ids", len(docIDs))
			return nil
		}
		return fetched
	default:
		result := make(map[string]*models.FullLog)
		for _, docID := range docIDs {
			fullLog, err := p.fetcher.FetchLog(ctx, docID)
			if err != nil {
				p.logger.Warn("distributed full log prefetch fetch failed", "error", err, "doc_id", docID)
				continue
			}
			if fullLog != nil {
				result[docID] = fullLog
			}
		}
		return result
	}
}
