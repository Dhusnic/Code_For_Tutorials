package logging

import (
	"log/slog"
	"os"
	"strings"
)

func New(level string) *slog.Logger {
	resolvedLevel := slog.LevelInfo
	switch strings.ToLower(strings.TrimSpace(level)) {
	case "debug":
		resolvedLevel = slog.LevelDebug
	case "warn", "warning":
		resolvedLevel = slog.LevelWarn
	case "error":
		resolvedLevel = slog.LevelError
	}

	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: resolvedLevel,
	})
	return slog.New(handler)
}
