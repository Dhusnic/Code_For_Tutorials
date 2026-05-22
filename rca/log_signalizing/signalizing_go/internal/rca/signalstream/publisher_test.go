package signalstream

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestSignalStreamEventMarshalOmitsNonRedisFields(t *testing.T) {
	event := Event{
		OrganizationID: "org-1",
		HostIdentity:   "10.0.0.12",
		DocID:          "doc-1",
		Signal:         "mongodb_host_unreachable",
		LogLevel:       "critical",
		TimeStamp:      time.Date(2026, 5, 13, 10, 0, 0, 0, time.UTC),
		SignalizedAt:   time.Date(2026, 5, 13, 10, 0, 1, 0, time.UTC),
		SourceIndex:    "linux-logs",
	}

	payload, err := json.Marshal(event)
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}

	text := string(payload)
	for _, omitted := range []string{`"source_index"`, `"source_id"`} {
		if strings.Contains(text, omitted) {
			t.Fatalf("expected compact redis payload to omit %s, got %s", omitted, text)
		}
	}
}

func TestBuildDedupKeyUsesOnlyDocIDAndSignal(t *testing.T) {
	publisher := &Publisher{dedupKeyPrefix: "Rca:signal_stream:dedupe:"}

	first := publisher.buildDedupKey(Event{
		OrganizationID: "org-1",
		HostIdentity:   "10.0.0.12",
		DocID:          "rca-123",
		Signal:         "mongodb_host_unreachable",
		SourceIndex:    "linux-2026.05.14",
	})
	second := publisher.buildDedupKey(Event{
		OrganizationID: "org-2",
		HostIdentity:   "10.0.0.99",
		DocID:          "rca-123",
		Signal:         "mongodb_host_unreachable",
		SourceIndex:    "linux-2026.05.15",
	})
	third := publisher.buildDedupKey(Event{
		OrganizationID: "org-1",
		DocID:          "rca-123",
		Signal:         "mongodb_auth_failed",
		SourceIndex:    "linux-2026.05.14",
	})

	if first != second {
		t.Fatalf("expected dedupe key to ignore organization/source index, got %q and %q", first, second)
	}
	if first == third {
		t.Fatalf("expected different signal to produce a different dedupe key, got %q", first)
	}
}
