package checkpoints

import (
	"strings"
	"testing"

	"rca/internal/rca/config"
)

type stubESClient struct{}

func (stubESClient) GetDocument(index string, id string) (map[string]any, int, error) {
	return nil, 404, nil
}

func (stubESClient) IndexDocument(index string, id string, document map[string]any) error {
	return nil
}

func TestCreateStoreBuildsFileBackend(t *testing.T) {
	store, err := CreateStore(config.CheckpointConfig{Provider: "file", Path: "state/checkpoints.json"}, nil)
	if err != nil {
		t.Fatalf("create store: %v", err)
	}
	if _, ok := store.(*FileStore); !ok {
		t.Fatalf("expected FileStore, got %T", store)
	}
}

func TestCreateStoreBuildsElasticsearchBackend(t *testing.T) {
	store, err := CreateStore(config.CheckpointConfig{Provider: "elasticsearch", ElasticsearchIndex: "rca-checkpoints"}, stubESClient{})
	if err != nil {
		t.Fatalf("create store: %v", err)
	}
	if _, ok := store.(*ElasticsearchStore); !ok {
		t.Fatalf("expected ElasticsearchStore, got %T", store)
	}
}

func TestCreateStoreRejectsUnsupportedProvider(t *testing.T) {
	_, err := CreateStore(config.CheckpointConfig{Provider: "unknown"}, nil)
	if err == nil {
		t.Fatal("expected unsupported provider error")
	}
	if !strings.Contains(err.Error(), "Unsupported checkpoint provider") {
		t.Fatalf("unexpected error: %v", err)
	}
}
