package ingest

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/segmentio/kafka-go"
	"github.com/segmentio/kafka-go/sasl"
	"github.com/segmentio/kafka-go/sasl/scram"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
	"rca/internal/rca/util"
)

// KafkaMessage is one decoded Kafka event plus transport metadata.
type KafkaMessage struct {
	Event       map[string]any
	SourceIndex string
	SourceID    string
	Topic       string
	Partition   int
	Offset      int64
	Raw         kafka.Message
}

// KafkaReader fetches Kafka messages in bounded batches and commits them on success.
type KafkaReader interface {
	ReadBatch(ctx context.Context, limit int) ([]KafkaMessage, error)
	Commit(ctx context.Context, messages []KafkaMessage) error
	Close() error
}

// Consumer reads Kafka batches using a managed consumer group.
type Consumer struct {
	reader *kafka.Reader
	config config.KafkaConfig
	logger logging.Logger
}

// NewKafkaReader creates the configured Kafka consumer.
func NewKafkaReader(cfg config.KafkaConfig) (*Consumer, error) {
	if len(cfg.Brokers) == 0 {
		return nil, fmt.Errorf("kafka.brokers must not be empty when input.source=kafka")
	}
	if strings.TrimSpace(cfg.Topic) == "" {
		return nil, fmt.Errorf("kafka.topic must not be empty when input.source=kafka")
	}
	if strings.TrimSpace(cfg.GroupID) == "" {
		return nil, fmt.Errorf("kafka.group_id must not be empty when input.source=kafka")
	}

	dialer, err := NewKafkaDialer(cfg)
	if err != nil {
		return nil, err
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:           append([]string{}, cfg.Brokers...),
		Topic:             cfg.Topic,
		GroupID:           cfg.GroupID,
		MaxBytes:          maxInt(1024, cfg.MaxBytes),
		MinBytes:          maxInt(1, cfg.MinBytes),
		MaxWait:           time.Duration(cfg.MaxWaitSeconds * float64(time.Second)),
		CommitInterval:    0,
		SessionTimeout:    time.Duration(cfg.SessionTimeoutSeconds) * time.Second,
		RebalanceTimeout:  time.Duration(cfg.RebalanceTimeoutSeconds) * time.Second,
		HeartbeatInterval: time.Duration(cfg.HeartbeatIntervalSeconds) * time.Second,
		StartOffset:       resolveKafkaStartOffset(cfg.StartOffset),
		Dialer:            dialer,
	})
	return &Consumer{
		reader: reader,
		config: cfg,
		logger: logging.GetLogger("KafkaReader"),
	}, nil
}

// ReadBatch fetches up to limit messages or returns sooner when the configured timeout elapses.
func (c *Consumer) ReadBatch(ctx context.Context, limit int) ([]KafkaMessage, error) {
	if limit < 1 {
		limit = 1
	}

	timeout := time.Duration(c.config.ReadBatchTimeoutSeconds * float64(time.Second))
	if timeout <= 0 {
		timeout = 2 * time.Second
	}

	deadline := time.Now().Add(timeout)
	batch := make([]KafkaMessage, 0, limit)
	for len(batch) < limit {
		readCtx, cancel := context.WithDeadline(ctx, deadline)
		msg, err := c.reader.FetchMessage(readCtx)
		cancel()
		if err != nil {
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			if errorsIsDeadline(err) {
				break
			}
			return nil, err
		}

		event := decodeKafkaMessage(msg, c.config)
		batch = append(batch, event)
		if time.Now().After(deadline) {
			break
		}
	}

	if len(batch) > 0 {
		last := batch[len(batch)-1]
		c.logger.Debug(
			"Read Kafka batch",
			logging.F("topic", last.Topic),
			logging.F("batch_size", len(batch)),
			logging.F("last_partition", last.Partition),
			logging.F("last_offset", last.Offset),
		)
	}
	return batch, nil
}

// Commit persists the processed offsets for the provided batch.
func (c *Consumer) Commit(ctx context.Context, messages []KafkaMessage) error {
	if len(messages) == 0 {
		return nil
	}

	rawMessages := make([]kafka.Message, 0, len(messages))
	for _, message := range messages {
		rawMessages = append(rawMessages, message.Raw)
	}

	attempts := maxInt(1, c.config.CommitRetries)
	var lastErr error
	for attempt := 1; attempt <= attempts; attempt++ {
		if err := c.reader.CommitMessages(ctx, rawMessages...); err != nil {
			lastErr = err
			time.Sleep(time.Duration(attempt) * 100 * time.Millisecond)
			continue
		}
		return nil
	}
	return lastErr
}

// Close releases the underlying Kafka reader.
func (c *Consumer) Close() error {
	if c == nil || c.reader == nil {
		return nil
	}
	return c.reader.Close()
}

func decodeKafkaMessage(msg kafka.Message, cfg config.KafkaConfig) KafkaMessage {
	now := time.Now().UTC()
	event := map[string]any{}
	rawText := strings.TrimSpace(string(msg.Value))

	if rawText != "" {
		var decoded any
		if err := json.Unmarshal(msg.Value, &decoded); err == nil {
			if decodedMap, ok := decoded.(map[string]any); ok {
				event = decodedMap
			} else {
				event["message"] = rawText
				util.SetNested(event, cfg.EventOriginalField, rawText)
				event["payload"] = decoded
			}
		} else {
			event["message"] = rawText
			util.SetNested(event, cfg.EventOriginalField, rawText)
		}
	}

	if event == nil {
		event = map[string]any{}
	}
	if util.GetNested(event, "@timestamp") == nil {
		timestamp := msg.Time.UTC()
		if timestamp.IsZero() {
			timestamp = now
		}
		event["@timestamp"] = timestamp.Format(time.RFC3339Nano)
	}
	if util.GetNested(event, "event.ingested") == nil {
		util.SetNested(event, "event.ingested", now.Format(time.RFC3339Nano))
	}

	headers := map[string]any{}
	for _, header := range msg.Headers {
		headers[header.Key] = string(header.Value)
	}
	util.SetNested(event, cfg.MetadataField, map[string]any{
		"topic":       msg.Topic,
		"partition":   msg.Partition,
		"offset":      msg.Offset,
		"key":         string(msg.Key),
		"group_id":    cfg.GroupID,
		"client_id":   cfg.ClientID,
		"headers":     headers,
		"received_at": now.Format(time.RFC3339Nano),
	})

	sourceIndex := strings.TrimSpace(fmt.Sprint(util.GetNested(event, cfg.SourceIndexField)))
	if cfg.SourceIndexField == "" || sourceIndex == "" || sourceIndex == "<nil>" {
		sourceIndex = strings.TrimSpace(cfg.SourceIndex)
	}
	if sourceIndex == "" {
		sourceIndex = msg.Topic
	}

	docIDPrefix := strings.Trim(strings.TrimSpace(cfg.DocumentIDPrefix), ":")
	docID := resolveMessageDocID(event, docIDPrefix, msg)
	event["source_index"] = sourceIndex
	event["source_rca_id"] = docID

	return KafkaMessage{
		Event:       event,
		SourceIndex: sourceIndex,
		SourceID:    docID,
		Topic:       msg.Topic,
		Partition:   msg.Partition,
		Offset:      msg.Offset,
		Raw:         msg,
	}
}

func resolveMessageDocID(event map[string]any, docIDPrefix string, msg kafka.Message) string {
	existing := strings.TrimSpace(fmt.Sprint(util.GetNested(event, "source_rca_id")))
	if existing != "" && existing != "<nil>" {
		return existing
	}

	if docIDPrefix == "" {
		return fmt.Sprintf("%s:%d:%d", msg.Topic, msg.Partition, msg.Offset)
	}
	return fmt.Sprintf("%s:%s:%d:%d", docIDPrefix, msg.Topic, msg.Partition, msg.Offset)
}

// NewKafkaDialer builds the shared Kafka dialer used by both readers and admin flows.
func NewKafkaDialer(cfg config.KafkaConfig) (*kafka.Dialer, error) {
	dialer := &kafka.Dialer{
		Timeout:   30 * time.Second,
		ClientID:  cfg.ClientID,
		DualStack: true,
	}

	if tlsConfig, err := newKafkaTLSConfig(cfg); err != nil {
		return nil, err
	} else if tlsConfig != nil {
		dialer.TLS = tlsConfig
	}

	mechanism, err := newKafkaSASLMechanism(cfg)
	if err != nil {
		return nil, err
	}
	if mechanism != nil {
		dialer.SASLMechanism = mechanism
	}
	return dialer, nil
}

func newKafkaTransport(cfg config.KafkaConfig) (*kafka.Transport, error) {
	tlsConfig, err := newKafkaTLSConfig(cfg)
	if err != nil {
		return nil, err
	}
	mechanism, err := newKafkaSASLMechanism(cfg)
	if err != nil {
		return nil, err
	}

	return &kafka.Transport{
		DialTimeout: 30 * time.Second,
		ClientID:    cfg.ClientID,
		TLS:         tlsConfig,
		SASL:        mechanism,
	}, nil
}

func newKafkaTLSConfig(cfg config.KafkaConfig) (*tls.Config, error) {
	if !cfg.TLSEnabled {
		return nil, nil
	}

	tlsConfig := &tls.Config{InsecureSkipVerify: cfg.InsecureSkipVerify} //nolint:gosec // config controlled for lab/dev parity
	if strings.TrimSpace(cfg.CAFile) == "" {
		return tlsConfig, nil
	}

	pemBytes, err := os.ReadFile(cfg.CAFile)
	if err != nil {
		return nil, err
	}

	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(pemBytes) {
		return nil, fmt.Errorf("failed to append kafka ca cert from %s", cfg.CAFile)
	}
	tlsConfig.RootCAs = pool
	return tlsConfig, nil
}

func newKafkaSASLMechanism(cfg config.KafkaConfig) (sasl.Mechanism, error) {
	mechanismName := strings.ToUpper(strings.TrimSpace(cfg.SASLMechanism))
	if mechanismName == "" {
		return nil, nil
	}

	if cfg.Username == nil || cfg.Password == nil {
		return nil, fmt.Errorf("kafka username/password are required when sasl_mechanism is configured")
	}

	switch mechanismName {
	case "SCRAM-SHA-256":
		return scram.Mechanism(scram.SHA256, *cfg.Username, *cfg.Password)
	case "SCRAM-SHA-512":
		return scram.Mechanism(scram.SHA512, *cfg.Username, *cfg.Password)
	default:
		return nil, fmt.Errorf("unsupported kafka sasl mechanism: %s", cfg.SASLMechanism)
	}
}

func resolveKafkaStartOffset(value string) int64 {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "earliest", "first", "oldest":
		return kafka.FirstOffset
	default:
		return kafka.LastOffset
	}
}

func errorsIsDeadline(err error) bool {
	return errors.Is(err, context.DeadlineExceeded) || strings.Contains(strings.ToLower(err.Error()), "context deadline exceeded")
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}
