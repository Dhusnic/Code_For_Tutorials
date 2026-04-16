package topology

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestFileRepositoryLoadsDeviceIPTopologyNodes(t *testing.T) {
	path := filepath.Join(t.TempDir(), "topology.json")
	payload := `{
	  "schema_version": 1,
	  "organizations": {
	    "org-1": {
	      "topology_current": {
	        "services": [
	          { "device_ip": "10.0.4.72", "service_name": "nginx" }
	        ],
	        "dependencies": [
	          { "from": "10.0.4.72", "to": "10.0.4.73" }
	        ]
	      }
	    }
	  }
	}`
	if err := os.WriteFile(path, []byte(payload), 0o644); err != nil {
		t.Fatalf("write test file: %v", err)
	}

	repo := NewFileRepository(path)
	document, err := repo.Load(context.Background())
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}
	service := document.Organizations["org-1"]["topology_current"].Services[0]
	if service.DeviceIP != "10.0.4.72" {
		t.Fatalf("expected device IP 10.0.4.72, got %#v", service)
	}
}

func TestFileRepositoryReturnsDecodeErrorForMalformedJSON(t *testing.T) {
	path := filepath.Join(t.TempDir(), "topology.json")
	if err := os.WriteFile(path, []byte("{invalid"), 0o644); err != nil {
		t.Fatalf("write test file: %v", err)
	}

	repo := NewFileRepository(path)
	if _, err := repo.Load(context.Background()); err == nil {
		t.Fatalf("expected malformed JSON error")
	}
}

func TestFileRepositoryLoadsMultipleTopologiesPerOrganization(t *testing.T) {
	path := filepath.Join(t.TempDir(), "topology.json")
	payload := `{
	  "schema_version": 1,
	  "organizations": {
	    "org-1": {
	      "topo-a": {
	          "services": [{ "device_ip": "10.0.4.72", "service_name": "api" }],
	          "dependencies": [{ "from": "10.0.4.72::api", "to": "10.0.4.72::redis" }]
	        },
	        "topo-b": {
	          "services": [{ "device_ip": "10.1.4.72", "service_name": "api" }],
	          "dependencies": [{ "from": "10.1.4.72::api", "to": "10.1.4.72::redis" }]
	        }
	    }
	  }
	}`
	if err := os.WriteFile(path, []byte(payload), 0o644); err != nil {
		t.Fatalf("write test file: %v", err)
	}

	repo := NewFileRepository(path)
	document, err := repo.Load(context.Background())
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}
	org := document.Organizations["org-1"]
	if len(org) != 2 {
		t.Fatalf("expected 2 topologies, got %d", len(org))
	}
	if org["topo-b"].Services[0].DeviceIP != "10.1.4.72" {
		t.Fatalf("expected topology topo-b to contain 10.1.4.72, got %#v", org["topo-b"].Services)
	}
}
