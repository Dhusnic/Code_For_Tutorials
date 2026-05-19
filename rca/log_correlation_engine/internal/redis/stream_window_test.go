package redis

import (
	"testing"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

func TestDecodeSignalWindowMessageUsesSourceRCAIDAsDocID(t *testing.T) {
	message := goredis.XMessage{
		ID: "1747116169590-0",
		Values: map[string]any{
			"payload": `{"@timestamp":"2026-05-13T06:02:49.590Z","signal":"system_raid_degraded","source_rca_id":"ad0f3829-f237-43a5-bf34-3ff8af0ed642","event":{"organization":"135098068173316952064","module":"system"},"log":{"level":"critical"},"host":{"ip":"10.0.4.72","name":"localhost.localdomain"}}`,
		},
	}

	fullLog, ok, err := decodeSignalWindowMessage(message)
	if err != nil {
		t.Fatalf("decodeSignalWindowMessage returned error: %v", err)
	}
	if !ok {
		t.Fatal("expected message to decode successfully")
	}
	if fullLog.DocID != "ad0f3829-f237-43a5-bf34-3ff8af0ed642" {
		t.Fatalf("expected doc id to use source_rca_id, got %q", fullLog.DocID)
	}
	if fullLog.Signal != "system_raid_degraded" {
		t.Fatalf("expected signal to be preserved, got %q", fullLog.Signal)
	}
}

func TestDecodeSignalWindowMessageSkipsSyntheticFallbackIDs(t *testing.T) {
	message := goredis.XMessage{
		ID: "1747116169590-0",
		Values: map[string]any{
			"payload": `{"@timestamp":"2026-05-13T06:02:49.590Z","signal":"system_raid_degraded","event":{"organization":"135098068173316952064"},"log":{"level":"critical"}}`,
		},
	}

	fullLog, ok, err := decodeSignalWindowMessage(message)
	if err != nil {
		t.Fatalf("decodeSignalWindowMessage returned error: %v", err)
	}
	if ok {
		t.Fatalf("expected message without source_rca_id/doc_id/source_id to be skipped, got %#v", fullLog)
	}
	if fullLog.DocID != "" || fullLog.Signal != "" || len(fullLog.Metadata) != 0 {
		t.Fatalf("expected skipped message to leave identity fields empty, got %#v", fullLog)
	}
}

func TestSignalWindowStartIDUsesPriorMillisecond(t *testing.T) {
	since := time.Date(2026, time.May, 13, 6, 2, 49, 590000000, time.UTC)
	if got := signalWindowStartID(since); got != "1778652169589-0" {
		t.Fatalf("expected prior-millisecond stream id, got %q", got)
	}
}

func TestDecodeSignalWindowMessageHydratesCompactFieldsIntoMetadata(t *testing.T) {
	message := goredis.XMessage{
		ID: "1747116169590-0",
		Values: map[string]any{
			"payload": `{"organization_id":"org-1","host_identity":"10.0.0.12","doc_id":"doc-1","signal":"mongodb_host_unreachable","log_level":"critical","time_stamp":"2026-05-13T06:02:49.590Z","signalized_at":"2026-05-13T06:02:50.590Z"}`,
		},
	}

	fullLog, ok, err := decodeSignalWindowMessage(message)
	if err != nil {
		t.Fatalf("decodeSignalWindowMessage returned error: %v", err)
	}
	if !ok {
		t.Fatal("expected compact message to decode successfully")
	}
	if got := extractNestedString(fullLog.Metadata, "event.organization"); got != "org-1" {
		t.Fatalf("expected event.organization org-1, got %q", got)
	}
	if got := extractNestedString(fullLog.Metadata, "host.ip"); got != "10.0.0.12" {
		t.Fatalf("expected host.ip 10.0.0.12, got %q", got)
	}
	if got := extractNestedString(fullLog.Metadata, "log.level"); got != "critical" {
		t.Fatalf("expected log.level critical, got %q", got)
	}
}
