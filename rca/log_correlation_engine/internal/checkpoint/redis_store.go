package checkpoint

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"log_correlation_engine/internal/models"

	goredis "github.com/redis/go-redis/v9"
)

type RedisStore struct {
	client    goredis.UniversalClient
	keyPrefix string
	logger    *slog.Logger
}

type redisPayload struct {
	Key                    string `json:"key"`
	Checkpoint             string `json:"checkpoint,omitempty"`
	CheckpointDocID        string `json:"checkpoint_doc_id,omitempty"`
	SignalPayloadSignature string `json:"signal_payload_signature,omitempty"`
	RulesSignature         string `json:"rules_signature,omitempty"`
	SignalCount            int    `json:"signal_count,omitempty"`
	StreamID               string `json:"stream_id,omitempty"`
	LeaseOwner             string `json:"lease_owner,omitempty"`
	LeaseToken             string `json:"lease_token,omitempty"`
	UpdatedAt              string `json:"updated_at"`
}

func NewRedisStore(client goredis.UniversalClient, keyPrefix string, logger *slog.Logger) *RedisStore {
	return &RedisStore{
		client:    client,
		keyPrefix: strings.TrimSuffix(strings.TrimSpace(keyPrefix), ":"),
		logger:    logger,
	}
}

func (s *RedisStore) LoadCheckpoint(ctx context.Context, key string) (models.ProcessingCheckpoint, error) {
	if err := ctx.Err(); err != nil {
		return models.ProcessingCheckpoint{}, err
	}
	if s == nil || s.client == nil {
		return models.ProcessingCheckpoint{}, nil
	}

	payload, err := s.client.Get(ctx, s.redisKey(key)).Result()
	if errors.Is(err, goredis.Nil) {
		return models.ProcessingCheckpoint{}, nil
	}
	if err != nil {
		return models.ProcessingCheckpoint{}, fmt.Errorf("load redis checkpoint %s: %w", key, err)
	}

	var stored redisPayload
	if err := json.Unmarshal([]byte(payload), &stored); err != nil {
		return models.ProcessingCheckpoint{}, fmt.Errorf("decode redis checkpoint %s: %w", key, err)
	}

	checkpoint := models.ProcessingCheckpoint{
		CheckpointDocID:        strings.TrimSpace(stored.CheckpointDocID),
		SignalPayloadSignature: strings.TrimSpace(stored.SignalPayloadSignature),
		RulesSignature:         strings.TrimSpace(stored.RulesSignature),
		SignalCount:            stored.SignalCount,
		StreamID:               strings.TrimSpace(stored.StreamID),
		LeaseOwner:             strings.TrimSpace(stored.LeaseOwner),
		LeaseToken:             strings.TrimSpace(stored.LeaseToken),
	}
	if strings.TrimSpace(stored.Checkpoint) != "" {
		parsed, err := time.Parse(time.RFC3339Nano, stored.Checkpoint)
		if err != nil {
			return models.ProcessingCheckpoint{}, fmt.Errorf("parse redis checkpoint timestamp %s: %w", key, err)
		}
		checkpoint.Checkpoint = parsed.UTC()
	}
	return checkpoint, nil
}

func (s *RedisStore) SaveCheckpoint(ctx context.Context, key string, checkpoint models.ProcessingCheckpoint) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if s == nil || s.client == nil {
		return nil
	}
	if checkpoint.Checkpoint.IsZero() && checkpoint.SignalPayloadSignature == "" && checkpoint.SignalCount == 0 && checkpoint.StreamID == "" {
		return nil
	}

	content, err := json.Marshal(redisPayload{
		Key:                    strings.TrimSpace(key),
		Checkpoint:             formatCheckpointTime(checkpoint.Checkpoint),
		CheckpointDocID:        strings.TrimSpace(checkpoint.CheckpointDocID),
		SignalPayloadSignature: strings.TrimSpace(checkpoint.SignalPayloadSignature),
		RulesSignature:         strings.TrimSpace(checkpoint.RulesSignature),
		SignalCount:            checkpoint.SignalCount,
		StreamID:               strings.TrimSpace(checkpoint.StreamID),
		LeaseOwner:             strings.TrimSpace(checkpoint.LeaseOwner),
		LeaseToken:             strings.TrimSpace(checkpoint.LeaseToken),
		UpdatedAt:              time.Now().UTC().Format(time.RFC3339Nano),
	})
	if err != nil {
		return fmt.Errorf("marshal redis checkpoint %s: %w", key, err)
	}

	if err := s.client.Set(ctx, s.redisKey(key), content, 0).Err(); err != nil {
		return fmt.Errorf("save redis checkpoint %s: %w", key, err)
	}
	if s.logger != nil {
		s.logger.Debug("saved redis checkpoint", "key", key, "redis_key", s.redisKey(key))
	}
	return nil
}

func (s *RedisStore) redisKey(key string) string {
	trimmed := strings.TrimSpace(key)
	if s.keyPrefix == "" {
		return "correlation_checkpoint:" + trimmed
	}
	return s.keyPrefix + ":correlation_checkpoint:" + trimmed
}
