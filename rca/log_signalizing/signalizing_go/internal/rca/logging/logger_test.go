package logging

import (
	"bytes"
	"errors"
	"testing"
	"time"

	"rca/internal/rca/config"
)

func TestJSONLoggerPreservesPythonFieldOrder(t *testing.T) {
	t.Cleanup(ResetForTests)

	var output bytes.Buffer
	SetOutput(&output)
	SetTimeNowForTests(func() time.Time {
		return time.Date(2024, time.January, 2, 3, 4, 5, 123456000, time.UTC)
	})
	ConfigureLogging(config.LoggingConfig{Level: "INFO", JSON: true})

	logger := GetLogger("demo")
	logger.Info("Processing cycle completed", F("processed", 7), F("service", "core"))

	expected := "{\"timestamp\": \"2024-01-02T03:04:05.123456+00:00\", \"level\": \"INFO\", \"logger\": \"demo\", \"message\": \"Processing cycle completed\", \"processed\": 7, \"service\": \"core\"}\n"
	if output.String() != expected {
		t.Fatalf("unexpected JSON log output:\nexpected: %q\nactual:   %q", expected, output.String())
	}
}

func TestPlainLoggerOmitsExtraFields(t *testing.T) {
	t.Cleanup(ResetForTests)

	var output bytes.Buffer
	SetOutput(&output)
	SetTimeNowForTests(func() time.Time {
		return time.Date(2024, time.January, 2, 3, 4, 5, 123000000, time.Local)
	})
	ConfigureLogging(config.LoggingConfig{Level: "INFO", JSON: false})

	logger := GetLogger("demo")
	logger.Warning("No source indices configured", F("service", "auth"))

	expected := "2024-01-02 03:04:05,123 WARNING demo No source indices configured\n"
	if output.String() != expected {
		t.Fatalf("unexpected plain log output:\nexpected: %q\nactual:   %q", expected, output.String())
	}
}

func TestJSONLoggerAddsExceptionBeforeExtraFields(t *testing.T) {
	t.Cleanup(ResetForTests)

	var output bytes.Buffer
	SetOutput(&output)
	SetTimeNowForTests(func() time.Time {
		return time.Date(2024, time.January, 2, 3, 4, 5, 0, time.UTC)
	})
	ConfigureLogging(config.LoggingConfig{Level: "DEBUG", JSON: true})

	logger := GetLogger("demo")
	logger.Exception("Fatal error in enrichment loop", errors.New("boom"), F("attempt", 2))

	expected := "{\"timestamp\": \"2024-01-02T03:04:05.000000+00:00\", \"level\": \"ERROR\", \"logger\": \"demo\", \"message\": \"Fatal error in enrichment loop\", \"exception\": \"boom\", \"attempt\": 2}\n"
	if output.String() != expected {
		t.Fatalf("unexpected JSON exception output:\nexpected: %q\nactual:   %q", expected, output.String())
	}
}
