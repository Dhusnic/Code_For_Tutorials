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

	"log_rca_engine/internal/models"
)

type Store struct {
	path   string
	logger *slog.Logger
}

func NewStore(path string, logger *slog.Logger) *Store {
	return &Store{
		path:   strings.TrimSpace(path),
		logger: logger,
	}
}

func (s *Store) Load(ctx context.Context) (models.ReaderCheckpoint, error) {
	if err := ctx.Err(); err != nil {
		return models.ReaderCheckpoint{}, err
	}
	payload, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return models.ReaderCheckpoint{}, nil
	}
	if err != nil {
		return models.ReaderCheckpoint{}, fmt.Errorf("read checkpoint file: %w", err)
	}

	var checkpoint models.ReaderCheckpoint
	if err := json.Unmarshal(payload, &checkpoint); err != nil {
		return models.ReaderCheckpoint{}, fmt.Errorf("decode checkpoint file: %w", err)
	}
	return checkpoint, nil
}

func (s *Store) Save(ctx context.Context, checkpoint models.ReaderCheckpoint) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(s.path) == "" {
		return fmt.Errorf("checkpoint path must not be empty")
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return fmt.Errorf("create checkpoint directory: %w", err)
	}

	checkpoint.UpdatedAt = time.Now().UTC()
	content, err := json.MarshalIndent(checkpoint, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal checkpoint: %w", err)
	}
	content = append(content, '\n')

	tmpFile, err := os.CreateTemp(filepath.Dir(s.path), "log-rca-checkpoint-*.tmp")
	if err != nil {
		return fmt.Errorf("create checkpoint temp file: %w", err)
	}
	tmpPath := tmpFile.Name()
	defer func() {
		_ = tmpFile.Close()
		_ = os.Remove(tmpPath)
	}()

	if _, err := tmpFile.Write(content); err != nil {
		return fmt.Errorf("write checkpoint temp file: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		return fmt.Errorf("close checkpoint temp file: %w", err)
	}
	if err := os.Rename(tmpPath, s.path); err != nil {
		if removeErr := os.Remove(s.path); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
			return fmt.Errorf("replace checkpoint file: %w", err)
		}
		if retryErr := os.Rename(tmpPath, s.path); retryErr != nil {
			return fmt.Errorf("rename checkpoint temp file: %w", retryErr)
		}
	}

	if s.logger != nil {
		s.logger.Debug("saved checkpoint", "path", s.path)
	}
	return nil
}
