package scheduler

import (
	"context"
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

	defer func() {
		duration := time.Since(started)
		if recovered := recover(); recovered != nil {
			if r.logger != nil {
				r.logger.Error(
					"scheduled job panicked",
					"panic", recovered,
					"stack", string(debug.Stack()),
					"duration", duration.String(),
				)
			}
			return
		}
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

	if err := r.job.RunCycle(runCtx); err != nil && r.logger != nil {
		r.logger.Error("scheduled job failed", "error", err)
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
