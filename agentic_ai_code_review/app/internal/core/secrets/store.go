package secrets

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

var ErrSecretReadUnsupported = errors.New("secret read is not supported by the configured store")

type Store interface {
	Get(ctx context.Context, key string) (string, error)
	Set(ctx context.Context, key, value string) error
	Delete(ctx context.Context, key string) error
}

type MemoryStore struct {
	mu    sync.RWMutex
	items map[string]string
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		items: make(map[string]string),
	}
}

func (s *MemoryStore) Get(_ context.Context, key string) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.items[key], nil
}

func (s *MemoryStore) Set(_ context.Context, key, value string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.items[key] = value
	return nil
}

func (s *MemoryStore) Delete(_ context.Context, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.items, key)
	return nil
}

func NewDefaultStore(logger *slog.Logger) Store {
	if store, err := NewWindowsCredentialStore("AgenticAICodeReview", logger); err == nil {
		return store
	}
	return NewMemoryStore()
}
