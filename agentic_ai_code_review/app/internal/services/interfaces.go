package services

import (
	"context"

	"agenticai/desktop/internal/contracts"
)

type DesktopService interface {
	RunFullReview(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error)
	ReviewDiffs(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error)
	GenerateChanges(ctx context.Context, request contracts.ConfigModel) (map[string]any, error)
	ApplyChanges(ctx context.Context, request contracts.ApplyChangesModel) (map[string]any, error)
	RunStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel, async bool) (map[string]any, error)
	GetUsageMetrics(ctx context.Context) (map[string]any, error)

	GetFeatureContext(ctx context.Context, request contracts.PRFeatureContextRequestModel) (map[string]any, error)
	ListChangedFiles(ctx context.Context, request contracts.PRWorkflowBaseRequestModel) (map[string]any, error)
	ListReviewers(ctx context.Context, request contracts.PRReviewersRequestModel) (map[string]any, error)
	GetWorkItemFamily(ctx context.Context, request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error)
	RaiseNewPR(ctx context.Context, request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error)
	CherryPick(ctx context.Context, request contracts.CherryPickRequestModel) (map[string]any, error)
	CommitAndPush(ctx context.Context, request contracts.CommitAndPushRequestModel) (map[string]any, error)

	GetJob(ctx context.Context, jobID string) (map[string]any, error)
	ProceedJob(ctx context.Context, jobID, requestID string) (map[string]any, error)
	GetApprovalPreview(ctx context.Context, jobID, requestID string) (map[string]any, error)
}
