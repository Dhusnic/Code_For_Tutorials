// Package service provides the core collection logic that fetches, normalizes, deduplicates,
// and stores signal logs in Redis with retention policy enforcement.
//
// Collection Pipeline (8 Steps per Cycle):
//  1. Calculate: Time window (now - config.window) and retention cutoff (now - config.retention_window)
//  2. Lock: Acquire distributed lock if enabled (multi-worker safety)
//  3. Fetch: Query Elasticsearch for documents with signal field using sliding window
//  4. Normalize: Map Elasticsearch documents to SignalLog records with organization metadata
//  5. Deduplicate: Merge with existing Redis logs, removing duplicates by doc_id
//  6. Retain: Filter out logs older than retention cutoff time
//  7. Sort: Order logs by timestamp then doc_id for predictable output
//  8. Store: Save to Redis or delete if empty, release lock, log completion
//
// Log Deduplication Strategy:
//   - Keyed by doc_id (Elasticsearch document ID)
//   - For duplicates: Keep newest by timestamp
//   - On timestamp tie: Prefer more complete record (more fields filled)
//   - Within organization hash, stored as JSON array field
//
// Thread Safety:
//   - Distributed locking prevents concurrent cycles in multi-worker PM2 deployments
//   - Each cycle is isolated (reads existing, merges, writes new)
//   - Lock TTL must be >= RunTimeout + safety margin
package service

import (
	"context"
	"fmt"
	"hash/fnv"
	"log/slog"
	"sort"
	"sync"
	"time"

	"log_signal_processor/internal/config"
	"log_signal_processor/internal/elasticsearch"
	"log_signal_processor/internal/model"
	"log_signal_processor/internal/util"
)

// SourceRepository fetches raw signal-bearing Elasticsearch documents within a time window.
//
// Implementation: elasticsearch.Repository wraps elasticsearch-go v8 client.
// Typically used with Point-in-Time for stable pagination across multiple pages.
//
// Responsibility:
//   - Apply field mappings from config during search
//   - Use sliding time window for efficient incremental collection
//   - Return DocumentHit structs with Source data intact for mapping
//
// Errors:
//   - Connection failures, Elasticsearch errors, timeout, parse errors
type SourceRepository interface {
	SearchSignalDocuments(ctx context.Context, windowStart time.Time, windowEnd time.Time) ([]elasticsearch.DocumentHit, error)
}

// OrganizationStore persists and retrieves signal logs from Redis in organization-scoped hashes.
//
// Implementation: redisstore.Client wraps go-redis/v9 connection.
// Storage format: Redis HASH at key="{KeyPrefix}:{organization}", field="signaled_logs" (JSON array)
//
// Responsibility:
//   - Enumerate existing organizations in Redis
//   - Load/save/delete signal log collections per organization
//   - Maintain consistency within organization boundary
//
// Atomicity:
//   - Each organization load/save is separate Redis operation
//   - No cross-organization consistency guarantees within single cycle
//
// Errors:
//   - Redis connection failures, timeout, permission errors
type OrganizationStore interface {
	ListOrganizations(ctx context.Context) ([]string, error)
	LoadLogs(ctx context.Context, organization string) ([]model.SignalLog, error)
	SaveLogs(ctx context.Context, organization string, logs []model.SignalLog) error
	DeleteLogs(ctx context.Context, organization string) error
}

// ReleaseFunc safely releases a previously acquired lock within a given context.
// Called by collector after cycle completion to return lock to other workers.
//
// Parameters:
//   - ctx: Context for operation (typically short timeout ~5s)
//
// Returns:
//   - bool: Whether lock was successfully released (false if ownership changed or expired)
//   - error: Operation error (connection, timeout, etc.)
type ReleaseFunc func(ctx context.Context) (bool, error)

// AcquireLockFunc attempts to acquire the cycle lock for this worker with a timeout.
// Returns immediately with acquired=false if lock held by another worker.
// Returns ReleaseFunc to unlock after cycle completion.
//
// Parameters:
//   - ctx: Context for lock acquisition attempt (typically ~2s timeout per config)
//
// Returns:
//   - ReleaseFunc: Function to call for lock cleanup (only if acquired=true)
//   - bool: Whether lock was successfully acquired (false = another worker holds lock)
//   - error: Operation error (connection, timeout, etc.)
//
// Behavior:
//   - Blocks up to timeout waiting for lock availability
//   - Returns immediately if already held (acquired=false, err=nil)
//   - Sets lock TTL = configuration value (default 90s)
type AcquireLockFunc func(ctx context.Context) (ReleaseFunc, bool, error)

// ShardLease describes the shard locks this worker owns for the current cycle.
// The collector uses the shard count and owned shard IDs to filter organizations
// so different PM2 instances can persist disjoint org subsets in parallel.
type ShardLease struct {
	ShardCount  int
	OwnedShards []int
	Release     ReleaseFunc
}

// AcquireShardLeaseFunc attempts to acquire the shard locks assigned to this worker.
// Returns acquired=false when no shard locks were obtained for this cycle.
type AcquireShardLeaseFunc func(ctx context.Context) (ShardLease, bool, error)

// Dependencies groups the collector's required dependencies for injection.
//
// Fields:
//   - Config: Application configuration with all settings for this cycle
//   - Source: Elasticsearch repository for document fetching
//   - Store: Redis store for persisting signals per organization
//   - AcquireLock: Lock function (nil = locking disabled, single worker mode)
//   - AcquireShardLease: Shard-aware lock function (preferred when shard_count > 1)
//   - Logger: slog.Logger for operational logging
type Dependencies struct {
	Config            config.Config
	Source            SourceRepository
	Store             OrganizationStore
	AcquireLock       AcquireLockFunc
	AcquireShardLease AcquireShardLeaseFunc
	Logger            *slog.Logger
}

// Collector fetches signal logs from Elasticsearch, merges with existing ones in Redis,
// applies retention policy, deduplicates by doc_id, and stores results back to Redis.
//
// Lifecycle:
//   - Created once at startup via NewCollector()
//   - RunCycle() called repeatedly by scheduler
//   - Thread-safe only when distributed lock enabled
//
// Logging:
//   - INFO: Cycle completion summary with metrics
//   - WARN: Document normalization failures, lock issues
//   - DEBUG: (Delegated to dependencies for operation details)
//
// Internal Fields:
//   - now: Time function (mockable for testing)
type Collector struct {
	config       config.Config
	source       SourceRepository
	store        OrganizationStore
	acquireLock  AcquireLockFunc
	acquireShard AcquireShardLeaseFunc
	logger       *slog.Logger
	now          func() time.Time
}

type organizationPersistenceOutcome struct {
	updated   int
	deleted   int
	unchanged int
	err       error
}

// NewCollector builds a signal log collector with injected dependencies.
//
// Parameters:
//   - deps: Dependencies structure containing all required components
//
// Returns:
//   - *Collector: Ready-to-use collector
//
// Logging:
//   - Adds "component": "collector" to all logger messages
//   - Delegates timestamp/debug logging to sub-components
//
// Example:
//
//	collector := NewCollector(Dependencies{
//	    Config: cfg,
//	    Source: esRepo,
//	    Store: redisStore,
//	    AcquireLock: lockFunc,
//	    Logger: logger,
//	})
func NewCollector(deps Dependencies) *Collector {
	return &Collector{
		config:       deps.Config,
		source:       deps.Source,
		store:        deps.Store,
		acquireLock:  deps.AcquireLock,
		acquireShard: deps.AcquireShardLease,
		logger:       deps.Logger.With("component", "collector"),
		now:          time.Now,
	}
}

// RunCycle executes one complete fetch -> normalize -> merge -> retain -> store cycle (8 steps).
//
// Step-by-step Execution:
//  1. Calculate: Determine query window (now - config.window) and retention cutoff time
//  2. Lock: Acquire distributed lock if enabled; return early if locked by another worker
//  3. Fetch: Query Elasticsearch for signals within time window
//  4. Normalize: Map fetched documents to SignalRecord with organization and log details
//  5. Group: Organize records by organization for Redis storage
//  6. Load: Read existing logs from Redis for all relevant organizations
//  7. Merge: Combine existing + new, deduplicate by doc_id, apply retention cutoff
//  8. Store: Save merged logs to Redis (or delete if empty), release lock, log completion
//
// Parameters:
//   - ctx: Context for all operations (should have timeout set by scheduler)
//
// Returns:
//   - error: Any step failure (Elasticsearch, Redis, mapping, lock errors)
//
// Logging (INFO level):
//   - window_start: Start of query window in RFC3339Nano format
//   - window_end: End of query window (current time)
//   - fetched_documents: Count of Elasticsearch documents retrieved
//   - normalized_records: Count of successfully mapped records
//   - skipped_documents: Count of documents failed mapping (logged as WARN individually)
//   - organizations_updated: Count of organizations with saved data
//   - organizations_deleted: Count of organizations with empty result (deleted from Redis)
//
// Lock Behavior:
//   - If lock acquisition fails: Returns nil immediately (another worker is running)
//   - If lock is held: Releases before returning (even on error)
//
// Error Handling:
//   - Wraps all errors with operation context
//   - Continues processing even if individual document mapping fails
//   - Stops immediately if Elasticsearch/Redis operations fail
//
// Example Output Log:
//
//	INFO collector cycle completed window_start="2024-01-15T10:00:00Z" window_end="2024-01-15T10:01:00Z"
//	     fetched_documents=1500 normalized_records=1420 skipped_documents=80
//	     organizations_updated=12 organizations_deleted=2
func (c *Collector) RunCycle(ctx context.Context) error {
	now := c.now().UTC()
	windowStart := now.Add(-c.config.Elasticsearch.Window)
	retentionCutoff := now.Add(-c.config.Redis.RetentionWindow)

	var releaseLock ReleaseFunc
	shardCount := 0
	var ownedShards []int
	if c.acquireShard != nil {
		lease, acquired, err := c.acquireShard(ctx)
		if err != nil {
			return err
		}
		if !acquired {
			return nil
		}
		releaseLock = lease.Release
		shardCount = lease.ShardCount
		ownedShards = append([]int(nil), lease.OwnedShards...)
		if releaseLock != nil {
			defer c.releaseLock(releaseLock)
		}
	} else if c.acquireLock != nil {
		var acquired bool
		var err error
		releaseLock, acquired, err = c.acquireLock(ctx)
		if err != nil {
			return err
		}
		if !acquired {
			return nil
		}
		if releaseLock != nil {
			defer c.releaseLock(releaseLock)
		}
	}

	documents, err := c.source.SearchSignalDocuments(ctx, windowStart, now)
	if err != nil {
		return fmt.Errorf("search signal documents: %w", err)
	}

	records := make([]model.SignalRecord, 0, len(documents))
	skipped := 0
	for _, document := range documents {
		record, err := MapDocument(document, c.config.Mappings)
		if err != nil {
			skipped++
			c.logger.Warn("skipping document with missing or invalid fields", "doc_id", document.ID, "error", err)
			continue
		}
		records = append(records, record)
	}

	grouped := GroupByOrganization(records)
	organizations, err := c.store.ListOrganizations(ctx)
	if err != nil {
		return fmt.Errorf("list redis organizations: %w", err)
	}

	orgSet := make(map[string]struct{}, len(organizations)+len(grouped))
	for _, organization := range organizations {
		orgSet[organization] = struct{}{}
	}
	for organization := range grouped {
		orgSet[organization] = struct{}{}
	}

	organizationList := make([]string, 0, len(orgSet))
	for organization := range orgSet {
		organizationList = append(organizationList, organization)
	}
	sort.Strings(organizationList)

	if shardCount > 1 {
		organizationList = filterOrganizationsByShard(organizationList, shardCount, ownedShards)
	}
	if len(organizationList) == 0 {
		c.logger.Info(
			"collector cycle completed",
			"window_start", windowStart.Format(time.RFC3339Nano),
			"window_end", now.Format(time.RFC3339Nano),
			"organization_workers", 0,
			"shard_count", shardCount,
			"owned_shards", ownedShards,
			"fetched_documents", len(documents),
			"normalized_records", len(records),
			"skipped_documents", skipped,
			"organizations_updated", 0,
			"organizations_deleted", 0,
			"organizations_unchanged", 0,
			"organizations_assigned", 0,
		)
		return nil
	}

	workerCount := c.config.Scheduler.OrganizationWorkers
	if workerCount > len(organizationList) {
		workerCount = len(organizationList)
	}
	if workerCount <= 0 {
		workerCount = 1
	}

	jobs := make(chan string, len(organizationList))
	outcomes := make(chan organizationPersistenceOutcome, len(organizationList))
	for _, organization := range organizationList {
		jobs <- organization
	}
	close(jobs)

	var wg sync.WaitGroup
	for workerID := 0; workerID < workerCount; workerID++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for organization := range jobs {
				outcomes <- c.persistOrganization(ctx, organization, grouped[organization], retentionCutoff)
			}
		}()
	}

	wg.Wait()
	close(outcomes)

	updated := 0
	deleted := 0
	unchanged := 0
	var firstErr error
	for outcome := range outcomes {
		updated += outcome.updated
		deleted += outcome.deleted
		unchanged += outcome.unchanged
		if outcome.err != nil && firstErr == nil {
			firstErr = outcome.err
		}
	}
	if firstErr != nil {
		return firstErr
	}

	c.logger.Info(
		"collector cycle completed",
		"window_start", windowStart.Format(time.RFC3339Nano),
		"window_end", now.Format(time.RFC3339Nano),
		"organization_workers", workerCount,
		"shard_count", shardCount,
		"owned_shards", ownedShards,
		"fetched_documents", len(documents),
		"normalized_records", len(records),
		"skipped_documents", skipped,
		"organizations_updated", updated,
		"organizations_deleted", deleted,
		"organizations_unchanged", unchanged,
		"organizations_assigned", len(organizationList),
	)
	return nil
}

func (c *Collector) persistOrganization(
	ctx context.Context,
	organization string,
	incoming []model.SignalLog,
	retentionCutoff time.Time,
) organizationPersistenceOutcome {
	existingLogs, err := c.store.LoadLogs(ctx, organization)
	if err != nil {
		return organizationPersistenceOutcome{
			err: fmt.Errorf("load redis logs for organization %s: %w", organization, err),
		}
	}

	merged := MergeLogs(existingLogs, incoming, retentionCutoff)
	if len(merged) == 0 {
		if err := c.store.DeleteLogs(ctx, organization); err != nil {
			return organizationPersistenceOutcome{
				err: fmt.Errorf("delete redis logs for organization %s: %w", organization, err),
			}
		}
		return organizationPersistenceOutcome{deleted: 1}
	}
	if signalLogsEqual(existingLogs, merged) {
		return organizationPersistenceOutcome{unchanged: 1}
	}

	if err := c.store.SaveLogs(ctx, organization, merged); err != nil {
		return organizationPersistenceOutcome{
			err: fmt.Errorf("save redis logs for organization %s: %w", organization, err),
		}
	}
	return organizationPersistenceOutcome{updated: 1}
}

// releaseLock safely releases the distributed lock acquired for this cycle.
// Handles lock ownership/expiry scenarios gracefully.
//
// Behavior:
//   - Creates short timeout context (~5s) for release operation
//   - Logs WARN if release fails (connection error, timeout)
//   - Logs WARN if lock ownership changed (another worker acquired it)
//   - Logs INFO on successful release
//   - Never returns error (logging only)
//
// Parameters:
//   - release: ReleaseFunc returned from AcquireLock
func (c *Collector) releaseLock(release ReleaseFunc) {
	releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	released, err := release(releaseCtx)
	if err != nil {
		c.logger.Warn("failed to release collector lock", "error", err)
		return
	}
	if !released {
		c.logger.Warn("collector lock was not released because ownership changed or expired")
		return
	}
	c.logger.Info("collector cycle lock released")
}

// MapDocument normalizes one Elasticsearch hit into an organization-scoped SignalRecord.
//
// Mapping Process (5 sub-steps):
//  1. Extract organization field from Elasticsearch source using dot-notation (e.g., "event.organization")
//  2. Extract signal field (e.g., "signal") - required, error if missing/empty
//  3. Extract timestamp field (e.g., "@timestamp") - must be RFC3339Nano parseable
//  4. Extract optional log_level field (e.g., "log_level") - silently skipped if missing
//  5. Resolve doc_id using DocIDSource (either _id or field-based)
//
// Field Mapping:
//   - Uses config.FieldMappings for all field names
//   - Supports dot-notation paths (e.g., "event.organization" → source.event.organization)
//   - Extracts values using util.LookupPath for nested access
//
// Error Cases (returns non-nil error):
//   - Missing organization field
//   - Empty organization string
//   - Missing signal field
//   - Empty signal string
//   - Missing timestamp field
//   - Unparseable timestamp
//   - Missing/invalid doc_id (depends on DocIDSource config)
//
// Parameters:
//   - hit: Elasticsearch document hit with ID and nested Source object
//   - mappings: Field mapping configuration from config.FieldMappings
//
// Returns:
//   - SignalRecord: Normalized record containing organization and SignalLog
//   - error: Mapping error with field name and reason
//
// Example:
//
//	record, err := MapDocument(esHit, config.FieldMappings{
//	    OrganizationField: "event.organization",
//	    SignalField: "signal",
//	    LogLevelField: "log_level",
//	    TimestampField: "@timestamp",
//	    DocIDSource: "_id",
//	})
//	// Result: {organization: "acme", log: {signal: "auth_failed", timestamp: "2024-01-15T10:00:00Z"}}
func MapDocument(hit elasticsearch.DocumentHit, mappings config.FieldMappings) (model.SignalRecord, error) {
	organizationValue, ok := util.LookupPath(hit.Source, mappings.OrganizationField)
	if !ok {
		return model.SignalRecord{}, fmt.Errorf("missing organization field %q", mappings.OrganizationField)
	}
	organization, ok := util.StringValue(organizationValue)
	if !ok || organization == "" {
		return model.SignalRecord{}, fmt.Errorf("empty organization field %q", mappings.OrganizationField)
	}

	signalValue, ok := util.LookupPath(hit.Source, mappings.SignalField)
	if !ok {
		return model.SignalRecord{}, fmt.Errorf("missing signal field %q", mappings.SignalField)
	}
	signal, ok := util.StringValue(signalValue)
	if !ok || signal == "" {
		return model.SignalRecord{}, fmt.Errorf("empty signal field %q", mappings.SignalField)
	}

	timestampValue, ok := util.LookupPath(hit.Source, mappings.TimestampField)
	if !ok {
		return model.SignalRecord{}, fmt.Errorf("missing timestamp field %q", mappings.TimestampField)
	}
	timestamp, err := util.ParseTimestamp(timestampValue)
	if err != nil {
		return model.SignalRecord{}, fmt.Errorf("parse timestamp field %q: %w", mappings.TimestampField, err)
	}

	logLevel := ""
	if mappings.LogLevelField != "" {
		if value, found := util.LookupPath(hit.Source, mappings.LogLevelField); found {
			if extracted, ok := util.StringValue(value); ok {
				logLevel = extracted
			}
		}
	}

	docID, err := resolveDocID(hit, mappings)
	if err != nil {
		return model.SignalRecord{}, err
	}

	return model.SignalRecord{
		Organization: organization,
		Log: model.SignalLog{
			Signal:    signal,
			LogLevel:  logLevel,
			DocID:     docID,
			TimeStamp: timestamp.UTC(),
		},
	}, nil
}

// resolveDocID determines the document identification value using configured strategy.
//
// Strategies:
//   - "_id" (docIDSourceDocumentID): Use Elasticsearch document _id directly
//   - "field" (docIDSourceField): Extract from configured document field using dot-notation
//
// Parameters:
//   - hit: Elasticsearch document hit
//   - mappings: Field mapping configuration with DocIDSource and DocIDField
//
// Returns:
//   - string: Resolved document ID
//   - error: If _id missing or field extraction fails
func resolveDocID(hit elasticsearch.DocumentHit, mappings config.FieldMappings) (string, error) {
	switch mappings.DocIDSource {
	case "_id":
		if hit.ID == "" {
			return "", fmt.Errorf("missing elasticsearch _id")
		}
		return hit.ID, nil
	case "field":
		value, ok := util.LookupPath(hit.Source, mappings.DocIDField)
		if !ok {
			return "", fmt.Errorf("missing doc id field %q", mappings.DocIDField)
		}
		docID, ok := util.StringValue(value)
		if !ok || docID == "" {
			return "", fmt.Errorf("empty doc id field %q", mappings.DocIDField)
		}
		return docID, nil
	default:
		return "", fmt.Errorf("unsupported doc id source %q", mappings.DocIDSource)
	}
}

// GroupByOrganization arranges normalized records into organization-keyed buckets.
// Creates the structure needed for per-organization Redis storage.
//
// Parameters:
//   - records: Slice of normalized SignalRecord structs with organization metadata
//
// Returns:
//   - map[string][]SignalLog: Records grouped by organization name
//
// Example:
//
//	Input: [
//	    {Organization: "acme", Log: {signal: "auth_failed", ...}},
//	    {Organization: "wile", Log: {signal: "timeout", ...}},
//	    {Organization: "acme", Log: {signal: "db_error", ...}},
//	]
//	Output: {
//	    "acme": [{signal: "auth_failed", ...}, {signal: "db_error", ...}],
//	    "wile": [{signal: "timeout", ...}],
//	}
func GroupByOrganization(records []model.SignalRecord) map[string][]model.SignalLog {
	grouped := make(map[string][]model.SignalLog)
	for _, record := range records {
		grouped[record.Organization] = append(grouped[record.Organization], record.Log)
	}
	return grouped
}

// MergeLogs combines existing and incoming logs with deduplication, retention filtering,
// and time-ordering. Critical operation for consistency.
//
// Deduplication Strategy:
//   - Key: doc_id (Elasticsearch document identifier)
//   - When duplicate doc_ids found:
//   - Keep record with newer timestamp
//   - On timestamp tie: Keep record with highest field completeness score
//   - Completeness measured by non-empty signal, log_level, and doc_id fields
//
// Retention Filtering:
//   - Records with timestamp < cutoff are discarded
//   - Prevents unbounded Redis storage growth
//   - Cutoff typically = now - config.retention_window (e.g., 30 minutes)
//
// Sorting:
//   - Primary: By timestamp (ascending - oldest first)
//   - Secondary: By doc_id (lexicographic)
//   - Ensures predictable, consistent output
//
// Parameters:
//   - existing: Current logs stored in Redis for this organization
//   - incoming: Newly fetched logs from Elasticsearch
//   - cutoff: Time threshold - records before this are dropped
//
// Returns:
//   - []SignalLog: Merged, deduplicated, retained, and sorted list
//
// Edge Cases:
//   - Empty existing/incoming return the other (filtered for retention)
//   - Records with zero docID or timestamp are silently dropped
//   - UTC normalization applied to all timestamps before comparison
//
// Example:
//
//	existing: [{docID: "1", timestamp: T1, signal: "a"}, {docID: "2", timestamp: T2, signal: "b"}]
//	incoming: [{docID: "1", timestamp: T1, signal: "a", logLevel: "ERROR"}, {docID: "3", timestamp: T3, signal: "c"}]
//	cutoff: T0 (earlier than all)
//	Result: [
//	    {docID: "1", timestamp: T1, signal: "a", logLevel: "ERROR"},  // Merged (more complete)
//	    {docID: "2", timestamp: T2, signal: "b"},
//	    {docID: "3", timestamp: T3, signal: "c"},
//	]
func MergeLogs(existing []model.SignalLog, incoming []model.SignalLog, cutoff time.Time) []model.SignalLog {
	deduped := make(map[string]model.SignalLog, len(existing)+len(incoming))

	combined := make([]model.SignalLog, 0, len(existing)+len(incoming))
	combined = append(combined, existing...)
	combined = append(combined, incoming...)

	for _, log := range combined {
		if log.DocID == "" || log.TimeStamp.IsZero() {
			continue
		}
		log.TimeStamp = log.TimeStamp.UTC()
		if log.TimeStamp.Before(cutoff.UTC()) {
			continue
		}

		current, exists := deduped[log.DocID]
		if !exists || shouldReplace(current, log) {
			deduped[log.DocID] = log
		}
	}

	merged := make([]model.SignalLog, 0, len(deduped))
	for _, log := range deduped {
		merged = append(merged, log)
	}

	sort.Slice(merged, func(i int, j int) bool {
		if merged[i].TimeStamp.Equal(merged[j].TimeStamp) {
			return merged[i].DocID < merged[j].DocID
		}
		return merged[i].TimeStamp.Before(merged[j].TimeStamp)
	})
	return merged
}

// shouldReplace determines whether a candidate log should replace an existing one during dedup.
// Prioritizes newer timestamps, uses completeness as tiebreaker.
//
// Replacement Logic:
//  1. If candidate timestamp > current timestamp: Replace (never keep older)
//  2. If candidate timestamp < current timestamp: Keep current (always prefer newer)
//  3. If timestamps equal: Use completeness score comparison
//     - Higher score wins (more fields populated = more complete record)
//     - Tie: Keep existing (stable approach)
//
// Parameters:
//   - current: Currently selected log for this doc_id
//   - candidate: New log being considered for this doc_id
//
// Returns:
//   - bool: True if candidate should replace current, false if current should stay
//
// Example:
//
//	shouldReplace(
//	    {timestamp: T1, signal: "a", logLevel: ""},        // Score: 1
//	    {timestamp: T1, signal: "a", logLevel: "ERROR"},   // Score: 2
//	) → true  // Candidate is more complete
func shouldReplace(current model.SignalLog, candidate model.SignalLog) bool {
	if candidate.TimeStamp.After(current.TimeStamp) {
		return true
	}
	if candidate.TimeStamp.Before(current.TimeStamp) {
		return false
	}
	return completenessScore(candidate) >= completenessScore(current)
}

// completenessScore rates how complete a signal log record is (0-3 range).
// Used as tiebreaker when dedup records have same timestamp.
//
// Scoring:
//   - +1 for non-empty signal
//   - +1 for non-empty log_level
//   - +1 for non-empty doc_id
//   - Maximum: 3 points
//
// Rationale:
//   - Signal is core business data (always +1 if present)
//   - LogLevel provides operational context
//   - DocID ensures uniqueness (technically always present after normalization, but checked for robustness)
//
// Parameters:
//   - log: Signal log to score
//
// Returns:
//   - int: Completeness score (0-3)
//
// Example:
//
//	completenessScore({signal: "auth_failed", logLevel: "WARN", docID: "123"}) → 3
//	completenessScore({signal: "timeout", logLevel: "", docID: "456"}) → 2
func completenessScore(log model.SignalLog) int {
	score := 0
	if log.Signal != "" {
		score++
	}
	if log.LogLevel != "" {
		score++
	}
	if log.DocID != "" {
		score++
	}
	return score
}

func signalLogsEqual(left []model.SignalLog, right []model.SignalLog) bool {
	if len(left) != len(right) {
		return false
	}
	for idx := range left {
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
	}
	return true
}

func organizationShard(organization string, shardCount int) int {
	if shardCount <= 1 {
		return 0
	}

	hasher := fnv.New32a()
	_, _ = hasher.Write([]byte(organization))
	return int(hasher.Sum32() % uint32(shardCount))
}

func filterOrganizationsByShard(organizations []string, shardCount int, ownedShards []int) []string {
	if shardCount <= 1 || len(organizations) == 0 {
		return append([]string(nil), organizations...)
	}
	if len(ownedShards) == 0 {
		return nil
	}

	owned := make(map[int]struct{}, len(ownedShards))
	for _, shardID := range ownedShards {
		if shardID < 0 || shardID >= shardCount {
			continue
		}
		owned[shardID] = struct{}{}
	}
	if len(owned) == 0 {
		return nil
	}

	filtered := make([]string, 0, len(organizations))
	for _, organization := range organizations {
		if _, ok := owned[organizationShard(organization, shardCount)]; ok {
			filtered = append(filtered, organization)
		}
	}
	return filtered
}
