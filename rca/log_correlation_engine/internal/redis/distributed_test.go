package redis

import (
	"testing"
	"time"

	"log_correlation_engine/internal/models"
)

func TestMergeSignalLogsRedisKeepsRecentlySignalizedDelayedEvents(t *testing.T) {
	cutoff := time.Date(2026, 5, 11, 7, 0, 0, 0, time.UTC)
	delayedEventTime := cutoff.Add(-1 * time.Hour)
	recentSignalizedAt := cutoff.Add(5 * time.Minute)

	merged := mergeSignalLogsRedis(nil, []models.SignalLog{
		{
			Signal:       "signal-a",
			LogLevel:     "warning",
			DocID:        "doc-1",
			TimeStamp:    delayedEventTime,
			SignalizedAt: recentSignalizedAt,
		},
	}, cutoff)

	if len(merged) != 1 {
		t.Fatalf("expected delayed event to be retained when signalized recently, got %d entries", len(merged))
	}
	if !merged[0].TimeStamp.Equal(delayedEventTime) {
		t.Fatalf("expected original event timestamp to be preserved, got %s", merged[0].TimeStamp)
	}
	if !merged[0].SignalizedAt.Equal(recentSignalizedAt) {
		t.Fatalf("expected signalized_at to be preserved, got %s", merged[0].SignalizedAt)
	}
}
