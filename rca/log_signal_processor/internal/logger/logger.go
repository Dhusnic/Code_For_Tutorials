// Package logger provides slog-based structured logging factory with format and level configuration.
package logger

import (
	"io"
	"log/slog"
	"os"
	"strings"
	"time"

	"log_signal_processor/internal/config"
)

// New builds the application logger from configuration with level and format settings.
//
// Output Format:
//   - "json": JSON structured logging (production-preferred)
//   - "text": Human-readable text format (development-friendly)
//   - default: JSON if format unrecognized
//
// Output: Always writes to os.Stdout (JSON or Text)
//
// Timestamp Handling:
//   - All timestamps converted to UTC in RFC3339Nano format
//   - Replaces slog-default time format for consistency
//
// Level Handling:
//   - Lowercase level names in output (debug, info, warn, error)
//   - Replaces slog-default uppercase for consistency
//
// Attribute Replacement:
//   - Customizes time key format (always RFC3339Nano UTC)
//   - Customizes level key format (always lowercase)
//
// Parameters:
//   - cfg: LoggingConfig with Level and Format settings
//
// Returns:
//   - *slog.Logger: Configured logger for application use
//
// Example:
//
//	cfg := config.LoggingConfig{Level: "debug", Format: "json"}
//	logger := New(cfg)
//	logger.Info("application started", "version", "1.0")
func New(cfg config.LoggingConfig) *slog.Logger {
	options := &slog.HandlerOptions{
		Level: parseLevel(cfg.Level),
		ReplaceAttr: func(_ []string, attr slog.Attr) slog.Attr {
			switch attr.Key {
			case slog.TimeKey:
				if value, ok := attr.Value.Any().(time.Time); ok {
					return slog.String("time", value.UTC().Format(time.RFC3339Nano))
				}
			case slog.LevelKey:
				return slog.String("level", strings.ToLower(attr.Value.String()))
			}
			return attr
		},
	}

	if strings.EqualFold(cfg.Format, "text") {
		return slog.New(slog.NewTextHandler(os.Stdout, options))
	}
	return slog.New(slog.NewJSONHandler(os.Stdout, options))
}

// NewDiscard builds a no-op logger that discards all output.
// Useful for tests and scenarios where logging is not desired.
//
// Behavior:
//   - All log calls accepted but produce no output
//   - Performance: Minimal overhead (discarded immediately)
//   - Thread-safe: Safe for concurrent use
//
// Returns:
//   - *slog.Logger: Logger with io.Discard sink
//
// Example:
//
//	logger := NewDiscard()  // Use in tests
//	logger.Info("this message is silently dropped")
func NewDiscard() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

// parseLevel converts configuration level string to slog.Level.
//
// Supported Levels:
//   - "debug": DEBUG level
//   - "info": INFO level (default)
//   - "warn"/"warning": WARN level
//   - "error": ERROR level
//   - default: INFO level (unknown strings default to INFO)
//
// Case Handling:
//   - Case-insensitive (Debug, DEBUG, debug all work)
//   - Whitespace trimmed before comparison
//
// Parameters:
//   - raw: Level string from configuration
//
// Returns:
//   - slog.Level: Parsed level (defaults to INFO if unrecognized)
//
// Example:
//
//	parseLevel("DEBUG") → slog.LevelDebug
//	parseLevel("warning") → slog.LevelWarn
//	parseLevel("") → slog.LevelInfo
func parseLevel(raw string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
