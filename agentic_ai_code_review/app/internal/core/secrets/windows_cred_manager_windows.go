//go:build windows

package secrets

import (
	"context"
	"fmt"
	"log/slog"
	"os/exec"
	"strings"
)

type WindowsCredentialStore struct {
	prefix string
	logger *slog.Logger
}

func NewWindowsCredentialStore(prefix string, logger *slog.Logger) (*WindowsCredentialStore, error) {
	p := strings.TrimSpace(prefix)
	if p == "" {
		p = "AgenticAICodeReview"
	}
	return &WindowsCredentialStore{
		prefix: p,
		logger: logger,
	}, nil
}

func (s *WindowsCredentialStore) Get(_ context.Context, key string) (string, error) {
	// cmdkey cannot reliably reveal secret values. Keep secure-by-default behavior
	// and force explicit user entry when readback is not available.
	if s.logger != nil {
		s.logger.Warn("windows credential manager read is unavailable via cmdkey on this host", "key", key)
	}
	return "", ErrSecretReadUnsupported
}

func (s *WindowsCredentialStore) Set(_ context.Context, key, value string) error {
	target := s.targetFor(key)
	command := exec.Command("cmdkey", "/generic:"+target, "/user:agentic-ai-code-review", "/pass:"+value)
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to store credential target=%s: %w; output=%s", target, err, string(output))
	}
	return nil
}

func (s *WindowsCredentialStore) Delete(_ context.Context, key string) error {
	target := s.targetFor(key)
	command := exec.Command("cmdkey", "/delete:"+target)
	output, err := command.CombinedOutput()
	if err != nil {
		text := strings.ToLower(string(output))
		if strings.Contains(text, "cannot find") || strings.Contains(text, "not found") {
			return nil
		}
		return fmt.Errorf("failed to delete credential target=%s: %w; output=%s", target, err, string(output))
	}
	return nil
}

func (s *WindowsCredentialStore) targetFor(key string) string {
	trimmed := strings.TrimSpace(key)
	if trimmed == "" {
		trimmed = "default"
	}
	return s.prefix + ":" + trimmed
}
