//go:build !windows

package secrets

import (
	"errors"
	"log/slog"
)

func NewWindowsCredentialStore(_ string, _ *slog.Logger) (*MemoryStore, error) {
	return nil, errors.New("windows credential manager is only available on windows")
}
