package service

import (
	"context"
	"errors"
	"log/slog"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"log_correlation_engine/internal/autoscaling"
	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/fetch"
	"log_correlation_engine/internal/models"
)

type testStore struct {
	mu                  sync.Mutex
	organizations       []string
	logBatches          map[string][][]models.SignalLog
	loadCalls           map[string]int
	published           []*models.CorrelationResult
	checkpoints         map[string]models.ProcessingCheckpoint
	incidents           map[string]models.IncidentState
	streamEvents        []models.SignalStreamEvent
	streamReads         int
	streamNextID        string
	trimCalls           int
	trimMinIDs          []string
	ackedStreamGroups   map[string][]string
	consumerGroups      []string
	leases              map[string]string
	fullLogCache        map[string]*models.FullLog
	workerHeartbeats    map[string]distributed.WorkerHeartbeat
	runRecords          map[string]distributed.WorkloadRun
	runStatuses         map[string]distributed.ShardState
	runMessages         map[string]string
	finalizationClaims  map[string]string
	shardContracts      map[string]distributed.ShardContract
	shardPayloads       map[string]distributed.ShardExecutionPayload
	shardResults        map[string]distributed.ShardExecutionResult
	shardLeases         map[string]string
	denyRunFinalization bool
}

func (s *testStore) ListOrganizations(context.Context) ([]string, error) {
	return append([]string(nil), s.organizations...), nil
}

func (s *testStore) LoadSignalPayload(_ context.Context, organization string) ([]byte, error) {
	s.loadCalls[organization]++
	batches := s.logBatches[organization]
	if len(batches) == 0 {
		return []byte{}, nil
	}

	index := s.loadCalls[organization] - 1
	if index >= len(batches) {
		index = len(batches) - 1
	}

	return models.MarshalSignalLogsPayload(batches[index])
}

func (s *testStore) PublishResult(_ context.Context, result *models.CorrelationResult) error {
	s.published = append(s.published, cloneCorrelationResult(result))
	return nil
}

func (s *testStore) SaveSignalLogs(_ context.Context, organization string, logs []models.SignalLog) error {
	if s.logBatches == nil {
		s.logBatches = make(map[string][][]models.SignalLog)
	}
	s.logBatches[organization] = [][]models.SignalLog{append([]models.SignalLog(nil), logs...)}
	found := false
	for _, existing := range s.organizations {
		if existing == organization {
			found = true
			break
		}
	}
	if !found {
		s.organizations = append(s.organizations, organization)
	}
	return nil
}

func (s *testStore) DeleteSignalLogs(_ context.Context, organization string) error {
	delete(s.logBatches, organization)
	filtered := make([]string, 0, len(s.organizations))
	for _, existing := range s.organizations {
		if existing != organization {
			filtered = append(filtered, existing)
		}
	}
	s.organizations = filtered
	return nil
}

func (s *testStore) ReadSignalStream(_ context.Context, lastID string) ([]models.SignalStreamEvent, string, error) {
	s.streamReads++
	if len(s.streamEvents) == 0 {
		return nil, lastID, nil
	}
	events := append([]models.SignalStreamEvent(nil), s.streamEvents...)
	s.streamEvents = nil
	nextID := "1-0"
	if strings.TrimSpace(lastID) != "" {
		nextID = lastID + "-next"
	}
	if strings.TrimSpace(s.streamNextID) != "" {
		nextID = s.streamNextID
	}
	return events, nextID, nil
}

func (s *testStore) EnsureSignalStreamConsumerGroup(_ context.Context, group string) error {
	s.consumerGroups = append(s.consumerGroups, group)
	return nil
}

func (s *testStore) ReadSignalStreamConsumerGroup(_ context.Context, group, _ string, _ time.Duration) ([]models.SignalStreamEvent, []string, error) {
	s.consumerGroups = append(s.consumerGroups, group)
	if len(s.streamEvents) == 0 {
		return nil, nil, nil
	}
	events := append([]models.SignalStreamEvent(nil), s.streamEvents...)
	ids := make([]string, len(events))
	for idx := range ids {
		ids[idx] = "msg-" + string(rune('1'+idx))
	}
	s.streamEvents = nil
	return events, ids, nil
}

func (s *testStore) AckSignalStream(_ context.Context, group string, ids []string) error {
	if s.ackedStreamGroups == nil {
		s.ackedStreamGroups = make(map[string][]string)
	}
	s.ackedStreamGroups[group] = append([]string(nil), ids...)
	return nil
}

func (s *testStore) TrimSignalStream(_ context.Context, minID string) (int64, error) {
	s.trimCalls++
	s.trimMinIDs = append(s.trimMinIDs, minID)
	return 0, nil
}

func (s *testStore) MergeSignalLogs(_ context.Context, organization string, incoming []models.SignalLog, retentionCutoff time.Time) (bool, bool, error) {
	existing := s.currentSignalLogs(organization)
	merged := mergeSignalLogs(existing, incoming, retentionCutoff.UTC())
	switch {
	case len(merged) == 0:
		if len(existing) == 0 {
			return false, false, nil
		}
		if err := s.DeleteSignalLogs(context.Background(), organization); err != nil {
			return false, true, err
		}
		return false, true, nil
	case signalLogsEqual(existing, merged):
		return false, false, nil
	default:
		if err := s.SaveSignalLogs(context.Background(), organization, merged); err != nil {
			return false, false, err
		}
		return true, false, nil
	}
}

func (s *testStore) LoadCheckpoint(_ context.Context, organization string) (models.ProcessingCheckpoint, error) {
	if s.checkpoints == nil {
		return models.ProcessingCheckpoint{}, nil
	}
	return s.checkpoints[organization], nil
}

func (s *testStore) SaveCheckpoint(_ context.Context, organization string, checkpoint models.ProcessingCheckpoint) error {
	if s.checkpoints == nil {
		s.checkpoints = make(map[string]models.ProcessingCheckpoint)
	}
	checkpoint.Checkpoint = checkpoint.Checkpoint.UTC()
	s.checkpoints[organization] = checkpoint
	return nil
}

func (s *testStore) LoadIncident(_ context.Context, organization, incidentID string) (*models.IncidentState, error) {
	if s.incidents == nil {
		return nil, nil
	}
	state, ok := s.incidents[organization+"|"+incidentID]
	if !ok {
		return nil, nil
	}
	cloned := state
	return &cloned, nil
}

func (s *testStore) ListActiveIncidents(_ context.Context, organization string) ([]models.IncidentState, error) {
	if s.incidents == nil {
		return nil, nil
	}

	results := make([]models.IncidentState, 0)
	prefix := organization + "|"
	for key, state := range s.incidents {
		if len(key) >= len(prefix) && key[:len(prefix)] == prefix {
			results = append(results, state)
		}
	}
	return results, nil
}

func (s *testStore) SaveIncident(_ context.Context, state *models.IncidentState, _ time.Duration) error {
	if state == nil {
		return errors.New("incident state is nil")
	}
	if s.incidents == nil {
		s.incidents = make(map[string]models.IncidentState)
	}
	s.incidents[state.OrganizationID+"|"+state.IncidentID] = *state
	return nil
}

func (s *testStore) DeleteIncident(_ context.Context, organization, incidentID string) error {
	if s.incidents != nil {
		delete(s.incidents, organization+"|"+incidentID)
	}
	return nil
}

func (s *testStore) ClaimWorkloadLease(_ context.Context, lease distributed.Lease, _ time.Duration) (bool, error) {
	if s.leases == nil {
		s.leases = make(map[string]string)
	}
	key := lease.Workload.LeaseKey()
	if _, ok := s.leases[key]; ok {
		return false, nil
	}
	s.leases[key] = lease.Token
	return true, nil
}

func (s *testStore) RenewWorkloadLease(_ context.Context, lease distributed.Lease, _ time.Duration) (bool, error) {
	if s.leases == nil {
		return false, nil
	}
	if token := s.leases[lease.Workload.LeaseKey()]; token == lease.Token {
		return true, nil
	}
	return false, nil
}

func (s *testStore) VerifyWorkloadLease(_ context.Context, lease distributed.Lease) (bool, error) {
	if s.leases == nil {
		return false, nil
	}
	return s.leases[lease.Workload.LeaseKey()] == lease.Token, nil
}

func (s *testStore) ReleaseWorkloadLease(_ context.Context, lease distributed.Lease) error {
	if s.leases != nil {
		delete(s.leases, lease.Workload.LeaseKey())
	}
	return nil
}

func (s *testStore) LoadCachedFullLogs(_ context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	if len(docIDs) == 0 || len(s.fullLogCache) == 0 {
		return nil, nil
	}
	result := make(map[string]*models.FullLog)
	for _, docID := range docIDs {
		if fullLog, ok := s.fullLogCache[docID]; ok && fullLog != nil {
			cloned := cloneFullLog(*fullLog)
			result[docID] = &cloned
		}
	}
	return result, nil
}

func (s *testStore) SaveCachedFullLogs(_ context.Context, logs map[string]*models.FullLog, _ time.Duration) error {
	if s.fullLogCache == nil {
		s.fullLogCache = make(map[string]*models.FullLog)
	}
	for docID, fullLog := range logs {
		if fullLog == nil {
			continue
		}
		cloned := cloneFullLog(*fullLog)
		s.fullLogCache[docID] = &cloned
	}
	return nil
}

func (s *testStore) HeartbeatWorker(_ context.Context, worker distributed.WorkerHeartbeat, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.workerHeartbeats == nil {
		s.workerHeartbeats = make(map[string]distributed.WorkerHeartbeat)
	}
	s.workerHeartbeats[worker.WorkerID] = distributed.WorkerHeartbeat{
		WorkerID:  worker.WorkerID,
		UpdatedAt: worker.UpdatedAt.UTC(),
	}
	return nil
}

func (s *testStore) ListActiveWorkers(_ context.Context) ([]distributed.WorkerHeartbeat, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.workerHeartbeats) == 0 {
		return nil, nil
	}
	workers := make([]distributed.WorkerHeartbeat, 0, len(s.workerHeartbeats))
	for _, worker := range s.workerHeartbeats {
		workers = append(workers, worker)
	}
	sort.Slice(workers, func(i, j int) bool {
		return workers[i].WorkerID < workers[j].WorkerID
	})
	return workers, nil
}

func (s *testStore) StartWorkloadRun(_ context.Context, lease distributed.Lease, run distributed.WorkloadRun, shard distributed.ShardContract, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.leases == nil || s.leases[lease.Workload.LeaseKey()] != lease.Token {
		return errors.New("workload lease not owned")
	}
	if s.runRecords == nil {
		s.runRecords = make(map[string]distributed.WorkloadRun)
	}
	if s.runStatuses == nil {
		s.runStatuses = make(map[string]distributed.ShardState)
	}
	if s.shardContracts == nil {
		s.shardContracts = make(map[string]distributed.ShardContract)
	}
	runKey := runStoreKey(run)
	s.runRecords[runKey] = run
	s.runStatuses[runKey] = distributed.ShardStateRunning
	shard.State = distributed.ShardStateRunning
	shard.RunID = run.ID
	s.shardContracts[shardStoreKey(shard)] = shard
	return nil
}

func (s *testStore) ClaimWorkloadRunFinalization(_ context.Context, lease distributed.Lease, run distributed.WorkloadRun, _ time.Duration) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.denyRunFinalization {
		return false, nil
	}
	if s.leases == nil || s.leases[lease.Workload.LeaseKey()] != lease.Token {
		return false, errors.New("workload lease not owned")
	}
	if s.finalizationClaims == nil {
		s.finalizationClaims = make(map[string]string)
	}
	runKey := runStoreKey(run)
	token := run.FinalizationToken()
	if existing, ok := s.finalizationClaims[runKey]; ok {
		return existing == token, nil
	}
	s.finalizationClaims[runKey] = token
	return true, nil
}

func (s *testStore) FinishWorkloadRun(
	_ context.Context,
	lease distributed.Lease,
	run distributed.WorkloadRun,
	shard distributed.ShardContract,
	status distributed.ShardState,
	_ time.Duration,
	message string,
) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.leases == nil || s.leases[lease.Workload.LeaseKey()] != lease.Token {
		return errors.New("workload lease not owned")
	}
	if s.runStatuses == nil {
		s.runStatuses = make(map[string]distributed.ShardState)
	}
	if s.runMessages == nil {
		s.runMessages = make(map[string]string)
	}
	if s.shardContracts == nil {
		s.shardContracts = make(map[string]distributed.ShardContract)
	}
	runKey := runStoreKey(run)
	s.runStatuses[runKey] = status
	s.runMessages[runKey] = message
	shard.State = status
	shard.RunID = run.ID
	s.shardContracts[shardStoreKey(shard)] = shard
	return nil
}

func (s *testStore) StoreWorkloadShards(_ context.Context, lease distributed.Lease, run distributed.WorkloadRun, shards []distributed.ShardExecutionPayload, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.leases == nil || s.leases[lease.Workload.LeaseKey()] != lease.Token {
		return errors.New("workload lease not owned")
	}
	if s.shardContracts == nil {
		s.shardContracts = make(map[string]distributed.ShardContract)
	}
	if s.shardPayloads == nil {
		s.shardPayloads = make(map[string]distributed.ShardExecutionPayload)
	}
	for _, shard := range shards {
		shard.Workload = run.Workload
		shard.RunID = run.ID
		contract := shard.Contract(run.Owner)
		s.shardContracts[shardStoreKey(contract)] = contract
		s.shardPayloads[shardStoreKey(contract)] = shard
	}
	return nil
}

func (s *testStore) ClaimWorkloadShard(_ context.Context, workerID string, _ time.Duration, run *distributed.WorkloadRun) (*distributed.ShardExecutionPayload, *distributed.ShardLease, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for key, contract := range s.shardContracts {
		if contract.NormalizedShardID() == "root" {
			continue
		}
		if run != nil {
			if contract.Workload.LeaseKey() != run.Workload.LeaseKey() || contract.RunID != run.ID {
				continue
			}
		}
		if contract.State == distributed.ShardStateCompleted {
			continue
		}
		if contract.State == distributed.ShardStateFailed && !contract.Retryable {
			continue
		}
		if s.shardLeases == nil {
			s.shardLeases = make(map[string]string)
		}
		if token := s.shardLeases[key]; token != "" {
			continue
		}
		payload := s.shardPayloads[key]
		lease := distributed.NewShardLease(contract, workerID)
		contract.State = distributed.ShardStateRunning
		contract.Owner = workerID
		contract.Attempt++
		s.shardContracts[key] = contract
		s.shardLeases[key] = lease.Token
		return &payload, &lease, nil
	}
	return nil, nil, nil
}

func (s *testStore) RenewWorkloadShardLease(_ context.Context, lease distributed.ShardLease, _ time.Duration) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.shardLeases == nil {
		return false, nil
	}
	return s.shardLeases[shardStoreKey(lease.Contract)] == lease.Token, nil
}

func (s *testStore) ReleaseWorkloadShardLease(_ context.Context, lease distributed.ShardLease) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.shardLeases != nil && s.shardLeases[shardStoreKey(lease.Contract)] == lease.Token {
		delete(s.shardLeases, shardStoreKey(lease.Contract))
	}
	return nil
}

func (s *testStore) CompleteWorkloadShard(_ context.Context, lease distributed.ShardLease, result distributed.ShardExecutionResult, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := shardStoreKey(lease.Contract)
	if s.shardLeases == nil || s.shardLeases[key] != lease.Token {
		return errors.New("distributed shard lease not owned")
	}
	if s.shardContracts == nil {
		s.shardContracts = make(map[string]distributed.ShardContract)
	}
	if s.shardResults == nil {
		s.shardResults = make(map[string]distributed.ShardExecutionResult)
	}
	contract := lease.Contract
	contract.State = distributed.ShardStateCompleted
	contract.Owner = lease.Owner
	s.shardContracts[key] = contract
	result.Workload = contract.Workload
	result.RunID = contract.RunID
	result.ShardID = contract.NormalizedShardID()
	result.Mode = contract.NormalizedMode()
	result.WorkerID = lease.Owner
	result.Status = distributed.ShardStateCompleted
	s.shardResults[key] = result
	delete(s.shardLeases, key)
	return nil
}

func (s *testStore) FailWorkloadShard(_ context.Context, lease distributed.ShardLease, message string, retryable bool, retryAfter time.Time, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := shardStoreKey(lease.Contract)
	if s.shardLeases == nil || s.shardLeases[key] != lease.Token {
		return errors.New("distributed shard lease not owned")
	}
	contract := lease.Contract
	contract.State = distributed.ShardStateFailed
	contract.Owner = lease.Owner
	contract.Retryable = retryable
	contract.RetryAfter = retryAfter.UTC()
	s.shardContracts[key] = contract
	if s.runMessages == nil {
		s.runMessages = make(map[string]string)
	}
	s.runMessages[key] = message
	delete(s.shardLeases, key)
	return nil
}

func (s *testStore) LoadWorkloadShardResults(_ context.Context, run distributed.WorkloadRun, mode string) ([]distributed.ShardExecutionResult, []distributed.ShardContract, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	results := make([]distributed.ShardExecutionResult, 0)
	contracts := make([]distributed.ShardContract, 0)
	for key, contract := range s.shardContracts {
		if contract.NormalizedShardID() == "root" {
			continue
		}
		if contract.Workload.LeaseKey() != run.Workload.LeaseKey() || contract.RunID != run.ID {
			continue
		}
		if mode != "" && contract.NormalizedMode() != strings.TrimSpace(mode) {
			continue
		}
		contracts = append(contracts, contract)
		if contract.State == distributed.ShardStateCompleted {
			if result, ok := s.shardResults[key]; ok {
				results = append(results, result)
			}
		}
	}
	sort.Slice(contracts, func(i, j int) bool {
		return contracts[i].NormalizedShardID() < contracts[j].NormalizedShardID()
	})
	sort.Slice(results, func(i, j int) bool {
		return results[i].NormalizedShardID() < results[j].NormalizedShardID()
	})
	return results, contracts, nil
}

func (s *testStore) currentSignalLogs(organization string) []models.SignalLog {
	batches := s.logBatches[organization]
	if len(batches) == 0 {
		return nil
	}
	current := batches[len(batches)-1]
	return append([]models.SignalLog(nil), current...)
}

func runStoreKey(run distributed.WorkloadRun) string {
	return run.Workload.LeaseKey() + "|" + strings.TrimSpace(run.ID)
}

func shardStoreKey(shard distributed.ShardContract) string {
	return shard.Workload.LeaseKey() + "|" + strings.TrimSpace(shard.RunID) + "|" + shard.NormalizedShardID()
}

type testFetcher struct {
	calls int
}

func (f *testFetcher) FetchLog(_ context.Context, docID string) (*models.FullLog, error) {
	f.calls++
	return &models.FullLog{
		DocID:     docID,
		Timestamp: time.Unix(0, 0).UTC(),
		Metadata:  map[string]any{},
	}, nil
}

type batchTestFetcher struct {
	batchCalls int
	requests   []string
	batchSizes []int
}

func (f *batchTestFetcher) FetchLog(_ context.Context, docID string) (*models.FullLog, error) {
	return &models.FullLog{
		DocID:     docID,
		Timestamp: time.Unix(0, 0).UTC(),
		Metadata:  map[string]any{},
	}, nil
}

func (f *batchTestFetcher) FetchLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	return f.FetchLogsWithOptions(ctx, docIDs, fetch.BatchFetchOptions{})
}

func (f *batchTestFetcher) FetchLogsWithOptions(_ context.Context, docIDs []string, options fetch.BatchFetchOptions) (map[string]*models.FullLog, error) {
	f.batchCalls++
	f.requests = append(f.requests, docIDs...)
	f.batchSizes = append(f.batchSizes, options.GroupedLookupBatchSize)
	result := make(map[string]*models.FullLog, len(docIDs))
	for _, docID := range docIDs {
		result[docID] = &models.FullLog{
			DocID:     docID,
			Timestamp: time.Unix(0, 0).UTC(),
			Metadata:  map[string]any{},
		}
	}
	return result, nil
}

type testRules struct {
	rules []models.Rule
}

func (r *testRules) GetRules() []models.Rule {
	return append([]models.Rule(nil), r.rules...)
}

type testWriter struct {
	results           []*models.CorrelationResult
	resultsByDocument map[string]*models.CorrelationResult
	failuresLeft      int
}

func (w *testWriter) WriteResults(_ context.Context, results []*models.CorrelationResult) []error {
	errs := make([]error, len(results))
	for idx, result := range results {
		if w.failuresLeft > 0 {
			w.failuresLeft--
			errs[idx] = errors.New("writer failed")
			continue
		}
		cloned := cloneCorrelationResult(result)
		w.results = append(w.results, cloned)
		if cloned == nil {
			continue
		}
		if err := cloned.EnsureDocumentID(); err != nil {
			errs[idx] = err
			continue
		}
		if w.resultsByDocument == nil {
			w.resultsByDocument = make(map[string]*models.CorrelationResult)
		}
		w.resultsByDocument[cloned.DocumentID] = cloneCorrelationResult(cloned)
	}
	return errs
}

type CorrelatorFunc func(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error)

func (fn CorrelatorFunc) Correlate(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error) {
	return fn(ctx, orgID, logs, rules)
}

func baseTestConfig() config.Config {
	return config.Config{
		Scheduler: config.SchedulerConfig{
			OrganizationWorkers: 1,
		},
		Redis: config.RedisConfig{
			SignalStreamConsumedRetention:   30 * time.Minute,
			SignalStreamUnconsumedRetention: 2 * time.Hour,
		},
		Engine: config.EngineConfig{
			DefaultWindow:         10 * time.Minute,
			DefaultMaxGap:         time.Minute,
			IncidentInactivityTTL: 30 * time.Minute,
			ParallelCorrelation: config.ParallelCorrelationConfig{
				TargetLogsPerShard:             5000,
				MaxWorkers:                     4,
				DistributedTargetShardDuration: 2 * time.Second,
				DistributedMinShardsPerWorker:  1,
				DistributedMaxShardsPerWorker:  4,
				ShardPollInterval:              20 * time.Millisecond,
			},
		},
		Fetcher: config.FetcherConfig{
			GroupedLookupBatchSize: 250,
		},
	}
}

func resultFromLogs(orgID, ruleID string, logs []models.FullLog) models.CorrelationResult {
	compact := make([]models.ResultLog, 0, len(logs))
	matchedAt := time.Time{}
	for _, log := range logs {
		compact = append(compact, models.ResultLog{
			ID:       log.DocID,
			Severity: log.LogLevel,
		})
		if log.Timestamp.After(matchedAt) {
			matchedAt = log.Timestamp
		}
	}

	return models.CorrelationResult{
		OrganizationID: orgID,
		RuleID:         ruleID,
		LogID:          compact,
		RuleCompletion: 1,
		SequenceMatch:  1,
		MatchedAt:      matchedAt,
	}
}

func TestProcessorSkipsUnchangedPayloadWithoutReprocessingIncident(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
	}
	fetcher := &testFetcher{}
	engineCalls := 0
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		engineCalls++
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()
	cfg.Redis.PublishResults = true

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      writer,
		Logger:      slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}

	if fetcher.calls != 1 {
		t.Fatalf("expected fetcher to run once, got %d", fetcher.calls)
	}
	if engineCalls != 1 {
		t.Fatalf("expected correlator to run once, got %d", engineCalls)
	}
	if len(writer.results) != 1 || writer.results[0].Status != "open" {
		t.Fatalf("expected one open incident write, got %#v", writer.results)
	}
}

func TestProcessorIngestsSignalStreamIntoRedisPayloadBeforeCorrelation(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		logBatches:   make(map[string][][]models.SignalLog),
		loadCalls:    make(map[string]int),
		streamNextID: streamTimeToID(base),
		streamEvents: []models.SignalStreamEvent{
			{
				OrganizationID: "org-1",
				DocID:          "doc-1",
				Signal:         "signal-a",
				LogLevel:       "warning",
				TimeStamp:      base,
			},
		},
	}
	engineCalls := 0
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		engineCalls++
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})
	cfg := baseTestConfig()
	cfg.Redis.SignalStreamEnabled = true
	cfg.Redis.SignalStreamKey = "Rca:signalized_log_events"
	cfg.Redis.SignalStreamBatchSize = 1000

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      &testWriter{},
		Logger:      slog.Default(),
	})
	processor.now = func() time.Time {
		return base.Add(10 * time.Minute)
	}

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if store.streamReads != 1 {
		t.Fatalf("expected one stream read, got %d", store.streamReads)
	}
	if engineCalls != 1 {
		t.Fatalf("expected one correlate call after stream hydration, got %d", engineCalls)
	}
	if len(store.organizations) != 1 || store.organizations[0] != "org-1" {
		t.Fatalf("expected org-1 to be added to redis payload state, got %#v", store.organizations)
	}
	gotPayload := store.logBatches["org-1"]
	if len(gotPayload) != 1 || len(gotPayload[0]) != 1 || gotPayload[0][0].DocID != "doc-1" {
		t.Fatalf("unexpected hydrated signal payload: %#v", gotPayload)
	}
	if got := store.checkpoints[signalStreamCheckpointKey].StreamID; got == "" {
		t.Fatalf("expected stream checkpoint id to be saved, got empty value")
	}
	if store.trimCalls != 1 {
		t.Fatalf("expected one stream trim call, got %d", store.trimCalls)
	}
	wantTrimID := computeSignalStreamTrimMinID(
		store.streamNextID,
		base.Add(10*time.Minute),
		cfg.Redis.SignalStreamConsumedRetention,
		cfg.Redis.SignalStreamUnconsumedRetention,
	)
	if len(store.trimMinIDs) != 1 || store.trimMinIDs[0] != wantTrimID {
		t.Fatalf("expected trim min id %q, got %#v", wantTrimID, store.trimMinIDs)
	}
}

func TestComputeSignalStreamTrimMinID(t *testing.T) {
	now := time.Date(2026, time.April, 10, 12, 0, 0, 0, time.UTC)
	consumedRetention := 30 * time.Minute
	unconsumedRetention := 2 * time.Hour

	cases := []struct {
		name           string
		lastConsumedID string
		want           string
	}{
		{
			name: "no checkpoint keeps unconsumed buffer",
			want: streamTimeToID(now.Add(-unconsumedRetention)),
		},
		{
			name:           "recent checkpoint trims consumed entries after shorter window",
			lastConsumedID: streamTimeToID(now.Add(-40 * time.Minute)),
			want:           streamTimeToID(now.Add(-40 * time.Minute)),
		},
		{
			name:           "stale checkpoint still protects only the longer backlog window",
			lastConsumedID: streamTimeToID(now.Add(-3 * time.Hour)),
			want:           streamTimeToID(now.Add(-unconsumedRetention)),
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := computeSignalStreamTrimMinID(tc.lastConsumedID, now, consumedRetention, unconsumedRetention)
			if got != tc.want {
				t.Fatalf("expected trim id %q, got %q", tc.want, got)
			}
		})
	}
}

func TestProcessorUsesBatchFetcherForUniqueDocIDs(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
					{Signal: "signal-c", LogLevel: "error", DocID: "doc-1", TimeStamp: base.Add(2 * time.Second)},
				},
			},
		},
	}
	fetcher := &batchTestFetcher{}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})

	processor := NewProcessor(Dependencies{
		Config:      baseTestConfig(),
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      &testWriter{},
		Logger:      slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if fetcher.batchCalls != 1 {
		t.Fatalf("expected one batch fetch call, got %d", fetcher.batchCalls)
	}
	if len(fetcher.requests) != 2 {
		t.Fatalf("expected 2 unique doc ids in batch fetch, got %d", len(fetcher.requests))
	}
}

func TestProcessorSkipsUnchangedPayloadUsingPersistedCheckpointSignature(t *testing.T) {
	base := time.Now().UTC()
	logs := []models.SignalLog{
		{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
	}
	payload, err := models.MarshalSignalLogsPayload(logs)
	if err != nil {
		t.Fatalf("marshal payload failed: %v", err)
	}

	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {logs},
		},
		checkpoints: map[string]models.ProcessingCheckpoint{
			"org-1": {
				Checkpoint:             base,
				SignalPayloadSignature: signalPayloadSignature(payload),
				SignalCount:            len(logs),
			},
		},
	}
	fetcher := &testFetcher{}
	engineCalls := 0
	engine := CorrelatorFunc(func(_ context.Context, orgID string, fullLogs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		engineCalls++
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", fullLogs)}, nil
	})

	processor := NewProcessor(Dependencies{
		Config:      baseTestConfig(),
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      &testWriter{},
		Logger:      slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if fetcher.calls != 0 {
		t.Fatalf("expected no fetch calls for unchanged payload, got %d", fetcher.calls)
	}
	if engineCalls != 0 {
		t.Fatalf("expected no correlate calls for unchanged payload, got %d", engineCalls)
	}
}

func TestProcessorSeparatesIncrementalAndFullPayloadRuleScopes(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(20 * time.Second)},
					{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base.Add(40 * time.Second)},
				},
			},
		},
		checkpoints: map[string]models.ProcessingCheckpoint{
			"org-1": {
				Checkpoint:             base.Add(35 * time.Second),
				SignalPayloadSignature: "older-signature",
				SignalCount:            2,
			},
		},
	}
	fetcher := &batchTestFetcher{}
	type correlateCall struct {
		ruleIDs  []string
		logCount int
	}
	calls := make([]correlateCall, 0, 2)
	engine := CorrelatorFunc(func(_ context.Context, orgID string, fullLogs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error) {
		ruleIDs := make([]string, 0, len(rules))
		for _, rule := range rules {
			ruleIDs = append(ruleIDs, rule.ID)
		}
		calls = append(calls, correlateCall{
			ruleIDs:  ruleIDs,
			logCount: len(fullLogs),
		})

		results := make([]models.CorrelationResult, 0, len(rules))
		for _, rule := range rules {
			results = append(results, resultFromLogs(orgID, rule.ID, fullLogs))
		}
		return results, nil
	})

	cfg := baseTestConfig()
	cfg.Engine.DefaultWindow = 10 * time.Second
	cfg.Engine.DefaultMaxGap = 5 * time.Second
	cfg.Engine.IncrementalLookback = 5 * time.Second

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-incremental", OrganizationID: "org-1", Window: "10s", MaxGapBetweenSteps: "5s"},
			{ID: "rule-full", OrganizationID: "org-1", Window: "1m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if fetcher.batchCalls != 1 {
		t.Fatalf("expected one shared batch fetch call, got %d", fetcher.batchCalls)
	}
	if len(fetcher.requests) != 3 {
		t.Fatalf("expected three unique doc ids fetched once, got %d", len(fetcher.requests))
	}
	if len(calls) != 2 {
		t.Fatalf("expected two correlate calls, got %d", len(calls))
	}

	callByRule := make(map[string]correlateCall, len(calls))
	for _, call := range calls {
		if len(call.ruleIDs) != 1 {
			t.Fatalf("expected one rule per correlate call, got %v", call.ruleIDs)
		}
		callByRule[call.ruleIDs[0]] = call
	}
	if callByRule["rule-full"].logCount != 3 {
		t.Fatalf("expected full-payload rule to receive 3 logs, got %d", callByRule["rule-full"].logCount)
	}
	if callByRule["rule-incremental"].logCount != 1 {
		t.Fatalf("expected incremental rule to receive 1 log, got %d", callByRule["rule-incremental"].logCount)
	}
}

func TestProcessorDoesNotWriteShadowModeMatches(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
	}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error) {
		results := make([]models.CorrelationResult, 0, len(rules))
		for _, rule := range rules {
			results = append(results, resultFromLogs(orgID, rule.ID, logs))
		}
		return results, nil
	})
	writer := &testWriter{}

	processor := NewProcessor(Dependencies{
		Config:      baseTestConfig(),
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "shadow-rule", OrganizationID: "org-1", ShadowMode: true, Window: "10m", GroupBy: []string{"event.organization"}},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if len(writer.results) != 0 {
		t.Fatalf("expected shadow matches to avoid writes, got %d results", len(writer.results))
	}
	if len(store.published) != 0 {
		t.Fatalf("expected shadow matches to avoid publishing, got %d events", len(store.published))
	}
}

func TestProcessorUpdatesIncidentWhenEvidenceChanges(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
				},
			},
		},
	}
	fetcher := &testFetcher{}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()
	cfg.Redis.PublishResults = true

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      writer,
		Logger:      slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}

	if len(writer.results) != 2 {
		t.Fatalf("expected two incident writes, got %d", len(writer.results))
	}
	if writer.results[0].Status != "open" || writer.results[1].Status != "updated" {
		t.Fatalf("expected open then updated, got %s then %s", writer.results[0].Status, writer.results[1].Status)
	}
	if len(store.published) != 2 || store.published[0].Status != "open" || store.published[1].Status != "updated" {
		t.Fatalf("expected open and updated events to be published, got %#v", store.published)
	}
}

func TestProcessorClosesIncidentOnRecoverySignal(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "recovered", LogLevel: "info", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
				},
			},
		},
	}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		filtered := make([]models.FullLog, 0)
		for _, log := range logs {
			if log.Signal == "recovered" {
				continue
			}
			filtered = append(filtered, log)
		}
		if len(filtered) == 0 {
			return nil, nil
		}
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", filtered)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()
	cfg.Redis.PublishResults = true

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", NotSequence: []models.NegativeStep{{SignalKey: "recovered"}}},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}

	if len(writer.results) != 2 {
		t.Fatalf("expected open and close writes, got %d", len(writer.results))
	}
	if writer.results[1].Status != "closed" {
		t.Fatalf("expected closed status, got %s", writer.results[1].Status)
	}
	if len(store.published) != 2 || store.published[1].Status != "closed" {
		t.Fatalf("expected close to be published, got %#v", store.published)
	}
}

func TestProcessorClosesInactiveIncidentWhenPayloadUnchanged(t *testing.T) {
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: time.Unix(100, 0).UTC()},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: time.Unix(100, 0).UTC()},
				},
			},
		},
	}
	currentTime := time.Unix(100, 0).UTC()
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		result := resultFromLogs(orgID, "rule-1", logs)
		result.MatchedAt = currentTime
		return []models.CorrelationResult{result}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()
	cfg.Engine.IncidentInactivityTTL = 5 * time.Minute

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer:      writer,
		Logger:      slog.Default(),
	})
	processor.now = func() time.Time {
		return currentTime
	}

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}

	currentTime = currentTime.Add(6 * time.Minute)
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}

	if len(writer.results) != 2 {
		t.Fatalf("expected open and inactivity close writes, got %d", len(writer.results))
	}
	if writer.results[1].Status != "closed" {
		t.Fatalf("expected closed status, got %s", writer.results[1].Status)
	}
}

func TestProcessorReusesDocumentIDForExactDuplicateEvidenceAfterClosure(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "recovered", LogLevel: "info", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "recovered", LogLevel: "info", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
					{Signal: "noise", LogLevel: "info", DocID: "doc-3", TimeStamp: base.Add(2 * time.Second)},
				},
			},
		},
	}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		filtered := make([]models.FullLog, 0)
		for _, log := range logs {
			switch log.Signal {
			case "recovered", "noise":
				continue
			default:
				filtered = append(filtered, log)
			}
		}
		if len(filtered) == 0 {
			return nil, nil
		}
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", filtered)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", NotSequence: []models.NegativeStep{{SignalKey: "recovered"}}},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("third cycle failed: %v", err)
	}

	if len(writer.results) != 3 {
		t.Fatalf("expected open, closed, and reopened write attempts, got %d", len(writer.results))
	}
	if writer.results[0].Status != "open" || writer.results[1].Status != "closed" || writer.results[2].Status != "open" {
		t.Fatalf("expected open, closed, then open, got %#v", writer.results)
	}
	if writer.results[0].DocumentID == "" || writer.results[2].DocumentID == "" {
		t.Fatalf("expected document ids on duplicate open events, got %#v", writer.results)
	}
	if writer.results[0].DocumentID != writer.results[2].DocumentID {
		t.Fatalf("expected exact duplicate evidence to reuse document id, got %s and %s", writer.results[0].DocumentID, writer.results[2].DocumentID)
	}
	if len(writer.resultsByDocument) != 2 {
		t.Fatalf("expected only two unique stored documents after document id reuse, got %d", len(writer.resultsByDocument))
	}
}

func TestProcessorCreatesNewIncidentAfterReopenWindow(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "recovered", LogLevel: "info", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "recovered", LogLevel: "info", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-3", TimeStamp: base.Add(31 * time.Minute)},
				},
			},
		},
	}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		filtered := make([]models.FullLog, 0)
		for _, log := range logs {
			if log.Signal == "recovered" {
				continue
			}
			filtered = append(filtered, log)
		}
		if len(filtered) == 0 {
			return nil, nil
		}
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", filtered)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", NotSequence: []models.NegativeStep{{SignalKey: "recovered"}}},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("third cycle failed: %v", err)
	}

	if len(writer.results) != 3 {
		t.Fatalf("expected open, closed, then new open writes, got %d", len(writer.results))
	}
	if writer.results[0].Status != "open" || writer.results[1].Status != "closed" || writer.results[2].Status != "open" {
		t.Fatalf("expected open, closed, then open statuses, got %#v", writer.results)
	}
	if writer.results[0].IncidentID == writer.results[2].IncidentID {
		t.Fatalf("expected a new incident id after reopen window, got %q for both", writer.results[0].IncidentID)
	}
}

func TestProcessorUsesCheckpointLookbackForIncrementalWork(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(20 * time.Second)},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(20 * time.Second)},
					{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base.Add(40 * time.Second)},
				},
			},
		},
	}
	fetcher := &testFetcher{}
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})
	writer := &testWriter{}
	cfg := baseTestConfig()
	cfg.Engine.DefaultWindow = 10 * time.Second
	cfg.Engine.DefaultMaxGap = 5 * time.Second
	cfg.Engine.IncrementalLookback = 10 * time.Second

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules:       &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1", Window: "10s", MaxGapBetweenSteps: "5s"}}},
		Writer:      writer,
		Logger:      slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("third cycle failed: %v", err)
	}

	if fetcher.calls != 5 {
		t.Fatalf("expected incremental fetches to total 5, got %d", fetcher.calls)
	}
}

func TestProcessorCapsIncrementalWorkAndSavesCheckpointDocID(t *testing.T) {
	base := time.Now().UTC()
	logs := []models.SignalLog{
		{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
		{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base},
		{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base},
		{Signal: "signal-d", LogLevel: "critical", DocID: "doc-4", TimeStamp: base},
	}
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {logs},
		},
	}

	cfg := baseTestConfig()
	cfg.Fetcher.GroupedLookupBatchSize = 1
	cfg.Autoscaling.Enabled = true
	cfg.Autoscaling.InputBasis = "incremental_logs"
	cfg.Autoscaling.InputLowWatermark = 1000
	cfg.Autoscaling.InputHighWatermark = 100000
	cfg.Autoscaling.ScaleDownCooldownCycles = 3
	cfg.Autoscaling.Scheduler.MinInterval = 10 * time.Second
	cfg.Autoscaling.Scheduler.MaxInterval = 60 * time.Second
	cfg.Autoscaling.Scheduler.TimeoutRatio = 0.9
	cfg.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 1000
	cfg.Autoscaling.Fetcher.MaxGroupedLookupBatchSize = 10000
	cfg.Autoscaling.Fetcher.MaxBatchesPerCycle = 2

	fetcher := &batchTestFetcher{}
	var correlatedDocIDs []string
	engine := CorrelatorFunc(func(_ context.Context, orgID string, fullLogs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		correlatedDocIDs = correlatedDocIDs[:0]
		for _, log := range fullLogs {
			correlatedDocIDs = append(correlatedDocIDs, log.DocID)
		}
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", fullLogs)}, nil
	})

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer:     &testWriter{},
		Autoscaler: autoscaling.NewController(cfg.Autoscaling, autoscaling.SchedulerSettings{Interval: 5 * time.Second, RunTimeout: 5 * time.Second}, cfg.Fetcher.GroupedLookupBatchSize),
		Logger:     slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if got := strings.Join(correlatedDocIDs, ","); got != "doc-1,doc-2" {
		t.Fatalf("expected capped incremental slice to correlate doc-1/doc-2, got %s", got)
	}
	checkpoint := store.checkpoints["org-1"]
	if checkpoint.CheckpointDocID != "doc-2" {
		t.Fatalf("expected checkpoint doc id doc-2, got %q", checkpoint.CheckpointDocID)
	}
	if checkpoint.Checkpoint.IsZero() || !checkpoint.Checkpoint.Equal(base) {
		t.Fatalf("expected checkpoint timestamp %s, got %s", base, checkpoint.Checkpoint)
	}
}

func TestProcessorContinuesUnchangedPayloadWhenCheckpointCursorIsBehind(t *testing.T) {
	base := time.Now().UTC()
	logs := []models.SignalLog{
		{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
		{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base},
		{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base},
		{Signal: "signal-d", LogLevel: "critical", DocID: "doc-4", TimeStamp: base},
	}
	payload, err := models.MarshalSignalLogsPayload(logs)
	if err != nil {
		t.Fatalf("marshal payload failed: %v", err)
	}

	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {logs},
		},
		checkpoints: map[string]models.ProcessingCheckpoint{
			"org-1": {
				Checkpoint:             base,
				CheckpointDocID:        "doc-2",
				SignalPayloadSignature: signalPayloadSignature(payload),
				RulesSignature:         ruleSetSignature([]models.Rule{{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"}}),
				SignalCount:            len(logs),
			},
		},
	}

	engineCalls := 0
	engine := CorrelatorFunc(func(_ context.Context, orgID string, fullLogs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		engineCalls++
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", fullLogs)}, nil
	})

	processor := NewProcessor(Dependencies{
		Config:      baseTestConfig(),
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("cycle failed: %v", err)
	}

	if engineCalls != 1 {
		t.Fatalf("expected unchanged payload with stale checkpoint cursor to continue processing, got %d engine calls", engineCalls)
	}
	if got := store.checkpoints["org-1"].CheckpointDocID; got != "doc-4" {
		t.Fatalf("expected checkpoint to advance to doc-4, got %q", got)
	}
}

func TestProcessorUsesFullPayloadWhenRuleOmitsMaxGap(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(20 * time.Second)},
				},
			},
		},
	}

	logCounts := make([]int, 0, 2)
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		logCounts = append(logCounts, len(logs))
		if len(logs) == 0 {
			return nil, nil
		}
		return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
	})

	cfg := baseTestConfig()
	cfg.Engine.DefaultWindow = 10 * time.Second
	cfg.Engine.DefaultMaxGap = 5 * time.Second
	cfg.Engine.IncrementalLookback = 5 * time.Second

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{
				ID:             "rule-1",
				OrganizationID: "org-1",
				Window:         "1m",
				Sequence: []models.SequenceStep{
					{SignalKey: "signal-a", MinCount: 1, Within: "1m"},
					{SignalKey: "signal-b", MinCount: 1, Within: "1m"},
				},
			},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first cycle failed: %v", err)
	}
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second cycle failed: %v", err)
	}

	if len(logCounts) != 2 {
		t.Fatalf("expected two correlate calls, got %d", len(logCounts))
	}
	if logCounts[0] != 1 {
		t.Fatalf("expected first cycle to correlate 1 log, got %d", logCounts[0])
	}
	if logCounts[1] != 2 {
		t.Fatalf("expected second cycle to correlate full Redis payload of 2 logs, got %d", logCounts[1])
	}
}

func TestProcessorPropagatesFetcherErrorContext(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
	}
	cfg := baseTestConfig()

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher: LogFetcherFunc(func(context.Context, string) (*models.FullLog, error) {
			return nil, errors.New("boom")
		}),
		Engine: CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			if len(logs) == 0 {
				return nil, nil
			}
			return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
		}),
		Rules:  &testRules{rules: []models.Rule{{ID: "rule-1", OrganizationID: "org-1"}}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("expected cycle to continue despite fetch error, got %v", err)
	}
}

type LogFetcherFunc func(ctx context.Context, docID string) (*models.FullLog, error)

func (fn LogFetcherFunc) FetchLog(ctx context.Context, docID string) (*models.FullLog, error) {
	return fn(ctx, docID)
}

func TestProcessorDistributedIngestsSignalStreamIntoOrgPayloadAndPrefetchesFullLogs(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		streamEvents: []models.SignalStreamEvent{
			{
				OrganizationID: "org-1",
				HostIdentity:   "10.0.0.1",
				DocID:          "doc-1",
				Signal:         "signal-a",
				LogLevel:       "warning",
				TimeStamp:      base,
			},
			{
				OrganizationID: "org-1",
				HostIdentity:   "10.0.0.2",
				DocID:          "doc-2",
				Signal:         "signal-b",
				LogLevel:       "error",
				TimeStamp:      base.Add(time.Second),
			},
		},
		loadCalls: make(map[string]int),
	}

	cfg := baseTestConfig()
	cfg.Redis.SignalStreamEnabled = true
	cfg.Redis.SignalStreamKey = "Rca:signalized_log_events"
	cfg.Redis.SignalStreamBatchSize = 1000
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10

	fetcher := &batchTestFetcher{}
	engineCalls := 0
	var correlatedLogCount int
	engine := CorrelatorFunc(func(_ context.Context, _ string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		engineCalls++
		correlatedLogCount = len(logs)
		return nil, nil
	})

	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     fetcher,
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", GroupBy: []string{"event.organization", "host.identity"}, Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("distributed cycle failed: %v", err)
	}

	if len(store.ackedStreamGroups["rca-correlation"]) != 2 {
		t.Fatalf("expected two acked stream ids, got %#v", store.ackedStreamGroups)
	}
	gotPayload := store.logBatches["org-1"]
	if len(gotPayload) != 1 || len(gotPayload[0]) != 2 {
		t.Fatalf("expected org-wide payload with 2 signals, got %#v", gotPayload)
	}
	if gotPayload[0][0].DocID != "doc-1" || gotPayload[0][1].DocID != "doc-2" {
		t.Fatalf("unexpected distributed org payload ordering: %#v", gotPayload[0])
	}
	if engineCalls != 1 {
		t.Fatalf("expected one correlation call per claimed organization, got %d", engineCalls)
	}
	if correlatedLogCount != 2 {
		t.Fatalf("expected one org-wide correlate call with 2 logs, got %d", correlatedLogCount)
	}
	if fetcher.batchCalls != 1 {
		t.Fatalf("expected exactly one batch fetch during distributed prefetch, got %d", fetcher.batchCalls)
	}
	if len(store.fullLogCache) != 2 || store.fullLogCache["doc-1"] == nil || store.fullLogCache["doc-2"] == nil {
		t.Fatalf("expected prefetched full logs to be cached, got %#v", store.fullLogCache)
	}
}

func TestProcessorDistributedUsesSharedFullLogCacheBeforeFetcher(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
		fullLogCache: map[string]*models.FullLog{
			"doc-1": {
				DocID:     "doc-1",
				Timestamp: base,
				LogLevel:  "warning",
				Signal:    "signal-a",
				Metadata:  map[string]any{"cached": true},
			},
		},
	}

	cfg := baseTestConfig()
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10

	fetchCalls := 0
	engineCalls := 0
	var correlatedDocIDs []string
	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher: LogFetcherFunc(func(_ context.Context, _ string) (*models.FullLog, error) {
			fetchCalls++
			return nil, errors.New("fetcher should not run when cache is warm")
		}),
		Engine: CorrelatorFunc(func(_ context.Context, _ string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			engineCalls++
			correlatedDocIDs = correlatedDocIDs[:0]
			for _, log := range logs {
				correlatedDocIDs = append(correlatedDocIDs, log.DocID)
			}
			return nil, nil
		}),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", GroupBy: []string{"event.organization", "host.identity"}, Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("distributed cache-backed cycle failed: %v", err)
	}
	if fetchCalls != 0 {
		t.Fatalf("expected zero fetcher calls with shared cache hit, got %d", fetchCalls)
	}
	if engineCalls != 1 {
		t.Fatalf("expected one correlation call, got %d", engineCalls)
	}
	if got := strings.Join(correlatedDocIDs, ","); got != "doc-1" {
		t.Fatalf("expected cached full log doc-1, got %s", got)
	}
}

func TestProcessorDistributedSkipsAlreadyLeasedOrganizations(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1", "org-2"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
			"org-2": {
				{
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
				},
			},
		},
		leases: map[string]string{
			distributed.OrganizationWorkload("org-2").LeaseKey(): "other-worker",
		},
	}

	cfg := baseTestConfig()
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10

	engineCalls := make(map[string]int)
	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine: CorrelatorFunc(func(_ context.Context, orgID string, _ []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			engineCalls[orgID]++
			return nil, nil
		}),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
			{ID: "rule-2", OrganizationID: "org-2", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("distributed org lease cycle failed: %v", err)
	}

	if engineCalls["org-1"] != 1 {
		t.Fatalf("expected org-1 to be processed once, got %d", engineCalls["org-1"])
	}
	if engineCalls["org-2"] != 0 {
		t.Fatalf("expected org-2 to be skipped because another worker owns the lease, got %d", engineCalls["org-2"])
	}
	if got := store.leases[distributed.OrganizationWorkload("org-2").LeaseKey()]; got != "other-worker" {
		t.Fatalf("expected existing org-2 lease to remain untouched, got %q", got)
	}
}

func TestProcessorDistributedRegistersWorkerAndCompletesRunContract(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
	}

	cfg := baseTestConfig()
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10

	writer := &testWriter{}
	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine: CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
		}),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})
	processor.now = func() time.Time {
		return base
	}

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("distributed cycle failed: %v", err)
	}

	workerHeartbeat, ok := store.workerHeartbeats[processor.workerID]
	if !ok {
		t.Fatalf("expected worker heartbeat for %q, got %#v", processor.workerID, store.workerHeartbeats)
	}
	if !workerHeartbeat.UpdatedAt.Equal(base) {
		t.Fatalf("expected worker heartbeat time %s, got %s", base, workerHeartbeat.UpdatedAt)
	}
	if len(store.runRecords) != 1 {
		t.Fatalf("expected one workload run record, got %#v", store.runRecords)
	}
	if len(store.finalizationClaims) != 1 {
		t.Fatalf("expected one workload run finalization claim, got %#v", store.finalizationClaims)
	}

	for runKey, run := range store.runRecords {
		if got := store.runStatuses[runKey]; got != distributed.ShardStateCompleted {
			t.Fatalf("expected completed run status for %s, got %s", runKey, got)
		}
		if got := store.runMessages[runKey]; got != "" {
			t.Fatalf("expected empty completed run message for %s, got %q", runKey, got)
		}
		rootShard, ok := store.shardContracts[shardStoreKey(distributed.RootShardContract(run))]
		if !ok {
			t.Fatalf("expected root shard contract for run %s, got %#v", runKey, store.shardContracts)
		}
		if rootShard.State != distributed.ShardStateCompleted {
			t.Fatalf("expected completed root shard state for %s, got %s", runKey, rootShard.State)
		}
	}
	if len(writer.results) != 1 || writer.results[0].Status != "open" {
		t.Fatalf("expected one open RCA write, got %#v", writer.results)
	}
}

func TestProcessorDistributedRunFinalizationBlocksCommit(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
				},
			},
		},
		denyRunFinalization: true,
	}

	cfg := baseTestConfig()
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10

	writer := &testWriter{}
	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine: CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
		}),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})
	processor.now = func() time.Time {
		return base
	}

	err := processor.RunCycle(context.Background())
	if err == nil {
		t.Fatalf("expected distributed cycle to fail when run finalization is denied")
	}
	if !strings.Contains(err.Error(), "finalization") {
		t.Fatalf("expected finalization ownership error, got %v", err)
	}
	if len(writer.results) != 0 {
		t.Fatalf("expected no RCA writes when finalization is denied, got %#v", writer.results)
	}
	if len(store.incidents) != 0 {
		t.Fatalf("expected no incident state writes when finalization is denied, got %#v", store.incidents)
	}
	if _, ok := store.checkpoints["organization:org-1"]; ok {
		t.Fatalf("expected no checkpoint save when finalization is denied, got %#v", store.checkpoints["organization:org-1"])
	}
	if len(store.runRecords) != 1 {
		t.Fatalf("expected one workload run record, got %#v", store.runRecords)
	}
	for runKey, run := range store.runRecords {
		if got := store.runStatuses[runKey]; got != distributed.ShardStateFailed {
			t.Fatalf("expected failed run status for %s, got %s", runKey, got)
		}
		if got := store.runMessages[runKey]; !strings.Contains(got, "finalization") {
			t.Fatalf("expected failed run message to mention finalization for %s, got %q", runKey, got)
		}
		rootShard, ok := store.shardContracts[shardStoreKey(distributed.RootShardContract(run))]
		if !ok {
			t.Fatalf("expected root shard contract for failed run %s", runKey)
		}
		if rootShard.State != distributed.ShardStateFailed {
			t.Fatalf("expected failed root shard state for %s, got %s", runKey, rootShard.State)
		}
	}
}

func TestProcessorDistributedShardCorrelationUsesHelperWorker(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
					{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base.Add(2 * time.Second)},
					{Signal: "signal-d", LogLevel: "critical", DocID: "doc-4", TimeStamp: base.Add(3 * time.Second)},
				},
			},
		},
		workerHeartbeats: map[string]distributed.WorkerHeartbeat{
			"owner-worker":  {WorkerID: "owner-worker", UpdatedAt: base},
			"helper-worker": {WorkerID: "helper-worker", UpdatedAt: base},
		},
	}

	cfg := baseTestConfig()
	cfg.Distributed.Enabled = true
	cfg.Distributed.StreamConsumerGroup = "rca-correlation"
	cfg.Distributed.LeaseTTL = 45 * time.Second
	cfg.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	cfg.Distributed.ClaimLimitPerCycle = 10
	cfg.Engine.ParallelCorrelation.Enabled = true
	cfg.Engine.ParallelCorrelation.MinLogs = 3
	cfg.Engine.ParallelCorrelation.TargetLogsPerShard = 2
	cfg.Engine.ParallelCorrelation.MaxWorkers = 4

	var (
		mu          sync.Mutex
		callsByProc = make(map[string]int)
	)
	newEngine := func(name string, delay time.Duration) CorrelatorFunc {
		return func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
			time.Sleep(delay)
			mu.Lock()
			callsByProc[name]++
			mu.Unlock()
			return []models.CorrelationResult{resultFromLogs(orgID, "rule-1", logs)}, nil
		}
	}

	ownerWriter := &testWriter{}
	owner := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      newEngine("owner", 80*time.Millisecond),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: ownerWriter,
		Logger: slog.Default(),
	})
	owner.workerID = "owner-worker"
	owner.consumer = "owner-worker"
	owner.now = func() time.Time { return base }

	helper := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      newEngine("helper", 10*time.Millisecond),
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: &testWriter{},
		Logger: slog.Default(),
	})
	helper.workerID = "helper-worker"
	helper.consumer = "helper-worker"
	helper.now = func() time.Time { return base }

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	helperDone := make(chan error, 1)
	go func() {
		_, err := helper.assistDistributedShardWork(ctx)
		helperDone <- err
	}()

	if err := owner.RunCycle(ctx); err != nil {
		t.Fatalf("distributed owner cycle failed: %v", err)
	}
	if err := <-helperDone; err != nil && !errors.Is(err, context.DeadlineExceeded) && !errors.Is(err, context.Canceled) {
		t.Fatalf("distributed helper assist failed: %v", err)
	}

	if len(ownerWriter.results) != 1 {
		t.Fatalf("expected one final RCA write from owner, got %#v", ownerWriter.results)
	}
	if ownerWriter.results[0].Status != "open" {
		t.Fatalf("expected owner to write open RCA result, got %#v", ownerWriter.results[0])
	}
	mu.Lock()
	ownerCalls := callsByProc["owner"]
	helperCalls := callsByProc["helper"]
	mu.Unlock()
	if ownerCalls == 0 {
		t.Fatalf("expected owner worker to process at least one shard, got %d", ownerCalls)
	}
	if helperCalls == 0 {
		t.Fatalf("expected helper worker to process at least one shard, got %d", helperCalls)
	}
	if len(store.shardResults) < 2 {
		t.Fatalf("expected completed distributed shard results, got %#v", store.shardResults)
	}
	workersSeen := make(map[string]struct{})
	for _, result := range store.shardResults {
		if strings.HasPrefix(result.ShardID, "incremental_live-") {
			workersSeen[result.WorkerID] = struct{}{}
		}
	}
	if len(workersSeen) < 2 {
		t.Fatalf("expected incremental distributed shards to be completed by both workers, got %#v", workersSeen)
	}
}

func TestBuildCorrelationShardsKeepsEqualTimestampsTogether(t *testing.T) {
	base := time.Now().UTC()
	logs := []models.FullLog{
		{DocID: "doc-1", Timestamp: base},
		{DocID: "doc-2", Timestamp: base},
		{DocID: "doc-3", Timestamp: base},
		{DocID: "doc-4", Timestamp: base.Add(time.Second)},
	}

	shards := buildCorrelationShards(logs, 2, time.Minute)
	if len(shards) != 2 {
		t.Fatalf("expected 2 shards, got %d", len(shards))
	}
	if len(shards[0].logs) != 3 {
		t.Fatalf("expected first shard to keep same-timestamp logs together, got %d logs", len(shards[0].logs))
	}
	if shards[0].primaryEnd != base {
		t.Fatalf("expected first shard primary end at %s, got %s", base, shards[0].primaryEnd)
	}
	if shards[1].primaryStart != base.Add(time.Second) {
		t.Fatalf("expected second shard primary start at %s, got %s", base.Add(time.Second), shards[1].primaryStart)
	}
}

func TestProcessorParallelCorrelationUsesOverlappedShardsForCrossBoundaryMatch(t *testing.T) {
	base := time.Now().UTC()
	store := &testStore{
		organizations: []string{"org-1"},
		loadCalls:     make(map[string]int),
		logBatches: map[string][][]models.SignalLog{
			"org-1": {
				{
					{Signal: "signal-a", LogLevel: "warning", DocID: "doc-1", TimeStamp: base},
					{Signal: "signal-b", LogLevel: "error", DocID: "doc-2", TimeStamp: base.Add(time.Second)},
					{Signal: "signal-c", LogLevel: "error", DocID: "doc-3", TimeStamp: base.Add(2 * time.Second)},
					{Signal: "signal-d", LogLevel: "critical", DocID: "doc-4", TimeStamp: base.Add(3 * time.Second)},
				},
			},
		},
	}

	cfg := baseTestConfig()
	cfg.Engine.ParallelCorrelation.Enabled = true
	cfg.Engine.ParallelCorrelation.MinLogs = 3
	cfg.Engine.ParallelCorrelation.TargetLogsPerShard = 2
	cfg.Engine.ParallelCorrelation.MaxWorkers = 4

	var (
		mu               sync.Mutex
		engineCalls      int
		observedShardLen []int
	)
	engine := CorrelatorFunc(func(_ context.Context, orgID string, logs []models.FullLog, _ []models.Rule) ([]models.CorrelationResult, error) {
		mu.Lock()
		engineCalls++
		observedShardLen = append(observedShardLen, len(logs))
		mu.Unlock()

		var left *models.FullLog
		var right *models.FullLog
		for idx := range logs {
			switch logs[idx].DocID {
			case "doc-2":
				cloned := logs[idx]
				left = &cloned
			case "doc-3":
				cloned := logs[idx]
				right = &cloned
			}
		}
		if left == nil || right == nil {
			return nil, nil
		}

		result := resultFromLogs(orgID, "rule-1", []models.FullLog{*left, *right})
		result.MatchedAt = right.Timestamp.UTC()
		return []models.CorrelationResult{result}, nil
	})

	writer := &testWriter{}
	processor := NewProcessor(Dependencies{
		Config:      cfg,
		Store:       store,
		Checkpoints: store,
		Fetcher:     &testFetcher{},
		Engine:      engine,
		Rules: &testRules{rules: []models.Rule{
			{ID: "rule-1", OrganizationID: "org-1", Window: "10m", MaxGapBetweenSteps: "5m"},
		}},
		Writer: writer,
		Logger: slog.Default(),
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("parallel correlation cycle failed: %v", err)
	}

	if engineCalls != 2 {
		t.Fatalf("expected 2 shard correlation calls, got %d", engineCalls)
	}
	if len(observedShardLen) != 2 {
		t.Fatalf("expected 2 observed shard sizes, got %#v", observedShardLen)
	}
	sawPrimaryOnly := false
	sawOverlapped := false
	for _, size := range observedShardLen {
		if size == 2 {
			sawPrimaryOnly = true
		}
		if size == 4 {
			sawOverlapped = true
		}
	}
	if !sawPrimaryOnly || !sawOverlapped {
		t.Fatalf("expected shard sizes to include 2 and 4 logs, got %#v", observedShardLen)
	}
	if len(writer.results) != 1 {
		t.Fatalf("expected exactly one RCA write from cross-boundary match, got %#v", writer.results)
	}
	if writer.results[0].Status != "open" {
		t.Fatalf("expected one open RCA write, got %#v", writer.results[0])
	}
	if len(writer.results[0].LogID) != 2 {
		t.Fatalf("expected RCA to contain the two matched boundary logs, got %#v", writer.results[0].LogID)
	}
}
