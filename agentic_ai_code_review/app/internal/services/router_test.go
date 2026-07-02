package services

import (
	"context"
	"errors"
	"testing"

	"agenticai/desktop/internal/contracts"
)

type stubDesktopService struct {
	label string
	errs  map[string]error
	calls []string
}

func (s *stubDesktopService) record(operation string) (map[string]any, error) {
	s.calls = append(s.calls, operation)
	if err := s.errs[operation]; err != nil {
		return nil, err
	}
	return map[string]any{"source": s.label, "operation": operation}, nil
}

func (s *stubDesktopService) RunFullReview(context.Context, contracts.ConfigModel, bool) (map[string]any, error) {
	return s.record("RunFullReview")
}
func (s *stubDesktopService) ReviewDiffs(context.Context, contracts.ConfigModel, bool) (map[string]any, error) {
	return s.record("ReviewDiffs")
}
func (s *stubDesktopService) GenerateChanges(context.Context, contracts.ConfigModel) (map[string]any, error) {
	return s.record("GenerateChanges")
}
func (s *stubDesktopService) ApplyChanges(context.Context, contracts.ApplyChangesModel) (map[string]any, error) {
	return s.record("ApplyChanges")
}
func (s *stubDesktopService) RunStaticChecks(context.Context, contracts.StaticChecksRequestModel, bool) (map[string]any, error) {
	return s.record("RunStaticChecks")
}
func (s *stubDesktopService) GetUsageMetrics(context.Context) (map[string]any, error) {
	return s.record("GetUsageMetrics")
}
func (s *stubDesktopService) GetFeatureContext(context.Context, contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	return s.record("GetFeatureContext")
}
func (s *stubDesktopService) ListChangedFiles(context.Context, contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	return s.record("ListChangedFiles")
}
func (s *stubDesktopService) ListReviewers(context.Context, contracts.PRReviewersRequestModel) (map[string]any, error) {
	return s.record("ListReviewers")
}
func (s *stubDesktopService) GetWorkItemFamily(context.Context, contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	return s.record("GetWorkItemFamily")
}
func (s *stubDesktopService) RaiseNewPR(context.Context, contracts.RaiseNewPRRequestModel, bool) (map[string]any, error) {
	return s.record("RaiseNewPR")
}
func (s *stubDesktopService) CherryPick(context.Context, contracts.CherryPickRequestModel) (map[string]any, error) {
	return s.record("CherryPick")
}
func (s *stubDesktopService) CommitAndPush(context.Context, contracts.CommitAndPushRequestModel) (map[string]any, error) {
	return s.record("CommitAndPush")
}
func (s *stubDesktopService) GetJob(context.Context, string) (map[string]any, error) {
	return s.record("GetJob")
}
func (s *stubDesktopService) ProceedJob(context.Context, string, string) (map[string]any, error) {
	return s.record("ProceedJob")
}
func (s *stubDesktopService) GetApprovalPreview(context.Context, string, string) (map[string]any, error) {
	return s.record("GetApprovalPreview")
}

func TestRouterHybridRoutesAzureDependentOperationsToLegacy(t *testing.T) {
	t.Parallel()

	nativeService := &stubDesktopService{label: "native", errs: map[string]error{}}
	legacyService := &stubDesktopService{label: "legacy", errs: map[string]error{}}
	router := NewRouter("hybrid", nativeService, legacyService)

	result, err := router.GetFeatureContext(context.Background(), contracts.PRFeatureContextRequestModel{})
	if err != nil {
		t.Fatalf("GetFeatureContext returned error: %v", err)
	}
	if result["source"] != "legacy" {
		t.Fatalf("expected legacy routing, got %#v", result)
	}
	if len(nativeService.calls) != 0 {
		t.Fatalf("expected native service to stay idle, got %v", nativeService.calls)
	}
}

func TestRouterHybridRoutesStableOperationsToNative(t *testing.T) {
	t.Parallel()

	nativeService := &stubDesktopService{label: "native", errs: map[string]error{}}
	legacyService := &stubDesktopService{label: "legacy", errs: map[string]error{}}
	router := NewRouter("hybrid", nativeService, legacyService)

	result, err := router.RunStaticChecks(context.Background(), contracts.StaticChecksRequestModel{}, false)
	if err != nil {
		t.Fatalf("RunStaticChecks returned error: %v", err)
	}
	if result["source"] != "native" {
		t.Fatalf("expected native routing, got %#v", result)
	}
}

func TestRouterHybridFallsBackToLegacyWhenNativeFails(t *testing.T) {
	t.Parallel()

	nativeService := &stubDesktopService{
		label: "native",
		errs:  map[string]error{"GetJob": errors.New("job not found")},
	}
	legacyService := &stubDesktopService{label: "legacy", errs: map[string]error{}}
	router := NewRouter("hybrid", nativeService, legacyService)

	result, err := router.GetJob(context.Background(), "job-1")
	if err != nil {
		t.Fatalf("GetJob returned error: %v", err)
	}
	if result["source"] != "legacy" {
		t.Fatalf("expected legacy fallback, got %#v", result)
	}
	if got := len(nativeService.calls); got != 1 {
		t.Fatalf("expected one native call before fallback, got %d", got)
	}
}
