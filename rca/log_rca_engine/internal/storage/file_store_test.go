package storage

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"log_rca_engine/internal/models"
)

func TestFileStoreSaveAndLoadRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "results.json")
	store := NewFileStore(path, nil)

	now := time.Now().UTC()
	document := models.RCAOutputDocument{
		Items: []models.RCARecord{
			{
				SchemaVersion:   1,
				IncidentID:      "incident-b",
				OrganizationID:  "org-2",
				Classification:  "probable_cause",
				ConfidenceScore: 4.2,
				UpdatedAt:       now,
			},
			{
				SchemaVersion:   1,
				IncidentID:      "incident-a",
				OrganizationID:  "org-1",
				Classification:  "confirmed_rca",
				ConfidenceScore: 8.3,
				UpdatedAt:       now,
			},
		},
	}

	if err := store.Save(context.Background(), document); err != nil {
		t.Fatalf("save returned error: %v", err)
	}

	loaded, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load returned error: %v", err)
	}
	if len(loaded.Items) != 2 {
		t.Fatalf("expected 2 items, got %d", len(loaded.Items))
	}
	if loaded.Items[0].IncidentID != "incident-a" {
		t.Fatalf("expected sorted items, got %#v", loaded.Items)
	}
}

func TestFileStoreKeepsClosedRecords(t *testing.T) {
	path := filepath.Join(t.TempDir(), "results.json")
	store := NewFileStore(path, nil)

	document := models.RCAOutputDocument{
		Items: []models.RCARecord{
			{IncidentID: "incident-open", Status: "open"},
			{IncidentID: "incident-updated", Status: "updated"},
			{IncidentID: "incident-closed", Status: "closed"},
		},
	}

	if err := store.Save(context.Background(), document); err != nil {
		t.Fatalf("save returned error: %v", err)
	}

	loaded, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load returned error: %v", err)
	}
	if len(loaded.Items) != 3 {
		t.Fatalf("expected all lifecycle items, got %#v", loaded.Items)
	}
	foundClosed := false
	for _, item := range loaded.Items {
		if item.Status == "closed" {
			foundClosed = true
		}
	}
	if !foundClosed {
		t.Fatalf("expected closed record to stay in result store: %#v", loaded.Items)
	}
}

func TestFileStoreLoadRepairsEmptyFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "results.json")
	if err := os.WriteFile(path, []byte{}, 0o644); err != nil {
		t.Fatalf("write empty file: %v", err)
	}

	store := NewFileStore(path, nil)
	loaded, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load returned error: %v", err)
	}
	if len(loaded.Items) != 0 {
		t.Fatalf("expected empty items, got %#v", loaded.Items)
	}

	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read repaired file: %v", err)
	}
	if string(payload) == "" {
		t.Fatal("expected repaired file to contain valid JSON")
	}
}

func TestFileStoreLoadBacksUpAndRepairsInvalidJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "results.json")
	if err := os.WriteFile(path, []byte("{invalid"), 0o644); err != nil {
		t.Fatalf("write invalid file: %v", err)
	}

	store := NewFileStore(path, nil)
	loaded, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load returned error: %v", err)
	}
	if len(loaded.Items) != 0 {
		t.Fatalf("expected empty items after repair, got %#v", loaded.Items)
	}

	backups, err := filepath.Glob(filepath.Join(dir, "results.corrupt-*.json"))
	if err != nil {
		t.Fatalf("glob backup files: %v", err)
	}
	if len(backups) != 1 {
		t.Fatalf("expected one backup file, got %d", len(backups))
	}
	backupPayload, err := os.ReadFile(backups[0])
	if err != nil {
		t.Fatalf("read backup file: %v", err)
	}
	if string(backupPayload) != "{invalid" {
		t.Fatalf("expected invalid content to be preserved, got %q", string(backupPayload))
	}
}
