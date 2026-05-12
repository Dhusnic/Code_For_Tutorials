package redis

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sort"
	"strings"
	"time"

	"log_correlation_engine/internal/distributed"
	"log_correlation_engine/internal/models"

	goredis "github.com/redis/go-redis/v9"
)

type shardExecutionPayloadDocument struct {
	WorkloadKey  string           `json:"workload_key"`
	RunID        string           `json:"run_id"`
	ShardID      string           `json:"shard_id"`
	Mode         string           `json:"mode"`
	PrimaryStart string           `json:"primary_start"`
	PrimaryEnd   string           `json:"primary_end"`
	Logs         []models.FullLog `json:"logs"`
	Rules        []models.Rule    `json:"rules"`
}

type shardExecutionResultDocument struct {
	WorkloadKey string                     `json:"workload_key"`
	RunID       string                     `json:"run_id"`
	ShardID     string                     `json:"shard_id"`
	Mode        string                     `json:"mode"`
	WorkerID    string                     `json:"worker_id"`
	LogCount    int                        `json:"log_count"`
	Duration    string                     `json:"duration,omitempty"`
	Status      string                     `json:"status"`
	Results     []models.CorrelationResult `json:"results"`
	Message     string                     `json:"message,omitempty"`
	CompletedAt string                     `json:"completed_at,omitempty"`
}

const compressedJSONPrefix = "gz:"

func (s *Store) StoreWorkloadShards(
	ctx context.Context,
	lease distributed.Lease,
	run distributed.WorkloadRun,
	shards []distributed.ShardExecutionPayload,
	ttl time.Duration,
) error {
	if len(shards) == 0 {
		return nil
	}
	if ttl <= 0 {
		return fmt.Errorf("distributed workload shard ttl must be greater than zero")
	}

	owned, err := s.VerifyWorkloadLease(ctx, lease)
	if err != nil {
		return err
	}
	if !owned {
		return fmt.Errorf("workload lease %s is not owned by worker %s while storing shards", lease.Workload.DisplayKey(), lease.Owner)
	}

	pipe := s.client.TxPipeline()
	runKey := run.Key()
	pipe.SAdd(ctx, s.activeRunsSetKey(), runKey)
	for idx, payload := range shards {
		payload.Workload = run.Workload
		payload.RunID = run.ID
		if strings.TrimSpace(payload.ShardID) == "" {
			payload.ShardID = fmt.Sprintf("shard-%04d", idx)
		}

		contract := payload.Contract(run.Owner)
		encodedPayload, err := encodeShardExecutionPayload(payload)
		if err != nil {
			return err
		}
		encodedState, err := s.encodeShardContractState(contract, lease.Token, "")
		if err != nil {
			return err
		}

		pipe.Set(ctx, s.shardPayloadRedisKey(contract), encodedPayload, ttl)
		pipe.Set(ctx, s.workloadRunShardStateRedisKey(contract), encodedState, ttl)
		pipe.SAdd(ctx, s.workloadRunShardIndexKey(run), contract.NormalizedShardID())
		pipe.Expire(ctx, s.workloadRunShardIndexKey(run), ttl)
	}
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("store distributed workload shards for %s: %w", run.DisplayKey(), err)
	}
	return nil
}

func (s *Store) ClaimWorkloadShard(
	ctx context.Context,
	workerID string,
	ttl time.Duration,
	run *distributed.WorkloadRun,
) (*distributed.ShardExecutionPayload, *distributed.ShardLease, error) {
	if ttl <= 0 {
		return nil, nil, fmt.Errorf("distributed workload shard lease ttl must be greater than zero")
	}

	runs, err := s.loadCandidateRuns(ctx, run)
	if err != nil {
		return nil, nil, err
	}
	now := time.Now().UTC()
	for _, candidateRun := range runs {
		shardIDs, err := s.client.SMembers(ctx, s.workloadRunShardIndexKey(candidateRun)).Result()
		if errors.Is(err, goredis.Nil) {
			continue
		}
		if err != nil {
			return nil, nil, fmt.Errorf("list distributed workload shards for %s: %w", candidateRun.DisplayKey(), err)
		}
		shardIDs = compactStrings(shardIDs)
		sort.Strings(shardIDs)
		for _, shardID := range shardIDs {
			if shardID == "root" {
				continue
			}

			contract, ok, err := s.loadShardContract(ctx, candidateRun, shardID)
			if err != nil {
				return nil, nil, err
			}
			if !ok {
				continue
			}
			if !shardRunnable(contract, now) {
				continue
			}
			if contract.State == distributed.ShardStateRunning {
				exists, err := s.client.Exists(ctx, s.shardLeaseRedisKey(contract)).Result()
				if err != nil {
					return nil, nil, fmt.Errorf("inspect distributed shard lease %s: %w", contract.StateKey(), err)
				}
				if exists > 0 {
					continue
				}
			}

			lease := distributed.NewShardLease(contract, workerID)
			ok, err = s.client.SetNX(ctx, s.shardLeaseRedisKey(contract), lease.Token, ttl).Result()
			if err != nil {
				return nil, nil, fmt.Errorf("claim distributed shard lease %s: %w", contract.StateKey(), err)
			}
			if !ok {
				continue
			}

			payload, payloadFound, err := s.loadShardPayload(ctx, contract)
			if err != nil {
				_ = s.ReleaseWorkloadShardLease(ctx, lease)
				return nil, nil, err
			}
			if !payloadFound {
				_ = s.ReleaseWorkloadShardLease(ctx, lease)
				continue
			}

			contract.Owner = strings.TrimSpace(workerID)
			contract.State = distributed.ShardStateRunning
			contract.Attempt++
			encodedState, err := s.encodeShardContractState(contract, lease.Token, "")
			if err != nil {
				_ = s.ReleaseWorkloadShardLease(ctx, lease)
				return nil, nil, err
			}
			if err := s.client.Set(ctx, s.workloadRunShardStateRedisKey(contract), encodedState, ttl).Err(); err != nil {
				_ = s.ReleaseWorkloadShardLease(ctx, lease)
				return nil, nil, fmt.Errorf("mark distributed shard %s running: %w", contract.StateKey(), err)
			}

			lease.Contract = contract
			payload.RunID = candidateRun.ID
			payload.Workload = candidateRun.Workload
			return payload, &lease, nil
		}
	}

	return nil, nil, nil
}

func (s *Store) RenewWorkloadShardLease(ctx context.Context, lease distributed.ShardLease, ttl time.Duration) (bool, error) {
	result, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("PEXPIRE", KEYS[1], ARGV[2])
end
return 0
`, []string{s.shardLeaseRedisKey(lease.Contract)}, lease.Token, ttl.Milliseconds()).Int64()
	if err != nil {
		return false, fmt.Errorf("renew distributed shard lease %s: %w", lease.Contract.StateKey(), err)
	}
	return result == 1, nil
}

func (s *Store) ReleaseWorkloadShardLease(ctx context.Context, lease distributed.ShardLease) error {
	_, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0
`, []string{s.shardLeaseRedisKey(lease.Contract)}, lease.Token).Int64()
	if err != nil {
		return fmt.Errorf("release distributed shard lease %s: %w", lease.Contract.StateKey(), err)
	}
	return nil
}

func (s *Store) CompleteWorkloadShard(
	ctx context.Context,
	lease distributed.ShardLease,
	result distributed.ShardExecutionResult,
	ttl time.Duration,
) error {
	if ttl <= 0 {
		return fmt.Errorf("distributed workload shard ttl must be greater than zero")
	}

	contract := lease.Contract
	contract.State = distributed.ShardStateCompleted
	contract.Owner = strings.TrimSpace(lease.Owner)
	contract.RetryAfter = time.Time{}
	result.Workload = contract.Workload
	result.RunID = contract.RunID
	result.ShardID = contract.NormalizedShardID()
	result.Mode = contract.NormalizedMode()
	result.WorkerID = strings.TrimSpace(lease.Owner)
	result.Status = distributed.ShardStateCompleted
	if result.CompletedAt.IsZero() {
		result.CompletedAt = time.Now().UTC()
	}

	encodedState, err := s.encodeShardContractState(contract, lease.Token, "")
	if err != nil {
		return err
	}
	encodedResult, err := encodeShardExecutionResult(result)
	if err != nil {
		return err
	}

	shardResultKey := s.shardResultRedisKey(contract)
	resultCode, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call("SET", KEYS[2], ARGV[2], "PX", ARGV[4])
redis.call("SET", KEYS[3], ARGV[3], "PX", ARGV[4])
redis.call("DEL", KEYS[1])
return 1
`, []string{
		s.shardLeaseRedisKey(contract),
		shardResultKey,
		s.workloadRunShardStateRedisKey(contract),
	}, lease.Token, encodedResult, encodedState, ttl.Milliseconds()).Int64()
	if err != nil {
		return fmt.Errorf("complete distributed shard %s: %w", contract.StateKey(), err)
	}
	if resultCode != 1 {
		return fmt.Errorf("distributed shard lease %s is no longer owned by worker %s", contract.StateKey(), lease.Owner)
	}
	return nil
}

func (s *Store) FailWorkloadShard(
	ctx context.Context,
	lease distributed.ShardLease,
	message string,
	retryable bool,
	retryAfter time.Time,
	ttl time.Duration,
) error {
	if ttl <= 0 {
		return fmt.Errorf("distributed workload shard ttl must be greater than zero")
	}

	contract := lease.Contract
	contract.State = distributed.ShardStateFailed
	contract.Owner = strings.TrimSpace(lease.Owner)
	contract.Retryable = retryable
	contract.RetryAfter = retryAfter.UTC()

	encodedState, err := s.encodeShardContractState(contract, lease.Token, message)
	if err != nil {
		return err
	}
	resultCode, err := s.client.Eval(ctx, `
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call("SET", KEYS[2], ARGV[2], "PX", ARGV[4])
redis.call("DEL", KEYS[1])
return 1
`, []string{
		s.shardLeaseRedisKey(contract),
		s.workloadRunShardStateRedisKey(contract),
	}, lease.Token, encodedState, "", ttl.Milliseconds()).Int64()
	if err != nil {
		return fmt.Errorf("fail distributed shard %s: %w", contract.StateKey(), err)
	}
	if resultCode != 1 {
		return fmt.Errorf("distributed shard lease %s is no longer owned by worker %s", contract.StateKey(), lease.Owner)
	}
	return nil
}

func (s *Store) LoadWorkloadShardResults(
	ctx context.Context,
	run distributed.WorkloadRun,
	mode string,
) ([]distributed.ShardExecutionResult, []distributed.ShardContract, error) {
	shardIDs, err := s.client.SMembers(ctx, s.workloadRunShardIndexKey(run)).Result()
	if errors.Is(err, goredis.Nil) {
		return nil, nil, nil
	}
	if err != nil {
		return nil, nil, fmt.Errorf("list distributed workload shards for %s: %w", run.DisplayKey(), err)
	}
	shardIDs = compactStrings(shardIDs)
	sort.Strings(shardIDs)

	results := make([]distributed.ShardExecutionResult, 0, len(shardIDs))
	contracts := make([]distributed.ShardContract, 0, len(shardIDs))
	for _, shardID := range shardIDs {
		if shardID == "root" {
			continue
		}
		contract, ok, err := s.loadShardContract(ctx, run, shardID)
		if err != nil {
			return nil, nil, err
		}
		if !ok {
			continue
		}
		if mode != "" && contract.NormalizedMode() != strings.TrimSpace(mode) {
			continue
		}
		contracts = append(contracts, contract)
		if contract.State != distributed.ShardStateCompleted {
			continue
		}

		payload, err := s.client.Get(ctx, s.shardResultRedisKey(contract)).Result()
		if errors.Is(err, goredis.Nil) {
			continue
		}
		if err != nil {
			return nil, nil, fmt.Errorf("load distributed shard result %s: %w", contract.ResultKey(), err)
		}
		decoded, err := decodeShardExecutionResult(payload)
		if err != nil {
			return nil, nil, err
		}
		results = append(results, decoded)
	}
	return results, contracts, nil
}

func (s *Store) loadCandidateRuns(ctx context.Context, run *distributed.WorkloadRun) ([]distributed.WorkloadRun, error) {
	if run != nil {
		return []distributed.WorkloadRun{*run}, nil
	}
	runKeys, err := s.client.SMembers(ctx, s.activeRunsSetKey()).Result()
	if errors.Is(err, goredis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("list active distributed workload runs: %w", err)
	}
	runKeys = compactStrings(runKeys)
	sort.Strings(runKeys)
	runs := make([]distributed.WorkloadRun, 0, len(runKeys))
	for _, runKey := range runKeys {
		candidate, ok, err := s.loadWorkloadRunByKey(ctx, runKey)
		if err != nil {
			return nil, err
		}
		if ok {
			runs = append(runs, candidate)
		}
	}
	return runs, nil
}

func (s *Store) loadWorkloadRunByKey(ctx context.Context, runKey string) (distributed.WorkloadRun, bool, error) {
	payload, err := s.client.Get(ctx, s.workloadRunRedisKeyByValue(runKey)).Result()
	if errors.Is(err, goredis.Nil) {
		_ = s.client.SRem(ctx, s.activeRunsSetKey(), runKey).Err()
		return distributed.WorkloadRun{}, false, nil
	}
	if err != nil {
		return distributed.WorkloadRun{}, false, fmt.Errorf("load distributed workload run %s: %w", runKey, err)
	}

	var decoded workloadRunPayload
	if err := json.Unmarshal([]byte(payload), &decoded); err != nil {
		return distributed.WorkloadRun{}, false, fmt.Errorf("decode distributed workload run %s: %w", runKey, err)
	}
	startedAt := time.Time{}
	if strings.TrimSpace(decoded.StartedAt) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, decoded.StartedAt)
		if err != nil {
			return distributed.WorkloadRun{}, false, fmt.Errorf("parse distributed workload run start %s: %w", runKey, err)
		}
		startedAt = parsed.UTC()
	}
	return distributed.WorkloadRun{
		Workload:  distributed.OrganizationWorkload(decoded.WorkloadKey),
		ID:        strings.TrimSpace(decoded.RunID),
		Owner:     strings.TrimSpace(decoded.Owner),
		StartedAt: startedAt,
	}, true, nil
}

func (s *Store) loadShardContract(ctx context.Context, run distributed.WorkloadRun, shardID string) (distributed.ShardContract, bool, error) {
	contract := distributed.ShardContract{
		Workload: run.Workload,
		RunID:    run.ID,
		ShardID:  shardID,
	}
	payload, err := s.client.Get(ctx, s.workloadRunShardStateRedisKey(contract)).Result()
	if errors.Is(err, goredis.Nil) {
		return distributed.ShardContract{}, false, nil
	}
	if err != nil {
		return distributed.ShardContract{}, false, fmt.Errorf("load distributed shard state %s: %w", contract.StateKey(), err)
	}
	decoded, err := decodeShardContractPayload(payload)
	if err != nil {
		return distributed.ShardContract{}, false, err
	}
	decoded.Workload = run.Workload
	decoded.RunID = run.ID
	return decoded, true, nil
}

func (s *Store) loadShardPayload(ctx context.Context, contract distributed.ShardContract) (*distributed.ShardExecutionPayload, bool, error) {
	payload, err := s.client.Get(ctx, s.shardPayloadRedisKey(contract)).Result()
	if errors.Is(err, goredis.Nil) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("load distributed shard payload %s: %w", contract.PayloadKey(), err)
	}
	decoded, err := decodeShardExecutionPayload(payload)
	if err != nil {
		return nil, false, err
	}
	decoded.Workload = contract.Workload
	decoded.RunID = contract.RunID
	decoded.ShardID = contract.NormalizedShardID()
	decoded.Mode = contract.NormalizedMode()
	return &decoded, true, nil
}

func (s *Store) activeRunsSetKey() string {
	return fmt.Sprintf("%s:distributed:active_runs", s.keyPrefix)
}

func (s *Store) workloadRunRedisKeyByValue(runKey string) string {
	return fmt.Sprintf("%s:distributed:run:%s", s.keyPrefix, encodeDistributedComponent(runKey))
}

func (s *Store) shardLeaseRedisKey(contract distributed.ShardContract) string {
	return fmt.Sprintf("%s:distributed:shard_lease:%s", s.keyPrefix, encodeDistributedComponent(contract.LeaseKey()))
}

func (s *Store) shardPayloadRedisKey(contract distributed.ShardContract) string {
	return fmt.Sprintf("%s:distributed:shard_payload:%s", s.keyPrefix, encodeDistributedComponent(contract.PayloadKey()))
}

func (s *Store) shardResultRedisKey(contract distributed.ShardContract) string {
	return fmt.Sprintf("%s:distributed:shard_result:%s", s.keyPrefix, encodeDistributedComponent(contract.ResultKey()))
}

func (s *Store) encodeShardContractState(contract distributed.ShardContract, leaseToken string, message string) (string, error) {
	payload, err := json.Marshal(shardContractPayload{
		WorkloadKey: contract.Workload.DisplayKey(),
		RunID:       contract.RunID,
		ShardID:     contract.NormalizedShardID(),
		Mode:        contract.NormalizedMode(),
		Owner:       contract.Owner,
		LeaseKey:    contract.LeaseKey(),
		ResultKey:   contract.ResultKey(),
		StateKey:    contract.StateKey(),
		LeaseToken:  strings.TrimSpace(leaseToken),
		State:       string(contract.State),
		Attempt:     contract.Attempt,
		Retryable:   contract.Retryable,
		RetryAfter:  formatOptionalTime(contract.RetryAfter),
		UpdatedAt:   time.Now().UTC().Format(time.RFC3339Nano),
		Message:     strings.TrimSpace(message),
	})
	if err != nil {
		return "", fmt.Errorf("marshal distributed shard contract %s: %w", contract.StateKey(), err)
	}
	return string(payload), nil
}

func encodeShardExecutionPayload(payload distributed.ShardExecutionPayload) (string, error) {
	document, err := json.Marshal(shardExecutionPayloadDocument{
		WorkloadKey:  payload.Workload.DisplayKey(),
		RunID:        strings.TrimSpace(payload.RunID),
		ShardID:      payload.NormalizedShardID(),
		Mode:         payload.NormalizedMode(),
		PrimaryStart: formatOptionalTime(payload.PrimaryStart),
		PrimaryEnd:   formatOptionalTime(payload.PrimaryEnd),
		Logs:         payload.Logs,
		Rules:        payload.Rules,
	})
	if err != nil {
		return "", fmt.Errorf("marshal distributed shard payload %s: %w", payload.NormalizedShardID(), err)
	}
	return encodeCompressedJSON(document)
}

func decodeShardExecutionPayload(payload string) (distributed.ShardExecutionPayload, error) {
	var decoded shardExecutionPayloadDocument
	document, err := decodeCompressedJSON(payload)
	if err != nil {
		return distributed.ShardExecutionPayload{}, fmt.Errorf("decode distributed shard payload: %w", err)
	}
	if err := json.Unmarshal(document, &decoded); err != nil {
		return distributed.ShardExecutionPayload{}, fmt.Errorf("decode distributed shard payload: %w", err)
	}
	result := distributed.ShardExecutionPayload{
		Workload: distributed.OrganizationWorkload(decoded.WorkloadKey),
		RunID:    strings.TrimSpace(decoded.RunID),
		ShardID:  strings.TrimSpace(decoded.ShardID),
		Mode:     strings.TrimSpace(decoded.Mode),
		Logs:     decoded.Logs,
		Rules:    decoded.Rules,
	}
	if strings.TrimSpace(decoded.PrimaryStart) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, decoded.PrimaryStart)
		if err != nil {
			return distributed.ShardExecutionPayload{}, fmt.Errorf("parse distributed shard primary start %s: %w", decoded.ShardID, err)
		}
		result.PrimaryStart = parsed.UTC()
	}
	if strings.TrimSpace(decoded.PrimaryEnd) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, decoded.PrimaryEnd)
		if err != nil {
			return distributed.ShardExecutionPayload{}, fmt.Errorf("parse distributed shard primary end %s: %w", decoded.ShardID, err)
		}
		result.PrimaryEnd = parsed.UTC()
	}
	return result, nil
}

func encodeShardExecutionResult(result distributed.ShardExecutionResult) (string, error) {
	document, err := json.Marshal(shardExecutionResultDocument{
		WorkloadKey: result.Workload.DisplayKey(),
		RunID:       strings.TrimSpace(result.RunID),
		ShardID:     result.NormalizedShardID(),
		Mode:        strings.TrimSpace(result.Mode),
		WorkerID:    strings.TrimSpace(result.WorkerID),
		LogCount:    result.LogCount,
		Duration:    result.Duration.String(),
		Status:      string(result.Status),
		Results:     result.Results,
		Message:     strings.TrimSpace(result.Message),
		CompletedAt: formatOptionalTime(result.CompletedAt),
	})
	if err != nil {
		return "", fmt.Errorf("marshal distributed shard result %s: %w", result.NormalizedShardID(), err)
	}
	return encodeCompressedJSON(document)
}

func decodeShardExecutionResult(payload string) (distributed.ShardExecutionResult, error) {
	var decoded shardExecutionResultDocument
	document, err := decodeCompressedJSON(payload)
	if err != nil {
		return distributed.ShardExecutionResult{}, fmt.Errorf("decode distributed shard result: %w", err)
	}
	if err := json.Unmarshal(document, &decoded); err != nil {
		return distributed.ShardExecutionResult{}, fmt.Errorf("decode distributed shard result: %w", err)
	}
	result := distributed.ShardExecutionResult{
		Workload: distributed.OrganizationWorkload(decoded.WorkloadKey),
		RunID:    strings.TrimSpace(decoded.RunID),
		ShardID:  strings.TrimSpace(decoded.ShardID),
		Mode:     strings.TrimSpace(decoded.Mode),
		WorkerID: strings.TrimSpace(decoded.WorkerID),
		LogCount: decoded.LogCount,
		Status:   distributed.ShardState(strings.TrimSpace(decoded.Status)),
		Results:  decoded.Results,
		Message:  strings.TrimSpace(decoded.Message),
	}
	if strings.TrimSpace(decoded.Duration) != "" {
		parsed, err := time.ParseDuration(decoded.Duration)
		if err != nil {
			return distributed.ShardExecutionResult{}, fmt.Errorf("parse distributed shard result duration %s: %w", decoded.ShardID, err)
		}
		result.Duration = parsed
	}
	if strings.TrimSpace(decoded.CompletedAt) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, decoded.CompletedAt)
		if err != nil {
			return distributed.ShardExecutionResult{}, fmt.Errorf("parse distributed shard result completion %s: %w", decoded.ShardID, err)
		}
		result.CompletedAt = parsed.UTC()
	}
	return result, nil
}

func decodeShardContractPayload(payload string) (distributed.ShardContract, error) {
	var decoded shardContractPayload
	if err := json.Unmarshal([]byte(payload), &decoded); err != nil {
		return distributed.ShardContract{}, fmt.Errorf("decode distributed shard contract: %w", err)
	}
	contract := distributed.ShardContract{
		Workload:  distributed.OrganizationWorkload(decoded.WorkloadKey),
		RunID:     strings.TrimSpace(decoded.RunID),
		ShardID:   strings.TrimSpace(decoded.ShardID),
		Mode:      strings.TrimSpace(decoded.Mode),
		Owner:     strings.TrimSpace(decoded.Owner),
		State:     distributed.ShardState(strings.TrimSpace(decoded.State)),
		Attempt:   decoded.Attempt,
		Retryable: decoded.Retryable,
	}
	if strings.TrimSpace(decoded.RetryAfter) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, decoded.RetryAfter)
		if err != nil {
			return distributed.ShardContract{}, fmt.Errorf("parse distributed shard retry_after %s: %w", decoded.ShardID, err)
		}
		contract.RetryAfter = parsed.UTC()
	}
	return contract, nil
}

func encodeCompressedJSON(document []byte) (string, error) {
	var compressed bytes.Buffer
	writer := gzip.NewWriter(&compressed)
	if _, err := writer.Write(document); err != nil {
		_ = writer.Close()
		return "", fmt.Errorf("gzip payload: %w", err)
	}
	if err := writer.Close(); err != nil {
		return "", fmt.Errorf("finalize gzip payload: %w", err)
	}
	return compressedJSONPrefix + base64.StdEncoding.EncodeToString(compressed.Bytes()), nil
}

func decodeCompressedJSON(payload string) ([]byte, error) {
	if !strings.HasPrefix(payload, compressedJSONPrefix) {
		return []byte(payload), nil
	}

	encoded := strings.TrimPrefix(payload, compressedJSONPrefix)
	compressed, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, fmt.Errorf("base64 payload: %w", err)
	}
	reader, err := gzip.NewReader(bytes.NewReader(compressed))
	if err != nil {
		return nil, fmt.Errorf("open gzip payload: %w", err)
	}
	defer reader.Close()

	document, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("read gzip payload: %w", err)
	}
	return document, nil
}

func shardRunnable(contract distributed.ShardContract, now time.Time) bool {
	switch contract.State {
	case distributed.ShardStateCompleted:
		return false
	case distributed.ShardStateRunning:
		return true
	case distributed.ShardStateFailed:
		if !contract.Retryable {
			return false
		}
		if !contract.RetryAfter.IsZero() && contract.RetryAfter.After(now) {
			return false
		}
		return true
	default:
		return true
	}
}
