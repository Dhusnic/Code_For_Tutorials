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
	"agenticai/desktop/internal/core/logging"
	"agenticai/desktop/internal/core/secrets"
	"agenticai/desktop/internal/services"
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
}

func New(configPath string) (*App, error) {
	settings, resolvedPath, err := config.Load(configPath)
	if err != nil {
		return nil, err
	}

	logger := logging.New(settings.LogLevel)
	jobManager := jobs.NewManager(2 * time.Hour)
	service := buildService(logger, jobManager)

	app := &App{
		logger:      logger,
		settings:    settings,
		configPath:  resolvedPath,
		service:     service,
		secretStore: secrets.NewDefaultStore(logger),
		jobManager:  jobManager,
		eventBus:    events.NewBus(),
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
			"service_mode":              a.settings.ServiceMode,
			"request_timeout_seconds":   a.settings.RequestTimeoutSeconds,
			"log_level":                 a.settings.LogLevel,
			"runtime":                   "wails-native",
			"external_backend_required": false,
		},
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
	if err := config.Save(a.configPath, next); err != nil {
		return nil, err
	}

	a.settings = next
	a.service = buildService(a.logger, a.jobManager)
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

func buildService(logger *slog.Logger, jobManager *jobs.Manager) services.DesktopService {
	return native.NewService(logger, jobManager)
}
