package scheduler

import (
	"context"
	"sync"
	"testing"
	"time"

	"log_correlation_engine/internal/autoscaling"
)

type testSettingsProvider struct {
	mu       sync.Mutex
	settings autoscaling.SchedulerSettings
}

func (p *testSettingsProvider) CurrentSchedulerSettings() autoscaling.SchedulerSettings {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.settings
}

func (p *testSettingsProvider) Set(settings autoscaling.SchedulerSettings) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.settings = settings
}

type testJob struct {
	mu       sync.Mutex
	count    int
	deadline []time.Duration
	onRun    func(run int)
}

func (j *testJob) RunCycle(ctx context.Context) error {
	j.mu.Lock()
	j.count++
	run := j.count
	if deadline, ok := ctx.Deadline(); ok {
		j.deadline = append(j.deadline, time.Until(deadline).Round(time.Millisecond))
	} else {
		j.deadline = append(j.deadline, 0)
	}
	onRun := j.onRun
	j.mu.Unlock()

	if onRun != nil {
		onRun(run)
	}
	return nil
}

func (j *testJob) Count() int {
	j.mu.Lock()
	defer j.mu.Unlock()
	return j.count
}

func (j *testJob) Deadlines() []time.Duration {
	j.mu.Lock()
	defer j.mu.Unlock()
	return append([]time.Duration(nil), j.deadline...)
}

func TestRunnerUsesUpdatedSchedulerSettingsOnLaterCycles(t *testing.T) {
	t.Parallel()

	provider := &testSettingsProvider{
		settings: autoscaling.SchedulerSettings{
			Interval:   20 * time.Millisecond,
			RunTimeout: 18 * time.Millisecond,
		},
	}
	done := make(chan struct{})
	job := &testJob{
		onRun: func(run int) {
			if run == 1 {
				provider.Set(autoscaling.SchedulerSettings{
					Interval:   10 * time.Millisecond,
					RunTimeout: 9 * time.Millisecond,
				})
				return
			}
			if run == 2 {
				close(done)
			}
		},
	}

	runner := NewRunner(Config{
		Interval:         50 * time.Millisecond,
		RunTimeout:       40 * time.Millisecond,
		Job:              job,
		SettingsProvider: provider,
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		_ = runner.Run(ctx)
	}()

	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatalf("runner did not execute two cycles in time")
	}
	cancel()

	deadlines := job.Deadlines()
	if len(deadlines) < 2 {
		t.Fatalf("expected at least 2 recorded deadlines, got %d", len(deadlines))
	}
	if deadlines[0] < 15*time.Millisecond || deadlines[0] > 30*time.Millisecond {
		t.Fatalf("expected first cycle timeout near 18ms, got %s", deadlines[0])
	}
	if deadlines[1] < 6*time.Millisecond || deadlines[1] > 20*time.Millisecond {
		t.Fatalf("expected second cycle timeout near 9ms, got %s", deadlines[1])
	}
}
