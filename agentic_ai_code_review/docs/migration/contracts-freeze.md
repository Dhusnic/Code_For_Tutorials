# Contract Freeze (Web Baseline -> Desktop)

This file freezes the payload shapes used by the legacy web API so the desktop app can preserve behavior during migration.

## Core Rule

- Desktop methods must return the same top-level keys as the web API for each operation.
- Any new desktop-only metadata must be additive and must not rename/remove baseline keys.

## Frozen Request Contracts

- `ConfigModel`
  - `repo_path`, `ai_model`, `max_tokens`, `organization`, `project`, `repository_name`, `pull_request_id`, `azure_pat`, `is_local`, `review`
- `ApplyChangesModel`
  - `file_path`, `new_content`, `repo_path`, `line_number`, `new_start_line_number`, `number_of_lines_removed_from_old`, `number_of_lines_added_in_new`, `old_start_line_number`, `old_content`, `allow_fallback_search`
- `StaticChecksRequestModel`
  - `repo_path`, `scope`, `organization`, `project`, `repository_name`, `pull_request_id`, `azure_pat`, `is_local`, `file_paths`
- `PRWorkflowBaseRequestModel`
  - `repo_path`, `organization`, `project`, `repository_name`, `azure_pat`, `defaults_path`
- `PRFeatureContextRequestModel`
  - base + `feature_id`
- `PRWorkItemFamilyRequestModel`
  - base + `work_item_id`
- `PRReviewersRequestModel`
  - base + `limit`, `preferred_emails`
- `RaiseNewPRRequestModel`
  - base + `feature_id`, `selected_serials`, `reviewer_ids`, `reviewer_ids_by_branch`, `target_branches`, `additional_work_item_ids`, `commit_message`
- `CherryPickRequestModel`
  - base + `source_branch`, `target_branch`, `commit_hashes`
- `CommitAndPushRequestModel`
  - base + `branch_name`, `base_branch`, `selected_serials`, `commit_message`

## Frozen Async Behavior

- Methods supporting async job submission must preserve:
  - query flag `async_job=true`
  - accepted response shape: `job_id`, `status`, `poll_url`, `ws_url`
- Job state lifecycle keys preserved:
  - `job_id`, `job_type`, `status`, `created_at`, `updated_at`, `started_at`, `finished_at`, `result`, `error`, `approval_request`

## Frozen Approval Checkpoint Behavior

- Pending approval flow keys preserved:
  - `request_id`, `source_branch`, `target_branch`, `target_key`, `workspace_repo_path`, `selected_files`, `selected_file_count`, `repo_root_label`, `preview_available`, `message`
- Desktop methods must preserve:
  - `GetApprovalPreview(job_id, request_id)`
  - `ProceedJob(job_id, request_id)`

## Fixture Source

Contract fixtures for initial desktop tests are under:

- [`app/internal/contracts/fixtures/`](../../app/internal/contracts/fixtures/)
