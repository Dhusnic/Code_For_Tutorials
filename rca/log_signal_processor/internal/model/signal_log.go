// Package model defines the data structures for signal log representation.
// Signals are normalized Elasticsearch documents that indicate important events.
// They are stored in Redis for efficient correlation and analysis.
package model

import (
	"encoding/json"
	"fmt"
	"time"
)

// SignalLog represents a normalized signal-bearing document.
// This is the core data structure stored in Redis for each organization.
//
// Fields:
//   - Signal: The signal type from Elasticsearch (e.g., "disk_failure", "network_error")
//   - LogLevel: Log severity level (e.g., "critical", "warning", "info")
//   - DocID: Unique Elasticsearch document ID for traceability
//   - TimeStamp: UTC timestamp when signal was generated, used for retention/correlation
//
// JSON Format (for Redis storage):
//
//	{
//	  "signal": "disk_failure",
//	  "log_level": "critical",
//	  "doc_id": "abc123def456",
//	  "time_stamp": "2026-03-17T10:21:00.000000Z"
//	}
//
// Retention:
//   - Signals older than retention_window are automatically trimmed
//   - Default retention: 30 minutes
//   - Configurable per organization
type SignalLog struct {
	Signal    string
	LogLevel  string
	DocID     string
	TimeStamp time.Time
}

// SignalRecord pairs a normalized signal log with its organization identifier.
// Used to track which organization each signal belongs to during collection.
//
// Fields:
//   - Organization: Organization ID / key for Redis storage
//   - Log: The actual signal log entry
type SignalRecord struct {
	Organization string
	Log          SignalLog
}

// signalLogPayload defines the JSON representation of a SignalLog.
// This matches the Redis storage contract and ensures stable serialization.
//
// Fields mirror SignalLog but with JSON tags for RFC3339Nano timestamp formatting.
type signalLogPayload struct {
	Signal    string `json:"signal"`
	LogLevel  string `json:"log_level"`
	DocID     string `json:"doc_id"`
	TimeStamp string `json:"time_stamp"`
}

// MarshalJSON serializes a SignalLog to JSON for Redis storage.
// Ensures timestamps use RFC3339Nano format for human-readability and consistency.
// This maintains the Redis storage contract.
//
// Returns:
//   - []byte: JSON-encoded signal log
//   - error: JSON encoding error (unlikely)
//
// Logging: None (hot path)
func (s SignalLog) MarshalJSON() ([]byte, error) {
	return json.Marshal(signalLogPayload{
		Signal:    s.Signal,
		LogLevel:  s.LogLevel,
		DocID:     s.DocID,
		TimeStamp: s.TimeStamp.UTC().Format(time.RFC3339Nano),
	})
}

// UnmarshalJSON deserializes a SignalLog from JSON stored in Redis.
// Parses the RFC3339Nano timestamp format back to Go time.Time.
// Handles timestamp parsing errors gracefully with context.
//
// Parameters:
//   - data: JSON-encoded signal log bytes
//
// Returns:
//   - error: JSON decoding error or timestamp parsing error
//
// Errors:
//   - JSON syntax error: Invalid JSON structure
//   - Timestamp parse error: Invalid RFC3339Nano format
//
// Logging: None (hot path)
func (s *SignalLog) UnmarshalJSON(data []byte) error {
	var payload signalLogPayload
	if err := json.Unmarshal(data, &payload); err != nil {
		return fmt.Errorf("parse JSON payload: %w", err)
	}

	parsed, err := time.Parse(time.RFC3339Nano, payload.TimeStamp)
	if err != nil {
		return fmt.Errorf("parse time_stamp %q (expected RFC3339Nano format): %w", payload.TimeStamp, err)
	}

	s.Signal = payload.Signal
	s.LogLevel = payload.LogLevel
	s.DocID = payload.DocID
	s.TimeStamp = parsed.UTC()
	return nil
}
