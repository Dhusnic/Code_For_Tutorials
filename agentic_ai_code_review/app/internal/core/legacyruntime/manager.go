package legacyruntime

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"agenticai/desktop/internal/core/config"
)

type Manager struct {
	logger          *slog.Logger
	baseURL         string
	autoStart       bool
	autoInstallDeps bool
	pythonBin       string
	scriptPath      string
	startupTimeout  time.Duration
	logFilePath     string

	mu            sync.Mutex
	cmd           *exec.Cmd
	logFile       *os.File
	depsCheckDone bool
	depsReady     bool
	lastError     string
}

func NewManager(settings config.Settings, logger *slog.Logger) *Manager {
	timeout := time.Duration(settings.LegacyStartupTimeoutSeconds) * time.Second
	if timeout < 10*time.Second {
		timeout = 10 * time.Second
	}
	return &Manager{
		logger:          logger,
		baseURL:         strings.TrimRight(strings.TrimSpace(settings.LegacyAPIBaseURL), "/"),
		autoStart:       settings.AutoStartLegacyAPI,
		autoInstallDeps: settings.AutoInstallLegacyDeps,
		pythonBin:       strings.TrimSpace(settings.LegacyAPIPythonBin),
		scriptPath:      strings.TrimSpace(settings.LegacyAPIScriptPath),
		startupTimeout:  timeout,
	}
}

func (m *Manager) EnsureRunning(ctx context.Context) error {
	if m.healthCheck(ctx) {
		return nil
	}
	if !m.autoStart {
		err := errors.New("legacy API is not running and auto-start is disabled")
		m.setLastError(err)
		return err
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.healthCheck(ctx) {
		return nil
	}
	if m.cmd != nil && m.cmd.Process != nil && m.cmd.ProcessState == nil {
		return m.waitForHealth(ctx, m.startupTimeout)
	}

	repoRoot, err := m.resolveRepoRoot()
	if err != nil {
		m.setLastErrorLocked(err)
		return err
	}
	scriptAbs := filepath.Join(repoRoot, filepath.FromSlash(m.scriptPath))
	if _, statErr := os.Stat(scriptAbs); statErr != nil {
		err = fmt.Errorf("legacy API script not found: %s", scriptAbs)
		m.setLastErrorLocked(err)
		return err
	}
	if depsErr := m.ensurePythonDependencies(ctx, repoRoot); depsErr != nil {
		m.setLastErrorLocked(depsErr)
		return depsErr
	}

	logPath, logFile, logErr := m.openLogFile(repoRoot)
	if logErr != nil {
		m.setLastErrorLocked(logErr)
		return logErr
	}
	m.logFilePath = logPath
	m.logFile = logFile

	cmd := exec.Command(m.pythonBin, scriptAbs)
	cmd.Dir = repoRoot
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	applyPlatformAttrs(cmd)

	if startErr := cmd.Start(); startErr != nil {
		_ = logFile.Close()
		m.logFile = nil
		err = fmt.Errorf("failed to start legacy API process: %w", startErr)
		m.setLastErrorLocked(err)
		return err
	}
	m.cmd = cmd
	if m.logger != nil {
		m.logger.Info("started legacy API process", "pid", cmd.Process.Pid, "script", scriptAbs, "log_file", logPath)
	}

	go m.waitProcessExit(cmd, logFile)
	waitErr := m.waitForHealth(ctx, m.startupTimeout)
	if waitErr != nil {
		err = fmt.Errorf("%w. startup logs: %s", waitErr, logPath)
		m.setLastErrorLocked(err)
		return err
	}
	m.setLastErrorLocked(nil)
	return nil
}

func (m *Manager) ensurePythonDependencies(ctx context.Context, repoRoot string) error {
	if m.depsCheckDone && m.depsReady {
		return nil
	}

	importCheck := []string{
		"-c",
		"import fastapi,uvicorn,pydantic,openai,requests,git,tiktoken,yaml",
	}
	if err := m.runPythonCommand(ctx, repoRoot, importCheck...); err == nil {
		m.depsCheckDone = true
		m.depsReady = true
		return nil
	}

	if !m.autoInstallDeps {
		err := errors.New(
			"legacy API dependencies are missing. Install them with: " +
				"python -m pip install fastapi uvicorn pydantic openai requests GitPython tiktoken pyyaml",
		)
		m.setLastErrorLocked(err)
		return err
	}

	if m.logger != nil {
		m.logger.Info("missing legacy API dependencies detected; attempting desktop-managed pip install")
	}

	installCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()
	installArgs := []string{
		"-m",
		"pip",
		"install",
		"--disable-pip-version-check",
		"fastapi",
		"uvicorn",
		"pydantic",
		"openai",
		"requests",
		"GitPython",
		"tiktoken",
		"pyyaml",
	}
	if err := m.runPythonCommand(installCtx, repoRoot, installArgs...); err != nil {
		wrapped := fmt.Errorf("desktop-managed dependency install failed: %w", err)
		m.setLastErrorLocked(wrapped)
		return wrapped
	}
	if err := m.runPythonCommand(ctx, repoRoot, importCheck...); err != nil {
		wrapped := fmt.Errorf("legacy dependencies still unavailable after install: %w", err)
		m.setLastErrorLocked(wrapped)
		return wrapped
	}
	m.depsCheckDone = true
	m.depsReady = true
	m.setLastErrorLocked(nil)
	return nil
}

func (m *Manager) waitProcessExit(cmd *exec.Cmd, logFile *os.File) {
	_ = cmd.Wait()
	if logFile != nil {
		_ = logFile.Close()
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.cmd == cmd {
		m.cmd = nil
		m.logFile = nil
	}
}

func (m *Manager) waitForHealth(ctx context.Context, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if m.healthCheck(ctx) {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(800 * time.Millisecond):
		}
	}
	return fmt.Errorf("legacy API did not become healthy within %s", timeout.String())
}

func (m *Manager) healthCheck(ctx context.Context) bool {
	base := m.baseURL
	if base == "" {
		base = "http://127.0.0.1:8000"
	}
	url := base + "/api/health"

	healthCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	request, err := http.NewRequestWithContext(healthCtx, http.MethodGet, url, nil)
	if err != nil {
		return false
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return false
	}
	defer response.Body.Close()
	return response.StatusCode >= 200 && response.StatusCode < 300
}

func (m *Manager) Status(ctx context.Context) map[string]any {
	m.mu.Lock()
	defer m.mu.Unlock()

	processRunning := m.cmd != nil && m.cmd.Process != nil && m.cmd.ProcessState == nil
	status := map[string]any{
		"base_url":                 defaultBaseURL(m.baseURL),
		"auto_start":               m.autoStart,
		"auto_install_deps":        m.autoInstallDeps,
		"python_bin":               m.pythonBin,
		"script_path":              m.scriptPath,
		"startup_timeout_seconds":  int(m.startupTimeout / time.Second),
		"log_file_path":            m.logFilePath,
		"process_running":          processRunning,
		"deps_check_completed":     m.depsCheckDone,
		"deps_ready":               m.depsReady,
		"last_error":               m.lastError,
		"health_endpoint_reachable": false,
	}
	status["health_endpoint_reachable"] = m.healthCheck(ctx)
	return status
}

func (m *Manager) Stop() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.cmd == nil || m.cmd.Process == nil || m.cmd.ProcessState != nil {
		if m.logFile != nil {
			_ = m.logFile.Close()
			m.logFile = nil
		}
		return nil
	}

	err := m.cmd.Process.Kill()
	if m.logFile != nil {
		_ = m.logFile.Close()
		m.logFile = nil
	}
	m.cmd = nil
	if err != nil {
		m.lastError = err.Error()
		return err
	}
	m.lastError = ""
	return nil
}

func (m *Manager) resolveRepoRoot() (string, error) {
	if explicit := strings.TrimSpace(os.Getenv("AGENTIC_REPO_ROOT")); explicit != "" {
		if m.hasScript(explicit) {
			return explicit, nil
		}
	}

	execPath, execErr := os.Executable()
	if execErr == nil {
		if repoRoot, ok := m.findScriptRootFrom(filepath.Dir(execPath)); ok {
			return repoRoot, nil
		}
	}

	cwd, cwdErr := os.Getwd()
	if cwdErr == nil {
		if repoRoot, ok := m.findScriptRootFrom(cwd); ok {
			return repoRoot, nil
		}
	}

	return "", fmt.Errorf(
		"unable to resolve repository root for legacy API script '%s'; set AGENTIC_REPO_ROOT to the repo path",
		m.scriptPath,
	)
}

func (m *Manager) findScriptRootFrom(start string) (string, bool) {
	current := strings.TrimSpace(start)
	if current == "" {
		return "", false
	}
	if abs, err := filepath.Abs(current); err == nil {
		current = abs
	}

	for {
		if m.hasScript(current) {
			return current, true
		}
		parent := filepath.Dir(current)
		if parent == current {
			return "", false
		}
		current = parent
	}
}

func (m *Manager) hasScript(root string) bool {
	if strings.TrimSpace(root) == "" {
		return false
	}
	path := filepath.Join(root, filepath.FromSlash(m.scriptPath))
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func (m *Manager) openLogFile(repoRoot string) (string, *os.File, error) {
	logDir := ""
	if appData := strings.TrimSpace(os.Getenv("APPDATA")); appData != "" {
		logDir = filepath.Join(appData, "AgenticAICodeReview", "logs")
	} else {
		logDir = filepath.Join(repoRoot, "logs")
	}
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		return "", nil, err
	}
	logPath := filepath.Join(logDir, "legacy-api.log")
	file, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return "", nil, err
	}
	return logPath, file, nil
}

func (m *Manager) runPythonCommand(ctx context.Context, workingDir string, args ...string) error {
	command := exec.CommandContext(ctx, m.pythonBin, args...)
	command.Dir = workingDir
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("python command failed: %s %s :: %w :: %s", m.pythonBin, strings.Join(args, " "), err, string(output))
	}
	return nil
}

func (m *Manager) setLastError(err error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.setLastErrorLocked(err)
}

func (m *Manager) setLastErrorLocked(err error) {
	if err == nil {
		m.lastError = ""
		return
	}
	m.lastError = err.Error()
}

func defaultBaseURL(value string) string {
	base := strings.TrimSpace(value)
	if base == "" {
		return "http://127.0.0.1:8000"
	}
	return base
}
