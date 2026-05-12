package distributed

import (
	"fmt"
	"os"
	"strings"
	"time"

	"log_correlation_engine/internal/models"
)

type Workload struct {
	OrganizationID string
}

type Lease struct {
	Workload Workload
	Owner    string
	Token    string
}

type WorkerHeartbeat struct {
	WorkerID  string
	UpdatedAt time.Time
}

type WorkloadRun struct {
	Workload  Workload
	ID        string
	Owner     string
	StartedAt time.Time
}

type ShardState string

const (
	ShardStatePending   ShardState = "pending"
	ShardStateRunning   ShardState = "running"
	ShardStateCompleted ShardState = "completed"
	ShardStateFailed    ShardState = "failed"
)

type ShardContract struct {
	Workload   Workload
	RunID      string
	ShardID    string
	Mode       string
	Owner      string
	State      ShardState
	Attempt    int
	Retryable  bool
	RetryAfter time.Time
}

type ShardLease struct {
	Contract ShardContract
	Owner    string
	Token    string
}

type ShardExecutionPayload struct {
	Workload     Workload
	RunID        string
	ShardID      string
	Mode         string
	PrimaryStart time.Time
	PrimaryEnd   time.Time
	Logs         []models.FullLog
	Rules        []models.Rule
}

type ShardExecutionResult struct {
	Workload    Workload
	RunID       string
	ShardID     string
	Mode        string
	WorkerID    string
	LogCount    int
	Duration    time.Duration
	Status      ShardState
	Results     []models.CorrelationResult
	Message     string
	CompletedAt time.Time
}

const signalStreamIngestWorkloadID = "__signal_stream_ingest__"

func OrganizationWorkload(organizationID string) Workload {
	return Workload{
		OrganizationID: strings.TrimSpace(organizationID),
	}
}

func SignalStreamIngestWorkload() Workload {
	return Workload{
		OrganizationID: signalStreamIngestWorkloadID,
	}
}

func (w Workload) DisplayKey() string {
	return strings.TrimSpace(w.OrganizationID)
}

func (w Workload) CheckpointKey() string {
	return fmt.Sprintf("organization:%s", strings.TrimSpace(w.OrganizationID))
}

func (w Workload) LeaseKey() string {
	return fmt.Sprintf("organization:%s", strings.TrimSpace(w.OrganizationID))
}

func (w Workload) RunKey(runID string) string {
	return fmt.Sprintf("%s:run:%s", w.LeaseKey(), strings.TrimSpace(runID))
}

func ResolveWorkerID(envKey string) string {
	keys := []string{strings.TrimSpace(envKey), "RCA_WORKER_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id"}
	for _, key := range keys {
		if key == "" {
			continue
		}
		if value := strings.TrimSpace(os.Getenv(key)); value != "" {
			return value
		}
	}
	return fmt.Sprintf("pid-%d", os.Getpid())
}

func NewLease(workload Workload, owner string) Lease {
	trimmedOwner := strings.TrimSpace(owner)
	if trimmedOwner == "" {
		trimmedOwner = ResolveWorkerID("")
	}
	return Lease{
		Workload: workload,
		Owner:    trimmedOwner,
		Token:    fmt.Sprintf("%s:%d", trimmedOwner, time.Now().UTC().UnixNano()),
	}
}

func NewWorkloadRun(workload Workload, owner string) WorkloadRun {
	return NewWorkloadRunAt(workload, owner, time.Now().UTC())
}

func NewWorkloadRunAt(workload Workload, owner string, startedAt time.Time) WorkloadRun {
	trimmedOwner := strings.TrimSpace(owner)
	if trimmedOwner == "" {
		trimmedOwner = ResolveWorkerID("")
	}
	startedAt = startedAt.UTC()
	if startedAt.IsZero() {
		startedAt = time.Now().UTC()
	}
	return WorkloadRun{
		Workload:  workload,
		ID:        fmt.Sprintf("%d", startedAt.UnixNano()),
		Owner:     trimmedOwner,
		StartedAt: startedAt,
	}
}

func (r WorkloadRun) DisplayKey() string {
	return fmt.Sprintf("%s/%s", r.Workload.DisplayKey(), strings.TrimSpace(r.ID))
}

func (r WorkloadRun) Key() string {
	return r.Workload.RunKey(r.ID)
}

func (r WorkloadRun) FinalizationToken() string {
	return fmt.Sprintf("%s:%s", strings.TrimSpace(r.Owner), strings.TrimSpace(r.ID))
}

func RootShardContract(run WorkloadRun) ShardContract {
	return ShardContract{
		Workload:  run.Workload,
		RunID:     strings.TrimSpace(run.ID),
		ShardID:   "root",
		Mode:      "root",
		Owner:     strings.TrimSpace(run.Owner),
		State:     ShardStateRunning,
		Attempt:   1,
		Retryable: true,
	}
}

func (s ShardContract) NormalizedShardID() string {
	trimmed := strings.TrimSpace(s.ShardID)
	if trimmed == "" {
		return "root"
	}
	return trimmed
}

func (s ShardContract) LeaseKey() string {
	return fmt.Sprintf("%s:shard:%s:lease", s.Workload.RunKey(s.RunID), s.NormalizedShardID())
}

func (s ShardContract) ResultKey() string {
	return fmt.Sprintf("%s:shard:%s:result", s.Workload.RunKey(s.RunID), s.NormalizedShardID())
}

func (s ShardContract) StateKey() string {
	return fmt.Sprintf("%s:shard:%s:state", s.Workload.RunKey(s.RunID), s.NormalizedShardID())
}

func (s ShardContract) PayloadKey() string {
	return fmt.Sprintf("%s:shard:%s:payload", s.Workload.RunKey(s.RunID), s.NormalizedShardID())
}

func (s ShardContract) NormalizedMode() string {
	return strings.TrimSpace(s.Mode)
}

func (s ShardExecutionPayload) NormalizedShardID() string {
	trimmed := strings.TrimSpace(s.ShardID)
	if trimmed == "" {
		return "root"
	}
	return trimmed
}

func (s ShardExecutionPayload) NormalizedMode() string {
	return strings.TrimSpace(s.Mode)
}

func (s ShardExecutionPayload) Contract(owner string) ShardContract {
	trimmedOwner := strings.TrimSpace(owner)
	if trimmedOwner == "" {
		trimmedOwner = ResolveWorkerID("")
	}
	return ShardContract{
		Workload:  s.Workload,
		RunID:     strings.TrimSpace(s.RunID),
		ShardID:   s.NormalizedShardID(),
		Mode:      s.NormalizedMode(),
		Owner:     trimmedOwner,
		State:     ShardStatePending,
		Attempt:   0,
		Retryable: true,
	}
}

func (s ShardExecutionResult) NormalizedShardID() string {
	trimmed := strings.TrimSpace(s.ShardID)
	if trimmed == "" {
		return "root"
	}
	return trimmed
}

func NewShardLease(contract ShardContract, owner string) ShardLease {
	trimmedOwner := strings.TrimSpace(owner)
	if trimmedOwner == "" {
		trimmedOwner = ResolveWorkerID("")
	}
	return ShardLease{
		Contract: contract,
		Owner:    trimmedOwner,
		Token:    fmt.Sprintf("%s:%d", trimmedOwner, time.Now().UTC().UnixNano()),
	}
}
