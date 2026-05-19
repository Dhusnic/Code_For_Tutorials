package ingest

import (
	"context"
	"io"
	"strings"
	"sync"
	"testing"
	"time"

	"rca/internal/rca/logging"
)

type fakeKafkaPartitionAdmin struct {
	mu                  sync.Mutex
	count               int
	partitionCountCalls int
	growTargets         []int
	partitionCountFunc  func(call int) (int, error)
	growFunc            func(target int) error
}

func (f *fakeKafkaPartitionAdmin) PartitionCount(_ context.Context, _ string) (int, error) {
	f.mu.Lock()
	defer f.mu.Unlock()

	f.partitionCountCalls++
	if f.partitionCountFunc != nil {
		return f.partitionCountFunc(f.partitionCountCalls)
	}
	return f.count, nil
}

func (f *fakeKafkaPartitionAdmin) GrowPartitions(_ context.Context, _ string, target int) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	f.growTargets = append(f.growTargets, target)
	if f.growFunc != nil {
		return f.growFunc(target)
	}
	f.count = target
	return nil
}

func TestEnsureTopicPartitionsAtStartupGrowsTopicFromWorkerZero(t *testing.T) {
	quietKafkaPartitionTestLogging(t)

	admin := &fakeKafkaPartitionAdmin{count: 4}
	err := ensureTopicPartitionsAtStartup(
		context.Background(),
		admin,
		"linux-logs",
		0,
		7,
		logging.GetLogger("test"),
		kafkaPartitionSyncOptions{WaitTimeout: 20 * time.Millisecond, PollInterval: time.Millisecond},
	)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	if len(admin.growTargets) != 1 || admin.growTargets[0] != 7 {
		t.Fatalf("expected grow target 7 once, got %#v", admin.growTargets)
	}
	if admin.partitionCountCalls < 2 {
		t.Fatalf("expected at least two partition count reads, got %d", admin.partitionCountCalls)
	}
}

func TestEnsureTopicPartitionsAtStartupDoesNotShrinkTopic(t *testing.T) {
	quietKafkaPartitionTestLogging(t)

	admin := &fakeKafkaPartitionAdmin{count: 7}
	err := ensureTopicPartitionsAtStartup(
		context.Background(),
		admin,
		"linux-logs",
		0,
		4,
		logging.GetLogger("test"),
		kafkaPartitionSyncOptions{WaitTimeout: 20 * time.Millisecond, PollInterval: time.Millisecond},
	)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	if len(admin.growTargets) != 0 {
		t.Fatalf("expected no grow calls, got %#v", admin.growTargets)
	}
}

func TestEnsureTopicPartitionsAtStartupWaitsForOtherWorkers(t *testing.T) {
	quietKafkaPartitionTestLogging(t)

	admin := &fakeKafkaPartitionAdmin{
		partitionCountFunc: func(call int) (int, error) {
			if call < 3 {
				return 4, nil
			}
			return 7, nil
		},
	}

	err := ensureTopicPartitionsAtStartup(
		context.Background(),
		admin,
		"linux-logs",
		4,
		7,
		logging.GetLogger("test"),
		kafkaPartitionSyncOptions{WaitTimeout: 30 * time.Millisecond, PollInterval: time.Millisecond},
	)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	if len(admin.growTargets) != 0 {
		t.Fatalf("expected no grow calls from non-zero worker, got %#v", admin.growTargets)
	}
	if admin.partitionCountCalls < 3 {
		t.Fatalf("expected repeated partition checks, got %d", admin.partitionCountCalls)
	}
}

func TestEnsureTopicPartitionsAtStartupTimesOutWhenTopicNeverGrows(t *testing.T) {
	quietKafkaPartitionTestLogging(t)

	admin := &fakeKafkaPartitionAdmin{count: 4}
	err := ensureTopicPartitionsAtStartup(
		context.Background(),
		admin,
		"linux-logs",
		2,
		7,
		logging.GetLogger("test"),
		kafkaPartitionSyncOptions{WaitTimeout: 5 * time.Millisecond, PollInterval: time.Millisecond},
	)
	if err == nil {
		t.Fatal("expected timeout error, got nil")
	}
	if !strings.Contains(err.Error(), "timed out waiting for kafka topic") {
		t.Fatalf("expected timeout error, got %v", err)
	}
}

func quietKafkaPartitionTestLogging(t *testing.T) {
	t.Helper()
	logging.ResetForTests()
	logging.SetOutput(io.Discard)
	t.Cleanup(logging.ResetForTests)
}
