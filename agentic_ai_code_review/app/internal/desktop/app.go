package desktop

import (
	"context"
	"log/slog"
	"strconv"
	"time"

	"agenticai/desktop/internal/contracts"
	"agenticai/desktop/internal/core/config"
	"agenticai/desktop/internal/core/events"
	"agenticai/desktop/internal/core/jobs"
	"agenticai/desktop/internal/core/legacyruntime"
	"agenticai/desktop/internal/core/logging"
	"agenticai/desktop/internal/core/secrets"
	"agenticai/desktop/internal/services"
	"agenticai/desktop/internal/services/legacy"
	"agenticai/desktop/internal/services/native"
)

type App struct {
	logger      *slog.Logger
	settings    config.Settings
	configPath  string
	service     services.DesktopService
	secretStore secrets.Store
	jobManager  *jobs.Manager
	eventBus    *events.Bus
	legacyRun   *legacyruntime.Manager
}

func New(configPath string) (*App, error) {
	settings, resolvedPath, err := config.Load(configPath)
	if err != nil {
		return nil, err
	}

	logger := logging.New(settings.LogLevel)
	legacyRun := legacyruntime.NewManager(settings, logger)
	service := buildService(settings, logger, legacyRun)

	app := &App{
		logger:      logger,
		settings:    settings,
		configPath:  resolvedPath,
		service:     service,
		secretStore: secrets.NewDefaultStore(logger),
		jobManager:  jobs.NewManager(2 * time.Hour),
		eventBus:    events.NewBus(),
		legacyRun:   legacyRun,
	}
	if settings.AutoStartLegacyAPI {
		go func() {
			if err := legacyRun.EnsureRunning(context.Background()); err != nil && logger != nil {
				logger.Warn("legacy API auto-start on boot failed", "error", err.Error())
			}
		}()
	}
	return app, nil
}

func (a *App) Health() map[string]any {
	return map[string]any{
		"status":       "healthy",
		"service":      "agentic-ai-code-review-desktop",
		"service_mode": a.settings.ServiceMode,
	}
}

func (a *App) GetSettings() map[string]any {
	return map[string]any{
		"path": a.configPath,
		"config": map[string]any{
			"service_mode":                   a.settings.ServiceMode,
			"legacy_api_base_url":            a.settings.LegacyAPIBaseURL,
			"request_timeout_seconds":        a.settings.RequestTimeoutSeconds,
			"log_level":                      a.settings.LogLevel,
			"auto_start_legacy_api":          a.settings.AutoStartLegacyAPI,
			"legacy_api_python_bin":          a.settings.LegacyAPIPythonBin,
			"legacy_api_script_path":         a.settings.LegacyAPIScriptPath,
			"legacy_startup_timeout_seconds": a.settings.LegacyStartupTimeoutSeconds,
			"auto_install_legacy_deps":       a.settings.AutoInstallLegacyDeps,
		},
	}
}

func (a *App) SaveSettings(input map[string]any) (map[string]any, error) {
	next := a.settings
	if value, ok := input["service_mode"].(string); ok {
		next.ServiceMode = value
	}
	if value, ok := input["legacy_api_base_url"].(string); ok {
		next.LegacyAPIBaseURL = value
	}
	if value, ok := input["log_level"].(string); ok {
		next.LogLevel = value
	}
	if value, ok := input["request_timeout_seconds"].(float64); ok {
		next.RequestTimeoutSeconds = int(value)
	}
	if value, ok := input["request_timeout_seconds"].(int); ok {
		next.RequestTimeoutSeconds = value
	}
	if value, ok := input["request_timeout_seconds"].(string); ok {
		parsed, err := strconv.Atoi(value)
		if err == nil {
			next.RequestTimeoutSeconds = parsed
		}
	}
	if value, ok := input["auto_start_legacy_api"].(bool); ok {
		next.AutoStartLegacyAPI = value
	}
	if value, ok := input["legacy_api_python_bin"].(string); ok {
		next.LegacyAPIPythonBin = value
	}
	if value, ok := input["legacy_api_script_path"].(string); ok {
		next.LegacyAPIScriptPath = value
	}
	if value, ok := input["legacy_startup_timeout_seconds"].(float64); ok {
		next.LegacyStartupTimeoutSeconds = int(value)
	}
	if value, ok := input["legacy_startup_timeout_seconds"].(int); ok {
		next.LegacyStartupTimeoutSeconds = value
	}
	if value, ok := input["legacy_startup_timeout_seconds"].(string); ok {
		parsed, err := strconv.Atoi(value)
		if err == nil {
			next.LegacyStartupTimeoutSeconds = parsed
		}
	}
	if value, ok := input["auto_install_legacy_deps"].(bool); ok {
		next.AutoInstallLegacyDeps = value
	}

	if err := config.Save(a.configPath, next); err != nil {
		return nil, err
	}

	a.settings = next
	a.legacyRun = legacyruntime.NewManager(a.settings, a.logger)
	a.service = buildService(a.settings, a.logger, a.legacyRun)
	if a.settings.AutoStartLegacyAPI {
		go func() {
			if err := a.legacyRun.EnsureRunning(context.Background()); err != nil && a.logger != nil {
				a.logger.Warn("legacy API auto-start after settings save failed", "error", err.Error())
			}
		}()
	}
	return a.GetSettings(), nil
}

func (a *App) RunFullReview(request contracts.ConfigModel, async bool) (map[string]any, error) {
	return a.service.RunFullReview(a.context(), request, async)
}

func (a *App) ReviewDiffs(request contracts.ConfigModel, async bool) (map[string]any, error) {
	return a.service.ReviewDiffs(a.context(), request, async)
}

func (a *App) GenerateChanges(request contracts.ConfigModel) (map[string]any, error) {
	return a.service.GenerateChanges(a.context(), request)
}

func (a *App) ApplyChanges(request contracts.ApplyChangesModel) (map[string]any, error) {
	return a.service.ApplyChanges(a.context(), request)
}

func (a *App) RunStaticChecks(request contracts.StaticChecksRequestModel, async bool) (map[string]any, error) {
	return a.service.RunStaticChecks(a.context(), request, async)
}

func (a *App) GetUsageMetrics() (map[string]any, error) {
	return a.service.GetUsageMetrics(a.context())
}

func (a *App) GetFeatureContext(request contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	return a.service.GetFeatureContext(a.context(), request)
}

func (a *App) ListChangedFiles(request contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	return a.service.ListChangedFiles(a.context(), request)
}

func (a *App) ListReviewers(request contracts.PRReviewersRequestModel) (map[string]any, error) {
	return a.service.ListReviewers(a.context(), request)
}

func (a *App) GetWorkItemFamily(request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	return a.service.GetWorkItemFamily(a.context(), request)
}

func (a *App) RaiseNewPR(request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error) {
	return a.service.RaiseNewPR(a.context(), request, async)
}

func (a *App) CherryPick(request contracts.CherryPickRequestModel) (map[string]any, error) {
	return a.service.CherryPick(a.context(), request)
}

func (a *App) CommitAndPush(request contracts.CommitAndPushRequestModel) (map[string]any, error) {
	return a.service.CommitAndPush(a.context(), request)
}

func (a *App) GetJob(jobID string) (map[string]any, error) {
	return a.service.GetJob(a.context(), jobID)
}

func (a *App) ProceedJob(jobID, requestID string) (map[string]any, error) {
	return a.service.ProceedJob(a.context(), jobID, requestID)
}

func (a *App) GetApprovalPreview(jobID, requestID string) (map[string]any, error) {
	return a.service.GetApprovalPreview(a.context(), jobID, requestID)
}

func (a *App) SetSecret(key, value string) map[string]any {
	err := a.secretStore.Set(context.Background(), key, value)
	if err != nil {
		return map[string]any{"ok": false, "error": err.Error()}
	}
	return map[string]any{"ok": true}
}

func (a *App) DeleteSecret(key string) map[string]any {
	err := a.secretStore.Delete(context.Background(), key)
	if err != nil {
		return map[string]any{"ok": false, "error": err.Error()}
	}
	return map[string]any{"ok": true}
}

func (a *App) context() context.Context {
	return context.Background()
}

func buildService(
	settings config.Settings,
	logger *slog.Logger,
	legacyRun *legacyruntime.Manager,
) services.DesktopService {
	timeout := config.Timeout(settings)
	ensureRunning := func(ctx context.Context) error {
		if legacyRun == nil {
			return nil
		}
		return legacyRun.EnsureRunning(ctx)
	}
	switch settings.ServiceMode {
	case config.ServiceModeNative:
		return native.NewService(settings.LegacyAPIBaseURL, timeout, logger, ensureRunning)
	case config.ServiceModeHybrid:
		// Hybrid currently routes all operations through the same stable bridge path.
		return native.NewService(settings.LegacyAPIBaseURL, timeout, logger, ensureRunning)
	default:
		return legacy.NewClient(settings.LegacyAPIBaseURL, timeout, logger, ensureRunning)
	}
}
