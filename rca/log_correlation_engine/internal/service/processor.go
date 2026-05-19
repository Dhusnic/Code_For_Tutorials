package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/autoscaling"
	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/fetch"
	"log_correlation_engine/internal/models"
	"log_correlation_engine/internal/utils"
)

type OrganizationStore interface {
	ListOrganizations(ctx context.Context) ([]string, error)
	LoadSignalEventsWindow(ctx context.Context, since time.Time) ([]models.FullLog, error)
	LoadSignalPayload(ctx context.Context, organization string) ([]byte, error)
	SaveSignalLogs(ctx context.Context, organization string, logs []models.SignalLog) error
	DeleteSignalLogs(ctx context.Context, organization string) error
	ReadSignalStream(ctx context.Context, lastID string) ([]models.SignalStreamEvent, string, error)
	TrimSignalStream(ctx context.Context, minID string) (int64, error)
	PublishResult(ctx context.Context, result *models.CorrelationResult) error
	LoadIncident(ctx context.Context, organization, incidentID string) (*models.IncidentState, error)
	ListActiveIncidents(ctx context.Context, organization string) ([]models.IncidentState, error)
	SaveIncident(ctx context.Context, state *models.IncidentState, ttl time.Duration) error
	DeleteIncident(ctx context.Context, organization, incidentID string) error
}

type SignalActivityStore interface {
	CountSignalEventsWindowForSignals(ctx context.Context, since time.Time, signalKeys []string) (map[string]int, error)
}

type CheckpointStore interface {
	LoadCheckpoint(ctx context.Context, organization string) (models.ProcessingCheckpoint, error)
	SaveCheckpoint(ctx context.Context, organization string, checkpoint models.ProcessingCheckpoint) error
}

type DistributedStore interface {
	EnsureSignalStreamConsumerGroup(ctx context.Context, group string) error
	ReadSignalStreamConsumerGroup(ctx context.Context, group, consumer string, minIdle time.Duration) ([]models.SignalStreamEvent, []string, error)
	AckSignalStream(ctx context.Context, group string, ids []string) error
	MergeSignalLogs(ctx context.Context, organization string, incoming []models.SignalLog, retentionCutoff time.Time) (bool, bool, error)
	LoadCachedFullLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error)
	SaveCachedFullLogs(ctx context.Context, logs map[string]*models.FullLog, ttl time.Duration) error
	HeartbeatWorker(ctx context.Context, worker distributed.WorkerHeartbeat, ttl time.Duration) error
	ListActiveWorkers(ctx context.Context) ([]distributed.WorkerHeartbeat, error)
	ClaimWorkloadLease(ctx context.Context, lease distributed.Lease, ttl time.Duration) (bool, error)
	RenewWorkloadLease(ctx context.Context, lease distributed.Lease, ttl time.Duration) (bool, error)
	VerifyWorkloadLease(ctx context.Context, lease distributed.Lease) (bool, error)
	ReleaseWorkloadLease(ctx context.Context, lease distributed.Lease) error
	StartWorkloadRun(ctx context.Context, lease distributed.Lease, run distributed.WorkloadRun, shard distributed.ShardContract, ttl time.Duration) error
	ClaimWorkloadRunFinalization(ctx context.Context, lease distributed.Lease, run distributed.WorkloadRun, ttl time.Duration) (bool, error)
	StoreWorkloadShards(ctx context.Context, lease distributed.Lease, run distributed.WorkloadRun, shards []distributed.ShardExecutionPayload, ttl time.Duration) error
	ClaimWorkloadShard(ctx context.Context, workerID string, ttl time.Duration, run *distributed.WorkloadRun) (*distributed.ShardExecutionPayload, *distributed.ShardLease, error)
	RenewWorkloadShardLease(ctx context.Context, lease distributed.ShardLease, ttl time.Duration) (bool, error)
	ReleaseWorkloadShardLease(ctx context.Context, lease distributed.ShardLease) error
	CompleteWorkloadShard(ctx context.Context, lease distributed.ShardLease, result distributed.ShardExecutionResult, ttl time.Duration) error
	FailWorkloadShard(ctx context.Context, lease distributed.ShardLease, message string, retryable bool, retryAfter time.Time, ttl time.Duration) error
	LoadWorkloadShardResults(ctx context.Context, run distributed.WorkloadRun, mode string) ([]distributed.ShardExecutionResult, []distributed.ShardContract, error)
	FinishWorkloadRun(
		ctx context.Context,
		lease distributed.Lease,
		run distributed.WorkloadRun,
		shard distributed.ShardContract,
		status distributed.ShardState,
		ttl time.Duration,
		message string,
	) error
}

type LogFetcher interface {
	FetchLog(ctx context.Context, docID string) (*models.FullLog, error)
}

type BatchLogFetcher interface {
	FetchLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error)
}

type BatchLogFetcherWithOptions interface {
	FetchLogsWithOptions(ctx context.Context, docIDs []string, options fetch.BatchFetchOptions) (map[string]*models.FullLog, error)
}

type Correlator interface {
	Correlate(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error)
}

type RuleProvider interface {
	GetRules() []models.Rule
}

type ResultWriter interface {
	WriteResults(ctx context.Context, results []*models.CorrelationResult) []error
}

type Dependencies struct {
	Config      config.Config
	Store       OrganizationStore
	Checkpoints CheckpointStore
	Fetcher     LogFetcher
	Engine      Correlator
	Rules       RuleProvider
	Writer      ResultWriter
	Autoscaler  *autoscaling.Controller
	Logger      *slog.Logger
}

type Processor struct {
	config                 config.Config
	store                  OrganizationStore
	distributed            DistributedStore
	checkpoints            CheckpointStore
	fetcher                LogFetcher
	engine                 Correlator
	rules                  RuleProvider
	writer                 ResultWriter
	autoscaler             *autoscaling.Controller
	logger                 *slog.Logger
	workerID               string
	consumer               string
	now                    func() time.Time
	prefetchMu             sync.Mutex
	prefetching            bool
	workerHeartbeatMu      sync.Mutex
	workerHeartbeatStarted bool
}

type CycleSummary struct {
	Organizations                 int
	OrganizationsWithLogs         int
	OrganizationsSkipped          int
	OrganizationFailures          int
	SignalLogsRead                int
	IncrementalSignalLogs         int
	EnrichedLogs                  int
	FetchErrors                   int
	CorrelationsFound             int
	IncidentsOpened               int
	IncidentsUpdated              int
	IncidentsClosed               int
	ResultsWritten                int
	ResultWriteFailures           int
	ResultPublishFailures         int
	ResultsSuppressed             int
	ShadowMatches                 int
	IncidentStateFailures         int
	CheckpointFailures            int
	DistributedShardsPlanned      int
	DistributedShardsCompleted    int
	DistributedShardRetries       int
	DistributedShardQueueDepth    int
	DistributedCorrelationLogs    int
	DistributedTotalShardDuration time.Duration
	DistributedMaxShardDuration   time.Duration
	DistributedMergeDuration      time.Duration
}

func (s *CycleSummary) mergeCorrelationMetrics(metrics correlationRunMetrics) {
	if s == nil {
		return
	}
	s.DistributedShardsPlanned += metrics.ShardsPlanned
	s.DistributedShardsCompleted += metrics.ShardsCompleted
	s.DistributedShardRetries += metrics.ShardRetryCount
	if metrics.ShardQueueDepth > s.DistributedShardQueueDepth {
		s.DistributedShardQueueDepth = metrics.ShardQueueDepth
	}
	s.DistributedCorrelationLogs += metrics.CorrelationLogs
	s.DistributedTotalShardDuration += metrics.TotalShardDuration
	if metrics.MaxShardDuration > s.DistributedMaxShardDuration {
		s.DistributedMaxShardDuration = metrics.MaxShardDuration
	}
	s.DistributedMergeDuration += metrics.MergeDuration
}

type organizationOutcome struct {
	organization string
	summary      CycleSummary
	err          error
}

type incidentAction struct {
	result        *models.CorrelationResult
	state         *models.IncidentState
	previousState *models.IncidentState
	publish       bool
	delete        bool
}

type enrichmentCache struct {
	fullLogs map[string]models.FullLog
	missing  map[string]struct{}
}

type signalCursor struct {
	Timestamp time.Time
	DocID     string
}

type incrementalSelection struct {
	WorkingLogs   []models.SignalLog
	NewLogs       []models.SignalLog
	RawNewCount   int
	MaxCursor     signalCursor
	LastProcessed signalCursor
	Capped        bool
}

type ruleExecutionBuckets struct {
	incrementalLive   []models.Rule
	incrementalShadow []models.Rule
	fullPayloadLive   []models.Rule
	fullPayloadShadow []models.Rule
}

type noopCheckpointStore struct{}

const signalStreamCheckpointKey = "__signal_stream__"

func (noopCheckpointStore) LoadCheckpoint(context.Context, string) (models.ProcessingCheckpoint, error) {
	return models.ProcessingCheckpoint{}, nil
}

func (noopCheckpointStore) SaveCheckpoint(context.Context, string, models.ProcessingCheckpoint) error {
	return nil
}

func NewProcessor(deps Dependencies) *Processor {
	log := deps.Logger
	if log == nil {
		log = slog.New(slog.NewTextHandler(io.Discard, nil))
	}
	checkpoints := deps.Checkpoints
	if checkpoints == nil {
		checkpoints = noopCheckpointStore{}
	}
	var distributedStore DistributedStore
	if ds, ok := deps.Store.(DistributedStore); ok {
		distributedStore = ds
	}
	workerID := ""
	consumer := ""
	if deps.Config.Distributed.Enabled {
		workerID = distributed.ResolveWorkerID(deps.Config.Distributed.WorkerIDEnv)
		consumer = workerID
	}

	return &Processor{
		config:      deps.Config,
		store:       deps.Store,
		distributed: distributedStore,
		checkpoints: checkpoints,
		fetcher:     deps.Fetcher,
		engine:      deps.Engine,
		rules:       deps.Rules,
		writer:      deps.Writer,
		autoscaler:  deps.Autoscaler,
		logger:      log.With("component", "processor"),
		workerID:    workerID,
		consumer:    consumer,
		now:         time.Now,
	}
}

func (p *Processor) RunCycle(ctx context.Context) error {
	started := p.now().UTC()

	if p.config.Distributed.Enabled {
		if err := p.ensurePersistentDistributedWorkerHeartbeat(ctx); err != nil {
			return fmt.Errorf("heartbeat distributed worker %s: %w", p.workerID, err)
		}
	}

	rules := p.rules.GetRules()
	if p.config.Engine.InputMode == "redis_stream" {
		return p.runRedisStreamCycle(ctx, started, rules)
	}
	if p.config.Distributed.Enabled {
		return p.runDistributedCycle(ctx, started, rules)
	}
	if p.config.Redis.SignalStreamEnabled {
		if err := p.ingestSignalStream(ctx, rules); err != nil {
			return fmt.Errorf("ingest signal stream: %w", err)
		}
	}

	organizations, err := p.store.ListOrganizations(ctx)
	if err != nil {
		return fmt.Errorf("list organizations: %w", err)
	}
	if len(organizations) == 0 {
		p.logger.Debug("no organizations found for processing")
		return nil
	}

	if len(rules) == 0 {
		p.logger.Warn("no correlation rules loaded")
		return nil
	}

	workerCount := p.config.Scheduler.OrganizationWorkers
	if workerCount > len(organizations) {
		workerCount = len(organizations)
	}

	summary := CycleSummary{
		Organizations: len(organizations),
	}
	outcomes := make(chan organizationOutcome, len(organizations))
	jobs := make(chan string, len(organizations))

	for _, organization := range organizations {
		jobs <- organization
	}
	close(jobs)

	var wg sync.WaitGroup
	for workerID := 0; workerID < workerCount; workerID++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for organization := range jobs {
				if err := ctx.Err(); err != nil {
					return
				}

				orgSummary, err := p.processOrganization(ctx, organization, rules)
				outcomes <- organizationOutcome{
					organization: organization,
					summary:      orgSummary,
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
				firstErr = fmt.Errorf("process organization %s: %w", outcome.organization, outcome.err)
			}
			p.logger.Error(
				"organization processing failed",
				"organization", outcome.organization,
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
		"organization_workers", workerCount,
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
	)

	if p.autoscaler != nil && p.autoscaler.Enabled() {
		p.autoscaler.ObserveCycle(summary.IncrementalSignalLogs)
		p.logger.Info(
			"autoscaling workload observed",
			"incremental_signal_logs", summary.IncrementalSignalLogs,
		)
	}

	if firstErr != nil {
		return firstErr
	}
	return ctx.Err()
}

func (p *Processor) ingestSignalStream(ctx context.Context, rules []models.Rule) error {
	checkpoint, err := p.checkpoints.LoadCheckpoint(ctx, signalStreamCheckpointKey)
	if err != nil {
		return fmt.Errorf("load signal stream checkpoint: %w", err)
	}

	events, nextID, err := p.store.ReadSignalStream(ctx, checkpoint.StreamID)
	if err != nil {
		return err
	}
	if len(events) == 0 {
		if nextID != "" && nextID != checkpoint.StreamID {
			checkpoint.StreamID = nextID
			if err := p.checkpoints.SaveCheckpoint(ctx, signalStreamCheckpointKey, checkpoint); err != nil {
				return fmt.Errorf("save signal stream checkpoint: %w", err)
			}
		}
		p.trimSignalStream(ctx, checkpoint.StreamID)
		return nil
	}

	retentionCutoff := p.now().UTC().Add(-p.signalRetentionWindow(rules))
	grouped := make(map[string][]models.SignalLog, len(events))
	skipped := 0
	for _, event := range events {
		organizationID := strings.TrimSpace(event.OrganizationID)
		if organizationID == "" || strings.TrimSpace(event.DocID) == "" || strings.TrimSpace(event.Signal) == "" ||
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
			DocID:        event.DocID,
			TimeStamp:    eventTimestamp.UTC(),
			SignalizedAt: event.SignalizedAt.UTC(),
		})
	}

	updatedOrgs := 0
	deletedOrgs := 0
	unchangedOrgs := 0
	for organization, incoming := range grouped {
		payload, err := p.store.LoadSignalPayload(ctx, organization)
		if err != nil {
			return fmt.Errorf("load existing signal payload for organization %s: %w", organization, err)
		}
		existing, err := models.DecodeSignalLogsPayload(payload)
		if err != nil {
			return fmt.Errorf("decode existing signal payload for organization %s: %w", organization, err)
		}

		merged := mergeSignalLogs(existing, incoming, retentionCutoff)
		if len(merged) == 0 {
			if err := p.store.DeleteSignalLogs(ctx, organization); err != nil {
				return fmt.Errorf("delete empty signal payload for organization %s: %w", organization, err)
			}
			deletedOrgs++
			continue
		}
		if signalLogsEqual(existing, merged) {
			unchangedOrgs++
			continue
		}
		if err := p.store.SaveSignalLogs(ctx, organization, merged); err != nil {
			return fmt.Errorf("save merged signal payload for organization %s: %w", organization, err)
		}
		updatedOrgs++
	}

	checkpoint.StreamID = nextID
	if err := p.checkpoints.SaveCheckpoint(ctx, signalStreamCheckpointKey, checkpoint); err != nil {
		return fmt.Errorf("save signal stream checkpoint: %w", err)
	}

	p.trimSignalStream(ctx, checkpoint.StreamID)

	p.logger.Info(
		"ingested compact signal stream",
		"stream_key", p.config.Redis.SignalStreamKey,
		"stream_events", len(events),
		"skipped_events", skipped,
		"organizations_updated", updatedOrgs,
		"organizations_deleted", deletedOrgs,
		"organizations_unchanged", unchangedOrgs,
		"stream_checkpoint_id", nextID,
	)
	return nil
}

func (p *Processor) trimSignalStream(ctx context.Context, lastConsumedID string) {
	trimMinID := computeSignalStreamTrimMinID(
		strings.TrimSpace(lastConsumedID),
		p.now().UTC(),
		p.config.Redis.SignalStreamConsumedRetention,
		p.config.Redis.SignalStreamUnconsumedRetention,
	)
	if trimMinID == "" {
		return
	}

	trimmed, err := p.store.TrimSignalStream(ctx, trimMinID)
	if err != nil {
		p.logger.Warn(
			"failed to trim compact signal stream",
			"stream_key", p.config.Redis.SignalStreamKey,
			"trim_min_id", trimMinID,
			"consumed_retention", p.config.Redis.SignalStreamConsumedRetention,
			"unconsumed_retention", p.config.Redis.SignalStreamUnconsumedRetention,
			"error", err,
		)
		return
	}

	p.logger.Debug(
		"trimmed compact signal stream",
		"stream_key", p.config.Redis.SignalStreamKey,
		"trim_min_id", trimMinID,
		"trimmed_entries", trimmed,
		"consumed_retention", p.config.Redis.SignalStreamConsumedRetention,
		"unconsumed_retention", p.config.Redis.SignalStreamUnconsumedRetention,
	)
}

func (p *Processor) processOrganization(ctx context.Context, organization string, rules []models.Rule) (CycleSummary, error) {
	payload, err := p.store.LoadSignalPayload(ctx, organization)
	if err != nil {
		return CycleSummary{}, fmt.Errorf("load signal payload for organization %s: %w", organization, err)
	}
	activeIncidents, err := p.store.ListActiveIncidents(ctx, organization)
	if err != nil {
		return CycleSummary{}, fmt.Errorf("list active incidents for organization %s: %w", organization, err)
	}
	return p.processSignalWorkload(ctx, processingScope{
		WorkloadKey:     organization,
		CheckpointKey:   organization,
		OrganizationID:  organization,
		Payload:         payload,
		ActiveIncidents: activeIncidents,
	}, rules)
}

func (p *Processor) buildIncidentAction(organization string, result *models.CorrelationResult, activeByID map[string]models.IncidentState) (incidentAction, bool, error) {
	if result == nil {
		return incidentAction{}, false, fmt.Errorf("result cannot be nil")
	}
	if strings.TrimSpace(result.OrganizationID) == "" {
		result.OrganizationID = strings.TrimSpace(organization)
	}

	incidentKey, err := models.BuildIncidentID(organization, result.RuleID, result.GroupByValues)
	if err != nil {
		return incidentAction{}, false, err
	}
	if result.MatchedAt.IsZero() {
		result.MatchedAt = p.now().UTC()
	}
	if result.CorrelatedAt.IsZero() {
		result.CorrelatedAt = p.now().UTC()
	}
	if err := result.EnsureResultSignature(); err != nil {
		return incidentAction{}, false, err
	}

	active, exists, err := findLatestIncidentByIdentity(organization, incidentKey, activeByID)
	if err != nil {
		return incidentAction{}, false, err
	}
	if exists && result.MatchedAt.UTC().Sub(active.LastSeen.UTC()) <= p.incidentReopenWindow() {
		result.IncidentID = active.IncidentID
		existingStatus := normalizeIncidentState(active.Status)
		if existingStatus != "closed" && active.LastResultSignature == result.ResultSignature {
			return incidentAction{}, false, nil
		}

		firstSeen := active.FirstSeen.UTC()
		lastSeen := result.MatchedAt.UTC()
		if existingStatus == "closed" {
			result.Status = "open"
		} else {
			result.Status = "updated"
		}
		result.FirstSeen = &firstSeen
		result.LastSeen = &lastSeen
		documentID, err := models.BuildCorrelationEventDocumentID(result.OrganizationID, result.IncidentID, result.Status, result.ResultSignature)
		if err != nil {
			return incidentAction{}, false, err
		}
		result.DocumentID = documentID
		state := buildIncidentState(result)
		activeByID[result.IncidentID] = *state
		previousState := active
		return incidentAction{
			result:        cloneCorrelationResult(result),
			state:         state,
			publish:       true,
			previousState: &previousState,
		}, true, nil
	}

	incidentID, err := models.BuildIncidentEpisodeID(incidentKey, result.MatchedAt.UTC())
	if err != nil {
		return incidentAction{}, false, err
	}
	result.IncidentID = incidentID
	if !exists {
		firstSeen := result.MatchedAt.UTC()
		lastSeen := result.MatchedAt.UTC()
		result.Status = "open"
		result.FirstSeen = &firstSeen
		result.LastSeen = &lastSeen
		documentID, err := models.BuildCorrelationEventDocumentID(result.OrganizationID, result.IncidentID, result.Status, result.ResultSignature)
		if err != nil {
			return incidentAction{}, false, err
		}
		result.DocumentID = documentID
		state := buildIncidentState(result)
		activeByID[incidentID] = *state
		return incidentAction{
			result:  cloneCorrelationResult(result),
			state:   state,
			publish: true,
		}, true, nil
	}

	firstSeen := result.MatchedAt.UTC()
	lastSeen := result.MatchedAt.UTC()
	result.Status = "open"
	result.FirstSeen = &firstSeen
	result.LastSeen = &lastSeen
	documentID, err := models.BuildCorrelationEventDocumentID(result.OrganizationID, result.IncidentID, result.Status, result.ResultSignature)
	if err != nil {
		return incidentAction{}, false, err
	}
	result.DocumentID = documentID
	state := buildIncidentState(result)
	activeByID[result.IncidentID] = *state
	return incidentAction{
		result:  cloneCorrelationResult(result),
		state:   state,
		publish: true,
	}, true, nil
}

func (p *Processor) buildRecoveryClosures(
	ctx context.Context,
	organization string,
	rules []models.Rule,
	newLogs []models.FullLog,
	activeByID map[string]models.IncidentState,
) ([]incidentAction, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if len(newLogs) == 0 || len(activeByID) == 0 {
		return nil, nil
	}

	closed := make(map[string]struct{})
	actions := make([]incidentAction, 0)

	for _, rule := range rules {
		if len(rule.NotSequence) == 0 {
			continue
		}

		negativeSignals := make(map[string]struct{}, len(rule.NotSequence))
		for _, step := range rule.NotSequence {
			negativeSignals[step.SignalKey] = struct{}{}
		}

		for _, log := range newLogs {
			if _, ok := negativeSignals[log.Signal]; !ok {
				continue
			}

			groupByValues := utils.ExtractGroupByValues(log.Metadata, p.resolvedGroupByFields(rule))
			incidentKey, err := models.BuildIncidentID(organization, rule.ID, groupByValues)
			if err != nil {
				return nil, err
			}

			state, exists, err := findLatestIncidentByIdentity(organization, incidentKey, activeByID)
			if err != nil {
				return nil, err
			}
			if !exists || normalizeIncidentState(state.Status) == "closed" {
				continue
			}
			if !state.LastSeen.IsZero() && log.Timestamp.Before(state.LastSeen.UTC()) {
				continue
			}
			incidentID := state.IncidentID
			if _, alreadyClosed := closed[incidentID]; alreadyClosed {
				continue
			}

			closingResult := buildClosedIncidentResult(state, log.Timestamp.UTC())
			closedState := buildIncidentState(&closingResult)
			previousState := state
			actions = append(actions, incidentAction{
				result:        &closingResult,
				state:         closedState,
				previousState: &previousState,
				publish:       true,
			})
			closed[incidentID] = struct{}{}
		}
	}

	return actions, nil
}

func (p *Processor) closeInactiveIncidents(
	ctx context.Context,
	scope *processingScope,
	activeByID map[string]models.IncidentState,
	matchedIncidentIDs map[string]struct{},
	now time.Time,
	summary *CycleSummary,
) error {
	organization := ""
	if scope != nil {
		organization = scope.OrganizationID
	}
	if len(activeByID) == 0 {
		return nil
	}

	for incidentID, state := range activeByID {
		if normalizeIncidentState(state.Status) != "closed" {
			continue
		}
		if now.Sub(state.LastSeen.UTC()) < p.incidentReopenWindow() {
			continue
		}
		if err := p.ensureMutationOwned(ctx, scope); err != nil {
			summary.IncidentStateFailures++
			return fmt.Errorf("verify mutation ownership before purging closed incident state for organization %s: %w", organization, err)
		}
		if err := p.store.DeleteIncident(ctx, organization, incidentID); err != nil {
			summary.IncidentStateFailures++
			return fmt.Errorf("purge closed incident state for organization %s: %w", organization, err)
		}
		delete(activeByID, incidentID)
	}

	actions := make([]incidentAction, 0)
	for incidentID, state := range activeByID {
		if normalizeIncidentState(state.Status) == "closed" {
			continue
		}
		if _, matched := matchedIncidentIDs[incidentID]; matched {
			continue
		}
		if now.Sub(state.LastSeen.UTC()) < p.config.Engine.IncidentInactivityTTL {
			continue
		}

		closingResult := buildClosedIncidentResult(state, now.UTC())
		closedState := buildIncidentState(&closingResult)
		previousState := state
		actions = append(actions, incidentAction{
			result:        &closingResult,
			state:         closedState,
			previousState: &previousState,
			publish:       true,
		})
		summary.IncidentsClosed++
	}

	return p.applyIncidentActions(ctx, scope, activeByID, actions, summary)
}

func (p *Processor) applyIncidentActions(
	ctx context.Context,
	scope *processingScope,
	activeByID map[string]models.IncidentState,
	actions []incidentAction,
	summary *CycleSummary,
) error {
	organization := ""
	if scope != nil {
		organization = scope.OrganizationID
	}
	if len(actions) == 0 {
		return nil
	}

	if err := p.ensureMutationOwned(ctx, scope); err != nil {
		summary.ResultWriteFailures += len(actions)
		return fmt.Errorf("verify mutation ownership before writing correlation results for organization %s: %w", organization, err)
	}

	results := make([]*models.CorrelationResult, 0, len(actions))
	for _, action := range actions {
		results = append(results, action.result)
	}

	writeErrors := p.writer.WriteResults(ctx, results)
	if len(writeErrors) != len(actions) {
		return fmt.Errorf("writer returned %d errors for %d actions", len(writeErrors), len(actions))
	}

	var firstCriticalErr error
	for idx, action := range actions {
		if err := writeErrors[idx]; err != nil {
			summary.ResultWriteFailures++
			rollbackIncidentActionState(activeByID, action)
			if firstCriticalErr == nil {
				firstCriticalErr = fmt.Errorf("write incident result for organization %s: %w", organization, err)
			}
			p.logger.Warn(
				"failed to write correlation result",
				"organization", organization,
				"rule_id", action.result.RuleID,
				"incident_id", action.result.IncidentID,
				"status", action.result.Status,
				"error", err,
			)
			continue
		}

		summary.ResultsWritten++
		if action.delete {
			if err := p.ensureMutationOwned(ctx, scope); err != nil {
				summary.IncidentStateFailures++
				rollbackIncidentActionState(activeByID, action)
				if firstCriticalErr == nil {
					firstCriticalErr = fmt.Errorf("verify mutation ownership before deleting incident state for organization %s: %w", organization, err)
				}
				continue
			}
			if err := p.store.DeleteIncident(ctx, organization, action.result.IncidentID); err != nil {
				summary.IncidentStateFailures++
				rollbackIncidentActionState(activeByID, action)
				if firstCriticalErr == nil {
					firstCriticalErr = fmt.Errorf("delete incident state for organization %s: %w", organization, err)
				}
				p.logger.Error(
					"failed to delete incident state",
					"organization", organization,
					"incident_id", action.result.IncidentID,
					"error", err,
				)
				continue
			}
		} else if action.state != nil {
			if err := p.ensureMutationOwned(ctx, scope); err != nil {
				summary.IncidentStateFailures++
				rollbackIncidentActionState(activeByID, action)
				if firstCriticalErr == nil {
					firstCriticalErr = fmt.Errorf("verify mutation ownership before saving incident state for organization %s: %w", organization, err)
				}
				continue
			}
			if err := p.store.SaveIncident(ctx, action.state, p.config.Engine.IncidentInactivityTTL); err != nil {
				summary.IncidentStateFailures++
				rollbackIncidentActionState(activeByID, action)
				if firstCriticalErr == nil {
					firstCriticalErr = fmt.Errorf("save incident state for organization %s: %w", organization, err)
				}
				p.logger.Error(
					"failed to save incident state",
					"organization", organization,
					"incident_id", action.result.IncidentID,
					"status", action.result.Status,
					"error", err,
				)
				continue
			}
		}

		if action.publish && p.config.Redis.PublishResults {
			if err := p.ensureMutationOwned(ctx, scope); err != nil {
				summary.ResultPublishFailures++
				if firstCriticalErr == nil {
					firstCriticalErr = fmt.Errorf("verify mutation ownership before publishing correlation result for organization %s: %w", organization, err)
				}
				continue
			}
			if err := p.store.PublishResult(ctx, action.result); err != nil {
				summary.ResultPublishFailures++
				p.logger.Warn(
					"failed to publish correlation result",
					"organization", organization,
					"incident_id", action.result.IncidentID,
					"status", action.result.Status,
					"error", err,
				)
			}
		}
	}

	return firstCriticalErr
}

func newEnrichmentCache() *enrichmentCache {
	return &enrichmentCache{
		fullLogs: make(map[string]models.FullLog),
		missing:  make(map[string]struct{}),
	}
}

func (p *Processor) enrichSignalLogs(
	ctx context.Context,
	workingSignalLogs []models.SignalLog,
	newSignalLogs []models.SignalLog,
	cache *enrichmentCache,
	options fetch.BatchFetchOptions,
) ([]models.FullLog, []models.FullLog, int, error) {
	if cache == nil {
		cache = newEnrichmentCache()
	}

	workingFullLogs := make([]models.FullLog, 0, len(workingSignalLogs))
	newFullLogs := make([]models.FullLog, 0, len(newSignalLogs))
	newDocIDs := make(map[string]struct{}, len(newSignalLogs))
	for _, signalLog := range newSignalLogs {
		newDocIDs[signalLog.DocID] = struct{}{}
	}

	fetchErrors := 0
	neededDocIDs := missingCacheDocIDs(workingSignalLogs, cache)
	if len(neededDocIDs) > 0 {
		p.hydrateDistributedFullLogCache(ctx, neededDocIDs, cache)
		neededDocIDs = filterMissingDocIDs(neededDocIDs, cache)
	}
	switch batchFetcher := p.fetcher.(type) {
	case BatchLogFetcherWithOptions:
		if len(neededDocIDs) > 0 {
			fetchedLogs, err := batchFetcher.FetchLogsWithOptions(ctx, neededDocIDs, options)
			if err != nil {
				return nil, nil, fetchErrors, err
			}
			p.saveDistributedFullLogCache(ctx, fetchedLogs)
			for docID, fetched := range fetchedLogs {
				if fetched == nil {
					continue
				}
				cache.fullLogs[docID] = cloneFullLog(*fetched)
			}
			for _, docID := range neededDocIDs {
				if _, ok := cache.fullLogs[docID]; ok {
					continue
				}
				if _, alreadyMissing := cache.missing[docID]; alreadyMissing {
					continue
				}
				cache.missing[docID] = struct{}{}
				fetchErrors++
				p.logger.Warn(
					"failed to fetch full log",
					"doc_id", docID,
					"error", "document not found in batch lookup",
				)
			}
		}
	case BatchLogFetcher:
		if len(neededDocIDs) > 0 {
			fetchedLogs, err := batchFetcher.FetchLogs(ctx, neededDocIDs)
			if err != nil {
				return nil, nil, fetchErrors, err
			}
			p.saveDistributedFullLogCache(ctx, fetchedLogs)
			for docID, fetched := range fetchedLogs {
				if fetched == nil {
					continue
				}
				cache.fullLogs[docID] = cloneFullLog(*fetched)
			}
			for _, docID := range neededDocIDs {
				if _, ok := cache.fullLogs[docID]; ok {
					continue
				}
				if _, alreadyMissing := cache.missing[docID]; alreadyMissing {
					continue
				}
				cache.missing[docID] = struct{}{}
				fetchErrors++
				p.logger.Warn(
					"failed to fetch full log",
					"doc_id", docID,
					"error", "document not found in batch lookup",
				)
			}
		}
	}

	for _, signalLog := range workingSignalLogs {
		if err := ctx.Err(); err != nil {
			return nil, nil, fetchErrors, err
		}

		fullLog, ok := cache.fullLogs[signalLog.DocID]
		if !ok {
			if _, missing := cache.missing[signalLog.DocID]; missing {
				continue
			}
			fetched, err := p.fetcher.FetchLog(ctx, signalLog.DocID)
			if err != nil {
				fetchErrors++
				cache.missing[signalLog.DocID] = struct{}{}
				p.logger.Warn(
					"failed to fetch full log",
					"doc_id", signalLog.DocID,
					"error", err,
				)
				continue
			}
			fullLog = cloneFullLog(*fetched)
			cache.fullLogs[signalLog.DocID] = fullLog
			p.saveDistributedFullLogCache(ctx, map[string]*models.FullLog{
				signalLog.DocID: fetched,
			})
		}

		enriched := cloneFullLog(fullLog)
		enriched.Signal = signalLog.Signal
		enriched.LogLevel = signalLog.LogLevel
		enriched.Timestamp = signalLog.TimeStamp.UTC()
		enriched.SignalizedAt = signalLog.SignalizedAt.UTC()
		if !signalLog.SignalizedAt.IsZero() {
			if enriched.Metadata == nil {
				enriched.Metadata = make(map[string]any)
			}
			enriched.Metadata["signalized_at"] = signalLog.SignalizedAt.UTC().Format(time.RFC3339Nano)
		}
		workingFullLogs = append(workingFullLogs, enriched)
		if _, ok := newDocIDs[signalLog.DocID]; ok {
			newFullLogs = append(newFullLogs, enriched)
		}
	}

	return workingFullLogs, newFullLogs, fetchErrors, nil
}

func (p *Processor) hydrateDistributedFullLogCache(ctx context.Context, docIDs []string, cache *enrichmentCache) {
	if cache == nil || p.distributed == nil || !p.config.Distributed.Enabled || len(docIDs) == 0 {
		return
	}

	cachedLogs, err := p.distributed.LoadCachedFullLogs(ctx, docIDs)
	if err != nil {
		p.logger.Warn("failed to load distributed full log cache", "error", err, "doc_ids", len(docIDs))
		return
	}
	for docID, fullLog := range cachedLogs {
		if fullLog == nil {
			continue
		}
		cache.fullLogs[docID] = cloneFullLog(*fullLog)
	}
}

func (p *Processor) saveDistributedFullLogCache(ctx context.Context, logs map[string]*models.FullLog) {
	if p.distributed == nil || !p.config.Distributed.Enabled || len(logs) == 0 {
		return
	}
	if err := p.distributed.SaveCachedFullLogs(ctx, logs, p.config.Distributed.FullLogCacheTTL); err != nil {
		p.logger.Warn("failed to save distributed full log cache", "error", err, "doc_ids", len(logs))
	}
}

func filterMissingDocIDs(docIDs []string, cache *enrichmentCache) []string {
	if len(docIDs) == 0 {
		return nil
	}

	result := make([]string, 0, len(docIDs))
	for _, docID := range docIDs {
		if _, ok := cache.fullLogs[docID]; ok {
			continue
		}
		if _, ok := cache.missing[docID]; ok {
			continue
		}
		result = append(result, docID)
	}
	return result
}

func filterRulesByOrg(rules []models.Rule, orgID string) []models.Rule {
	result := make([]models.Rule, 0)
	for _, rule := range rules {
		if rule.OrganizationID == orgID {
			result = append(result, rule)
		}
	}
	return result
}

func (p *Processor) resolvedGroupByFields(rule models.Rule) []string {
	if len(p.config.Engine.GroupByFields) > 0 {
		return append([]string(nil), p.config.Engine.GroupByFields...)
	}
	if len(rule.GroupBy) == 0 {
		return nil
	}
	return append([]string(nil), rule.GroupBy...)
}

func (p *Processor) lookbackWindow(rules []models.Rule) time.Duration {
	lookback := p.config.Engine.IncrementalLookback
	if lookback < p.config.Engine.DefaultWindow {
		lookback = p.config.Engine.DefaultWindow
	}
	if p.config.Engine.DefaultMaxGap > lookback {
		lookback = p.config.Engine.DefaultMaxGap
	}

	for _, rule := range rules {
		if window, err := utils.ParseDuration(rule.Window); err == nil && window > lookback {
			lookback = window
		}
		if gap, err := utils.ParseDuration(rule.MaxGapBetweenSteps); err == nil && gap > lookback {
			lookback = gap
		}
		if dedupWindow, err := utils.ParseDuration(rule.Deduplication.Window); err == nil && dedupWindow > lookback {
			lookback = dedupWindow
		}
		for _, step := range rule.Sequence {
			if within, err := utils.ParseDuration(step.Within); err == nil && within > lookback {
				lookback = within
			}
		}
	}

	return lookback
}

func selectIncrementalSignalLogs(
	signalLogs []models.SignalLog,
	checkpoint models.ProcessingCheckpoint,
	lookback time.Duration,
	maxNewLogsPerCycle int,
) incrementalSelection {
	if len(signalLogs) == 0 {
		return incrementalSelection{}
	}

	maxCursor := signalLogToCursor(signalLogs[len(signalLogs)-1])
	newLogs := selectNewSignalLogs(signalLogs, checkpoint)
	if len(newLogs) == 0 {
		return incrementalSelection{MaxCursor: maxCursor}
	}

	selectedNewLogs := append([]models.SignalLog(nil), newLogs...)
	capped := false
	if maxNewLogsPerCycle > 0 && len(selectedNewLogs) > maxNewLogsPerCycle {
		selectedNewLogs = append([]models.SignalLog(nil), selectedNewLogs[:maxNewLogsPerCycle]...)
		capped = true
	}

	working := make([]models.SignalLog, 0, len(signalLogs))
	lastProcessed := signalLogToCursor(selectedNewLogs[len(selectedNewLogs)-1])
	if capped {
		lookbackStart := selectedNewLogs[0].TimeStamp.UTC().Add(-lookback)
		for _, signalLog := range signalLogs {
			if signalLog.TimeStamp.Before(lookbackStart) {
				continue
			}
			if compareSignalCursor(signalLogToCursor(signalLog), lastProcessed) > 0 {
				continue
			}
			working = append(working, signalLog)
		}
	} else {
		checkpointCursor := checkpointToCursor(checkpoint)
		if checkpointCursor.IsZero() {
			working = append([]models.SignalLog(nil), signalLogs...)
		} else {
			lookbackStart := checkpointCursor.Timestamp.Add(-lookback)
			for _, signalLog := range signalLogs {
				if !signalLog.TimeStamp.Before(lookbackStart) {
					working = append(working, signalLog)
				}
			}
		}
	}

	return incrementalSelection{
		WorkingLogs:   working,
		NewLogs:       selectedNewLogs,
		RawNewCount:   len(newLogs),
		MaxCursor:     maxCursor,
		LastProcessed: lastProcessed,
		Capped:        capped,
	}
}

func selectNewSignalLogs(signalLogs []models.SignalLog, checkpoint models.ProcessingCheckpoint) []models.SignalLog {
	if len(signalLogs) == 0 {
		return nil
	}
	if checkpoint.Checkpoint.IsZero() {
		return append([]models.SignalLog(nil), signalLogs...)
	}

	newLogs := make([]models.SignalLog, 0, len(signalLogs))
	for _, signalLog := range signalLogs {
		if isSignalLogAfterCheckpoint(signalLog, checkpoint) {
			newLogs = append(newLogs, signalLog)
		}
	}
	return newLogs
}

func sortSignalLogs(signalLogs []models.SignalLog) {
	sort.Slice(signalLogs, func(i, j int) bool {
		return compareSignalCursor(signalLogToCursor(signalLogs[i]), signalLogToCursor(signalLogs[j])) < 0
	})
}

func isSignalLogAfterCheckpoint(signalLog models.SignalLog, checkpoint models.ProcessingCheckpoint) bool {
	if checkpoint.Checkpoint.IsZero() {
		return true
	}
	if signalLog.TimeStamp.After(checkpoint.Checkpoint) {
		return true
	}
	if signalLog.TimeStamp.Before(checkpoint.Checkpoint) {
		return false
	}
	checkpointDocID := strings.TrimSpace(checkpoint.CheckpointDocID)
	if checkpointDocID == "" {
		return false
	}
	return strings.TrimSpace(signalLog.DocID) > checkpointDocID
}

func checkpointToCursor(checkpoint models.ProcessingCheckpoint) signalCursor {
	if checkpoint.Checkpoint.IsZero() {
		return signalCursor{}
	}
	return signalCursor{
		Timestamp: checkpoint.Checkpoint.UTC(),
		DocID:     strings.TrimSpace(checkpoint.CheckpointDocID),
	}
}

func compareCheckpointToSignalCursor(checkpoint models.ProcessingCheckpoint, cursor signalCursor) int {
	if checkpoint.Checkpoint.IsZero() {
		if cursor.IsZero() {
			return 0
		}
		return -1
	}
	if checkpoint.Checkpoint.Before(cursor.Timestamp) {
		return -1
	}
	if checkpoint.Checkpoint.After(cursor.Timestamp) {
		return 1
	}
	checkpointDocID := strings.TrimSpace(checkpoint.CheckpointDocID)
	if checkpointDocID == "" {
		return 1
	}
	switch {
	case checkpointDocID < strings.TrimSpace(cursor.DocID):
		return -1
	case checkpointDocID > strings.TrimSpace(cursor.DocID):
		return 1
	default:
		return 0
	}
}

func isCheckpointAheadOfSignals(checkpoint models.ProcessingCheckpoint, cursor signalCursor) bool {
	if checkpoint.Checkpoint.IsZero() || cursor.IsZero() {
		return false
	}
	if checkpoint.Checkpoint.After(cursor.Timestamp) {
		return true
	}
	if checkpoint.Checkpoint.Before(cursor.Timestamp) {
		return false
	}
	checkpointDocID := strings.TrimSpace(checkpoint.CheckpointDocID)
	if checkpointDocID == "" {
		return false
	}
	return checkpointDocID > strings.TrimSpace(cursor.DocID)
}

func signalLogToCursor(signalLog models.SignalLog) signalCursor {
	return signalCursor{
		Timestamp: signalLog.TimeStamp.UTC(),
		DocID:     strings.TrimSpace(signalLog.DocID),
	}
}

func (c signalCursor) IsZero() bool {
	return c.Timestamp.IsZero()
}

func compareSignalCursor(left, right signalCursor) int {
	leftTime := left.Timestamp.UTC()
	rightTime := right.Timestamp.UTC()
	if leftTime.Before(rightTime) {
		return -1
	}
	if leftTime.After(rightTime) {
		return 1
	}
	leftDocID := strings.TrimSpace(left.DocID)
	rightDocID := strings.TrimSpace(right.DocID)
	switch {
	case leftDocID < rightDocID:
		return -1
	case leftDocID > rightDocID:
		return 1
	default:
		return 0
	}
}

func maxSignalCursor(left, right signalCursor) signalCursor {
	if compareSignalCursor(left, right) >= 0 {
		return left
	}
	return right
}

func (p *Processor) resolveOrganizationSettings(organization string, incrementalCount int) autoscaling.OrganizationSettings {
	if p.autoscaler != nil && p.autoscaler.Enabled() {
		return p.autoscaler.ResolveOrganization(organization, incrementalCount)
	}
	return autoscaling.OrganizationSettings{
		GroupedLookupBatchSize: maxInt(1, p.config.Fetcher.GroupedLookupBatchSize),
	}
}

func (p *Processor) logOrganizationAutoscaling(
	organization string,
	incrementalCount int,
	settings autoscaling.OrganizationSettings,
	capped bool,
) {
	if p.logger == nil || p.autoscaler == nil || !p.autoscaler.Enabled() {
		return
	}

	fields := []any{
		"organization", organization,
		"raw_incremental_signal_logs", incrementalCount,
		"effective_grouped_lookup_batch_size", settings.GroupedLookupBatchSize,
		"effective_max_new_logs_per_cycle", settings.MaxNewLogsPerCycle,
		"incremental_backlog_capped", capped,
	}
	schedulerSettings := p.autoscaler.CurrentSchedulerSettings()
	fields = append(fields,
		"effective_scheduler_interval", schedulerSettings.Interval.String(),
		"effective_scheduler_run_timeout", schedulerSettings.RunTimeout.String(),
	)
	p.logger.Info("organization autoscaling resolved", fields...)
}

func (p *Processor) incidentReopenWindow() time.Duration {
	window := p.config.Engine.IncidentInactivityTTL
	if window <= 0 {
		return 30 * time.Minute
	}
	return window
}

func normalizeIncidentState(status string) string {
	switch strings.ToLower(strings.TrimSpace(status)) {
	case "closed":
		return "closed"
	case "updated":
		return "updated"
	default:
		return "open"
	}
}

func findLatestIncidentByIdentity(
	organization string,
	incidentKey string,
	activeByID map[string]models.IncidentState,
) (models.IncidentState, bool, error) {
	trimmedIncidentKey := strings.TrimSpace(incidentKey)
	if trimmedIncidentKey == "" {
		return models.IncidentState{}, false, fmt.Errorf("incident key must not be empty")
	}

	var selected models.IncidentState
	found := false
	for _, state := range activeByID {
		if strings.TrimSpace(state.OrganizationID) != "" && strings.TrimSpace(state.OrganizationID) != strings.TrimSpace(organization) {
			continue
		}
		stateKey, err := models.BuildIncidentID(organization, state.RuleID, state.GroupByValues)
		if err != nil {
			continue
		}
		if stateKey != trimmedIncidentKey {
			continue
		}
		if !found || state.LastSeen.UTC().After(selected.LastSeen.UTC()) {
			selected = state
			found = true
		}
	}
	return selected, found, nil
}

func shouldScanFullPayload(rules []models.Rule) bool {
	for _, rule := range rules {
		if strings.TrimSpace(rule.MaxGapBetweenSteps) == "" {
			return true
		}
	}
	return false
}

func buildIncidentState(result *models.CorrelationResult) *models.IncidentState {
	firstSeen := result.MatchedAt.UTC()
	lastSeen := result.MatchedAt.UTC()
	if result.FirstSeen != nil {
		firstSeen = result.FirstSeen.UTC()
	}
	if result.LastSeen != nil {
		lastSeen = result.LastSeen.UTC()
	}

	return &models.IncidentState{
		IncidentID:          result.IncidentID,
		OrganizationID:      result.OrganizationID,
		RuleID:              result.RuleID,
		Status:              result.Status,
		FirstSeen:           firstSeen,
		LastSeen:            lastSeen,
		LastResultSignature: result.ResultSignature,
		GroupByValues:       cloneGroupByValues(result.GroupByValues),
		Snapshot:            buildIncidentSnapshot(result),
	}
}

func buildClosedIncidentResult(state models.IncidentState, closedAt time.Time) models.CorrelationResult {
	result := models.CorrelationResult{
		SchemaVersion:   state.Snapshot.SchemaVersion,
		LogID:           cloneResultLogs(state.Snapshot.LogID),
		RuleCompletion:  state.Snapshot.RuleCompletion,
		RuleID:          state.RuleID,
		SequenceMatch:   state.Snapshot.SequenceMatch,
		IncidentID:      state.IncidentID,
		Status:          "closed",
		OrganizationID:  state.OrganizationID,
		GroupByValues:   cloneGroupByValues(state.GroupByValues),
		MatchedAt:       state.Snapshot.MatchedAt.UTC(),
		CorrelatedAt:    state.Snapshot.CorrelatedAt.UTC(),
		ResultSignature: state.LastResultSignature,
		Audit:           cloneMatchAudit(state.Snapshot.Audit),
	}
	if result.MatchedAt.IsZero() {
		result.MatchedAt = state.LastSeen.UTC()
	}
	if result.CorrelatedAt.IsZero() {
		result.CorrelatedAt = state.LastSeen.UTC()
	}
	firstSeen := state.FirstSeen.UTC()
	lastSeen := closedAt.UTC()
	result.FirstSeen = &firstSeen
	result.LastSeen = &lastSeen
	documentID, err := models.BuildCorrelationEventDocumentID(result.OrganizationID, result.IncidentID, result.Status, state.LastResultSignature)
	if err == nil {
		result.DocumentID = documentID
	}
	return result
}

func cloneCorrelationResult(result *models.CorrelationResult) *models.CorrelationResult {
	if result == nil {
		return nil
	}

	cloned := *result
	cloned.LogID = cloneResultLogs(result.LogID)
	if result.FirstSeen != nil {
		firstSeen := result.FirstSeen.UTC()
		cloned.FirstSeen = &firstSeen
	}
	if result.LastSeen != nil {
		lastSeen := result.LastSeen.UTC()
		cloned.LastSeen = &lastSeen
	}
	cloned.GroupByValues = cloneGroupByValues(result.GroupByValues)
	cloned.Audit = cloneMatchAudit(result.Audit)
	return &cloned
}

func buildIncidentSnapshot(result *models.CorrelationResult) models.IncidentSnapshot {
	if result == nil {
		return models.IncidentSnapshot{}
	}
	return models.IncidentSnapshot{
		SchemaVersion:  result.SchemaVersion,
		LogID:          cloneResultLogs(result.LogID),
		RuleCompletion: result.RuleCompletion,
		SequenceMatch:  result.SequenceMatch,
		MatchedAt:      result.MatchedAt.UTC(),
		CorrelatedAt:   result.CorrelatedAt.UTC(),
		Audit:          cloneMatchAudit(result.Audit),
	}
}

func cloneResultLogs(entries []models.ResultLog) []models.ResultLog {
	if len(entries) == 0 {
		return nil
	}
	cloned := make([]models.ResultLog, len(entries))
	for idx, entry := range entries {
		cloned[idx] = entry
		if len(entry.HostIPs) > 0 {
			cloned[idx].HostIPs = append([]string(nil), entry.HostIPs...)
		}
	}
	return cloned
}

func cloneMatchAudit(audit *models.MatchAudit) *models.MatchAudit {
	if audit == nil {
		return nil
	}

	cloned := *audit
	if len(audit.GroupBy) > 0 {
		cloned.GroupBy = append([]string(nil), audit.GroupBy...)
	}
	cloned.GroupByValues = cloneGroupByValues(audit.GroupByValues)
	cloned.RequiredMetadata = cloneGroupByValues(audit.RequiredMetadata)
	if len(audit.NegativeSignals) > 0 {
		cloned.NegativeSignals = append([]string(nil), audit.NegativeSignals...)
	}
	if len(audit.DeduplicationKey) > 0 {
		cloned.DeduplicationKey = append([]string(nil), audit.DeduplicationKey...)
	}
	if len(audit.MatchedLogIDs) > 0 {
		cloned.MatchedLogIDs = append([]string(nil), audit.MatchedLogIDs...)
	}
	if len(audit.MatchedSignals) > 0 {
		cloned.MatchedSignals = append([]string(nil), audit.MatchedSignals...)
	}
	if len(audit.Steps) > 0 {
		cloned.Steps = make([]models.MatchStepAudit, len(audit.Steps))
		for idx, step := range audit.Steps {
			cloned.Steps[idx] = step
			if len(step.MatchedLogIDs) > 0 {
				cloned.Steps[idx].MatchedLogIDs = append([]string(nil), step.MatchedLogIDs...)
			}
		}
	}
	return &cloned
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

func cloneFullLog(input models.FullLog) models.FullLog {
	clone := input
	if input.Metadata == nil {
		return clone
	}

	clone.Metadata = deepCloneMetadataMap(input.Metadata)
	return clone
}

func (p *Processor) signalRetentionWindow(rules []models.Rule) time.Duration {
	retention := p.config.Engine.DefaultWindow
	if p.config.Engine.DefaultMaxGap > retention {
		retention = p.config.Engine.DefaultMaxGap
	}
	if p.config.Engine.IncrementalLookback > retention {
		retention = p.config.Engine.IncrementalLookback
	}
	if p.config.Engine.IncidentInactivityTTL > retention {
		retention = p.config.Engine.IncidentInactivityTTL
	}
	for _, rule := range rules {
		if window, err := utils.ParseDuration(rule.Window); err == nil && window > retention {
			retention = window
		}
		if gap, err := utils.ParseDuration(rule.MaxGapBetweenSteps); err == nil && gap > retention {
			retention = gap
		}
		if dedupWindow, err := utils.ParseDuration(rule.Deduplication.Window); err == nil && dedupWindow > retention {
			retention = dedupWindow
		}
		for _, step := range rule.Sequence {
			if within, err := utils.ParseDuration(step.Within); err == nil && within > retention {
				retention = within
			}
		}
	}
	if retention <= 0 {
		return 30 * time.Minute
	}
	return retention
}

func computeSignalStreamTrimMinID(
	lastConsumedID string,
	now time.Time,
	consumedRetention time.Duration,
	unconsumedRetention time.Duration,
) string {
	if now.IsZero() || consumedRetention <= 0 || unconsumedRetention <= 0 {
		return ""
	}

	unconsumedCutoffID := streamTimeToID(now.Add(-unconsumedRetention))
	consumedCutoffID := streamTimeToID(now.Add(-consumedRetention))
	if unconsumedCutoffID == "" || consumedCutoffID == "" {
		return ""
	}

	checkpointID := normalizeStreamID(lastConsumedID)
	if checkpointID == "" {
		return unconsumedCutoffID
	}

	consumedTrimID := minStreamID(checkpointID, consumedCutoffID)
	return maxStreamID(consumedTrimID, unconsumedCutoffID)
}

func streamTimeToID(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return fmt.Sprintf("%d-0", value.UTC().UnixMilli())
}

func normalizeStreamID(value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return ""
	}
	if _, _, ok := parseStreamID(trimmed); !ok {
		return ""
	}
	return trimmed
}

func minStreamID(left, right string) string {
	switch compareStreamIDs(left, right) {
	case -1, 0:
		return left
	case 1:
		return right
	default:
		if normalizeStreamID(left) != "" {
			return left
		}
		return right
	}
}

func maxStreamID(left, right string) string {
	switch compareStreamIDs(left, right) {
	case -1:
		return right
	case 0, 1:
		return left
	default:
		if normalizeStreamID(left) != "" {
			return left
		}
		return right
	}
}

func compareStreamIDs(left, right string) int {
	leftMillis, leftSequence, leftOK := parseStreamID(left)
	rightMillis, rightSequence, rightOK := parseStreamID(right)
	switch {
	case !leftOK && !rightOK:
		return 0
	case !leftOK:
		return -1
	case !rightOK:
		return 1
	}

	if leftMillis < rightMillis {
		return -1
	}
	if leftMillis > rightMillis {
		return 1
	}
	if leftSequence < rightSequence {
		return -1
	}
	if leftSequence > rightSequence {
		return 1
	}
	return 0
}

func parseStreamID(value string) (int64, int64, bool) {
	parts := strings.SplitN(strings.TrimSpace(value), "-", 2)
	if len(parts) != 2 {
		return 0, 0, false
	}

	millis, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return 0, 0, false
	}
	sequence, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		return 0, 0, false
	}
	return millis, sequence, true
}

func deepCloneMetadataMap(input map[string]any) map[string]any {
	if input == nil {
		return nil
	}

	cloned := make(map[string]any, len(input))
	for key, value := range input {
		cloned[key] = deepCloneMetadataValue(value)
	}
	return cloned
}

func deepCloneMetadataValue(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		return deepCloneMetadataMap(typed)
	case []any:
		cloned := make([]any, len(typed))
		for idx, item := range typed {
			cloned[idx] = deepCloneMetadataValue(item)
		}
		return cloned
	default:
		return typed
	}
}

func mergeSignalLogs(existing []models.SignalLog, incoming []models.SignalLog, cutoff time.Time) []models.SignalLog {
	deduped := make(map[string]models.SignalLog, len(existing)+len(incoming))
	combined := make([]models.SignalLog, 0, len(existing)+len(incoming))
	combined = append(combined, existing...)
	combined = append(combined, incoming...)

	for _, log := range combined {
		if strings.TrimSpace(log.DocID) == "" || (log.TimeStamp.IsZero() && log.SignalizedAt.IsZero()) {
			continue
		}
		log.TimeStamp = log.TimeStamp.UTC()
		log.SignalizedAt = log.SignalizedAt.UTC()
		if signalLogRetentionTime(log).Before(cutoff.UTC()) {
			continue
		}

		current, exists := deduped[log.DocID]
		if !exists || shouldReplaceSignalLog(current, log) {
			deduped[log.DocID] = log
		}
	}

	merged := make([]models.SignalLog, 0, len(deduped))
	for _, log := range deduped {
		merged = append(merged, log)
	}
	sort.Slice(merged, func(i, j int) bool {
		if merged[i].TimeStamp.Equal(merged[j].TimeStamp) {
			return merged[i].DocID < merged[j].DocID
		}
		return merged[i].TimeStamp.Before(merged[j].TimeStamp)
	})
	return merged
}

func shouldReplaceSignalLog(current models.SignalLog, candidate models.SignalLog) bool {
	if candidate.TimeStamp.After(current.TimeStamp) {
		return true
	}
	if candidate.TimeStamp.Before(current.TimeStamp) {
		return false
	}
	if candidate.SignalizedAt.After(current.SignalizedAt) {
		return true
	}
	if candidate.SignalizedAt.Before(current.SignalizedAt) {
		return false
	}
	return signalLogCompletenessScore(candidate) >= signalLogCompletenessScore(current)
}

func signalLogCompletenessScore(log models.SignalLog) int {
	score := 0
	if strings.TrimSpace(log.HostIdentity) != "" {
		score++
	}
	if strings.TrimSpace(log.Signal) != "" {
		score++
	}
	if strings.TrimSpace(log.LogLevel) != "" {
		score++
	}
	if strings.TrimSpace(log.DocID) != "" {
		score++
	}
	if !log.SignalizedAt.IsZero() {
		score++
	}
	return score
}

func signalLogsEqual(left []models.SignalLog, right []models.SignalLog) bool {
	if len(left) != len(right) {
		return false
	}
	for idx := range left {
		if left[idx].HostIdentity != right[idx].HostIdentity {
			return false
		}
		if left[idx].Signal != right[idx].Signal {
			return false
		}
		if left[idx].LogLevel != right[idx].LogLevel {
			return false
		}
		if left[idx].DocID != right[idx].DocID {
			return false
		}
		if !left[idx].TimeStamp.UTC().Equal(right[idx].TimeStamp.UTC()) {
			return false
		}
		if !left[idx].SignalizedAt.UTC().Equal(right[idx].SignalizedAt.UTC()) {
			return false
		}
	}
	return true
}

func signalLogRetentionTime(log models.SignalLog) time.Time {
	if log.SignalizedAt.After(log.TimeStamp) {
		return log.SignalizedAt.UTC()
	}
	return log.TimeStamp.UTC()
}

func rollbackIncidentActionState(activeByID map[string]models.IncidentState, action incidentAction) {
	if activeByID == nil || action.result == nil || action.result.IncidentID == "" || action.delete {
		return
	}
	if action.previousState != nil {
		activeByID[action.result.IncidentID] = *action.previousState
		return
	}
	delete(activeByID, action.result.IncidentID)
}

func signalPayloadSignature(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func ruleSetSignature(rules []models.Rule) string {
	payload, err := json.Marshal(rules)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func boolToInt(value bool) int {
	if value {
		return 1
	}
	return 0
}

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}

func uniqueSignalDocIDs(signalLogs []models.SignalLog) []string {
	seen := make(map[string]struct{}, len(signalLogs))
	result := make([]string, 0, len(signalLogs))
	for _, signalLog := range signalLogs {
		if signalLog.DocID == "" {
			continue
		}
		if _, ok := seen[signalLog.DocID]; ok {
			continue
		}
		seen[signalLog.DocID] = struct{}{}
		result = append(result, signalLog.DocID)
	}
	return result
}

func shouldProcessOrganization(signalSignature, rulesSignature string, checkpoint models.ProcessingCheckpoint) (bool, int, bool) {
	previousSignature := strings.TrimSpace(checkpoint.SignalPayloadSignature)
	previousRulesSignature := strings.TrimSpace(checkpoint.RulesSignature)
	if previousSignature != "" && previousSignature == signalSignature &&
		previousRulesSignature != "" && previousRulesSignature == rulesSignature {
		return false, checkpoint.SignalCount, false
	}
	rulesChanged := previousRulesSignature != "" && previousRulesSignature != rulesSignature
	return true, checkpoint.SignalCount, rulesChanged
}

func maxCheckpointTimestamp(previous, candidate time.Time) time.Time {
	if candidate.After(previous) {
		return candidate.UTC()
	}
	return previous.UTC()
}

func (p *Processor) distributedMetadataTTL() time.Duration {
	ttl := p.config.Redis.SignalStreamUnconsumedRetention
	if ttl <= 0 {
		ttl = 2 * time.Hour
	}
	if leaseTTL := p.config.Distributed.LeaseTTL; leaseTTL > ttl {
		return leaseTTL
	}
	return ttl
}

func (p *Processor) ensurePersistentDistributedWorkerHeartbeat(ctx context.Context) error {
	if !p.config.Distributed.Enabled || p.distributed == nil || strings.TrimSpace(p.workerID) == "" {
		return nil
	}
	if err := p.heartbeatDistributedWorker(ctx); err != nil {
		return err
	}
	if p.config.Distributed.LeaseHeartbeatInterval <= 0 {
		return nil
	}

	p.workerHeartbeatMu.Lock()
	defer p.workerHeartbeatMu.Unlock()
	if p.workerHeartbeatStarted {
		return nil
	}
	p.workerHeartbeatStarted = true

	go p.runPersistentDistributedWorkerHeartbeat()
	return nil
}

func (p *Processor) runPersistentDistributedWorkerHeartbeat() {
	interval := p.config.Distributed.LeaseHeartbeatInterval
	if interval <= 0 {
		return
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		timeout := p.config.Redis.WriteTimeout
		if timeout <= 0 || timeout > interval {
			timeout = interval
		}
		heartbeatCtx, cancel := context.WithTimeout(context.Background(), timeout)
		err := p.heartbeatDistributedWorker(heartbeatCtx)
		cancel()
		if err != nil {
			p.logger.Warn(
				"distributed worker heartbeat failed",
				"worker_id", p.workerID,
				"error", err,
			)
		}
	}
}

func partitionRulesByExecutionMode(rules []models.Rule) ruleExecutionBuckets {
	buckets := ruleExecutionBuckets{
		incrementalLive:   make([]models.Rule, 0, len(rules)),
		incrementalShadow: make([]models.Rule, 0),
		fullPayloadLive:   make([]models.Rule, 0),
		fullPayloadShadow: make([]models.Rule, 0),
	}
	for _, rule := range rules {
		target := &buckets.incrementalLive
		if strings.TrimSpace(rule.MaxGapBetweenSteps) == "" {
			target = &buckets.fullPayloadLive
		}
		if rule.ShadowMode {
			if strings.TrimSpace(rule.MaxGapBetweenSteps) == "" {
				target = &buckets.fullPayloadShadow
			} else {
				target = &buckets.incrementalShadow
			}
		}
		*target = append(*target, rule)
	}
	return buckets
}

func indexRulesByID(rules []models.Rule) map[string]models.Rule {
	index := make(map[string]models.Rule, len(rules))
	for _, rule := range rules {
		index[rule.ID] = rule
	}
	return index
}

func missingCacheDocIDs(signalLogs []models.SignalLog, cache *enrichmentCache) []string {
	seen := make(map[string]struct{}, len(signalLogs))
	result := make([]string, 0, len(signalLogs))
	for _, signalLog := range signalLogs {
		docID := strings.TrimSpace(signalLog.DocID)
		if docID == "" {
			continue
		}
		if _, ok := seen[docID]; ok {
			continue
		}
		if _, ok := cache.fullLogs[docID]; ok {
			continue
		}
		if _, ok := cache.missing[docID]; ok {
			continue
		}
		seen[docID] = struct{}{}
		result = append(result, docID)
	}
	return result
}

func (p *Processor) logShadowMatches(organization string, results []models.CorrelationResult, rulesByID map[string]models.Rule) {
	if len(results) == 0 || p.logger == nil {
		return
	}
	for _, result := range results {
		p.logMatchAudit("shadow rule matched", organization, &result, rulesByID[result.RuleID], true)
	}
}

func (p *Processor) logMatchAudit(message, organization string, result *models.CorrelationResult, rule models.Rule, shadow bool) {
	if p.logger == nil || result == nil {
		return
	}

	p.logger.Info(
		message,
		"organization", organization,
		"rule_id", result.RuleID,
		"incident_id", result.IncidentID,
		"status", result.Status,
		"shadow_mode", shadow,
		"priority", rule.Priority,
		"rule_completion", result.RuleCompletion,
		"sequence_match", result.SequenceMatch,
		"matched_logs", len(result.LogID),
		"audit", auditLogValue(result.Audit),
	)
}

func auditLogValue(audit *models.MatchAudit) map[string]any {
	if audit == nil {
		return nil
	}

	steps := make([]map[string]any, 0, len(audit.Steps))
	for _, step := range audit.Steps {
		steps = append(steps, map[string]any{
			"step_index":      step.StepIndex,
			"signal_key":      step.SignalKey,
			"required_count":  step.RequiredCount,
			"matched_count":   step.MatchedCount,
			"within":          step.Within,
			"matched_log_ids": append([]string(nil), step.MatchedLogIDs...),
		})
	}

	return map[string]any{
		"rule_type":             audit.RuleType,
		"window":                audit.Window,
		"max_gap_between_steps": audit.MaxGapBetweenSteps,
		"group_by":              append([]string(nil), audit.GroupBy...),
		"group_by_values":       cloneGroupByValues(audit.GroupByValues),
		"required_metadata":     cloneGroupByValues(audit.RequiredMetadata),
		"negative_signals":      append([]string(nil), audit.NegativeSignals...),
		"deduplication_key":     append([]string(nil), audit.DeduplicationKey...),
		"deduplication_window":  audit.DeduplicationWindow,
		"matched_log_ids":       append([]string(nil), audit.MatchedLogIDs...),
		"matched_signals":       append([]string(nil), audit.MatchedSignals...),
		"steps":                 steps,
	}
}
