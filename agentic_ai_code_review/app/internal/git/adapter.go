package git

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

var retryableFetchErrors = []string{
	"rpc failed",
	"curl 56",
	"recv failure",
	"connection was reset",
	"unexpected disconnect",
	"early eof",
	"invalid index-pack output",
	"failed to connect",
	"timed out",
	"operation too slow",
}

type Result struct {
	Command    string `json:"command"`
	ExitCode   int    `json:"exit_code"`
	Stdout     string `json:"stdout"`
	Stderr     string `json:"stderr"`
	DurationMS int64  `json:"duration_ms"`
}

type Adapter struct {
	logger          *slog.Logger
	maxFetchRetries int
}

func NewAdapter(logger *slog.Logger) *Adapter {
	return &Adapter{
		logger:          logger,
		maxFetchRetries: 3,
	}
}

func (a *Adapter) EnsureGitRepo(ctx context.Context, repoPath string) error {
	repo, err := resolveRepoPath(repoPath)
	if err != nil {
		return err
	}

	result, err := a.runOnce(ctx, repo, "rev-parse", "--is-inside-work-tree")
	if err != nil {
		return err
	}
	if strings.TrimSpace(strings.ToLower(result.Stdout)) != "true" {
		return fmt.Errorf("not a git repository: %s", repo)
	}
	return nil
}

func (a *Adapter) Run(ctx context.Context, repoPath string, args ...string) (Result, error) {
	repo, err := resolveRepoPath(repoPath)
	if err != nil {
		return Result{}, err
	}
	if len(args) == 0 {
		return Result{}, errors.New("git args cannot be empty")
	}

	retries := 1
	if isFetchOperation(args) {
		retries = a.maxFetchRetries
	}

	var lastResult Result
	var lastErr error
	for attempt := 1; attempt <= retries; attempt++ {
		lastResult, lastErr = a.runOnce(ctx, repo, args...)
		if lastErr == nil {
			return lastResult, nil
		}
		if !isRetryable(lastResult.Stderr) || attempt == retries {
			return lastResult, lastErr
		}

		backoff := time.Duration(attempt) * time.Second
		if a.logger != nil {
			a.logger.Warn(
				"retryable git error; retrying",
				"attempt", attempt,
				"max_attempts", retries,
				"repo", repo,
				"args", strings.Join(args, " "),
				"backoff", backoff.String(),
			)
		}
		select {
		case <-ctx.Done():
			return lastResult, ctx.Err()
		case <-time.After(backoff):
		}
	}
	return lastResult, lastErr
}

func (a *Adapter) runOnce(ctx context.Context, repo string, args ...string) (Result, error) {
	started := time.Now()
	command := exec.CommandContext(ctx, "git", args...)
	command.Dir = repo
	output, err := command.CombinedOutput()
	duration := time.Since(started)
	text := string(output)

	result := Result{
		Command:    "git " + strings.Join(args, " "),
		ExitCode:   0,
		Stdout:     text,
		Stderr:     text,
		DurationMS: duration.Milliseconds(),
	}

	if command.ProcessState != nil {
		result.ExitCode = command.ProcessState.ExitCode()
	}

	if err != nil {
		if a.logger != nil {
			a.logger.Error("git command failed",
				"repo", repo,
				"command", result.Command,
				"duration_ms", result.DurationMS,
				"error", err.Error(),
			)
		}
		return result, fmt.Errorf("git command failed: %s :: %w", result.Command, err)
	}
	return result, nil
}

func resolveRepoPath(path string) (string, error) {
	trimmed := strings.TrimSpace(path)
	if trimmed == "" {
		return "", errors.New("repo path is required")
	}
	resolved, err := filepath.Abs(trimmed)
	if err != nil {
		return "", err
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", fmt.Errorf("repo path is not a directory: %s", resolved)
	}
	return resolved, nil
}

func isFetchOperation(args []string) bool {
	if len(args) == 0 {
		return false
	}
	joined := strings.ToLower(strings.Join(args, " "))
	return strings.Contains(joined, " fetch") || strings.HasPrefix(joined, "fetch ")
}

func isRetryable(stderr string) bool {
	normalized := strings.ToLower(stderr)
	for _, item := range retryableFetchErrors {
		if strings.Contains(normalized, item) {
			return true
		}
	}
	return false
}
