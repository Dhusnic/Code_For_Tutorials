package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"runtime/debug"
	"time"
)

type Job interface {
	RunCycle(ctx context.Context) error
}

type Config struct {
	Interval   time.Duration
	RunTimeout time.Duration
	Logger     *slog.Logger
	Job        Job
}

type Runner struct {
	interval   time.Duration
	runTimeout time.Duration
	logger     *slog.Logger
	job        Job
}

func NewRunner(cfg Config) *Runner {
	return &Runner{
		interval:   cfg.Interval,
		runTimeout: cfg.RunTimeout,
		logger:     cfg.Logger,
		job:        cfg.Job,
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

	ticker := time.NewTicker(r.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			if r.logger != nil {
				r.logger.Info("scheduler stopped", "reason", ctx.Err())
			}
			return nil
		case <-ticker.C:
			r.execute(ctx)
		}
	}
}

func (r *Runner) execute(parent context.Context) {
	started := time.Now()

	runCtx := parent
	cancel := func() {}
	if r.runTimeout > 0 {
		runCtx, cancel = context.WithTimeout(parent, r.runTimeout)
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

	if err := r.job.RunCycle(runCtx); err != nil && r.logger != nil {
		r.logger.Error("scheduled job failed", "error", err)
	}
}
