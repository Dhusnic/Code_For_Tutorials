package native

import (
	"context"
	"log/slog"
	"time"

	"agenticai/desktop/internal/contracts"
	"agenticai/desktop/internal/services"
	"agenticai/desktop/internal/services/legacy"
)

type Service struct {
	bridge services.DesktopService
	logger *slog.Logger
}

var _ services.DesktopService = (*Service)(nil)

func NewService(
	legacyBaseURL string,
	timeout time.Duration,
	logger *slog.Logger,
	ensureRunning legacy.EnsureRunningFunc,
) *Service {
	return &Service{
		bridge: legacy.NewClient(legacyBaseURL, timeout, logger, ensureRunning),
		logger: logger,
	}
}

func (s *Service) RunFullReview(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return s.forward("RunFullReview", func() (map[string]any, error) {
		return s.bridge.RunFullReview(ctx, request, async)
	})
}

func (s *Service) ReviewDiffs(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return s.forward("ReviewDiffs", func() (map[string]any, error) {
		return s.bridge.ReviewDiffs(ctx, request, async)
	})
}

func (s *Service) GenerateChanges(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	return s.forward("GenerateChanges", func() (map[string]any, error) {
		return s.bridge.GenerateChanges(ctx, request)
	})
}

func (s *Service) ApplyChanges(ctx context.Context, request contracts.ApplyChangesModel) (map[string]any, error) {
	return s.forward("ApplyChanges", func() (map[string]any, error) {
		return s.bridge.ApplyChanges(ctx, request)
	})
}

func (s *Service) RunStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel, async bool) (map[string]any, error) {
	return s.forward("RunStaticChecks", func() (map[string]any, error) {
		return s.bridge.RunStaticChecks(ctx, request, async)
	})
}

func (s *Service) GetUsageMetrics(ctx context.Context) (map[string]any, error) {
	return s.forward("GetUsageMetrics", func() (map[string]any, error) {
		return s.bridge.GetUsageMetrics(ctx)
	})
}

func (s *Service) GetFeatureContext(ctx context.Context, request contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	return s.forward("GetFeatureContext", func() (map[string]any, error) {
		return s.bridge.GetFeatureContext(ctx, request)
	})
}

func (s *Service) ListChangedFiles(ctx context.Context, request contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	return s.forward("ListChangedFiles", func() (map[string]any, error) {
		return s.bridge.ListChangedFiles(ctx, request)
	})
}

func (s *Service) ListReviewers(ctx context.Context, request contracts.PRReviewersRequestModel) (map[string]any, error) {
	return s.forward("ListReviewers", func() (map[string]any, error) {
		return s.bridge.ListReviewers(ctx, request)
	})
}

func (s *Service) GetWorkItemFamily(ctx context.Context, request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	return s.forward("GetWorkItemFamily", func() (map[string]any, error) {
		return s.bridge.GetWorkItemFamily(ctx, request)
	})
}

func (s *Service) RaiseNewPR(ctx context.Context, request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error) {
	return s.forward("RaiseNewPR", func() (map[string]any, error) {
		return s.bridge.RaiseNewPR(ctx, request, async)
	})
}

func (s *Service) CherryPick(ctx context.Context, request contracts.CherryPickRequestModel) (map[string]any, error) {
	return s.forward("CherryPick", func() (map[string]any, error) {
		return s.bridge.CherryPick(ctx, request)
	})
}

func (s *Service) CommitAndPush(ctx context.Context, request contracts.CommitAndPushRequestModel) (map[string]any, error) {
	return s.forward("CommitAndPush", func() (map[string]any, error) {
		return s.bridge.CommitAndPush(ctx, request)
	})
}

func (s *Service) GetJob(ctx context.Context, jobID string) (map[string]any, error) {
	return s.forward("GetJob", func() (map[string]any, error) {
		return s.bridge.GetJob(ctx, jobID)
	})
}

func (s *Service) ProceedJob(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	return s.forward("ProceedJob", func() (map[string]any, error) {
		return s.bridge.ProceedJob(ctx, jobID, requestID)
	})
}

func (s *Service) GetApprovalPreview(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	return s.forward("GetApprovalPreview", func() (map[string]any, error) {
		return s.bridge.GetApprovalPreview(ctx, jobID, requestID)
	})
}

func (s *Service) forward(operation string, fn func() (map[string]any, error)) (map[string]any, error) {
	result, err := fn()
	if err != nil {
		return nil, err
	}
	if result == nil {
		result = map[string]any{}
	}
	result["desktop_execution_mode"] = "native_bridge"
	result["desktop_operation"] = operation
	if s.logger != nil {
		s.logger.Info(
			"native service bridged operation to legacy baseline",
			"operation", operation,
		)
	}
	return result, nil
}
