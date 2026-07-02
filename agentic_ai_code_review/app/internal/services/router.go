package services

import (
	"context"
	"errors"
	"strings"

	"agenticai/desktop/internal/contracts"
)

const (
	serviceModeLegacy = "legacy"
	serviceModeHybrid = "hybrid"
	serviceModeNative = "native"
)

type Router struct {
	mode          string
	nativeService DesktopService
	legacyService DesktopService
}

var _ DesktopService = (*Router)(nil)

func NewRouter(mode string, nativeService, legacyService DesktopService) *Router {
	normalizedMode := strings.ToLower(strings.TrimSpace(mode))
	switch normalizedMode {
	case serviceModeLegacy, serviceModeHybrid, serviceModeNative:
	default:
		normalizedMode = serviceModeHybrid
	}
	return &Router{
		mode:          normalizedMode,
		nativeService: nativeService,
		legacyService: legacyService,
	}
}

func (r *Router) RunFullReview(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return r.call(ctx, "RunFullReview", true, func(service DesktopService) (map[string]any, error) {
		return service.RunFullReview(ctx, request, async)
	})
}

func (r *Router) ReviewDiffs(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return r.call(ctx, "ReviewDiffs", true, func(service DesktopService) (map[string]any, error) {
		return service.ReviewDiffs(ctx, request, async)
	})
}

func (r *Router) GenerateChanges(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	return r.call(ctx, "GenerateChanges", true, func(service DesktopService) (map[string]any, error) {
		return service.GenerateChanges(ctx, request)
	})
}

func (r *Router) ApplyChanges(ctx context.Context, request contracts.ApplyChangesModel) (map[string]any, error) {
	return r.call(ctx, "ApplyChanges", false, func(service DesktopService) (map[string]any, error) {
		return service.ApplyChanges(ctx, request)
	})
}

func (r *Router) RunStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel, async bool) (map[string]any, error) {
	return r.call(ctx, "RunStaticChecks", false, func(service DesktopService) (map[string]any, error) {
		return service.RunStaticChecks(ctx, request, async)
	})
}

func (r *Router) GetUsageMetrics(ctx context.Context) (map[string]any, error) {
	return r.call(ctx, "GetUsageMetrics", false, func(service DesktopService) (map[string]any, error) {
		return service.GetUsageMetrics(ctx)
	})
}

func (r *Router) GetFeatureContext(ctx context.Context, request contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	return r.call(ctx, "GetFeatureContext", true, func(service DesktopService) (map[string]any, error) {
		return service.GetFeatureContext(ctx, request)
	})
}

func (r *Router) ListChangedFiles(ctx context.Context, request contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	return r.call(ctx, "ListChangedFiles", false, func(service DesktopService) (map[string]any, error) {
		return service.ListChangedFiles(ctx, request)
	})
}

func (r *Router) ListReviewers(ctx context.Context, request contracts.PRReviewersRequestModel) (map[string]any, error) {
	return r.call(ctx, "ListReviewers", true, func(service DesktopService) (map[string]any, error) {
		return service.ListReviewers(ctx, request)
	})
}

func (r *Router) GetWorkItemFamily(ctx context.Context, request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	return r.call(ctx, "GetWorkItemFamily", true, func(service DesktopService) (map[string]any, error) {
		return service.GetWorkItemFamily(ctx, request)
	})
}

func (r *Router) RaiseNewPR(ctx context.Context, request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error) {
	return r.call(ctx, "RaiseNewPR", true, func(service DesktopService) (map[string]any, error) {
		return service.RaiseNewPR(ctx, request, async)
	})
}

func (r *Router) CherryPick(ctx context.Context, request contracts.CherryPickRequestModel) (map[string]any, error) {
	return r.call(ctx, "CherryPick", true, func(service DesktopService) (map[string]any, error) {
		return service.CherryPick(ctx, request)
	})
}

func (r *Router) CommitAndPush(ctx context.Context, request contracts.CommitAndPushRequestModel) (map[string]any, error) {
	return r.call(ctx, "CommitAndPush", true, func(service DesktopService) (map[string]any, error) {
		return service.CommitAndPush(ctx, request)
	})
}

func (r *Router) GetJob(ctx context.Context, jobID string) (map[string]any, error) {
	return r.call(ctx, "GetJob", false, func(service DesktopService) (map[string]any, error) {
		return service.GetJob(ctx, jobID)
	})
}

func (r *Router) ProceedJob(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	return r.call(ctx, "ProceedJob", false, func(service DesktopService) (map[string]any, error) {
		return service.ProceedJob(ctx, jobID, requestID)
	})
}

func (r *Router) GetApprovalPreview(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	return r.call(ctx, "GetApprovalPreview", false, func(service DesktopService) (map[string]any, error) {
		return service.GetApprovalPreview(ctx, jobID, requestID)
	})
}

func (r *Router) call(
	ctx context.Context,
	operation string,
	preferLegacyInHybrid bool,
	invoke func(DesktopService) (map[string]any, error),
) (map[string]any, error) {
	switch r.mode {
	case serviceModeLegacy:
		return r.invoke(operation, "legacy", r.legacyService, invoke)
	case serviceModeNative:
		return r.invoke(operation, "native", r.nativeService, invoke)
	default:
		if preferLegacyInHybrid {
			return r.invokeWithFallback(operation, invoke, r.legacyService, "legacy", r.nativeService, "native")
		}
		return r.invokeWithFallback(operation, invoke, r.nativeService, "native", r.legacyService, "legacy")
	}
}

func (r *Router) invokeWithFallback(
	operation string,
	invoke func(DesktopService) (map[string]any, error),
	primary DesktopService,
	primaryLabel string,
	fallback DesktopService,
	fallbackLabel string,
) (map[string]any, error) {
	result, err := r.invoke(operation, primaryLabel, primary, invoke)
	if err == nil {
		return result, nil
	}
	return r.invoke(operation, fallbackLabel, fallback, invoke)
}

func (r *Router) invoke(
	operation string,
	route string,
	service DesktopService,
	invoke func(DesktopService) (map[string]any, error),
) (map[string]any, error) {
	if service == nil {
		return nil, errors.New("service route is unavailable")
	}
	result, err := invoke(service)
	if err != nil {
		return nil, err
	}
	if result == nil {
		result = map[string]any{}
	}
	result["desktop_service_mode"] = r.mode
	result["desktop_routed_via"] = route
	result["desktop_router_operation"] = operation
	return result, nil
}
