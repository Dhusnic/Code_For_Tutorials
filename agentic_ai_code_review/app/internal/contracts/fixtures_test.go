package contracts

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestFixturesAreValidJSON(t *testing.T) {
	t.Parallel()

	fixturesDir := filepath.Join(".", "fixtures")
	entries, err := os.ReadDir(fixturesDir)
	if err != nil {
		t.Fatalf("failed to read fixtures directory: %v", err)
	}

	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}
		path := filepath.Join(fixturesDir, entry.Name())
		raw, readErr := os.ReadFile(path)
		if readErr != nil {
			t.Fatalf("failed to read fixture %s: %v", path, readErr)
		}
		var parsed any
		if unmarshalErr := json.Unmarshal(raw, &parsed); unmarshalErr != nil {
			t.Fatalf("invalid json fixture %s: %v", path, unmarshalErr)
		}
	}
}
