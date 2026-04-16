package writer

import (
	"encoding/json"
	"fmt"
)

// BatcherStats stores runtime stats for one batcher.
type BatcherStats struct {
	FlushedBatches int
	FlushedActions int
	FlushedBytes   int
}

// ActionBatcher accumulates actions until count or byte thresholds are hit.
type ActionBatcher struct {
	maxActions int
	maxBytes   int
	actions    []map[string]any
	bytes      int
	stats      BatcherStats
}

// NewActionBatcher constructs one batch accumulator.
func NewActionBatcher(maxActions int, maxBytes int) *ActionBatcher {
	if maxActions < 1 {
		maxActions = 1
	}
	if maxBytes < 1 {
		maxBytes = 1
	}
	return &ActionBatcher{
		maxActions: maxActions,
		maxBytes:   maxBytes,
		actions:    make([]map[string]any, 0),
	}
}

// Stats returns flush counters for the batcher.
func (b *ActionBatcher) Stats() BatcherStats {
	return b.stats
}

// Add adds one action and returns a flushed batch when a threshold is crossed.
func (b *ActionBatcher) Add(action map[string]any) []map[string]any {
	actionSize := estimateActionSize(action)

	shouldFlushBeforeAdd := len(b.actions) > 0 && (len(b.actions) >= b.maxActions || b.bytes+actionSize > b.maxBytes)
	if shouldFlushBeforeAdd {
		flushed := b.flushInternal()
		b.actions = append(b.actions, action)
		b.bytes += actionSize
		return flushed
	}

	b.actions = append(b.actions, action)
	b.bytes += actionSize
	if len(b.actions) >= b.maxActions || b.bytes >= b.maxBytes {
		return b.flushInternal()
	}
	return nil
}

// FlushRemaining flushes the remaining in-memory actions.
func (b *ActionBatcher) FlushRemaining() []map[string]any {
	if len(b.actions) == 0 {
		return nil
	}
	return b.flushInternal()
}

func (b *ActionBatcher) flushInternal() []map[string]any {
	actions := b.actions
	size := b.bytes
	b.actions = make([]map[string]any, 0)
	b.bytes = 0

	b.stats.FlushedBatches++
	b.stats.FlushedActions += len(actions)
	b.stats.FlushedBytes += size
	return actions
}

func estimateActionSize(action map[string]any) int {
	encoded, err := json.Marshal(action)
	if err != nil {
		return len([]byte(fmt.Sprint(action)))
	}
	return len(encoded)
}
