# Feature Parity Matrix

This matrix maps each baseline web endpoint/workflow to desktop bindings and implementation modules.

## Review + Changes

| Web Endpoint | Desktop Binding | Current Module | Target Native Module | Status |
| --- | --- | --- | --- | --- |
| `POST /api/review-diffs` | `ReviewDiffs` | `internal/services/legacy/client.go` | `internal/services/native/review_service.go` | Bridge ready |
| `POST /api/generate-changes` | `GenerateChanges` | `internal/services/legacy/client.go` | `internal/services/native/review_service.go` | Bridge ready |
| `POST /api/run-full-review` | `RunFullReview` | `internal/services/legacy/client.go` | `internal/services/native/review_service.go` | Bridge ready |
| `POST /api/apply-changes` | `ApplyChanges` | `internal/services/legacy/client.go` | `internal/services/native/patch_service.go` | Bridge ready |
| `POST /api/static-checks` | `RunStaticChecks` | `internal/services/legacy/client.go` | `internal/services/native/static_checks_service.go` | Bridge ready |
| `GET /api/usage-metrics` | `GetUsageMetrics` | `internal/services/legacy/client.go` | `internal/services/native/usage_service.go` | Bridge ready |

## Async Jobs

| Web Endpoint | Desktop Binding | Current Module | Target Native Module | Status |
| --- | --- | --- | --- | --- |
| `GET /api/jobs/{job_id}` | `GetJob` | `internal/services/legacy/client.go` | `internal/core/jobs/manager.go` + adapters | Bridge ready |
| `POST /api/jobs/{job_id}/proceed` | `ProceedJob` | `internal/services/legacy/client.go` | `internal/core/jobs/manager.go` + workflow adapter | Bridge ready |
| `GET /api/jobs/{job_id}/approval-preview` | `GetApprovalPreview` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |

## PR Workflow

| Web Endpoint | Desktop Binding | Current Module | Target Native Module | Status |
| --- | --- | --- | --- | --- |
| `POST /api/pr-workflow/feature-context` | `GetFeatureContext` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/changed-files` | `ListChangedFiles` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/reviewers` | `ListReviewers` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/work-item-family` | `GetWorkItemFamily` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/raise-new-pr` | `RaiseNewPR` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/cherry-pick` | `CherryPick` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |
| `POST /api/pr-workflow/commit-and-push` | `CommitAndPush` | `internal/services/legacy/client.go` | `internal/services/native/pr_workflow_service.go` | Bridge ready |

## Notes

- "Bridge ready" means desktop contract is implemented and forwards to `web`.
- Native implementation files are scaffolded and can be cut over method-by-method with parity tests.
