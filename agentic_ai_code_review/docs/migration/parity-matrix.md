# Feature Parity Matrix

This matrix maps the previous web API surface to current Wails desktop bindings.

## Review + Changes

| Previous Web Endpoint | Desktop Binding | Current Module | Status |
| --- | --- | --- | --- |
| `POST /api/review-diffs` | `ReviewDiffs` | `internal/services/native/service.go` | Native local git review |
| `POST /api/generate-changes` | `GenerateChanges` | `internal/services/native/service.go` | Native guarded response |
| `POST /api/run-full-review` | `RunFullReview` | `internal/services/native/service.go` | Native local git review |
| `POST /api/apply-changes` | `ApplyChanges` | `internal/services/native/service.go` | Native patch application |
| `POST /api/static-checks` | `RunStaticChecks` | `internal/services/native/static_checks.go` | Native command runner |
| `GET /api/usage-metrics` | `GetUsageMetrics` | `internal/services/native/service.go` | Native in-memory metrics |

## Async Jobs

| Previous Web Endpoint | Desktop Binding | Current Module | Status |
| --- | --- | --- | --- |
| `GET /api/jobs/{job_id}` | `GetJob` | `internal/core/jobs/manager.go` | Native |
| `POST /api/jobs/{job_id}/proceed` | `ProceedJob` | `internal/core/jobs/manager.go` | Native |
| `GET /api/jobs/{job_id}/approval-preview` | `GetApprovalPreview` | `internal/services/native/service.go` | Native local preview |

## PR Workflow

| Previous Web Endpoint | Desktop Binding | Current Module | Status |
| --- | --- | --- | --- |
| `POST /api/pr-workflow/feature-context` | `GetFeatureContext` | `internal/services/native/service.go` | Native offline context |
| `POST /api/pr-workflow/changed-files` | `ListChangedFiles` | `internal/services/native/service.go` | Native git status |
| `POST /api/pr-workflow/reviewers` | `ListReviewers` | `internal/services/native/service.go` | Native preferred-email list |
| `POST /api/pr-workflow/work-item-family` | `GetWorkItemFamily` | `internal/services/native/service.go` | Native offline response |
| `POST /api/pr-workflow/raise-new-pr` | `RaiseNewPR` | `internal/services/native/service.go` | Native PR plan |
| `POST /api/pr-workflow/cherry-pick` | `CherryPick` | `internal/services/native/service.go` | Native plan |
| `POST /api/pr-workflow/commit-and-push` | `CommitAndPush` | `internal/services/native/service.go` | Native plan |

## Notes

- The desktop app no longer forwards to FastAPI during normal operation.
- Azure DevOps write actions are represented as native plans until a confirmed Go-side remote integration is added.
