package scheduler

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"runtime/debug"
	"time"

	"log_correlation_engine/internal/autoscaling"
)

type Job interface {
	RunCycle(ctx context.Context) error
}

type Config struct {
	Interval         time.Duration
	RunTimeout       time.Duration
	Logger           *slog.Logger
	Job              Job
	SettingsProvider SettingsProvider
}

type SettingsProvider interface {
	CurrentSchedulerSettings() autoscaling.SchedulerSettings
}

type ExecutionObserver interface {
	ObserveExecution(observation autoscaling.ExecutionObservation)
	Enabled() bool
}

type Runner struct {
	interval         time.Duration
	runTimeout       time.Duration
	logger           *slog.Logger
	job              Job
	settingsProvider SettingsProvider
}

func NewRunner(cfg Config) *Runner {
	return &Runner{
		interval:         cfg.Interval,
		runTimeout:       cfg.RunTimeout,
		logger:           cfg.Logger,
		job:              cfg.Job,
		settingsProvider: cfg.SettingsProvider,
	}
}

func (r *Runner) Run(ctx context.Context) error {
	if r.interval <= 0 {
		return fmt.Errorf("scheduler interval must be greater than zero")
	}
	if r.job == nil {
		return fmt.Errorf("scheduler job must not be nil")
	}

	r.execute(ctx)

	for {
		settings := r.currentSettings()
		timer := time.NewTimer(settings.Interval)
		select {
		case <-ctx.Done():
			timer.Stop()
			if r.logger != nil {
				r.logger.Info("scheduler stopped", "reason", ctx.Err())
			}
			return nil
		case <-timer.C:
			r.execute(ctx)
		}
	}
}

func (r *Runner) execute(parent context.Context) {
	started := time.Now()
	settings := r.currentSettings()

	runCtx := parent
	cancel := func() {}
	if settings.RunTimeout > 0 {
		runCtx, cancel = context.WithTimeout(parent, settings.RunTimeout)
	}
	defer cancel()

	var runErr error
	defer func() {
		duration := time.Since(started)
		timedOut := errors.Is(runErr, context.DeadlineExceeded) || errors.Is(runCtx.Err(), context.DeadlineExceeded)
		failed := runErr != nil
		if recovered := recover(); recovered != nil {
			failed = true
			if r.logger != nil {
				r.logger.Error(
					"scheduled job panicked",
					"panic", recovered,
					"stack", string(debug.Stack()),
					"duration", duration.String(),
				)
			}
			r.observeExecution(settings, duration, failed, timedOut)
			return
		}
		r.observeExecution(settings, duration, failed, timedOut)
		if r.logger != nil {
			r.logger.Debug("scheduled job finished", "duration", duration.String())
		}
	}()

	if r.logger != nil {
		r.logger.Debug(
			"running scheduled job",
			"effective_interval", settings.Interval.String(),
			"effective_run_timeout", settings.RunTimeout.String(),
		)
	}

	runErr = r.job.RunCycle(runCtx)
	if runErr != nil && r.logger != nil {
		r.logger.Error("scheduled job failed", "error", runErr)
	}
}

func (r *Runner) currentSettings() autoscaling.SchedulerSettings {
	settings := autoscaling.SchedulerSettings{
		Interval:   r.interval,
		RunTimeout: r.runTimeout,
	}
	if r.settingsProvider != nil {
		provided := r.settingsProvider.CurrentSchedulerSettings()
		if provided.Interval > 0 {
			settings.Interval = provided.Interval
		}
		if provided.RunTimeout > 0 {
			settings.RunTimeout = provided.RunTimeout
		}
	}
	if settings.Interval <= 0 {
		settings.Interval = time.Second
	}
	if settings.RunTimeout <= 0 || settings.RunTimeout > settings.Interval {
		settings.RunTimeout = settings.Interval
	}
	return settings
}

func (r *Runner) observeExecution(
	settings autoscaling.SchedulerSettings,
	duration time.Duration,
	failed bool,
	timedOut bool,
) {
	observer, ok := r.settingsProvider.(ExecutionObserver)
	if !ok || !observer.Enabled() {
		return
	}

	observer.ObserveExecution(autoscaling.ExecutionObservation{
		Interval:   settings.Interval,
		RunTimeout: settings.RunTimeout,
		Duration:   duration,
		Failed:     failed,
		TimedOut:   timedOut,
	})

	if r.logger != nil {
		next := r.currentSettings()
		r.logger.Info(
			"autoscaling execution observed",
			"observed_duration", duration.String(),
			"timed_out", timedOut,
			"failed", failed,
			"previous_interval", settings.Interval.String(),
			"previous_run_timeout", settings.RunTimeout.String(),
			"next_interval", next.Interval.String(),
			"next_run_timeout", next.RunTimeout.String(),
		)
	}
}
