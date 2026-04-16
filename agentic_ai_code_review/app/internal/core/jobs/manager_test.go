package jobs

import (
	"context"
	"testing"
	"time"
)

func TestSubmitAndGetJob(t *testing.T) {
	t.Parallel()

	manager := NewManager(2 * time.Minute)
	submission, err := manager.Submit(context.Background(), "unit-test", map[string]any{
		"value": "x",
	}, func(_ context.Context, _ string, payload map[string]any) (map[string]any, error) {
		return map[string]any{
			"echo": payload["value"],
		}, nil
	})
	if err != nil {
		t.Fatalf("submit failed: %v", err)
	}

	jobID := submission["job_id"].(string)
	if jobID == "" {
		t.Fatal("job_id should not be empty")
	}

	var final map[string]any
	for i := 0; i < 20; i++ {
		current, ok := manager.Get(jobID)
		if !ok {
			t.Fatalf("job missing: %s", jobID)
		}
		if current["status"] == StatusSucceeded {
			final = current
			break
		}
		time.Sleep(30 * time.Millisecond)
	}
	if final == nil {
		t.Fatalf("job did not finish in time")
	}
}

func TestWaitForApprovalAndProceed(t *testing.T) {
	t.Parallel()

	manager := NewManager(2 * time.Minute)
	submission, err := manager.Submit(context.Background(), "approval-flow", map[string]any{}, func(_ context.Context, jobID string, _ map[string]any) (map[string]any, error) {
		waitErr := manager.WaitForApproval(jobID, map[string]any{
			"source_branch": "feature/demo",
			"target_branch": "main",
		})
		if waitErr != nil {
			return nil, waitErr
		}
		return map[string]any{"ok": true}, nil
	})
	if err != nil {
		t.Fatalf("submit failed: %v", err)
	}

	jobID := submission["job_id"].(string)

	var requestID string
	for i := 0; i < 30; i++ {
		current, ok := manager.Get(jobID)
		if !ok {
			t.Fatalf("job missing: %s", jobID)
		}
		if current["status"] == StatusWaitingForApproval {
			approval := current["approval_request"].(map[string]any)
			requestID, _ = approval["request_id"].(string)
			break
		}
		time.Sleep(30 * time.Millisecond)
	}
	if requestID == "" {
		t.Fatal("did not receive approval request id")
	}

	_, proceedErr := manager.Proceed(jobID, requestID)
	if proceedErr != nil {
		t.Fatalf("proceed failed: %v", proceedErr)
	}

	for i := 0; i < 30; i++ {
		current, ok := manager.Get(jobID)
		if !ok {
			t.Fatalf("job missing: %s", jobID)
		}
		if current["status"] == StatusSucceeded {
			return
		}
		time.Sleep(30 * time.Millisecond)
	}
	t.Fatal("job did not finish after approval")
}
