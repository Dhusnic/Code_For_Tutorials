package redisstore

import (
	"log/slog"
	"testing"

	"log_signal_processor/internal/config"
)

func TestStoreKeys(t *testing.T) {
	store := NewStore(nil, config.RedisConfig{
		KeyPrefix: "Rca",
		HashField: "signaled_logs",
	}, slog.Default(), "Rca:collector_lock")

	if key := store.OrganizationKey("org-1"); key != "Rca:org-1" {
		t.Fatalf("expected organization key Rca:org-1, got %s", key)
	}
	if _, ok := store.reservedKeys["Rca:collector_lock"]; !ok {
		t.Fatalf("expected explicit reserved key to be retained")
	}
}
