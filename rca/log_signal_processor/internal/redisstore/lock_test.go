package redisstore

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"log_signal_processor/internal/config"
)

type fakeLockBackend struct {
	values map[string]string
}

func newFakeLockBackend() *fakeLockBackend {
	return &fakeLockBackend{
		values: make(map[string]string),
	}
}

func (f *fakeLockBackend) SetNX(_ context.Context, key string, value string, _ time.Duration) (bool, error) {
	if _, exists := f.values[key]; exists {
		return false, nil
	}
	f.values[key] = value
	return true, nil
}

func (f *fakeLockBackend) CompareAndDelete(_ context.Context, key string, expected string) (bool, error) {
	if f.values[key] != expected {
		return false, nil
	}
	delete(f.values, key)
	return true, nil
}

func TestLockerAcquireAndRelease(t *testing.T) {
	locker := NewLocker(newFakeLockBackend(), config.LockConfig{
		Key:            "Rca:collector_lock",
		TTL:            time.Minute,
		AcquireTimeout: time.Second,
	}, "worker-a", slog.New(slog.NewTextHandler(io.Discard, nil)))

	lease, acquired, err := locker.Acquire(context.Background())
	if err != nil {
		t.Fatalf("unexpected acquire error: %v", err)
	}
	if !acquired {
		t.Fatalf("expected lock acquisition")
	}
	released, err := lease.Release(context.Background())
	if err != nil {
		t.Fatalf("unexpected release error: %v", err)
	}
	if !released {
		t.Fatalf("expected lock release")
	}
}

func TestLockerAcquireContention(t *testing.T) {
	backend := newFakeLockBackend()
	lockerA := NewLocker(backend, config.LockConfig{
		Key:            "Rca:collector_lock",
		TTL:            time.Minute,
		AcquireTimeout: time.Second,
	}, "worker-a", slog.New(slog.NewTextHandler(io.Discard, nil)))
	lockerB := NewLocker(backend, config.LockConfig{
		Key:            "Rca:collector_lock",
		TTL:            time.Minute,
		AcquireTimeout: time.Second,
	}, "worker-b", slog.New(slog.NewTextHandler(io.Discard, nil)))

	if _, acquired, err := lockerA.Acquire(context.Background()); err != nil || !acquired {
		t.Fatalf("worker A should acquire the lock, err=%v acquired=%v", err, acquired)
	}
	if _, acquired, err := lockerB.Acquire(context.Background()); err != nil {
		t.Fatalf("worker B acquire returned error: %v", err)
	} else if acquired {
		t.Fatalf("worker B should not acquire the lock while it is held")
	}
}
