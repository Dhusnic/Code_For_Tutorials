package checkpoint

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"

	"log_correlation_engine/internal/models"
)

type Store struct {
	directory string
	keyPrefix string
	logger    *slog.Logger
}

type filePayload struct {
	Key                    string `json:"key"`
	OrganizationID         string `json:"organization_id"`
	Checkpoint             string `json:"checkpoint,omitempty"`
	CheckpointDocID        string `json:"checkpoint_doc_id,omitempty"`
	SignalPayloadSignature string `json:"signal_payload_signature,omitempty"`
	RulesSignature         string `json:"rules_signature,omitempty"`
	SignalCount            int    `json:"signal_count,omitempty"`
	StreamID               string `json:"stream_id,omitempty"`
	UpdatedAt              string `json:"updated_at"`
}

func NewStore(directory, keyPrefix string, logger *slog.Logger) *Store {
	return &Store{
		directory: strings.TrimSpace(directory),
		keyPrefix: strings.TrimSuffix(strings.TrimSpace(keyPrefix), ":"),
		logger:    logger,
	}
}

func (s *Store) CheckpointKey(organization string) string {
	return fmt.Sprintf("%s:%s:correlation_checkpoint", s.keyPrefix, organization)
}

func (s *Store) LoadCheckpoint(ctx context.Context, organization string) (models.ProcessingCheckpoint, error) {
	if err := ctx.Err(); err != nil {
		return models.ProcessingCheckpoint{}, err
	}

	path := s.filePath(organization)
	payload, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return models.ProcessingCheckpoint{}, nil
	}
	if err != nil {
		return models.ProcessingCheckpoint{}, fmt.Errorf("read checkpoint file for organization %s: %w", organization, err)
	}

	var stored filePayload
	if err := json.Unmarshal(payload, &stored); err != nil {
		return models.ProcessingCheckpoint{}, fmt.Errorf("decode checkpoint file for organization %s: %w", organization, err)
	}

	state := models.ProcessingCheckpoint{
		CheckpointDocID:        strings.TrimSpace(stored.CheckpointDocID),
		SignalPayloadSignature: strings.TrimSpace(stored.SignalPayloadSignature),
		RulesSignature:         strings.TrimSpace(stored.RulesSignature),
		SignalCount:            stored.SignalCount,
		StreamID:               strings.TrimSpace(stored.StreamID),
	}

	if strings.TrimSpace(stored.Checkpoint) != "" {
		checkpoint, err := time.Parse(time.RFC3339Nano, stored.Checkpoint)
		if err != nil {
			return models.ProcessingCheckpoint{}, fmt.Errorf("parse checkpoint file timestamp for organization %s: %w", organization, err)
		}
		state.Checkpoint = checkpoint.UTC()
	}
	return state, nil
}

func (s *Store) SaveCheckpoint(ctx context.Context, organization string, checkpoint models.ProcessingCheckpoint) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if checkpoint.Checkpoint.IsZero() && checkpoint.SignalPayloadSignature == "" && checkpoint.SignalCount == 0 {
		return nil
	}

	if err := os.MkdirAll(s.directory, 0o755); err != nil {
		return fmt.Errorf("create checkpoint directory %s: %w", s.directory, err)
	}

	now := time.Now().UTC()
	content, err := json.MarshalIndent(filePayload{
		Key:                    s.CheckpointKey(organization),
		OrganizationID:         organization,
		Checkpoint:             formatCheckpointTime(checkpoint.Checkpoint),
		CheckpointDocID:        strings.TrimSpace(checkpoint.CheckpointDocID),
		SignalPayloadSignature: checkpoint.SignalPayloadSignature,
		RulesSignature:         checkpoint.RulesSignature,
		SignalCount:            checkpoint.SignalCount,
		StreamID:               strings.TrimSpace(checkpoint.StreamID),
		UpdatedAt:              now.Format(time.RFC3339Nano),
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal checkpoint file for organization %s: %w", organization, err)
	}
	content = append(content, '\n')

	target := s.filePath(organization)
	tmpFile, err := os.CreateTemp(s.directory, "checkpoint-*.tmp")
	if err != nil {
		return fmt.Errorf("create checkpoint temp file for organization %s: %w", organization, err)
	}
	tmpPath := tmpFile.Name()
	defer func() {
		_ = tmpFile.Close()
		_ = os.Remove(tmpPath)
	}()

	if _, err := tmpFile.Write(content); err != nil {
		return fmt.Errorf("write checkpoint temp file for organization %s: %w", organization, err)
	}
	if err := tmpFile.Close(); err != nil {
		return fmt.Errorf("close checkpoint temp file for organization %s: %w", organization, err)
	}

	if err := os.Rename(tmpPath, target); err != nil {
		if removeErr := os.Remove(target); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
			return fmt.Errorf("replace checkpoint file for organization %s: %w", organization, err)
		}
		if retryErr := os.Rename(tmpPath, target); retryErr != nil {
			return fmt.Errorf("rename checkpoint temp file for organization %s: %w", organization, retryErr)
		}
	}

	if s.logger != nil {
		s.logger.Debug(
			"saved checkpoint file",
			"organization", organization,
			"checkpoint_key", s.CheckpointKey(organization),
			"path", target,
		)
	}
	return nil
}

func formatCheckpointTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339Nano)
}

func (s *Store) filePath(organization string) string {
	filename := sanitizeFilename(s.CheckpointKey(organization)) + ".json"
	return filepath.Join(s.directory, filename)
}

func sanitizeFilename(value string) string {
	replacer := strings.NewReplacer(
		"<", "_",
		">", "_",
		":", "_",
		"\"", "_",
		"/", "_",
		"\\", "_",
		"|", "_",
		"?", "_",
		"*", "_",
	)
	sanitized := replacer.Replace(strings.TrimSpace(value))
	sanitized = strings.Trim(sanitized, ". ")
	if sanitized == "" {
		return "correlation_checkpoint"
	}
	return sanitized
}
