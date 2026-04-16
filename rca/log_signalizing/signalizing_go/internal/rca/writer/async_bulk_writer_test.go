package writer

import (
	"sync"
	"testing"
	"time"

	"rca/internal/rca/logging"
)

func waitUntil(predicate func() bool, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if predicate() {
			return true
		}
		time.Sleep(20 * time.Millisecond)
	}
	return predicate()
}

func TestAsyncBulkWriterSpoolsWhenQueueIsSaturatedAndReplays(t *testing.T) {
	replayGate := make(chan struct{})
	var releaseOnce sync.Once
	release := func() {
		releaseOnce.Do(func() {
			close(replayGate)
		})
	}
	var mu sync.Mutex
	flushedCount := 0

	writer, err := NewAsyncBulkWriter(
		func(_ []map[string]any) error {
			mu.Lock()
			flushedCount++
			mu.Unlock()
			<-replayGate
			return nil
		},
		1,
		1,
		logging.GetLogger("test_async_bulk_writer_spool"),
		false,
		1,
		16,
		0.75,
		0.25,
		85.0,
		85.0,
		2.0,
		10.0,
		true,
		t.TempDir(),
		1024*1024,
		0.05,
		0.01,
	)
	if err != nil {
		t.Fatalf("create writer: %v", err)
	}
	defer func() {
		release()
		_ = writer.Close()
	}()

	if err := writer.Submit([]map[string]any{{"id": 1}}); err != nil {
		t.Fatalf("submit 1: %v", err)
	}
	time.Sleep(30 * time.Millisecond)
	if err := writer.Submit([]map[string]any{{"id": 2}}); err != nil {
		t.Fatalf("submit 2: %v", err)
	}
	if err := writer.Submit([]map[string]any{{"id": 3}}); err != nil {
		t.Fatalf("submit 3: %v", err)
	}

	if writer.spool == nil || !writer.spool.HasPendingBatches() {
		t.Fatal("expected spooled batch")
	}

	release()
	if err := writer.Drain(); err != nil {
		t.Fatalf("drain: %v", err)
	}

	if writer.spool.HasPendingBatches() {
		t.Fatal("expected empty spool after drain")
	}
	mu.Lock()
	count := flushedCount
	mu.Unlock()
	if count < 3 {
		t.Fatalf("expected at least 3 flushes, got %d", count)
	}
}

func TestAsyncBulkWriterAutoscaleScalesUpOnHighQueuePressure(t *testing.T) {
	releaseFlush := make(chan struct{})

	writer, err := NewAsyncBulkWriter(
		func(_ []map[string]any) error {
			<-releaseFlush
			return nil
		},
		1,
		8,
		logging.GetLogger("test_async_bulk_writer_autoscaling"),
		false,
		1,
		3,
		0.5,
		0.1,
		85.0,
		85.0,
		2.0,
		0.0,
		false,
		"",
		0,
		1.0,
		0.25,
	)
	if err != nil {
		t.Fatalf("create writer: %v", err)
	}
	defer func() {
		close(releaseFlush)
		_ = writer.Close()
	}()

	for i := 0; i < 6; i++ {
		if err := writer.Submit([]map[string]any{{"k": "v"}}); err != nil {
			t.Fatalf("submit %d: %v", i, err)
		}
	}
	before := writer.activeWorkerCount()
	writer.autoscaleMaxWorkers = 3
	writer.autoscaleMinWorkers = 1
	writer.resourcePressureHighFn = func() bool { return false }

	if err := writer.autoscaleOnce(); err != nil {
		t.Fatalf("autoscale once: %v", err)
	}

	if !waitUntil(func() bool { return writer.activeWorkerCount() > before }, 1500*time.Millisecond) {
		t.Fatalf("expected worker count to increase from %d", before)
	}
}
