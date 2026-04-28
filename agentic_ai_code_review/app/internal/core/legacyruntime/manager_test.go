package legacyruntime

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindScriptRootFromWalksUpToRepoRoot(t *testing.T) {
	repoRoot := t.TempDir()
	webDir := filepath.Join(repoRoot, "web")
	if err := os.MkdirAll(webDir, 0o755); err != nil {
		t.Fatalf("failed to create web dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(webDir, "main.py"), []byte("print('ok')\n"), 0o644); err != nil {
		t.Fatalf("failed to create legacy script: %v", err)
	}
	startDir := filepath.Join(repoRoot, "app", "build", "bin")
	if err := os.MkdirAll(startDir, 0o755); err != nil {
		t.Fatalf("failed to create start dir: %v", err)
	}

	manager := &Manager{scriptPath: "web/main.py"}
	resolved, ok := manager.findScriptRootFrom(startDir)
	if !ok {
		t.Fatal("expected repo root to be resolved")
	}
	if resolved != repoRoot {
		t.Fatalf("expected %q, got %q", repoRoot, resolved)
	}
}

func TestFindScriptRootFromReturnsFalseWhenScriptMissing(t *testing.T) {
	manager := &Manager{scriptPath: "web/main.py"}
	if resolved, ok := manager.findScriptRootFrom(t.TempDir()); ok {
		t.Fatalf("expected no repo root, got %q", resolved)
	}
}
