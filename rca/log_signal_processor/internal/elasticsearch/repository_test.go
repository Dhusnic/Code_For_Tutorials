package elasticsearch

import (
	"testing"
	"time"

	"log_signal_processor/internal/config"
	"log_signal_processor/internal/logger"
)

func TestBuildQueryWithPointInTimeAvoidsIDSort(t *testing.T) {
	repository := NewRepository(
		nil,
		config.ElasticsearchConfig{
			PageSize:       500,
			QueryTimeout:   10 * time.Second,
			UsePointInTime: true,
			PITKeepAlive:   2 * time.Minute,
		},
		config.FieldMappings{
			SignalField:    "signal",
			TimestampField: "@timestamp",
		},
		logger.NewDiscard(),
	)

	body := repository.buildQuery(
		time.Date(2026, 3, 17, 10, 0, 0, 0, time.UTC),
		time.Date(2026, 3, 17, 10, 10, 0, 0, time.UTC),
		[]any{"2026-03-17T10:00:00Z", 1},
		"pit-123",
	)

	sortFields := body["sort"].([]any)
	firstSort := sortFields[0].(map[string]any)
	if _, ok := firstSort["@timestamp"]; !ok {
		t.Fatalf("expected first sort field to be @timestamp, got %v", firstSort)
	}
	secondSort := sortFields[1].(map[string]any)
	if _, ok := secondSort["_shard_doc"]; !ok {
		t.Fatalf("expected second sort field to be _shard_doc, got %v", secondSort)
	}
	if _, found := secondSort["_id"]; found {
		t.Fatalf("did not expect _id sort field")
	}

	pit, ok := body["pit"].(map[string]any)
	if !ok {
		t.Fatalf("expected pit block in query body")
	}
	if pit["id"] != "pit-123" {
		t.Fatalf("expected pit id pit-123, got %v", pit["id"])
	}
	if pit["keep_alive"] != "2m" {
		t.Fatalf("expected pit keep_alive 2m, got %v", pit["keep_alive"])
	}
	if body["timeout"] != "10s" {
		t.Fatalf("expected query timeout 10s, got %v", body["timeout"])
	}
}

func TestFormatDurationForElasticsearch(t *testing.T) {
	testCases := map[time.Duration]string{
		2 * time.Minute:           "2m",
		90 * time.Second:          "90s",
		1500 * time.Millisecond:   "1500ms",
		1500*time.Millisecond + 1: "1501ms",
		250 * time.Millisecond:    "250ms",
		time.Hour:                 "1h",
	}

	for input, expected := range testCases {
		actual := formatDurationForElasticsearch(input)
		if actual != expected {
			t.Fatalf("expected %s for %s, got %s", expected, input, actual)
		}
	}
}
