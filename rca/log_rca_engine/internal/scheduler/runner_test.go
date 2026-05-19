package scheduler

import (
	"context"
	"testing"
	"time"

	"log_rca_engine/internal/autoscaling"
)

type testJob struct {
	run func(context.Context) error
}

func (j testJob) RunCycle(ctx context.Context) error {
	if j.run != nil {
		return j.run(ctx)
	}
	return nil
}

type testSettingsProvider struct {
	settings autoscaling.SchedulerSettings
	observed []autoscaling.ExecutionObservation
}

func (p *testSettingsProvider) CurrentSchedulerSettings() autoscaling.SchedulerSettings {
	return p.settings
}

func (p *testSettingsProvider) ObserveExecution(observation autoscaling.ExecutionObservation) {
	p.observed = append(p.observed, observation)
}

func (p *testSettingsProvider) Enabled() bool {
	return true
}

func TestRunnerUsesDynamicSettingsProvider(t *testing.T) {
	provider := &testSettingsProvider{
		settings: autoscaling.SchedulerSettings{
			Interval:   20 * time.Second,
			RunTimeout: 18 * time.Second,
		},
	}

	runner := NewRunner(Config{
		Interval:         30 * time.Second,
		RunTimeout:       27 * time.Second,
		Job:              testJob{},
		SettingsProvider: provider,
	})

	settings := runner.currentSettings()
	if settings.Interval != 20*time.Second || settings.RunTimeout != 18*time.Second {
		t.Fatalf("expected provider settings to win, got %#v", settings)
	}
}

func TestRunnerObservesExecution(t *testing.T) {
	provider := &testSettingsProvider{
		settings: autoscaling.SchedulerSettings{
			Interval:   20 * time.Second,
			RunTimeout: 18 * time.Second,
		},
	}

	runner := NewRunner(Config{
		Interval:   30 * time.Second,
		RunTimeout: 27 * time.Second,
		Job: testJob{run: func(context.Context) error {
			time.Sleep(10 * time.Millisecond)
			return nil
		}},
		SettingsProvider: provider,
	})

	runner.execute(context.Background())

	if len(provider.observed) != 1 {
		t.Fatalf("expected one execution observation, got %d", len(provider.observed))
	}
	if provider.observed[0].Interval != 20*time.Second || provider.observed[0].RunTimeout != 18*time.Second {
		t.Fatalf("unexpected execution observation: %#v", provider.observed[0])
	}
	if provider.observed[0].Duration <= 0 {
		t.Fatalf("expected positive duration, got %#v", provider.observed[0])
	}
}
