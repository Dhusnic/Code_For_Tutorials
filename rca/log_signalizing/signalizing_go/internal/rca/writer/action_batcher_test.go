package writer

import (
	"strings"
	"testing"
)

func TestActionBatcherFlushesOnActionCountLimit(t *testing.T) {
	batcher := NewActionBatcher(2, 10000)

	if flushed := batcher.Add(map[string]any{"a": 1}); flushed != nil {
		t.Fatal("expected nil flush after first action")
	}
	flushed := batcher.Add(map[string]any{"b": 2})
	if len(flushed) != 2 {
		t.Fatalf("expected 2 flushed actions, got %d", len(flushed))
	}
	if remaining := batcher.FlushRemaining(); remaining != nil {
		t.Fatal("expected no remaining actions")
	}
}

func TestActionBatcherFlushesOnByteLimit(t *testing.T) {
	batcher := NewActionBatcher(100, 80)

	if flushed := batcher.Add(map[string]any{"message": strings.Repeat("x", 30)}); flushed != nil {
		t.Fatal("expected no flush yet")
	}
	flushed := batcher.Add(map[string]any{"message": strings.Repeat("y", 40)})
	if len(flushed) != 1 {
		t.Fatalf("expected first action to flush, got %d", len(flushed))
	}

	remaining := batcher.FlushRemaining()
	if len(remaining) != 1 {
		t.Fatalf("expected one remaining action, got %d", len(remaining))
	}
}
