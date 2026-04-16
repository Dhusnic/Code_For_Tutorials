// Package scheduler provides periodic execution of collection cycles with panic recovery.
//
// Scheduler Workflow:
//  1. Run() starts immediately with first job execution
//  2. Sets up ticker with configured interval
//  3. Waits for each tick or context cancellation
//  4. Executes job with runTimeout protection
//  5. Logs completion/error/panic for each cycle
//  6. Continues until context is Done
//
// Error Handling:
//   - Panic recovery: Global panic handler with stack trace logging
//   - Context cancellation: Graceful shutdown on ctx.Done()
//   - Job errors: Logged as ERROR, scheduler continues
//   - Timeout protection: runTimeout cancels individual cycles
package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"runtime/debug"
	"time"
)

// Job represents the unit of scheduled work executed repeatedly by the Runner.
//
// Responsibility:
//   - Implement collection cycle (fetch, normalize, merge, store)
//   - Handle all errors gracefully
//   - Respect context deadline/cancellation
//   - Return error if cycle failed, nil if successful
//
// Typical Implementation:
//   - Collector.RunCycle() from service package
//   - Should check context.Err() periodically for cancellation
//
// Thread Safety:
//   - Single-threaded execution (called sequentially by Runner)
//   - Not safe for concurrent calls from multiple runners
type Job interface {
	RunCycle(ctx context.Context) error
}

// Config stores runner configuration for periodic job execution.
//
// Fields:
//   - Interval: Time between job executions (e.g., 1 minute)
//   - RunTimeout: Maximum time allowed per job execution (e.g., 50 seconds)
//   - Logger: slog.Logger for operational logging
//   - Job: Job implementation to execute (typically Collector)
//
// Validation:
//   - Interval must be > 0 (checked in Runner.Run)
//   - RunTimeout should be < Interval (scheduler determines, not enforced)
//   - Logger must not be nil (panics if nil)
//   - Job must not be nil (checked in Runner.Run)
type Config struct {
	Interval   time.Duration
	RunTimeout time.Duration
	Logger     *slog.Logger
	Job        Job
}

// Runner executes a job on a fixed interval with panic recovery and logging.
//
// Execution Model:
//   - Fixed-interval scheduling: Waits full interval between cycles (not adjusted for job duration)
//   - If job takes 45s with 60s interval: Next cycle starts 60s after previous start
//   - Panic recovery: Protects event loop from job crashes
//   - Graceful shutdown: Responds to context cancellation
//
// Logging:
//   - DEBUG: Job finished with duration (always)
//   - ERROR: Job failed with error (job returned error)
//   - ERROR: Job panicked with panic value and stack (job crashed)
//   - INFO: Scheduler stopped with reason (context cancellation)
//
// Timeout Behavior:
//   - If runTimeout ≤ 0: No timeout (job runs as long as needed)
//   - If runTimeout > 0: Job deadline = time.Now() + runTimeout
//   - Timeout enforces: If job exceeds deadline, runCtx.Done() becomes readable
//   - Job responsibility: Check runCtx.Done() periodically
//
// Thread Safety:
//   - Not thread-safe: Designed for single-threaded Start()
//   - Do not call Run() concurrently with same Runner instance
type Runner struct {
	interval   time.Duration
	runTimeout time.Duration
	logger     *slog.Logger
	job        Job
}

// NewRunner creates a scheduler runner with configuration.
//
// Parameters:
//   - cfg: Config with interval, timeout, logger, and job
//
// Returns:
//   - *Runner: Runner ready to call Run()
//
// Example:
//
//	runner := NewRunner(Config{
//	    Interval: 1 * time.Minute,
//	    RunTimeout: 50 * time.Second,
//	    Logger: logger,
//	    Job: collector,
//	})
//	go runner.Run(ctx)  // Start in goroutine
func NewRunner(cfg Config) *Runner {
	return &Runner{
		interval:   cfg.Interval,
		runTimeout: cfg.RunTimeout,
		logger:     cfg.Logger,
		job:        cfg.Job,
	}
}

// Run executes the job immediately, then repeatedly on interval until context cancellation.
//
// Execution Sequence:
//  1. Validate: Interval > 0, Job != nil (returns error if not)
//  2. Execute: Run job immediately (no wait)
//  3. Initialize: Create ticker with configured interval
//  4. Loop: Wait for ticker or context.Done()
//  5. On tick: Execute job with timeout protection
//  6. On cancel: Log shutdown reason and return nil
//
// Panic Handling:
//   - Defer catches panic in job execution
//   - Logs panic with value and full stack trace
//   - Continues event loop (does not crash scheduler)
//
// Parameters:
//   - ctx: Context for cancellation control (usually from app lifecycle)
//
// Returns:
//   - error: Configuration validation error (happens before loop starts)
//   - nil: Normal graceful shutdown via context cancellation
//
// Errors Returned:
//   - "scheduler interval must be > zero" - Interval not positive
//   - "scheduler job must not be nil" - Job not configured
//
// Example (typical usage):
//
//	ctx, cancel := context.WithCancel(context.Background())
//	go runner.Run(ctx)
//	// ... later, to stop:
//	cancel()
//	<-done  // Wait for Run() to return
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
			r.logger.Info("scheduler stopped", "reason", ctx.Err())
			return nil
		case <-ticker.C:
			r.execute(ctx)
		}
	}
}

// execute runs one job cycle with timeout, panic recovery, and logging.
//
// Execution Steps:
//  1. Record start time
//  2. Create runCtx: WithTimeout if runTimeout > 0, else use parent
//  3. Defer: Cancel context, log completion
//  4. Panic recovery: Log panic value and stack trace
//  5. Call: job.RunCycle(runCtx)
//  6. Log: Error if job returned error, DEBUG if successful
//
// Logging Levels:
//   - ERROR: "scheduled job panicked" (also logs stack trace and duration)
//   - ERROR: "scheduled job failed" (also logs error details)
//   - DEBUG: "scheduled job finished" (includes duration)
//
// Timeout Mechanism:
//   - If runTimeout ≤ 0: No timeout (runCtx == parent context)
//   - If runTimeout > 0: runCtx deadline = now + runTimeout
//   - Job should respect context deadline
//   - Runner doesn't force kill, relies on job checking ctx.Done()
//
// Duration Tracking:
//   - Measured from execute() start to defer execution
//   - Includes job execution time + any logging overhead
//   - Always logged in job finished/panicked/failed messages
//
// Parameters:
//   - parent: Parent context for timeout derivation
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
			r.logger.Error("scheduled job panicked", "panic", recovered, "stack", string(debug.Stack()), "duration", duration.String())
			return
		}
		r.logger.Debug("scheduled job finished", "duration", duration.String())
	}()

	if err := r.job.RunCycle(runCtx); err != nil {
		r.logger.Error("scheduled job failed", "error", err)
	}
}
