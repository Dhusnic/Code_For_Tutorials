package utils

import (
	"testing"
	"time"
)

func TestParseDuration(t *testing.T) {
	tests := []struct {
		input    string
		expected time.Duration
	}{
		{"5s", 5 * time.Second},
		{"10m", 10 * time.Minute},
		{"1h", time.Hour},
		{"2d", 2 * 24 * time.Hour},
	}

	for _, test := range tests {
		result, err := ParseDuration(test.input)
		if err != nil {
			t.Errorf("Expected no error for %s, got %v", test.input, err)
		}

		if result != test.expected {
			t.Errorf("Expected %v for %s, got %v", test.expected, test.input, result)
		}
	}
}

func TestExtractGroupByValues(t *testing.T) {
	metadata := map[string]interface{}{
		"event.organization": "org123",
		"host.name":          "host1",
		"service.name":       "api",
	}

	fields := []string{"event.organization", "host.name"}
	result := ExtractGroupByValues(metadata, fields)

	if result["event.organization"] != "org123" {
		t.Errorf("Expected org123, got %s", result["event.organization"])
	}

	if result["host.name"] != "host1" {
		t.Errorf("Expected host1, got %s", result["host.name"])
	}
}

func TestExtractGroupByValueSupportsDerivedTopologyIdentities(t *testing.T) {
	metadata := map[string]interface{}{
		"event": map[string]interface{}{
			"module": "mongodb",
		},
		"host": map[string]interface{}{
			"name": "host1",
			"ip":   "172.16.1.10, 10.0.4.72",
		},
		"service": map[string]interface{}{
			"name": "api",
		},
	}

	if got := ExtractGroupByValue(metadata, "host.ip"); got != "172.16.1.10" {
		t.Fatalf("expected primary host ip, got %q", got)
	}
	if got := ExtractGroupByValue(metadata, "service.identity"); got != "api" {
		t.Fatalf("expected service identity api, got %q", got)
	}
	if got := ExtractGroupByValue(metadata, "host.identity"); got != "172.16.1.10" {
		t.Fatalf("expected host identity from ip, got %q", got)
	}
	if got := ExtractGroupByValue(metadata, "topology.identity"); got != "172.16.1.10::api" {
		t.Fatalf("expected topology identity, got %q", got)
	}
}
