package logger

import (
	"io"
	"log/slog"
	"os"
	"strings"
	"time"

	"log_rca_engine/internal/config"
)

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

func NewDiscard() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

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
