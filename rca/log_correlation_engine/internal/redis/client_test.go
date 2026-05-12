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
	if key := store.activeOrgCursorKey; key != "Rca:active_organizations:rebuild_cursor" {
		t.Fatalf("expected active organization cursor key Rca:active_organizations:rebuild_cursor, got %s", key)
	}
}

func TestScanOrganizationFromKey(t *testing.T) {
	store := NewStore(nil, config.RedisConfig{
		KeyPrefix:  "Rca",
		HashField:  "signaled_logs",
		ResultList: "correlated_events",
	}, nil)

	testCases := []struct {
		name           string
		key            string
		wantOrg        string
		wantInspection bool
	}{
		{
			name:           "signal hash",
			key:            "Rca:org-1",
			wantOrg:        "org-1",
			wantInspection: true,
		},
		{
			name:           "active incident state hash",
			key:            "Rca:org-1:active_incident_states",
			wantOrg:        "org-1",
			wantInspection: false,
		},
		{
			name:           "legacy incident index",
			key:            "Rca:org-1:active_incidents",
			wantOrg:        "org-1",
			wantInspection: false,
		},
		{
			name:           "legacy incident payload",
			key:            "Rca:org-1:incident:abc123",
			wantOrg:        "org-1",
			wantInspection: false,
		},
		{
			name:           "last seen helper",
			key:            "Rca:org-1:active_incidents_by_last_seen",
			wantOrg:        "org-1",
			wantInspection: false,
		},
		{
			name:           "ignore distributed key",
			key:            "Rca:distributed:worker:abc",
			wantOrg:        "",
			wantInspection: false,
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			gotOrg, gotInspection := store.scanOrganizationFromKey(testCase.key)
			if gotOrg != testCase.wantOrg {
				t.Fatalf("expected organization %q, got %q", testCase.wantOrg, gotOrg)
			}
			if gotInspection != testCase.wantInspection {
				t.Fatalf("expected needsInspection=%t, got %t", testCase.wantInspection, gotInspection)
			}
		})
	}
}
