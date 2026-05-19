package ingest

import (
	"context"
	"fmt"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/segmentio/kafka-go"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
)

const (
	defaultKafkaPartitionSyncWaitTimeout  = 30 * time.Second
	defaultKafkaPartitionSyncPollInterval = 500 * time.Millisecond
)

type kafkaPartitionAdmin interface {
	PartitionCount(ctx context.Context, topic string) (int, error)
	GrowPartitions(ctx context.Context, topic string, target int) error
}

type kafkaPartitionSyncOptions struct {
	WaitTimeout  time.Duration
	PollInterval time.Duration
}

type kafkaTopicAdmin struct {
	cfg       config.KafkaConfig
	dialer    *kafka.Dialer
	transport *kafka.Transport
}

// EnsureTopicPartitionsAtStartup grows the Kafka topic partition count up to the
// configured worker count before consumers begin steady-state processing.
func EnsureTopicPartitionsAtStartup(ctx context.Context, cfg config.KafkaConfig, workerID int, workerCount int, logger logging.Logger) error {
	admin, err := newKafkaTopicAdmin(cfg)
	if err != nil {
		return err
	}

	return ensureTopicPartitionsAtStartup(
		ctx,
		admin,
		strings.TrimSpace(cfg.Topic),
		workerID,
		workerCount,
		logger,
		kafkaPartitionSyncOptions{
			WaitTimeout:  defaultKafkaPartitionSyncWaitTimeout,
			PollInterval: defaultKafkaPartitionSyncPollInterval,
		},
	)
}

func ensureTopicPartitionsAtStartup(
	ctx context.Context,
	admin kafkaPartitionAdmin,
	topic string,
	workerID int,
	workerCount int,
	logger logging.Logger,
	options kafkaPartitionSyncOptions,
) error {
	if workerCount <= 1 {
		return nil
	}
	if strings.TrimSpace(topic) == "" {
		return nil
	}

	options = normalizeKafkaPartitionSyncOptions(options)

	if workerID == 0 {
		current, err := admin.PartitionCount(ctx, topic)
		if err != nil {
			return fmt.Errorf("read kafka partition count for topic %q: %w", topic, err)
		}

		if current < workerCount {
			logger.Warning(
				"Kafka topic has fewer partitions than configured workers; growing topic",
				logging.F("topic", topic),
				logging.F("current_partitions", current),
				logging.F("target_partitions", workerCount),
				logging.F("worker_id", workerID),
				logging.F("worker_count", workerCount),
			)
			if err := admin.GrowPartitions(ctx, topic, workerCount); err != nil {
				return fmt.Errorf("grow kafka topic %q partitions from %d to %d: %w", topic, current, workerCount, err)
			}
		} else {
			logger.Info(
				"Kafka topic partitions already satisfy configured workers",
				logging.F("topic", topic),
				logging.F("current_partitions", current),
				logging.F("worker_count", workerCount),
			)
		}
	}

	current, err := waitForKafkaTopicPartitions(ctx, admin, topic, workerCount, options)
	if err != nil {
		return err
	}

	logger.Info(
		"Kafka topic partition sync ready",
		logging.F("topic", topic),
		logging.F("partitions", current),
		logging.F("worker_id", workerID),
		logging.F("worker_count", workerCount),
	)
	return nil
}

func waitForKafkaTopicPartitions(
	ctx context.Context,
	admin kafkaPartitionAdmin,
	topic string,
	target int,
	options kafkaPartitionSyncOptions,
) (int, error) {
	deadline := time.NewTimer(options.WaitTimeout)
	defer deadline.Stop()

	for {
		current, err := admin.PartitionCount(ctx, topic)
		if err != nil {
			return 0, fmt.Errorf("read kafka partition count for topic %q: %w", topic, err)
		}
		if current >= target {
			return current, nil
		}

		timer := time.NewTimer(options.PollInterval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return 0, ctx.Err()
		case <-deadline.C:
			timer.Stop()
			return 0, fmt.Errorf("timed out waiting for kafka topic %q to reach %d partitions", topic, target)
		case <-timer.C:
		}
	}
}

func normalizeKafkaPartitionSyncOptions(options kafkaPartitionSyncOptions) kafkaPartitionSyncOptions {
	if options.WaitTimeout <= 0 {
		options.WaitTimeout = defaultKafkaPartitionSyncWaitTimeout
	}
	if options.PollInterval <= 0 {
		options.PollInterval = defaultKafkaPartitionSyncPollInterval
	}
	return options
}

func newKafkaTopicAdmin(cfg config.KafkaConfig) (*kafkaTopicAdmin, error) {
	if len(cfg.Brokers) == 0 {
		return nil, fmt.Errorf("kafka.brokers must not be empty when syncing topic partitions")
	}

	dialer, err := NewKafkaDialer(cfg)
	if err != nil {
		return nil, err
	}
	transport, err := newKafkaTransport(cfg)
	if err != nil {
		return nil, err
	}

	return &kafkaTopicAdmin{
		cfg:       cfg,
		dialer:    dialer,
		transport: transport,
	}, nil
}

func (a *kafkaTopicAdmin) PartitionCount(ctx context.Context, topic string) (int, error) {
	conn, err := a.dialer.DialContext(ctx, "tcp", a.cfg.Brokers[0])
	if err != nil {
		return 0, err
	}
	defer conn.Close()

	partitions, err := conn.ReadPartitions(topic)
	if err != nil {
		return 0, err
	}

	count := 0
	for _, partition := range partitions {
		if partition.Topic == topic {
			count++
		}
	}
	return count, nil
}

func (a *kafkaTopicAdmin) GrowPartitions(ctx context.Context, topic string, target int) error {
	conn, err := a.dialer.DialContext(ctx, "tcp", a.cfg.Brokers[0])
	if err != nil {
		return err
	}
	controller, err := conn.Controller()
	_ = conn.Close()
	if err != nil {
		return err
	}

	controllerAddress := net.JoinHostPort(controller.Host, strconv.Itoa(controller.Port))
	client := &kafka.Client{
		Addr:      kafka.TCP(controllerAddress),
		Timeout:   30 * time.Second,
		Transport: a.transport,
	}

	response, err := client.CreatePartitions(ctx, &kafka.CreatePartitionsRequest{
		Topics: []kafka.TopicPartitionsConfig{{
			Name:  topic,
			Count: int32(target),
		}},
	})
	if err != nil {
		return err
	}

	if topicErr, ok := response.Errors[topic]; ok && topicErr != nil {
		return topicErr
	}
	return nil
}
