package storage

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"log_rca_engine/internal/models"
)

type FileStore struct {
	path   string
	logger *slog.Logger
}

func NewFileStore(path string, logger *slog.Logger) *FileStore {
	return &FileStore{
		path:   strings.TrimSpace(path),
		logger: logger,
	}
}

func (s *FileStore) Load(ctx context.Context) (models.RCAOutputDocument, error) {
	if err := ctx.Err(); err != nil {
		return models.RCAOutputDocument{}, err
	}
	payload, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return models.RCAOutputDocument{Items: []models.RCARecord{}}, nil
	}
	if err != nil {
		return models.RCAOutputDocument{}, fmt.Errorf("read result store file: %w", err)
	}
	if len(bytes.TrimSpace(payload)) == 0 {
		if err := s.recoverInvalidStoreFile(payload, "result store file was empty"); err != nil {
			return models.RCAOutputDocument{}, err
		}
		return models.RCAOutputDocument{Items: []models.RCARecord{}}, nil
	}

	var document models.RCAOutputDocument
	if err := json.Unmarshal(payload, &document); err != nil {
		if recoveryErr := s.recoverInvalidStoreFile(payload, fmt.Sprintf("result store JSON was invalid: %v", err)); recoveryErr != nil {
			return models.RCAOutputDocument{}, recoveryErr
		}
		return models.RCAOutputDocument{Items: []models.RCARecord{}}, nil
	}
	if document.Items == nil {
		document.Items = []models.RCARecord{}
	}
	return document, nil
}

func (s *FileStore) Save(ctx context.Context, document models.RCAOutputDocument) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	return s.writeDocument(document)
}

func (s *FileStore) writeDocument(document models.RCAOutputDocument) error {
	if strings.TrimSpace(s.path) == "" {
		return fmt.Errorf("result store path must not be empty")
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return fmt.Errorf("create result store directory: %w", err)
	}

	document.UpdatedAt = time.Now().UTC()
	document.Items = sortedItems(document.Items)
	content, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal result store document: %w", err)
	}
	content = append(content, '\n')

	tmpFile, err := os.CreateTemp(filepath.Dir(s.path), "log-rca-results-*.tmp")
	if err != nil {
		return fmt.Errorf("create result store temp file: %w", err)
	}
	tmpPath := tmpFile.Name()
	defer func() {
		_ = tmpFile.Close()
		_ = os.Remove(tmpPath)
	}()

	if _, err := tmpFile.Write(content); err != nil {
		return fmt.Errorf("write result store temp file: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		return fmt.Errorf("close result store temp file: %w", err)
	}
	if err := os.Rename(tmpPath, s.path); err != nil {
		if removeErr := os.Remove(s.path); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
			return fmt.Errorf("replace result store file: %w", err)
		}
		if retryErr := os.Rename(tmpPath, s.path); retryErr != nil {
			return fmt.Errorf("rename result store temp file: %w", retryErr)
		}
	}

	if s.logger != nil {
		s.logger.Debug("saved RCA result store", "path", s.path, "items", len(document.Items))
	}
	return nil
}

func (s *FileStore) recoverInvalidStoreFile(payload []byte, reason string) error {
	emptyDocument := models.RCAOutputDocument{Items: []models.RCARecord{}}
	trimmedPayload := bytes.TrimSpace(payload)
	if len(trimmedPayload) > 0 {
		backupPath := corruptBackupPath(s.path)
		if err := os.WriteFile(backupPath, payload, 0o644); err != nil {
			return fmt.Errorf("backup invalid result store file: %w", err)
		}
		if s.logger != nil {
			s.logger.Warn("backed up invalid RCA result store file", "path", s.path, "backup_path", backupPath, "reason", reason)
		}
	} else if s.logger != nil {
		s.logger.Warn("repairing empty RCA result store file", "path", s.path, "reason", reason)
	}

	if err := s.writeDocument(emptyDocument); err != nil {
		return fmt.Errorf("repair invalid result store file: %w", err)
	}
	return nil
}

func corruptBackupPath(path string) string {
	trimmed := strings.TrimSpace(path)
	extension := filepath.Ext(trimmed)
	base := strings.TrimSuffix(trimmed, extension)
	timestamp := time.Now().UTC().Format("20060102T150405.000000000Z")
	if extension == "" {
		return base + ".corrupt-" + timestamp
	}
	return base + ".corrupt-" + timestamp + extension
}

func ByIncident(document models.RCAOutputDocument) map[string]models.RCARecord {
	result := make(map[string]models.RCARecord, len(document.Items))
	for _, item := range document.Items {
		if strings.TrimSpace(item.IncidentID) == "" {
			continue
		}
		result[item.IncidentID] = item
	}
	return result
}

func FromIncidentMap(items map[string]models.RCARecord) models.RCAOutputDocument {
	records := make([]models.RCARecord, 0, len(items))
	for _, item := range items {
		records = append(records, item)
	}
	return models.RCAOutputDocument{Items: sortedItems(records)}
}

func sortedItems(items []models.RCARecord) []models.RCARecord {
	sorted := append([]models.RCARecord(nil), items...)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].OrganizationID != sorted[j].OrganizationID {
			return sorted[i].OrganizationID < sorted[j].OrganizationID
		}
		return sorted[i].IncidentID < sorted[j].IncidentID
	})
	return sorted
}
