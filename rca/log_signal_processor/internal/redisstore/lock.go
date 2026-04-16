// Package redis store provides Redis-based storage for signal logs with distributed locking support.
package redisstore

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	goredis "github.com/redis/go-redis/v9"

	"log_signal_processor/internal/config"
)

// releaseScript is a Lua script for atomic compare-and-delete of the lock.
// Ensures only the lock owner (with matching token) can release it.
//
// Script Logic:
//  1. GET KEYS[1] (the lock key)
//  2. If value == ARGV[1] (token matches owner):
//     - DEL lock key (release)
//     - Return 1 (success)
//  3. Else (token doesn't match, ownership changed):
//     - Return 0 (failure)
//
// Atomicity:
//   - Lock verification and deletion are atomic in Redis
//   - Prevents race conditions between ownership check and deletion
//   - Handles case where lock expired and new owner acquired it
//
// Token Format: "{workerID}:{nanosecond_timestamp}"
//   - Unique per acquisition attempt
//   - Timestamp for debugging and leak detection
const releaseScript = `
if redis.call("GET", KEYS[1]) == ARGV[1] then
	return redis.call("DEL", KEYS[1])
end
return 0
`

// LockBackend defines the Redis operations needed for safe distributed locking.
//
// Separation of Concerns:
//   - Abstracts Redis client for testability
//   - Enables mock implementations for testing
//   - Clear contract for lock operations
type LockBackend interface {
	// SetNX creates lock if not exists. Used to acquire lock with atomic set-and-expire.
	SetNX(ctx context.Context, key string, value string, expiration time.Duration) (bool, error)
	//CompareAndDelete atomically checks ownership and deletes lock. Used to release lock safely.
	CompareAndDelete(ctx context.Context, key string, expected string) (bool, error)
}

// RedisLockBackend implements LockBackend using go-redis/v9 client.
//
// Implementation Details:
//   - SetNX: Uses Redis SET key value NX EX ttl command
//   - CompareAndDelete: Uses Lua script for atomic compare-and-delete
//
// Thread Safety:
//   - Safe for concurrent use (go-redis client is thread-safe)
type RedisLockBackend struct {
	client goredis.UniversalClient
}

// NewLockBackend creates a Redis lock backend from a go-redis universal client.
//
// Parameters:
//   - client: go-redis UniversalClient (Cluster or Standalone)
//
// Returns:
//   - *RedisLockBackend: Ready-to-use backend
func NewLockBackend(client goredis.UniversalClient) *RedisLockBackend {
	return &RedisLockBackend{client: client}
}

// SetNX creates the lock if it does not already exist, with automatic expiration.
//
// Parameters:
//   - ctx: Context with deadline
//   - key: Lock key (typically "Rca:collector_lock")
//   - value: Token identifying lock owner
//   - expiration: TTL for automatic lock release (e.g., 90 seconds)
//
// Returns:
//   - bool: True if lock was created (acquired), false if key already exists
//   - error: Connection or timeout error
//
// Behavior:
//   - Atomic: Only succeeds if key doesn't exist
//   - Automatic expiration: Lock released if holder crashes
//   - No retry: Returns immediately (caller handles retry/backoff)
func (b *RedisLockBackend) SetNX(ctx context.Context, key string, value string, expiration time.Duration) (bool, error) {
	return b.client.SetNX(ctx, key, value, expiration).Result()
}

// CompareAndDelete atomically checks ownership and deletes the lock.
// Uses Lua script for atomic verify-and-delete (without separate read/delete).
//
// Parameters:
//   - ctx: Context with deadline
//   - key: Lock key
//   - expected: Token that must match for deletion to succeed
//
// Returns:
//   - bool: True if lock was deleted (ownership matched), false if not owner
//   - error: Connection, timeout, or script execution error
//
// Behavior:
//   - Atomic: No race between check and delete
//   - Safe: Only deletes if token matches (owns lock)
//   - Returns false if token doesn't match (lock taken by another worker)
//
// Use Cases:
//   - Normal case: Owner releases lock after cycle
//   - Expired case: Lock already deleted/expired, returns false gracefully
//   - Stolen case: Another worker acquired existing lock (timeout), returns false
func (b *RedisLockBackend) CompareAndDelete(ctx context.Context, key string, expected string) (bool, error) {
	result, err := b.client.Eval(ctx, releaseScript, []string{key}, expected).Int64()
	if err != nil {
		return false, err
	}
	return result == 1, nil
}

// Lease represents an acquired lock ownership token. Safe for single Release() call.
//
// Lifecycle:
//   - Created by Locker.Acquire() when lock successfully acquired
//   - Single Release() call to relinquish lock
//   - After Release(), lease should not be reused
//
// Thread Safety:
//   - Multiple Release() calls safe (idempotent: second call returns false)
//   - Not safe for concurrent use in general case (single caller expected)
type Lease struct {
	backend LockBackend
	key     string
	token   string
}

// Release deletes the lock only when the caller still owns it.
// Returns false if lock ownership changed (timed out) or already released.
//
// Parameters:
//   - ctx: Context with deadline (typically short, ~5s)
//
// Returns:
//   - bool: True if lock was released (still owned), false if not owned or error
//   - error: Redis connection or script execution error
//
// Behavior:
//   - Idempotent: Safe to call multiple times
//   - First call (owner): Returns (true, nil) - lock released
//   - Second call: Returns (false, nil) - already deleted, not owned
//   - Timeout case: Returns (false, nil) - another worker owns it now
//   - Error case: Returns (false, err) - connection problem
//
// Error Wrapping:
//   - Wraps errors with "release redis lock" context
//
// Best Practice:
//
//	defer func() {
//	    if lease != nil {
//	        released, err := lease.Release(ctx)
//	        if err != nil { log.Warn("release error", "err", err) }
//	        if !released { log.Warn("lock not released (ownership changed)") }
//	    }
//	}()
func (l *Lease) Release(ctx context.Context) (bool, error) {
	released, err := l.backend.CompareAndDelete(ctx, l.key, l.token)
	if err != nil {
		return false, fmt.Errorf("release redis lock: %w", err)
	}
	return released, nil
}

// Locker coordinates one-cycle leader election across PM2 workers using Redis lock.
//
// Distributed Locking:
//   - All workers attempt to acquire same key
//   - First worker succeeds (SetNX creates new key)
//   - Other workers skip cycle (return false immediately)
//   - Worker releases lock after cycle completion
//
// Workflow:
//  1. Worker calls Acquire()
//  2. If Redis SetNX succeeds: Worker is leader, runs cycle
//  3. If Redis SetNX fails: Another worker is leader, skip cycle
//  4. Leader calls Release() on Lease when done
//  5. Lock auto-expires if leader crashes (TTL enforcement)
//
// PM2 Multi-Worker Scenario:
//   - Multiple PM2 processes running same app
//   - Only 1 process runs collection per cycle
//   - Prevents duplicate collection, race conditions
//   - Automatic failover if worker dies
//
// Configuration:
//   - Key: Lock key name (auto-generated from KeyPrefix if empty)
//   - TTL: Time to hold lock (must be ≥ RunTimeout, typically 90s)
//   - AcquireTimeout: Max time to attempt lock acquisition (typically 2s)
//   - WorkerID: Generated from hostname, process name, instance number
//
// Logging:
//   - INFO: Lock acquired with TTL duration
//   - INFO: Cycle skipped because another worker holds lock
//   - ERROR delegated to caller
type Locker struct {
	backend        LockBackend
	key            string
	ttl            time.Duration
	acquireTimeout time.Duration
	workerID       string
	logger         *slog.Logger
}

// NewLocker creates a distributed Redis lock helper for multi-worker coordination.
//
// Parameters:
//   - backend: LockBackend implementation (typically from NewLockBackend)
//   - cfg: LockConfig with key, TTL, acquire timeout
//   - workerID: Unique worker identifier (e.g., "collector:host:1:1234")
//   - logger: slog.Logger for operational logging
//
// Returns:
//   - *Locker: Ready-to-use locker configured for this worker
//
// Example:
//
//	lockBackend := NewLockBackend(redisClient)
//	locker := NewLocker(
//	    lockBackend,
//	    config.LockConfig{Key: "Rca:collector_lock", TTL: 90s, AcquireTimeout: 2s},
//	    "collector:worker1:1:12345",
//	    logger,
//	)
func NewLocker(backend LockBackend, cfg config.LockConfig, workerID string, logger *slog.Logger) *Locker {
	return &Locker{
		backend:        backend,
		key:            cfg.Key,
		ttl:            cfg.TTL,
		acquireTimeout: cfg.AcquireTimeout,
		workerID:       workerID,
		logger:         logger.With("component", "redis_lock", "lock_key", cfg.Key, "worker_id", workerID),
	}
}

// Acquire attempts to acquire the cycle lock for this worker.
// Returns immediately with (nil, false, nil) if another worker holds lock.
//
// Acquisition Process:
//  1. Create token: "{workerID}:{nanosecond_timestamp}" (unique per attempt)
//  2. Call SetNX with token, key, TTL
//  3. If success: Lock acquired, return Lease
//  4. If failure: Another worker owns lock, log and return false
//
// Token Format:
//   - Format: "{workerID}:{nanosecond_timestamp}"
//   - Example: "collector:host:1:1234:1705317600123456789"
//   - Uniqueness: Nanosecond precision ensures uniqueness across retries
//   - Owner verification: Used to verify ownership during Release()
//
// Parameters:
//   - ctx: Parent context with deadline (acquireTimeout applied)
//
// Returns:
//   - *Lease: Lease for releasing lock (only if acquired=true)
//   - bool: True if lock acquired, false if another worker holds it
//   - error: Redis connection, timeout, or other errors
//
// Errors Returned:
//   - "acquire redis lock: ..." - Connection, timeout, or Redis error
//
// Behavior:
//   - No retry: Returns immediately on failure
//   - AcquireTimeout: Respects config timeout before giving up
//   - Logging: INFO on success or skip, ERROR on actual errors
//
// Example:
//
//	lease, acquired, err := locker.Acquire(ctx)
//	if err != nil { return fmt.Errorf("acquire lock: %w", err) }
//	if !acquired { return nil }  // Another worker running
//	defer lease.Release(ctx)
//
//	// Run collection cycle
//	if err := runCycle(ctx); err != nil {
//	    return err
//	}
func (l *Locker) Acquire(ctx context.Context) (*Lease, bool, error) {
	lockCtx, cancel := context.WithTimeout(ctx, l.acquireTimeout)
	defer cancel()

	token := fmt.Sprintf("%s:%d", l.workerID, time.Now().UTC().UnixNano())
	acquired, err := l.backend.SetNX(lockCtx, l.key, token, l.ttl)
	if err != nil {
		return nil, false, fmt.Errorf("acquire redis lock: %w", err)
	}
	if !acquired {
		l.logger.Info("collector cycle skipped because another worker holds the lock")
		return nil, false, nil
	}

	l.logger.Info("collector cycle lock acquired", "ttl", l.ttl.String())
	return &Lease{
		backend: l.backend,
		key:     l.key,
		token:   token,
	}, true, nil
}
