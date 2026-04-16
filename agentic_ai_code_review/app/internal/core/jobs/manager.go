package jobs

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"
)

const (
	StatusQueued             = "queued"
	StatusRunning            = "running"
	StatusWaitingForApproval = "waiting_for_approval"
	StatusSucceeded          = "succeeded"
	StatusFailed             = "failed"
)

type Runner func(ctx context.Context, jobID string, payload map[string]any) (map[string]any, error)

type Job struct {
	JobID           string         `json:"job_id"`
	JobType         string         `json:"job_type"`
	Status          string         `json:"status"`
	CreatedAt       int64          `json:"created_at"`
	UpdatedAt       int64          `json:"updated_at"`
	StartedAt       int64          `json:"started_at,omitempty"`
	FinishedAt      int64          `json:"finished_at,omitempty"`
	Result          map[string]any `json:"result,omitempty"`
	Error           map[string]any `json:"error,omitempty"`
	ApprovalRequest map[string]any `json:"approval_request,omitempty"`
}

type submission struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"`
	PollURL string `json:"poll_url"`
	WSURL   string `json:"ws_url"`
}

type approvalState struct {
	requestID string
	signal    chan struct{}
}

type Manager struct {
	mu              sync.RWMutex
	jobs            map[string]*Job
	approvals       map[string]*approvalState
	approvalTimeout time.Duration
}

func NewManager(approvalTimeout time.Duration) *Manager {
	if approvalTimeout < time.Minute {
		approvalTimeout = 2 * time.Hour
	}
	return &Manager{
		jobs:            make(map[string]*Job),
		approvals:       make(map[string]*approvalState),
		approvalTimeout: approvalTimeout,
	}
}

func (m *Manager) Submit(ctx context.Context, jobType string, payload map[string]any, runner Runner) (map[string]any, error) {
	if runner == nil {
		return nil, errors.New("runner is required")
	}
	jobID, err := newID()
	if err != nil {
		return nil, err
	}
	now := time.Now().Unix()

	job := &Job{
		JobID:      jobID,
		JobType:    jobType,
		Status:     StatusQueued,
		CreatedAt:  now,
		UpdatedAt:  now,
		StartedAt:  0,
		FinishedAt: 0,
	}

	m.mu.Lock()
	m.jobs[jobID] = job
	m.mu.Unlock()

	go m.run(ctx, jobID, cloneMap(payload), runner)
	return submission{
		JobID:   jobID,
		Status:  StatusQueued,
		PollURL: fmt.Sprintf("/api/jobs/%s", jobID),
		WSURL:   fmt.Sprintf("/ws/jobs/%s", jobID),
	}.asMap(), nil
}

func (m *Manager) run(parent context.Context, jobID string, payload map[string]any, runner Runner) {
	startedAt := time.Now().Unix()
	m.mu.Lock()
	job := m.jobs[jobID]
	if job == nil {
		m.mu.Unlock()
		return
	}
	job.Status = StatusRunning
	job.StartedAt = startedAt
	job.UpdatedAt = startedAt
	m.mu.Unlock()

	ctx := parent
	if ctx == nil {
		ctx = context.Background()
	}

	result, err := runner(ctx, jobID, cloneMap(payload))
	finishedAt := time.Now().Unix()

	m.mu.Lock()
	defer m.mu.Unlock()
	job = m.jobs[jobID]
	if job == nil {
		return
	}
	if err != nil {
		job.Status = StatusFailed
		job.Error = map[string]any{"message": err.Error()}
	} else {
		job.Status = StatusSucceeded
		job.Result = cloneMap(result)
	}
	job.FinishedAt = finishedAt
	job.UpdatedAt = finishedAt
	job.ApprovalRequest = nil
	delete(m.approvals, jobID)
}

func (m *Manager) WaitForApproval(jobID string, approvalRequest map[string]any) error {
	requestID, err := newID()
	if err != nil {
		return err
	}
	state := &approvalState{
		requestID: requestID,
		signal:    make(chan struct{}),
	}

	payload := cloneMap(approvalRequest)
	payload["request_id"] = requestID
	if _, ok := payload["selected_file_count"]; !ok {
		if selected, okSelected := payload["selected_files"].([]any); okSelected {
			payload["selected_file_count"] = len(selected)
		}
	}

	now := time.Now().Unix()

	m.mu.Lock()
	job := m.jobs[jobID]
	if job == nil {
		m.mu.Unlock()
		return fmt.Errorf("job not found: %s", jobID)
	}
	job.Status = StatusWaitingForApproval
	job.ApprovalRequest = payload
	job.UpdatedAt = now
	m.approvals[jobID] = state
	m.mu.Unlock()

	timer := time.NewTimer(m.approvalTimeout)
	defer timer.Stop()

	select {
	case <-state.signal:
		return nil
	case <-timer.C:
		return fmt.Errorf("timed out waiting for manual approval for job %s", jobID)
	}
}

func (m *Manager) Proceed(jobID, requestID string) (map[string]any, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	job := m.jobs[jobID]
	if job == nil {
		return nil, fmt.Errorf("job not found: %s", jobID)
	}
	if job.Status != StatusWaitingForApproval || job.ApprovalRequest == nil {
		return nil, fmt.Errorf("job is not waiting for approval: %s", jobID)
	}

	activeRequestID, _ := job.ApprovalRequest["request_id"].(string)
	if requestID != "" && requestID != activeRequestID {
		return nil, errors.New("approval request id does not match current pending request")
	}

	state := m.approvals[jobID]
	if state == nil {
		return nil, errors.New("no pending approval signal found for job")
	}

	job.Status = StatusRunning
	job.UpdatedAt = time.Now().Unix()
	job.ApprovalRequest = nil
	close(state.signal)
	delete(m.approvals, jobID)

	return cloneMap(job.asMap()), nil
}

func (m *Manager) Get(jobID string) (map[string]any, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	job := m.jobs[jobID]
	if job == nil {
		return nil, false
	}
	return cloneMap(job.asMap()), true
}

func (m *Manager) GetPendingApproval(jobID, requestID string) (map[string]any, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	job := m.jobs[jobID]
	if job == nil {
		return nil, fmt.Errorf("job not found: %s", jobID)
	}
	if job.Status != StatusWaitingForApproval || job.ApprovalRequest == nil {
		return nil, fmt.Errorf("job is not waiting for approval: %s", jobID)
	}
	activeRequestID, _ := job.ApprovalRequest["request_id"].(string)
	if requestID != "" && requestID != activeRequestID {
		return nil, errors.New("approval request id does not match current pending request")
	}
	return cloneMap(job.ApprovalRequest), nil
}

func cloneMap(input map[string]any) map[string]any {
	if input == nil {
		return nil
	}
	raw, err := json.Marshal(input)
	if err != nil {
		out := make(map[string]any, len(input))
		for k, v := range input {
			out[k] = v
		}
		return out
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		out = make(map[string]any, len(input))
		for k, v := range input {
			out[k] = v
		}
	}
	return out
}

func newID() (string, error) {
	buffer := make([]byte, 16)
	_, err := rand.Read(buffer)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(buffer), nil
}

func (j submission) asMap() map[string]any {
	return map[string]any{
		"job_id":   j.JobID,
		"status":   j.Status,
		"poll_url": j.PollURL,
		"ws_url":   j.WSURL,
	}
}

func (j *Job) asMap() map[string]any {
	if j == nil {
		return nil
	}
	return map[string]any{
		"job_id":           j.JobID,
		"job_type":         j.JobType,
		"status":           j.Status,
		"created_at":       j.CreatedAt,
		"updated_at":       j.UpdatedAt,
		"started_at":       j.StartedAt,
		"finished_at":      j.FinishedAt,
		"result":           cloneMap(j.Result),
		"error":            cloneMap(j.Error),
		"approval_request": cloneMap(j.ApprovalRequest),
	}
}
