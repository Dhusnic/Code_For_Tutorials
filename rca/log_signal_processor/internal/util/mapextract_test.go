package util

import (
	"testing"
	"time"
)

func TestLookupPath(t *testing.T) {
	source := map[string]any{
		"event": map[string]any{
			"organization": "org-1",
		},
	}

	value, ok := LookupPath(source, "event.organization")
	if !ok {
		t.Fatalf("expected value to be found")
	}
	if value != "org-1" {
		t.Fatalf("expected org-1, got %v", value)
	}
}

func TestParseTimestampRFC3339(t *testing.T) {
	value, err := ParseTimestamp("2026-03-17T10:21:00Z")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := time.Date(2026, 3, 17, 10, 21, 0, 0, time.UTC)
	if !value.Equal(expected) {
		t.Fatalf("expected %s, got %s", expected, value)
	}
}

func TestParseTimestampEpochMillis(t *testing.T) {
	value, err := ParseTimestamp(int64(1_773_477_660_000))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := time.UnixMilli(1_773_477_660_000).UTC()
	if !value.Equal(expected) {
		t.Fatalf("expected %s, got %s", expected, value)
	}
}
