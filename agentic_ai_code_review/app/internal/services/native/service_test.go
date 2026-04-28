package native

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"agenticai/desktop/internal/contracts"
)

func TestNativeServiceReviewsLocalDiffWithoutBridge(t *testing.T) {
	repo := initGitRepo(t)
	writeFile(t, filepath.Join(repo, "app.go"), "package main\n\nfunc main() {}\n")
	runGit(t, repo, "add", ".")
	runGit(t, repo, "commit", "-m", "initial")
	writeFile(t, filepath.Join(repo, "app.go"), "package main\n\nfunc main() {\n\tpanic(\"boom\")\n}\n")

	service := NewService(nil, nil)
	result, err := service.ReviewDiffs(context.Background(), contracts.ConfigModel{
		RepoPath: repo,
		IsLocal:  true,
	}, false)
	if err != nil {
		t.Fatalf("ReviewDiffs returned error: %v", err)
	}
	if result["desktop_execution_mode"] != executionMode {
		t.Fatalf("expected native execution mode, got %v", result["desktop_execution_mode"])
	}
	review := strings.ToLower(result["review"].(string))
	if !strings.Contains(review, "panic") {
		t.Fatalf("expected native review to flag panic, got %s", result["review"])
	}
}

func TestNativeStaticChecksValidateJSON(t *testing.T) {
	repo := t.TempDir()
	writeFile(t, filepath.Join(repo, "bad.json"), "{nope")

	service := NewService(nil, nil)
	result, err := service.RunStaticChecks(context.Background(), contracts.StaticChecksRequestModel{
		RepoPath: repo,
	}, false)
	if err != nil {
		t.Fatalf("RunStaticChecks returned error: %v", err)
	}
	summary := result["summary"].(map[string]any)
	if summary["issues_high"].(int) != 1 {
		t.Fatalf("expected one high issue, got %#v", summary)
	}
}

func TestApplyChangesWritesBackupAndPatch(t *testing.T) {
	repo := t.TempDir()
	target := filepath.Join(repo, "file.txt")
	writeFile(t, target, "old\n")

	service := NewService(nil, nil)
	result, err := service.ApplyChanges(context.Background(), contracts.ApplyChangesModel{
		RepoPath:           repo,
		FilePath:           "file.txt",
		OldContent:         "old\n",
		NewContent:         "new\n",
		LineNumber:         1,
		OldStartLineNumber: 1,
	})
	if err != nil {
		t.Fatalf("ApplyChanges returned error: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("expected success, got %#v", result)
	}
	raw, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) != "new\n" {
		t.Fatalf("expected patched content, got %q", string(raw))
	}
	if _, err := os.Stat(result["backup_path"].(string)); err != nil {
		t.Fatalf("expected backup file: %v", err)
	}
}

func initGitRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	runGit(t, repo, "init")
	runGit(t, repo, "config", "user.email", "test@example.com")
	runGit(t, repo, "config", "user.name", "Test User")
	return repo
}

func runGit(t *testing.T, repo string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", args...)
	cmd.Dir = repo
	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %s failed: %v\n%s", strings.Join(args, " "), err, string(output))
	}
}

func writeFile(t *testing.T, path string, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}
