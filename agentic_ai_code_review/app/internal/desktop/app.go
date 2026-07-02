package desktop

import (
	"context"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"time"

	"agenticai/desktop/internal/contracts"
	"agenticai/desktop/internal/core/config"
	"agenticai/desktop/internal/core/events"
	"agenticai/desktop/internal/core/jobs"
	"agenticai/desktop/internal/core/legacyruntime"
	"agenticai/desktop/internal/core/logging"
	"agenticai/desktop/internal/core/secrets"
	"agenticai/desktop/internal/services/legacy"
	"agenticai/desktop/internal/services"
	"agenticai/desktop/internal/services/native"
)

type App struct {
	logger      *slog.Logger
	settings    config.Settings
	configPath  string
	service     services.DesktopService
	secretStore secrets.Store
	legacyMgr   *legacyruntime.Manager
	jobManager  *jobs.Manager
	eventBus    *events.Bus
}

func New(configPath string) (*App, error) {
	settings, resolvedPath, err := config.Load(configPath)
	if err != nil {
		return nil, err
	}

	logger := logging.New(settings.LogLevel)
	jobManager := jobs.NewManager(2 * time.Hour)
	service, legacyMgr := buildRuntime(settings, logger, jobManager)

	app := &App{
		logger:      logger,
		settings:    settings,
		configPath:  resolvedPath,
		service:     service,
		secretStore: secrets.NewDefaultStore(logger),
		legacyMgr:   legacyMgr,
		jobManager:  jobManager,
		eventBus:    events.NewBus(),
	}
	return app, nil
}

func (a *App) Health() map[string]any {
	health := map[string]any{
		"status":       "healthy",
		"service":      "agentic-ai-code-review-desktop",
		"service_mode": a.settings.ServiceMode,
		"request_timeout_seconds": a.settings.RequestTimeoutSeconds,
		"runtime":                "wails-native",
		"secret_store":           secretStoreMetadata(a.secretStore),
	}
	if a.legacyMgr != nil {
		health["compatibility_backend"] = a.legacyMgr.Status(a.context())
	}
	return health
}

func (a *App) GetSettings() map[string]any {
	return map[string]any{
		"path": a.configPath,
		"config": map[string]any{
			"service_mode":                    a.settings.ServiceMode,
			"legacy_api_base_url":             a.settings.LegacyAPIBaseURL,
			"request_timeout_seconds":         a.settings.RequestTimeoutSeconds,
			"log_level":                       a.settings.LogLevel,
			"auto_start_legacy_api":           a.settings.AutoStartLegacyAPI,
			"legacy_api_python_bin":           a.settings.LegacyAPIPythonBin,
			"legacy_api_script_path":          a.settings.LegacyAPIScriptPath,
			"legacy_startup_timeout_seconds":  a.settings.LegacyStartupTimeoutSeconds,
			"auto_install_legacy_deps":        a.settings.AutoInstallLegacyDeps,
			"runtime":                         "wails-native",
			"external_backend_required":       a.settings.ServiceMode != config.ServiceModeNative,
			"compatibility_backend_supported": true,
			"secret_store":                    secretStoreMetadata(a.secretStore),
		},
		"health": a.Health(),
	}
}

func (a *App) SaveSettings(input map[string]any) (map[string]any, error) {
	next := a.settings
	if value, ok := input["service_mode"].(string); ok {
		next.ServiceMode = value
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
	if value, ok := input["legacy_api_base_url"].(string); ok {
		next.LegacyAPIBaseURL = value
	}
	if value, ok := input["auto_start_legacy_api"]; ok {
		next.AutoStartLegacyAPI = coerceBool(value, next.AutoStartLegacyAPI)
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
	if value, ok := input["auto_install_legacy_deps"]; ok {
		next.AutoInstallLegacyDeps = coerceBool(value, next.AutoInstallLegacyDeps)
	}
	if err := config.Save(a.configPath, next); err != nil {
		return nil, err
	}
	loadedSettings, _, err := config.Load(a.configPath)
	if err != nil {
		return nil, err
	}

	if a.legacyMgr != nil {
		_ = a.legacyMgr.Stop()
	}
	a.settings = loadedSettings
	a.service, a.legacyMgr = buildRuntime(a.settings, a.logger, a.jobManager)
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

func (a *App) Shutdown() {
	if a.legacyMgr != nil {
		_ = a.legacyMgr.Stop()
	}
}

func (a *App) context() context.Context {
	return context.Background()
}

func buildRuntime(settings config.Settings, logger *slog.Logger, jobManager *jobs.Manager) (services.DesktopService, *legacyruntime.Manager) {
	nativeService := native.NewService(logger, jobManager)
	legacyManager := legacyruntime.NewManager(settings, logger)
	legacyService := legacy.NewClient(
		settings.LegacyAPIBaseURL,
		config.Timeout(settings),
		logger,
		legacyManager.EnsureRunning,
	)

	switch settings.ServiceMode {
	case config.ServiceModeLegacy:
		return legacyService, legacyManager
	case config.ServiceModeNative:
		return nativeService, legacyManager
	default:
		return services.NewRouter(settings.ServiceMode, nativeService, legacyService), legacyManager
	}
}

func coerceBool(value any, fallback bool) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		normalized := strings.ToLower(strings.TrimSpace(typed))
		switch normalized {
		case "1", "true", "yes", "on":
			return true
		case "0", "false", "no", "off":
			return false
		}
	case float64:
		return typed != 0
	case int:
		return typed != 0
	}
	return fallback
}

func secretStoreMetadata(store secrets.Store) map[string]any {
	typeName := fmt.Sprintf("%T", store)
	metadata := map[string]any{
		"type":           typeName,
		"read_supported": true,
	}
	switch store.(type) {
	case *secrets.MemoryStore:
		metadata["kind"] = "memory"
	default:
		if strings.Contains(typeName, "WindowsCredentialStore") {
			metadata["kind"] = "credential_store"
			metadata["read_supported"] = false
			break
		}
		metadata["kind"] = "credential_store"
	}
	return metadata
}
