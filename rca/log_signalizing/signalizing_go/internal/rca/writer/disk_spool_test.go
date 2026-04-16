package writer

import (
	"strings"
	"testing"

	"rca/internal/rca/logging"
)

func TestDiskSpoolEnqueueAndDequeueRoundTrip(t *testing.T) {
	spool, err := NewDiskSpoolStore(t.TempDir(), 1024*1024, logging.GetLogger("test_disk_spool"))
	if err != nil {
		t.Fatalf("create spool: %v", err)
	}
	batch := []map[string]any{{"_index": "a", "_id": "1", "doc": map[string]any{"k": "v"}}}

	if err := spool.EnqueueBatch(batch); err != nil {
		t.Fatalf("enqueue: %v", err)
	}
	if !spool.HasPendingBatches() {
		t.Fatal("expected pending batches")
	}
	if spool.PendingBytes() <= 0 {
		t.Fatal("expected pending bytes")
	}

	loaded, err := spool.DequeueOldestBatch()
	if err != nil {
		t.Fatalf("dequeue: %v", err)
	}
	if len(loaded) != 1 || loaded[0]["_id"] != "1" {
		t.Fatalf("unexpected batch: %#v", loaded)
	}
	if spool.HasPendingBatches() {
		t.Fatal("expected empty spool")
	}
	if spool.PendingBytes() != 0 {
		t.Fatalf("expected zero pending bytes, got %d", spool.PendingBytes())
	}
}

func TestDiskSpoolRespectsCapacityLimit(t *testing.T) {
	spool, err := NewDiskSpoolStore(t.TempDir(), 32, logging.GetLogger("test_disk_spool"))
	if err != nil {
		t.Fatalf("create spool: %v", err)
	}

	if err := spool.EnqueueBatch([]map[string]any{{"big": strings.Repeat("x", 100)}}); err == nil {
		t.Fatal("expected capacity error")
	}
}
