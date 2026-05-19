package ingest

import (
	"testing"

	"github.com/segmentio/kafka-go"

	"rca/internal/rca/config"
)

func TestDecodeKafkaMessageUsesExistingSourceRCAID(t *testing.T) {
	cfg := config.KafkaConfig{
		MetadataField:      "kafka",
		EventOriginalField: "event.original",
		SourceIndex:        "linux-logs",
		DocumentIDPrefix:   "kafka",
	}

	msg := kafka.Message{
		Topic:     "linux-logs",
		Partition: 2,
		Offset:    42,
		Value:     []byte(`{"source_rca_id":"rca-123","message":"hello"}`),
	}

	decoded := decodeKafkaMessage(msg, cfg)

	if decoded.SourceID != "rca-123" {
		t.Fatalf("expected source id rca-123, got %q", decoded.SourceID)
	}
	if decoded.Event["source_rca_id"] != "rca-123" {
		t.Fatalf("expected event source_rca_id rca-123, got %#v", decoded.Event["source_rca_id"])
	}
	if _, exists := decoded.Event["source_id"]; exists {
		t.Fatalf("expected legacy source_id field to be absent, got %#v", decoded.Event["source_id"])
	}
}

func TestDecodeKafkaMessageFallsBackToDerivedSourceRCAID(t *testing.T) {
	cfg := config.KafkaConfig{
		MetadataField:      "kafka",
		EventOriginalField: "event.original",
		SourceIndex:        "linux-logs",
		DocumentIDPrefix:   "kafka",
	}

	msg := kafka.Message{
		Topic:     "linux-logs",
		Partition: 2,
		Offset:    42,
		Value:     []byte(`{"message":"hello"}`),
	}

	decoded := decodeKafkaMessage(msg, cfg)

	if decoded.SourceID != "kafka:linux-logs:2:42" {
		t.Fatalf("expected derived source id, got %q", decoded.SourceID)
	}
	if decoded.Event["source_rca_id"] != "kafka:linux-logs:2:42" {
		t.Fatalf("expected derived event source_rca_id, got %#v", decoded.Event["source_rca_id"])
	}
}

func TestDecodeKafkaMessageUsesConfiguredSourceIndexField(t *testing.T) {
	cfg := config.KafkaConfig{
		MetadataField:      "kafka",
		EventOriginalField: "event.original",
		SourceIndex:        "linux-logs",
		SourceIndexField:   "source_rca_index",
		DocumentIDPrefix:   "kafka",
	}

	msg := kafka.Message{
		Topic:     "linux-logs",
		Partition: 1,
		Offset:    7,
		Value:     []byte(`{"source_rca_id":"rca-777","source_rca_index":"linux-2026.05.14","message":"hello"}`),
	}

	decoded := decodeKafkaMessage(msg, cfg)

	if decoded.SourceIndex != "linux-2026.05.14" {
		t.Fatalf("expected source index linux-2026.05.14, got %q", decoded.SourceIndex)
	}
	if decoded.SourceID != "rca-777" {
		t.Fatalf("expected source id rca-777, got %q", decoded.SourceID)
	}
}
