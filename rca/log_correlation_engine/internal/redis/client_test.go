package redis

import (
	"testing"

	"log_correlation_engine/internal/config"
)

func TestStoreKeys(t *testing.T) {
	store := NewStore(nil, config.RedisConfig{
		KeyPrefix:  "Rca",
		HashField:  "signaled_logs",
		ResultList: "correlated_events",
	}, nil)

	if key := store.OrganizationKey("org-1"); key != "Rca:org-1" {
		t.Fatalf("expected organization key Rca:org-1, got %s", key)
	}
	if key := store.ResultKey("org-1"); key != "Rca:org-1:correlated_events" {
		t.Fatalf("expected result key Rca:org-1:correlated_events, got %s", key)
	}
	if key := store.IncidentKey("org-1", "incident-1"); key != "Rca:org-1:incident:incident-1" {
		t.Fatalf("expected legacy incident key Rca:org-1:incident:incident-1, got %s", key)
	}
	if key := store.ActiveIncidentStateKey("org-1"); key != "Rca:org-1:active_incident_states" {
		t.Fatalf("expected active incident state key Rca:org-1:active_incident_states, got %s", key)
	}
	if key := store.ActiveIncidentLastSeenKey("org-1"); key != "Rca:org-1:active_incidents_by_last_seen" {
		t.Fatalf("expected active incident zset key Rca:org-1:active_incidents_by_last_seen, got %s", key)
	}
}
