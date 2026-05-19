package signalstream

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
)

// Event is the compact signal payload published for downstream correlation ingestion.
type Event struct {
	OrganizationID string    `json:"organization_id"`
	HostIdentity   string    `json:"host_identity,omitempty"`
	DocID          string    `json:"doc_id"`
	Signal         string    `json:"signal"`
	LogLevel       string    `json:"log_level"`
	TimeStamp      time.Time `json:"time_stamp"`
	SignalizedAt   time.Time `json:"signalized_at,omitempty"`
	SourceIndex    string    `json:"-"`
}

// Publisher writes compact signal events into a Redis stream.
type Publisher struct {
	client         *redis.Client
	streamKey      string
	maxLen         int64
	dedupEnabled   bool
	dedupTTL       time.Duration
	dedupKeyPrefix string
	logger         logging.Logger
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
		streamKey:      cfg.StreamKey,
		maxLen:         cfg.MaxLen,
		dedupEnabled:   cfg.PublishDedupEnabled,
		dedupTTL:       time.Duration(cfg.PublishDedupTTLSeconds) * time.Second,
		dedupKeyPrefix: cfg.PublishDedupKeyPrefix,
		logger:         logging.GetLogger("signalstream.Publisher"),
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

	id, published, err := p.publishPayload(ctx, event, string(payload))
	if err != nil {
		return err
	}
	if !published {
		p.logger.Debug(
			"skipped duplicate compact signal event",
			logging.F("stream_key", p.signalStreamKey(event.Signal)),
			logging.F("organization_id", event.OrganizationID),
			logging.F("signal", event.Signal),
			logging.F("doc_id", event.DocID),
		)
		return nil
	}

	p.logger.Debug(
		"published compact signal event",
		logging.F("stream_key", p.signalStreamKey(event.Signal)),
		logging.F("stream_id", id),
		logging.F("organization_id", event.OrganizationID),
		logging.F("signal", event.Signal),
		logging.F("doc_id", event.DocID),
	)
	return nil
}

func (p *Publisher) publishPayload(ctx context.Context, event Event, payload string) (string, bool, error) {
	signalStreamKey := p.signalStreamKey(event.Signal)
	if !p.dedupEnabled {
		return p.publishWithoutDedup(ctx, payload, signalStreamKey)
	}

	dedupKey := p.buildDedupKey(event)
	maxLen := ""
	if p.maxLen > 0 {
		maxLen = strconv.FormatInt(p.maxLen, 10)
	}
	ttlMillis := strconv.FormatInt(p.dedupTTL.Milliseconds(), 10)
	result, err := p.client.Eval(ctx, `
if redis.call("EXISTS", KEYS[2]) == 1 then
	return ""
end
local stream_id
if ARGV[2] ~= "" then
	stream_id = redis.call("XADD", KEYS[1], "MAXLEN", "~", ARGV[2], "*", "payload", ARGV[1])
else
	stream_id = redis.call("XADD", KEYS[1], "*", "payload", ARGV[1])
end
if tonumber(ARGV[3]) > 0 then
	redis.call("PSETEX", KEYS[2], ARGV[3], stream_id)
else
	redis.call("SET", KEYS[2], stream_id)
end
return stream_id
`, []string{signalStreamKey, dedupKey}, payload, maxLen, ttlMillis).Text()
	if err != nil {
		return "", false, fmt.Errorf("publish deduplicated signal stream event: %w", err)
	}
	if strings.TrimSpace(result) == "" {
		return "", false, nil
	}
	return result, true, nil
}

func (p *Publisher) buildDedupKey(event Event) string {
	keyBase := fmt.Sprintf("%s|%s", strings.TrimSpace(event.DocID), strings.TrimSpace(event.Signal))
	sum := sha256.Sum256([]byte(keyBase))
	return p.dedupKeyPrefix + fmt.Sprintf("%x", sum[:])
}

func (p *Publisher) signalStreamKey(signal string) string {
	trimmed := strings.TrimSpace(signal)
	if trimmed == "" {
		return p.streamKey
	}
	return p.streamKey + ":signal:" + trimmed
}

func (p *Publisher) publishWithoutDedup(ctx context.Context, payload string, signalStreamKey string) (string, bool, error) {
	args := &redis.XAddArgs{
		Stream: signalStreamKey,
		Values: map[string]any{
			"payload": payload,
		},
	}
	if p.maxLen > 0 {
		args.MaxLen = p.maxLen
		args.Approx = true
	}
	id, err := p.client.XAdd(ctx, args).Result()
	if err != nil {
		return "", false, fmt.Errorf("publish signal stream event: %w", err)
	}
	return id, true, nil
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
