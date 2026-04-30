package redis

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/models"

	goredis "github.com/redis/go-redis/v9"
)

const maxMergeSignalLogsRetries = 5

type workerRegistryPayload struct {
	WorkerID  string `json:"worker_id"`
	UpdatedAt string `json:"updated_at"`
}

type workloadRunPayload struct {
	WorkloadKey string `json:"workload_key"`
	RunID       string `json:"run_id"`
	Owner       string `json:"owner"`
	LeaseToken  string `json:"lease_token"`
	ShardID     string `json:"shard_id"`
	StartedAt   string `json:"started_at"`
	UpdatedAt   string `json:"updated_at"`
	Status      string `json:"status"`
	Message     string `json:"message,omitempty"`
}

type shardContractPayload struct {
	WorkloadKey string `json:"workload_key"`
	RunID       string `json:"run_id"`
	ShardID     string `json:"shard_id"`
	Mode        string `json:"mode"`
	Owner       string `json:"owner"`
	LeaseKey    string `json:"lease_key"`
	ResultKey   string `json:"result_key"`
	StateKey    string `json:"state_key"`
	LeaseToken  string `json:"lease_token"`
	State       string `json:"state"`
	Attempt     int    `json:"attempt"`
	Retryable   bool   `json:"retryable"`
	RetryAfter  string `json:"retry_after,omitempty"`
	UpdatedAt   string `json:"updated_at"`
	Message     string `json:"message,omitempty"`
}

func (s *Store) EnsureSignalStreamConsumerGroup(ctx context.Context, group string) error {
	if !s.signalStreamEnabled {
		return nil
	}
	err := s.client.XGroupCreateMkStream(ctx, s.signalStreamKey, strings.TrimSpace(group), "0-0").Err()
	if err == nil {
		return nil
	}
	if strings.Contains(strings.ToUpper(err.Error()), "BUSYGROUP") {
		return nil
	}
	return fmt.Errorf("ensure redis signal stream consumer group %s: %w", group, err)
}

func (s *Store) ReadSignalStreamConsumerGroup(
	ctx context.Context,
	group string,
	consumer string,
	minIdle time.Duration,
) ([]models.SignalStreamEvent, []string, error) {
	if !s.signalStreamEnabled {
		return nil, nil, nil
	}

	count := int64(s.signalStreamBatchSize)
	if count <= 0 {
		count = 1000
	}

	events := make([]models.SignalStreamEvent, 0, count)
	ids := make([]string, 0, count)

	appendMessages := func(messages []goredis.XMessage) error {
		for _, message := range messages {
			payloadRaw, ok := message.Values["payload"]
			if !ok {
				continue
			}
			payload := strings.TrimSpace(fmt.Sprint(payloadRaw))
			if payload == "" {
				continue
			}
			var event models.SignalStreamEvent
			if err := json.Unmarshal([]byte(payload), &event); err != nil {
				return fmt.Errorf("decode signal stream payload %s: %w", message.ID, err)
			}
			events = append(events, event)
			ids = append(ids, message.ID)
		}
		return nil
	}

	if minIdle > 0 {
		claimed, _, err := s.client.XAutoClaim(ctx, &goredis.XAutoClaimArgs{
			Stream:   s.signalStreamKey,
			Group:    strings.TrimSpace(group),
			Consumer: strings.TrimSpace(consumer),
			MinIdle:  minIdle,
			Start:    "0-0",
			Count:    count,
		}).Result()
		if err != nil && !errors.Is(err, goredis.Nil) {
			return nil, nil, fmt.Errorf("reclaim redis signal stream entries for group %s: %w", group, err)
		}
		if err := appendMessages(claimed); err != nil {
			return nil, nil, err
		}
	}

	remaining := count - int64(len(ids))
	if remaining <= 0 {
		return events, ids, nil
	}

	streams, err := s.client.XReadGroup(ctx, &goredis.XReadGroupArgs{
		Group:    strings.TrimSpace(group),
		Consumer: strings.TrimSpace(consumer),
		Streams:  []string{s.signalStreamKey, ">"},
		Count:    remaining,
		Block:    0,
	}).Result()
	if errors.Is(err, goredis.Nil) {
		return events, ids, nil
	}
	if err != nil {
		return nil, nil, fmt.Errorf("read redis signal stream group %s consumer %s: %w", group, consumer, err)
	}
	for _, stream := range streams {
		if err := appendMessages(stream.Messages); err != nil {
			return nil, nil, err
		}
	}
	return events, ids, nil
}

func (s *Store) AckSignalStream(ctx context.Context, group string, ids []string) error {
	if !s.signalStreamEnabled || len(ids) == 0 {
		return nil
	}
	if err := s.client.XAck(ctx, s.signalStreamKey, strings.TrimSpace(group), ids...).Err(); err != nil {
		return fmt.Errorf("ack redis signal stream for group %s: %w", group, err)
	}
	return nil
}

func (s *Store) MergeSignalLogs(
	ctx context.Context,
	organization string,
	incoming []models.SignalLog,
	retentionCutoff time.Time,
) (bool, bool, error) {
	if strings.TrimSpace(organization) == "" {
		return false, false, fmt.Errorf("organization must not be empty")
	}
	if len(incoming) == 0 {
		return false, false, nil
	}

	orgKey := s.OrganizationKey(organization)
	cutoff := retentionCutoff.UTC()

	for attempt := 0; attempt < maxMergeSignalLogsRetries; attempt++ {
		updated := false
		deleted := false

		err := s.client.Watch(ctx, func(tx *goredis.Tx) error {
			payload, err := tx.HGet(ctx, orgKey, s.hashField).Result()
			if errors.Is(err, goredis.Nil) {
				payload = ""
			} else if err != nil {
				return fmt.Errorf("read redis hash for organization %s: %w", organization, err)
			}

			existing, err := models.DecodeSignalLogsPayload([]byte(payload))
			if err != nil {
				return fmt.Errorf("decode redis payload for organization %s: %w", organization, err)
			}

			merged := mergeSignalLogsRedis(existing, incoming, cutoff)
			if len(merged) == 0 {
				if len(existing) == 0 {
					return nil
				}
				_, err = tx.TxPipelined(ctx, func(pipe goredis.Pipeliner) error {
					pipe.HDel(ctx, orgKey, s.hashField)
					return nil
				})
				if err != nil {
					return fmt.Errorf("delete signal logs for organization %s: %w", organization, err)
				}
				deleted = true
				return nil
			}

			if signalLogsEqualRedis(existing, merged) {
				return nil
			}

			encoded, err := models.MarshalSignalLogsPayload(merged)
			if err != nil {
				return fmt.Errorf("marshal redis payload for organization %s: %w", organization, err)
			}

			_, err = tx.TxPipelined(ctx, func(pipe goredis.Pipeliner) error {
				pipe.HSet(ctx, orgKey, s.hashField, encoded)
				pipe.SAdd(ctx, s.activeOrgSetKey, organization)
				return nil
			})
			if err != nil {
				return fmt.Errorf("write redis hash for organization %s: %w", organization, err)
			}
			updated = true
			return nil
		}, orgKey)

		switch {
		case err == nil:
			if deleted {
				if err := s.cleanupOrganizationHashIfEmpty(ctx, orgKey); err != nil {
					return false, true, fmt.Errorf("cleanup redis key for organization %s: %w", organization, err)
				}
				if err := s.cleanupOrganizationMembership(ctx, organization); err != nil {
					return false, true, fmt.Errorf("cleanup organization index for organization %s: %w", organization, err)
				}
			}
			return updated, deleted, nil
		case errors.Is(err, goredis.TxFailedErr):
			continue
		default:
			return false, false, err
		}
	}

	return false, false, fmt.Errorf("merge signal logs for organization %s: exceeded retry limit", organization)
}

func (s *Store) LoadCachedFullLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	if len(docIDs) == 0 {
		return nil, nil
	}

	keys := make([]string, 0, len(docIDs))
	requested := make([]string, 0, len(docIDs))
	seen := make(map[string]struct{}, len(docIDs))
	for _, docID := range docIDs {
		trimmed := strings.TrimSpace(docID)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		requested = append(requested, trimmed)
		keys = append(keys, s.fullLogCacheKey(trimmed))
	}
	if len(keys) == 0 {
		return nil, nil
	}

	values, err := s.client.MGet(ctx, keys...).Result()
	if err != nil {
		return nil, fmt.Errorf("load distributed full log cache: %w", err)
	}

	result := make(map[string]*models.FullLog)
	for idx, raw := range values {
		if raw == nil {
			continue
		}
		payload := strings.TrimSpace(fmt.Sprint(raw))
		if payload == "" || payload == "<nil>" {
			continue
		}
		var fullLog models.FullLog
		if err := json.Unmarshal([]byte(payload), &fullLog); err != nil {
			return nil, fmt.Errorf("decode distributed full log cache for doc %s: %w", requested[idx], err)
		}
		result[requested[idx]] = &fullLog
	}
	return result, nil
}

func (s *Store) SaveCachedFullLogs(ctx context.Context, logs map[string]*models.FullLog, ttl time.Duration) error {
	if len(logs) == 0 {
		return nil
	}

	pipe := s.client.TxPipeline()
	for docID, fullLog := range logs {
		trimmed := strings.TrimSpace(docID)
		if trimmed == "" || fullLog == nil {
			continue
		}
		payload, err := json.Marshal(fullLog)
		if err != nil {
			return fmt.Errorf("marshal distributed full log cache for doc %s: %w", trimmed, err)
		}
		pipe.Set(ctx, s.fullLogCacheKey(trimmed), payload, ttl)
	}
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("save distributed full log cache: %w", err)
	}
	return nil
}

func (s *Store) HeartbeatWorker(ctx context.Context, worker distributed.WorkerHeartbeat, ttl time.Duration) error {
	workerID := strings.TrimSpace(worker.WorkerID)
	if workerID == "" {
		return fmt.Errorf("distributed worker id must not be empty")
	}
	if ttl <= 0 {
		return fmt.Errorf("distributed worker heartbeat ttl must be greater than zero")
	}

	updatedAt := worker.UpdatedAt.UTC()
	if updatedAt.IsZero() {
		updatedAt = time.Now().UTC()
	}

	payload, err := json.Marshal(workerRegistryPayload{
		WorkerID:  workerID,
		UpdatedAt: updatedAt.Format(time.RFC3339Nano),
	})
	if err != nil {
		return fmt.Errorf("marshal distributed worker heartbeat %s: %w", workerID, err)
	}

	pipe := s.client.TxPipeline()
	pipe.Set(ctx, s.workerRegistryKey(workerID), payload, ttl)
	pipe.SAdd(ctx, s.workerRegistrySetKey(), workerID)
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("save distributed worker heartbeat %s: %w", workerID, err)
	}
	return nil
}

func (s *Store) ListActiveWorkers(ctx context.Context) ([]distributed.WorkerHeartbeat, error) {
	workerIDs, err := s.client.SMembers(ctx, s.workerRegistrySetKey()).Result()
	if errors.Is(err, goredis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("list distributed workers: %w", err)
	}
	workerIDs = compactStrings(workerIDs)
	if len(workerIDs) == 0 {
		return nil, nil
	}
	sort.Strings(workerIDs)

	keys := make([]string, 0, len(workerIDs))
	for _, workerID := range workerIDs {
		keys = append(keys, s.workerRegistryKey(workerID))
	}

	values, err := s.client.MGet(ctx, keys...).Result()
	if err != nil {
		return nil, fmt.Errorf("load distributed worker registry payloads: %w", err)
	}

	active := make([]distributed.WorkerHeartbeat, 0, len(workerIDs))
	stale := make([]string, 0)
	for idx, raw := range values {
		if raw == nil {
			stale = append(stale, workerIDs[idx])
			continue
		}
		payload := strings.TrimSpace(fmt.Sprint(raw))
		if payload == "" || payload == "<nil>" {
			stale = append(stale, workerIDs[idx])
			continue
		}

		var decoded workerRegistryPayload
		if err := json.Unmarshal([]byte(payload), &decoded); err != nil {
			return nil, fmt.Errorf("decode distributed worker heartbeat %s: %w", workerIDs[idx], err)
		}

		heartbeat := distributed.WorkerHeartbeat{
			WorkerID: strings.TrimSpace(decoded.WorkerID),
		}
		if heartbeat.WorkerID == "" {
			heartbeat.WorkerID = workerIDs[idx]
		}
		if timestamp := strings.TrimSpace(decoded.UpdatedAt); timestamp != "" {
			parsed, err := time.Parse(time.RFC3339Nano, timestamp)
			if err != nil {
				return nil, fmt.Errorf("parse distributed worker heartbeat time %s: %w", workerIDs[idx], err)
			}
			heartbeat.UpdatedAt = parsed.UTC()
		}
		active = append(active, heartbeat)
	}

	if len(stale) > 0 {
		if err := s.client.SRem(ctx, s.workerRegistrySetKey(), stringSliceToAny(stale)...).Err(); err != nil && s.logger != nil {
			s.logger.Warn("failed to remove stale distributed workers from registry", "workers", stale, "error", err)
		}
	}

	sort.Slice(active, func(i, j int) bool {
		return active[i].WorkerID < active[j].WorkerID
	})
	return active, nil
}

func (s *Store) ClaimWorkloadLease(ctx context.Context, lease distributed.Lease, ttl time.Duration) (bool, error) {
	ok, err := s.client.SetNX(ctx, s.workloadLeaseKey(lease.Workload), lease.Token, ttl).Result()
	if err != nil {
		return false, fmt.Errorf("claim workload lease %s: %w", lease.Workload.DisplayKey(), err)
	}
	return ok, nil
}

func (s *Store) RenewWorkloadLease(ctx context.Context, lease distributed.Lease, ttl time.Duration) (bool, error) {
	result, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("PEXPIRE", KEYS[1], ARGV[2])
end
return 0
`, []string{s.workloadLeaseKey(lease.Workload)}, lease.Token, ttl.Milliseconds()).Int64()
	if err != nil {
		return false, fmt.Errorf("renew workload lease %s: %w", lease.Workload.DisplayKey(), err)
	}
	return result == 1, nil
}

func (s *Store) VerifyWorkloadLease(ctx context.Context, lease distributed.Lease) (bool, error) {
	value, err := s.client.Get(ctx, s.workloadLeaseKey(lease.Workload)).Result()
	if errors.Is(err, goredis.Nil) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("verify workload lease %s: %w", lease.Workload.DisplayKey(), err)
	}
	return value == lease.Token, nil
}

func (s *Store) ReleaseWorkloadLease(ctx context.Context, lease distributed.Lease) error {
	_, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0
`, []string{s.workloadLeaseKey(lease.Workload)}, lease.Token).Int64()
	if err != nil {
		return fmt.Errorf("release workload lease %s: %w", lease.Workload.DisplayKey(), err)
	}
	return nil
}

func (s *Store) StartWorkloadRun(
	ctx context.Context,
	lease distributed.Lease,
	run distributed.WorkloadRun,
	shard distributed.ShardContract,
	ttl time.Duration,
) error {
	if ttl <= 0 {
		return fmt.Errorf("distributed workload run ttl must be greater than zero")
	}

	runPayloadJSON, shardPayloadJSON, err := s.encodeWorkloadRunState(lease, run, shard, distributed.ShardStateRunning, "")
	if err != nil {
		return err
	}

	result, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call("SET", KEYS[2], ARGV[2], "PX", ARGV[4])
redis.call("SET", KEYS[3], ARGV[3], "PX", ARGV[4])
redis.call("SADD", KEYS[4], ARGV[5])
redis.call("PEXPIRE", KEYS[4], ARGV[4])
redis.call("SADD", KEYS[5], ARGV[6])
return 1
`, []string{
		s.workloadLeaseKey(lease.Workload),
		s.workloadRunKey(run),
		s.workloadRunShardStateRedisKey(shard),
		s.workloadRunShardIndexKey(run),
		s.activeRunsSetKey(),
	}, lease.Token, runPayloadJSON, shardPayloadJSON, ttl.Milliseconds(), shard.NormalizedShardID(), run.Key()).Int64()
	if err != nil {
		return fmt.Errorf("start distributed workload run %s: %w", run.DisplayKey(), err)
	}
	if result != 1 {
		return fmt.Errorf("workload lease %s is not owned by worker %s while starting run %s", lease.Workload.DisplayKey(), lease.Owner, run.DisplayKey())
	}
	return nil
}

func (s *Store) ClaimWorkloadRunFinalization(
	ctx context.Context,
	lease distributed.Lease,
	run distributed.WorkloadRun,
	ttl time.Duration,
) (bool, error) {
	if ttl <= 0 {
		return false, fmt.Errorf("distributed workload run finalization ttl must be greater than zero")
	}

	result, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
  return -1
end
local existing = redis.call("GET", KEYS[2])
if not existing then
  redis.call("SET", KEYS[2], ARGV[2], "PX", ARGV[3])
  return 1
end
if existing == ARGV[2] then
  redis.call("PEXPIRE", KEYS[2], ARGV[3])
  return 1
end
return 0
`, []string{
		s.workloadLeaseKey(lease.Workload),
		s.workloadRunFinalizationKey(run),
	}, lease.Token, run.FinalizationToken(), ttl.Milliseconds()).Int64()
	if err != nil {
		return false, fmt.Errorf("claim distributed workload run finalization %s: %w", run.DisplayKey(), err)
	}
	switch result {
	case 1:
		return true, nil
	case 0:
		return false, nil
	default:
		return false, fmt.Errorf("workload lease %s is not owned by worker %s while claiming run finalization %s", lease.Workload.DisplayKey(), lease.Owner, run.DisplayKey())
	}
}

func (s *Store) FinishWorkloadRun(
	ctx context.Context,
	lease distributed.Lease,
	run distributed.WorkloadRun,
	shard distributed.ShardContract,
	status distributed.ShardState,
	ttl time.Duration,
	message string,
) error {
	if ttl <= 0 {
		return fmt.Errorf("distributed workload run ttl must be greater than zero")
	}

	runPayloadJSON, shardPayloadJSON, err := s.encodeWorkloadRunState(lease, run, shard, status, message)
	if err != nil {
		return err
	}

	result, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call("SET", KEYS[2], ARGV[2], "PX", ARGV[4])
redis.call("SET", KEYS[3], ARGV[3], "PX", ARGV[4])
redis.call("SADD", KEYS[4], ARGV[5])
redis.call("PEXPIRE", KEYS[4], ARGV[4])
redis.call("SREM", KEYS[5], ARGV[6])
return 1
`, []string{
		s.workloadLeaseKey(lease.Workload),
		s.workloadRunKey(run),
		s.workloadRunShardStateRedisKey(shard),
		s.workloadRunShardIndexKey(run),
		s.activeRunsSetKey(),
	}, lease.Token, runPayloadJSON, shardPayloadJSON, ttl.Milliseconds(), shard.NormalizedShardID(), run.Key()).Int64()
	if err != nil {
		return fmt.Errorf("finish distributed workload run %s: %w", run.DisplayKey(), err)
	}
	if result != 1 {
		return fmt.Errorf("workload lease %s is not owned by worker %s while finishing run %s", lease.Workload.DisplayKey(), lease.Owner, run.DisplayKey())
	}
	return nil
}

func (s *Store) workloadLeaseKey(workload distributed.Workload) string {
	return fmt.Sprintf("%s:lease:%s", s.keyPrefix, workload.LeaseKey())
}

func (s *Store) workerRegistrySetKey() string {
	return fmt.Sprintf("%s:distributed:workers", s.keyPrefix)
}

func (s *Store) workerRegistryKey(workerID string) string {
	return fmt.Sprintf("%s:distributed:worker:%s", s.keyPrefix, encodeDistributedComponent(workerID))
}

func (s *Store) workloadRunKey(run distributed.WorkloadRun) string {
	return fmt.Sprintf("%s:distributed:run:%s", s.keyPrefix, encodeDistributedComponent(run.Key()))
}

func (s *Store) workloadRunFinalizationKey(run distributed.WorkloadRun) string {
	return fmt.Sprintf("%s:distributed:run_finalization:%s", s.keyPrefix, encodeDistributedComponent(run.Key()))
}

func (s *Store) workloadRunShardIndexKey(run distributed.WorkloadRun) string {
	return fmt.Sprintf("%s:distributed:run_shards:%s", s.keyPrefix, encodeDistributedComponent(run.Key()))
}

func (s *Store) workloadRunShardStateRedisKey(shard distributed.ShardContract) string {
	return fmt.Sprintf("%s:distributed:shard_state:%s", s.keyPrefix, encodeDistributedComponent(shard.StateKey()))
}

func (s *Store) fullLogCacheKey(docID string) string {
	return fmt.Sprintf("%s:full_log_cache:%s", s.keyPrefix, encodeDistributedComponent(docID))
}

func (s *Store) encodeWorkloadRunState(
	lease distributed.Lease,
	run distributed.WorkloadRun,
	shard distributed.ShardContract,
	status distributed.ShardState,
	message string,
) (string, string, error) {
	runID := strings.TrimSpace(run.ID)
	if runID == "" {
		return "", "", fmt.Errorf("distributed workload run id must not be empty")
	}

	startedAt := run.StartedAt.UTC()
	if startedAt.IsZero() {
		startedAt = time.Now().UTC()
	}
	updatedAt := time.Now().UTC()

	runPayload, err := json.Marshal(workloadRunPayload{
		WorkloadKey: run.Workload.DisplayKey(),
		RunID:       runID,
		Owner:       strings.TrimSpace(run.Owner),
		LeaseToken:  strings.TrimSpace(lease.Token),
		ShardID:     shard.NormalizedShardID(),
		StartedAt:   startedAt.Format(time.RFC3339Nano),
		UpdatedAt:   updatedAt.Format(time.RFC3339Nano),
		Status:      string(status),
		Message:     strings.TrimSpace(message),
	})
	if err != nil {
		return "", "", fmt.Errorf("marshal distributed workload run %s: %w", run.DisplayKey(), err)
	}

	updatedShard := shard
	updatedShard.RunID = runID
	updatedShard.Workload = run.Workload
	updatedShard.Owner = strings.TrimSpace(run.Owner)
	updatedShard.State = status

	shardPayload, err := json.Marshal(shardContractPayload{
		WorkloadKey: run.Workload.DisplayKey(),
		RunID:       runID,
		ShardID:     updatedShard.NormalizedShardID(),
		Mode:        updatedShard.NormalizedMode(),
		Owner:       updatedShard.Owner,
		LeaseKey:    updatedShard.LeaseKey(),
		ResultKey:   updatedShard.ResultKey(),
		StateKey:    updatedShard.StateKey(),
		LeaseToken:  strings.TrimSpace(lease.Token),
		State:       string(status),
		Attempt:     updatedShard.Attempt,
		Retryable:   updatedShard.Retryable,
		RetryAfter:  formatOptionalTime(updatedShard.RetryAfter),
		UpdatedAt:   updatedAt.Format(time.RFC3339Nano),
		Message:     strings.TrimSpace(message),
	})
	if err != nil {
		return "", "", fmt.Errorf("marshal distributed shard contract %s: %w", updatedShard.StateKey(), err)
	}
	return string(runPayload), string(shardPayload), nil
}

func encodeDistributedComponent(value string) string {
	return base64.RawURLEncoding.EncodeToString([]byte(strings.TrimSpace(value)))
}

func formatOptionalTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339Nano)
}

func mergeSignalLogsRedis(existing []models.SignalLog, incoming []models.SignalLog, cutoff time.Time) []models.SignalLog {
	deduped := make(map[string]models.SignalLog, len(existing)+len(incoming))
	combined := make([]models.SignalLog, 0, len(existing)+len(incoming))
	combined = append(combined, existing...)
	combined = append(combined, incoming...)

	for _, log := range combined {
		docID := strings.TrimSpace(log.DocID)
		if docID == "" || log.TimeStamp.IsZero() {
			continue
		}
		log.DocID = docID
		log.TimeStamp = log.TimeStamp.UTC()
		if !cutoff.IsZero() && log.TimeStamp.Before(cutoff) {
			continue
		}

		current, exists := deduped[docID]
		if !exists || shouldReplaceSignalLogRedis(current, log) {
			deduped[docID] = log
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

func signalLogsEqualRedis(left []models.SignalLog, right []models.SignalLog) bool {
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
	}
	return true
}

func shouldReplaceSignalLogRedis(current models.SignalLog, candidate models.SignalLog) bool {
	if candidate.TimeStamp.After(current.TimeStamp) {
		return true
	}
	if candidate.TimeStamp.Before(current.TimeStamp) {
		return false
	}
	return signalLogCompletenessScoreRedis(candidate) >= signalLogCompletenessScoreRedis(current)
}

func signalLogCompletenessScoreRedis(log models.SignalLog) int {
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
	return score
}
