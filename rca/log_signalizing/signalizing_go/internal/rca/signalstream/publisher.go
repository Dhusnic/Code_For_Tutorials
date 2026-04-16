package signalstream

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
)

// Event is the compact signal payload published for downstream correlation ingestion.
type Event struct {
	OrganizationID string    `json:"organization_id"`
	DocID          string    `json:"doc_id"`
	Signal         string    `json:"signal"`
	LogLevel       string    `json:"log_level"`
	TimeStamp      time.Time `json:"time_stamp"`
	SourceIndex    string    `json:"source_index,omitempty"`
	SourceID       string    `json:"source_id,omitempty"`
}

// Publisher writes compact signal events into a Redis stream.
type Publisher struct {
	client    *redis.Client
	streamKey string
	maxLen    int64
	logger    logging.Logger
}

// NewPublisher creates a Redis stream publisher from config.
func NewPublisher(cfg config.SignalStreamConfig) (*Publisher, error) {
	if cfg.Address == "" {
		return nil, fmt.Errorf("signal stream address must not be empty")
	}
	if cfg.StreamKey == "" {
		return nil, fmt.Errorf("signal stream key must not be empty")
	}

	return &Publisher{
		client: redis.NewClient(&redis.Options{
			Addr:         cfg.Address,
			Username:     dereferenceString(cfg.Username),
			Password:     dereferenceString(cfg.Password),
			DB:           cfg.DB,
			DialTimeout:  time.Duration(cfg.DialTimeoutSeconds) * time.Second,
			ReadTimeout:  time.Duration(cfg.ReadTimeoutSeconds) * time.Second,
			WriteTimeout: time.Duration(cfg.WriteTimeoutSeconds) * time.Second,
		}),
		streamKey: cfg.StreamKey,
		maxLen:    cfg.MaxLen,
		logger:    logging.GetLogger("signalstream.Publisher"),
	}, nil
}

// Publish appends one event to the Redis stream.
func (p *Publisher) Publish(ctx context.Context, event Event) error {
	if p == nil {
		return fmt.Errorf("signal stream publisher is nil")
	}
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal signal stream event: %w", err)
	}

	args := &redis.XAddArgs{
		Stream: p.streamKey,
		Values: map[string]any{
			"payload": string(payload),
		},
	}
	if p.maxLen > 0 {
		args.MaxLen = p.maxLen
		args.Approx = true
	}

	id, err := p.client.XAdd(ctx, args).Result()
	if err != nil {
		return fmt.Errorf("publish signal stream event: %w", err)
	}

	p.logger.Debug(
		"published compact signal event",
		logging.F("stream_key", p.streamKey),
		logging.F("stream_id", id),
		logging.F("organization_id", event.OrganizationID),
		logging.F("signal", event.Signal),
		logging.F("doc_id", event.DocID),
	)
	return nil
}

// Close closes the underlying Redis client.
func (p *Publisher) Close() error {
	if p == nil || p.client == nil {
		return nil
	}
	return p.client.Close()
}

func dereferenceString(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}
