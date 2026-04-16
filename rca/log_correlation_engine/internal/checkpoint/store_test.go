package checkpoint

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"log_correlation_engine/internal/models"
)

func TestStoreSaveAndLoadCheckpoint(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	store := NewStore(dir, "Rca", nil)
	want := time.Date(2026, 4, 8, 12, 30, 0, 0, time.UTC)
	state := models.ProcessingCheckpoint{
		Checkpoint:             want,
		SignalPayloadSignature: "abc123",
		SignalCount:            4,
		StreamID:               "1678901234567-0",
	}

	if err := store.SaveCheckpoint(context.Background(), "135098068173316952064", state); err != nil {
		t.Fatalf("save checkpoint returned error: %v", err)
	}

	got, err := store.LoadCheckpoint(context.Background(), "135098068173316952064")
	if err != nil {
		t.Fatalf("load checkpoint returned error: %v", err)
	}
	if !got.Checkpoint.Equal(want) {
		t.Fatalf("expected checkpoint %s, got %s", want, got.Checkpoint)
	}
	if got.SignalPayloadSignature != state.SignalPayloadSignature {
		t.Fatalf("expected signature %q, got %q", state.SignalPayloadSignature, got.SignalPayloadSignature)
	}
	if got.SignalCount != state.SignalCount {
		t.Fatalf("expected signal count %d, got %d", state.SignalCount, got.SignalCount)
	}
	if got.StreamID != state.StreamID {
		t.Fatalf("expected stream id %q, got %q", state.StreamID, got.StreamID)
	}
}

func TestStoreWritesJSONFileWithCheckpointKey(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	store := NewStore(dir, "Rca", nil)
	organization := "135098068173316952064"
	checkpoint := time.Date(2026, 4, 8, 12, 31, 0, 0, time.UTC)
	state := models.ProcessingCheckpoint{
		Checkpoint:             checkpoint,
		SignalPayloadSignature: "deadbeef",
		SignalCount:            7,
		StreamID:               "42-1",
	}

	if err := store.SaveCheckpoint(context.Background(), organization, state); err != nil {
		t.Fatalf("save checkpoint returned error: %v", err)
	}

	files, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read dir returned error: %v", err)
	}
	if len(files) != 1 {
		t.Fatalf("expected 1 checkpoint file, got %d", len(files))
	}

	payload, err := os.ReadFile(filepath.Join(dir, files[0].Name()))
	if err != nil {
		t.Fatalf("read checkpoint file returned error: %v", err)
	}

	var stored filePayload
	if err := json.Unmarshal(payload, &stored); err != nil {
		t.Fatalf("decode checkpoint file returned error: %v", err)
	}

	if stored.Key != "Rca:135098068173316952064:correlation_checkpoint" {
		t.Fatalf("unexpected checkpoint key %q", stored.Key)
	}
	if stored.OrganizationID != organization {
		t.Fatalf("unexpected organization id %q", stored.OrganizationID)
	}
	if stored.Checkpoint != checkpoint.Format(time.RFC3339Nano) {
		t.Fatalf("unexpected checkpoint value %q", stored.Checkpoint)
	}
	if stored.SignalPayloadSignature != state.SignalPayloadSignature {
		t.Fatalf("unexpected stored signature %q", stored.SignalPayloadSignature)
	}
	if stored.SignalCount != state.SignalCount {
		t.Fatalf("unexpected stored signal count %d", stored.SignalCount)
	}
	if stored.StreamID != state.StreamID {
		t.Fatalf("unexpected stored stream id %q", stored.StreamID)
	}
}
