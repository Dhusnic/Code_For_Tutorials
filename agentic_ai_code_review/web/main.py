"""FastAPI application entry point for the Agentic AI code review service."""

from __future__ import annotations

import asyncio
import os
import logging
import inspect
import mimetypes
import threading
import time
import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cli import AgenticAICodeReviewCLI
from git_manager.patch_applier import PatchApplier, PatchApplyRequest
from pr_manager.pr_workflow import PRWorkflowError, PRWorkflowService
from review_manager.static_checks import StaticCheckRunner


def configure_logging() -> None:
    """Configure process-wide logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def configure_static_mime_types() -> None:
    """Ensure local static assets use browser-safe MIME types on Windows."""
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")


configure_logging()
configure_static_mime_types()
LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
patch_applier = PatchApplier()


def _read_dotenv_value(dotenv_path: Path, key: str) -> str:
    """Read one key from dotenv file without loading process-wide environment variables."""
    if not dotenv_path.exists():
        return ""

    try:
        with dotenv_path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                parsed_key, parsed_value = line.split("=", 1)
                if parsed_key.strip() == key:
                    return parsed_value.strip().strip("\"'")
    except Exception:
        LOGGER.exception("Unable to read key '%s' from %s", key, dotenv_path)
    return ""


def _resolve_default_azure_pat() -> str:
    """Resolve Azure PAT from environment or local config/.env for UI default prefill."""
    env_value = (os.getenv("AZURE_DEVOPS_PAT") or "").strip()
    if env_value:
        return env_value

    dotenv_path = BASE_DIR / "config" / ".env"
    return _read_dotenv_value(dotenv_path, "AZURE_DEVOPS_PAT")


def _resolve_env_or_dotenv(key: str) -> str:
    """Resolve a key from process environment first, then config/.env file."""
    env_value = (os.getenv(key) or "").strip()
    if env_value:
        return env_value
    dotenv_path = BASE_DIR / "config" / ".env"
    return _read_dotenv_value(dotenv_path, key)


def _parse_email_list(raw_value: str | None) -> list[str]:
    """Parse comma/semicolon/newline-separated reviewer email values."""
    if not raw_value:
        return []
    normalized = str(raw_value).replace("\n", ",").replace(";", ",")
    values = [item.strip() for item in normalized.split(",")]
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        lowered = value.lower()
        if not value or lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(value)
    return deduped


def _resolve_default_reviewer_emails() -> dict[str, list[str]]:
    """Resolve default reviewer email lists for UI preselection."""
    shared = _parse_email_list(_resolve_env_or_dotenv("DEFAULT_PR_REVIEWER_EMAILS"))
    main = _parse_email_list(_resolve_env_or_dotenv("DEFAULT_PR_REVIEWER_EMAILS_MAIN"))
    prerelease = _parse_email_list(_resolve_env_or_dotenv("DEFAULT_PR_REVIEWER_EMAILS_PRERELEASE"))
    return {
        "shared": shared,
        "main": main,
        "prerelease": prerelease,
    }


def _load_pr_workflow_defaults_for_ui() -> dict[str, Any]:
    """Load PR workflow defaults for UI rendering without hardcoded branch names."""
    defaults_path = BASE_DIR / "config" / "pr_workflow_defaults.json"
    fallback = {
        "base_branches": {
            "main": "main",
            "prerelease": "PreRelease/3.13/2026/Mar/18",
        },
        "branch_templates": {
            "main": "Feature/#{feature_id}/{feature_slug}",
            "prerelease": "Feature/#{feature_id}/{feature_slug}_{month_abbr}",
        },
    }
    if not defaults_path.exists():
        return fallback
    try:
        parsed = json.loads(defaults_path.read_text(encoding="utf-8"))
        base_branches = parsed.get("base_branches", {})
        branch_templates = parsed.get("branch_templates", {})
        normalized_base_branches = {
            str(key): str(value)
            for key, value in (base_branches if isinstance(base_branches, dict) else {}).items()
            if str(key).strip() and str(value).strip()
        }
        normalized_templates = {
            str(key): str(value)
            for key, value in (branch_templates if isinstance(branch_templates, dict) else {}).items()
            if str(key).strip() and str(value).strip()
        }
        return {
            "base_branches": normalized_base_branches or fallback["base_branches"],
            "branch_templates": normalized_templates or fallback["branch_templates"],
        }
    except Exception:
        LOGGER.exception("Unable to load UI PR workflow defaults from %s", defaults_path)
        return fallback


def _pr_workflow_defaults_path() -> Path:
    """Return the repository-backed PR workflow defaults JSON path."""
    return BASE_DIR / "config" / "pr_workflow_defaults.json"


def _read_pr_workflow_defaults_file() -> dict[str, Any]:
    """Read the raw PR workflow defaults JSON file from disk."""
    defaults_path = _pr_workflow_defaults_path()
    if not defaults_path.exists():
        raise FileNotFoundError(f"Config file not found: {defaults_path}")
    raw_text = defaults_path.read_text(encoding="utf-8")
    parsed = json.loads(raw_text or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("PR workflow defaults JSON must contain an object at the top level.")
    return parsed


def _write_pr_workflow_defaults_file(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist PR workflow defaults JSON back into the repository config folder."""
    if not isinstance(payload, dict):
        raise ValueError("PR workflow defaults payload must be a JSON object.")
    defaults_path = _pr_workflow_defaults_path()
    defaults_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = json.loads(json.dumps(payload))
    defaults_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return normalized


def _parse_cors_origins(raw_value: str | None) -> list[str]:
    """Parse comma-separated CORS origins from env into normalized values."""
    if not raw_value:
        return []
    values = [item.strip() for item in raw_value.split(",")]
    return [item.rstrip("/") for item in values if item]


def _build_cors_settings() -> tuple[list[str], bool, str | None]:
    """
    Build CORS settings with safe defaults.

    Defaults:
    - Allow local browser UIs only (localhost/127.0.0.1 on any port).
    - Disable credentials unless explicitly enabled.
    Guardrail:
    - Never allow wildcard origins when credentials are enabled.
    """
    permissive_mode = os.getenv("CORS_PERMISSIVE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if permissive_mode:
        return ["*"], False, None

    origins = _parse_cors_origins(os.getenv("CORS_ALLOWED_ORIGINS"))
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    allow_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip() or r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    if "*" in origins:
        if allow_credentials:
            LOGGER.warning(
                "CORS wildcard with credentials is unsafe. Disabling credentials for current process."
            )
        allow_credentials = False
        allow_origin_regex = None

    return origins, allow_credentials, allow_origin_regex


class UsageTracker:
    """In-memory AI usage tracker for token and estimated cost monitoring."""

    MODEL_ESTIMATED_COST_PER_MILLION = {
        "gpt-4o-mini": 0.375,  # blended estimate (USD / 1M tokens)
        "gpt-4.1-mini": 0.8,
        "gpt-4.1": 6.0,
    }

    def __init__(self) -> None:
        self.token_budget = int(os.getenv("USAGE_TOKEN_BUDGET", "5000000"))
        self.cost_budget_usd = float(os.getenv("USAGE_COST_BUDGET_USD", "25"))
        self._lock = threading.Lock()
        self._total_tokens = 0
        self._total_cost_usd = 0.0
        self._request_count = 0
        self._recent = deque(maxlen=100)

    def _cost_for(self, model: str, tokens: int) -> float:
        model_key = (model or "").strip().lower()
        rate = self.MODEL_ESTIMATED_COST_PER_MILLION.get(model_key, 0.5)
        return (max(tokens, 0) / 1_000_000.0) * rate

    def record(
        self,
        *,
        endpoint: str,
        model: str,
        tokens_used: int,
        token_source: str = "unknown",
        token_usage: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Record one request usage and return request-level usage payload."""
        tokens = max(int(tokens_used or 0), 0)
        estimated_cost = self._cost_for(model, tokens)
        usage_input = max(int((token_usage or {}).get("input_tokens", 0) or 0), 0)
        usage_output = max(int((token_usage or {}).get("output_tokens", 0) or 0), 0)
        normalized_source = (token_source or (token_usage or {}).get("source") or "unknown").strip().lower()
        event = {
            "timestamp": int(time.time()),
            "endpoint": endpoint,
            "model": model,
            "tokens_used": tokens,
            "token_source": normalized_source,
            "input_tokens": usage_input,
            "output_tokens": usage_output,
            "estimated_cost_usd": round(estimated_cost, 6),
        }
        with self._lock:
            self._total_tokens += tokens
            self._total_cost_usd += estimated_cost
            self._request_count += 1
            self._recent.appendleft(event)
        return event

    def snapshot(self) -> dict:
        """Return current usage metrics and remaining budget."""
        with self._lock:
            total_tokens = self._total_tokens
            total_cost = round(self._total_cost_usd, 6)
            request_count = self._request_count
            recent = list(self._recent)

        remaining_tokens = max(self.token_budget - total_tokens, 0)
        remaining_cost = max(self.cost_budget_usd - total_cost, 0.0)
        token_percent = min((total_tokens / self.token_budget) * 100, 100.0) if self.token_budget > 0 else 0.0
        cost_percent = min((total_cost / self.cost_budget_usd) * 100, 100.0) if self.cost_budget_usd > 0 else 0.0

        return {
            "summary": {
                "request_count": request_count,
                "total_tokens_used": total_tokens,
                "total_estimated_cost_usd": total_cost,
                "token_budget": self.token_budget,
                "cost_budget_usd": self.cost_budget_usd,
                "token_budget_remaining": remaining_tokens,
                "cost_budget_remaining_usd": round(remaining_cost, 6),
                "token_budget_used_percent": round(token_percent, 2),
                "cost_budget_used_percent": round(cost_percent, 2),
            },
            "recent_requests": recent,
        }


class AsyncJobManager:
    """In-memory async job registry backed by a thread pool."""

    TERMINAL_STATUSES = {"succeeded", "failed"}

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-worker")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._approval_events: dict[str, threading.Event] = {}
        self._approval_timeout_seconds = max(
            int(os.getenv("ASYNC_JOB_APPROVAL_TIMEOUT_SECONDS", "7200")),
            60,
        )

    def submit(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        runner: Any,
    ) -> str:
        """Submit background job and return generated job ID."""
        job_id = uuid4().hex
        now = int(time.time())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "job_type": job_type,
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
                "approval_request": None,
            }
        self._executor.submit(self._run_job, job_id, runner, deepcopy(payload))
        return job_id

    def _run_job(self, job_id: str, runner: Any, payload: dict[str, Any]) -> None:
        """Execute one queued job and persist terminal state."""
        started_at = int(time.time())
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "running"
            job["started_at"] = started_at
            job["updated_at"] = started_at

        try:
            result = runner(payload, job_id) if self._runner_accepts_job_id(runner) else runner(payload)
            finished_at = int(time.time())
            pending_event: threading.Event | None = None
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "succeeded"
                job["result"] = result
                job["finished_at"] = finished_at
                job["updated_at"] = finished_at
                job["approval_request"] = None
                pending_event = self._approval_events.pop(job_id, None)
            if pending_event:
                pending_event.set()
        except Exception as exc:
            finished_at = int(time.time())
            LOGGER.exception("Background job failed job_id=%s", job_id)
            pending_event = None
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "failed"
                job["error"] = {"message": str(exc)}
                job["finished_at"] = finished_at
                job["updated_at"] = finished_at
                job["approval_request"] = None
                pending_event = self._approval_events.pop(job_id, None)
            if pending_event:
                pending_event.set()

    @staticmethod
    def _runner_accepts_job_id(runner: Any) -> bool:
        """Return True when runner accepts the optional second positional arg (job_id)."""
        try:
            signature = inspect.signature(runner)
        except (TypeError, ValueError):
            return False

        params = list(signature.parameters.values())
        positional = [
            item
            for item in params
            if item.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(item.kind == inspect.Parameter.VAR_POSITIONAL for item in params)
        return has_varargs or len(positional) >= 2

    def wait_for_approval(
        self,
        job_id: str,
        approval_request: dict[str, Any],
        timeout_seconds: int | None = None,
    ) -> None:
        """Pause job execution until client sends proceed for branch-level manual review."""
        request_id = uuid4().hex
        normalized_request = {
            "request_id": request_id,
            "source_branch": str((approval_request or {}).get("source_branch", "")).strip(),
            "target_branch": str((approval_request or {}).get("target_branch", "")).strip(),
            "target_key": str((approval_request or {}).get("target_key", "")).strip(),
            "workspace_repo_path": str((approval_request or {}).get("workspace_repo_path", "")).strip(),
            "selected_files": list((approval_request or {}).get("selected_files", []) or []),
            "selected_file_count": int((approval_request or {}).get("selected_file_count") or 0),
            "repo_root_label": str((approval_request or {}).get("repo_root_label", "")).strip(),
            "preview_available": bool((approval_request or {}).get("preview_available", False)),
            "message": str((approval_request or {}).get("message", "")).strip(),
        }
        if normalized_request["selected_file_count"] <= 0:
            normalized_request["selected_file_count"] = len(normalized_request["selected_files"])
        event = threading.Event()
        now = int(time.time())
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise RuntimeError(f"Job not found while waiting for approval: {job_id}")
            job["status"] = "waiting_for_approval"
            job["approval_request"] = normalized_request
            job["updated_at"] = now
            self._approval_events[job_id] = event

        timeout = max(int(timeout_seconds or self._approval_timeout_seconds), 1)
        approved = event.wait(timeout=timeout)
        if approved:
            return
        raise RuntimeError(
            "Timed out waiting for manual approval "
            f"for branch '{normalized_request.get('source_branch', '')}'."
        )

    def approve(self, job_id: str, request_id: str | None = None) -> dict[str, Any]:
        """Resume one job currently paused in waiting_for_approval state."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(f"Job not found: {job_id}")

            status = str(job.get("status", "")).strip().lower()
            pending_request = job.get("approval_request")
            if status != "waiting_for_approval" or not isinstance(pending_request, dict):
                raise ValueError(f"Job is not waiting for approval: {job_id}")

            active_request_id = str(pending_request.get("request_id", "")).strip()
            if request_id and request_id.strip() and request_id.strip() != active_request_id:
                raise ValueError("Approval request id does not match current pending request.")

            event = self._approval_events.get(job_id)
            if not event:
                raise ValueError("No pending approval signal found for job.")

            now = int(time.time())
            job["status"] = "running"
            job["approval_request"] = None
            job["updated_at"] = now
            snapshot = deepcopy(job)

        event.set()
        return snapshot

    def get_pending_approval(self, job_id: str, request_id: str | None = None) -> dict[str, Any]:
        """Return the active approval payload for a paused async job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(f"Job not found: {job_id}")

            status = str(job.get("status", "")).strip().lower()
            pending_request = job.get("approval_request")
            if status != "waiting_for_approval" or not isinstance(pending_request, dict):
                raise RuntimeError(f"Job is not waiting for approval: {job_id}")

            active_request_id = str(pending_request.get("request_id", "")).strip()
            if request_id and request_id.strip() and request_id.strip() != active_request_id:
                raise ValueError("Approval request id does not match current pending request.")
            return deepcopy(pending_request)

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a copy of job state by ID."""
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def is_terminal(self, status: str) -> bool:
        """Check whether status is terminal."""
        return (status or "").strip().lower() in self.TERMINAL_STATUSES


usage_tracker = UsageTracker()
job_manager = AsyncJobManager(max_workers=int(os.getenv("ASYNC_JOB_WORKERS", "4")))
cors_origins, cors_allow_credentials, cors_allow_origin_regex = _build_cors_settings()

app = FastAPI(title="Agentic AI Code Review API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


class ConfigModel(BaseModel):
    """Request model for review configuration."""

    repo_path: str = Field(..., description="Repository root path")
    ai_model: str = Field(default="gpt-4o-mini")
    max_tokens: int = Field(default=30000, ge=1, le=120000)
    organization: str
    project: str
    repository_name: str
    pull_request_id: str
    azure_pat: Optional[str] = None
    is_local: Optional[bool] = False
    review: Optional[str] = ""


class ApplyChangesModel(BaseModel):
    """Request model for applying a single AI generated change block."""

    file_path: str
    new_content: str
    repo_path: str
    line_number: int
    new_start_line_number: int
    number_of_lines_removed_from_old: int
    number_of_lines_added_in_new: int
    old_start_line_number: int
    old_content: str
    allow_fallback_search: Optional[bool] = True


class StaticChecksRequestModel(BaseModel):
    """Request model for command-based static checks."""

    repo_path: str = Field(..., description="Repository root path")
    scope: str = Field(default="repo", description="Either 'repo' or 'changed'")
    organization: Optional[str] = None
    project: Optional[str] = None
    repository_name: Optional[str] = None
    pull_request_id: Optional[str] = None
    azure_pat: Optional[str] = None
    is_local: Optional[bool] = False
    file_paths: Optional[list[str]] = None


class PRWorkflowBaseRequestModel(BaseModel):
    """Base request model for PR workflow actions."""

    repo_path: str = Field(..., description="Repository root path")
    organization: str
    project: str
    repository_name: str
    azure_pat: str
    defaults_path: Optional[str] = None


class PRFeatureContextRequestModel(PRWorkflowBaseRequestModel):
    """Request model for feature context lookup."""

    feature_id: int = Field(..., ge=1)


class PRWorkItemFamilyRequestModel(PRWorkflowBaseRequestModel):
    """Request model for one-level work item family lookup."""

    work_item_id: int = Field(..., ge=1)


class PRReviewersRequestModel(PRWorkflowBaseRequestModel):
    """Request model for reviewer candidate listing."""

    limit: int = Field(default=50, ge=1, le=200)
    preferred_emails: Optional[list[str]] = None


class RaiseNewPRRequestModel(PRWorkflowBaseRequestModel):
    """Request model for option-1 PR raise workflow."""

    feature_id: int = Field(..., ge=1)
    selected_serials: list[int] = Field(default_factory=list)
    reviewer_ids: Optional[list[str]] = None
    reviewer_ids_by_branch: Optional[dict[str, list[str]]] = None
    target_branches: Optional[list[str]] = None
    additional_work_item_ids: Optional[list[int]] = None
    commit_message: Optional[str] = None


class JobProceedRequestModel(BaseModel):
    """Request model for proceeding one paused async job checkpoint."""

    request_id: Optional[str] = None


class PRWorkflowDefaultsUpdateModel(BaseModel):
    """Request model for updating config/pr_workflow_defaults.json from the UI."""

    config: dict[str, Any] = Field(default_factory=dict)


class CherryPickRequestModel(PRWorkflowBaseRequestModel):
    """Request model for option-2 cherry-pick flow."""

    source_branch: str
    target_branch: str
    commit_hashes: list[str] = Field(default_factory=list)


class CommitAndPushRequestModel(PRWorkflowBaseRequestModel):
    """Request model for option-3 commit and push flow."""

    branch_name: str
    base_branch: str
    selected_serials: list[int] = Field(default_factory=list)
    commit_message: str


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    """Convert Pydantic model to dict for background payload transfer."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _job_submission_payload(job_id: str) -> dict[str, Any]:
    """Build standard payload returned when background job is accepted."""
    return {
        "job_id": job_id,
        "status": "queued",
        "poll_url": f"/api/jobs/{job_id}",
        "ws_url": f"/ws/jobs/{job_id}",
    }


def _execute_review_diffs(config: ConfigModel) -> dict:
    """Run review-diffs workflow synchronously and return final payload."""
    LOGGER.info("API request /api/review-diffs repo=%s", config.repository_name)
    controller = AgenticAICodeReviewCLI(config)
    result = controller.review_diffs()
    usage = usage_tracker.record(
        endpoint="/api/review-diffs",
        model=config.ai_model,
        tokens_used=int(result.get("tokens_used", 0)),
        token_source=str(result.get("token_source", "unknown")),
        token_usage=result.get("token_usage"),
    )
    result["usage"] = usage
    return result


def _execute_run_full_review(config: ConfigModel) -> dict:
    """Run full-review workflow synchronously and return final payload."""
    LOGGER.info("API request /api/run-full-review repo=%s", config.repository_name)
    controller = AgenticAICodeReviewCLI(config=config)
    result = controller.run_full_review()
    usage = usage_tracker.record(
        endpoint="/api/run-full-review",
        model=config.ai_model,
        tokens_used=int(result.get("tokens_used", 0)),
        token_source=str(result.get("token_source", "unknown")),
        token_usage=result.get("token_usage"),
    )
    result["usage"] = usage
    return result


def _execute_static_checks(request: StaticChecksRequestModel) -> dict:
    """Run static-check workflow synchronously and return final payload."""
    LOGGER.info(
        "API request /api/static-checks repo=%s scope=%s",
        request.repo_path,
        request.scope,
    )
    runner = StaticCheckRunner(repo_path=request.repo_path)
    scope = (request.scope or "repo").strip().lower()
    target_files: list[str] | None = request.file_paths or None
    if scope not in {"repo", "changed"}:
        raise ValueError("Invalid static check scope. Use 'repo' or 'changed'.")

    if scope == "changed" and target_files is None:
        controller = AgenticAICodeReviewCLI(config=request)
        diffs = controller._collect_diffs()
        target_files = _extract_changed_file_paths(diffs)

    result = runner.run_checks(file_paths=target_files)
    result["scope"] = scope
    result["target_files_count"] = len(target_files or [])
    return result


def _build_pr_workflow_service(request: PRWorkflowBaseRequestModel) -> PRWorkflowService:
    """Construct PR workflow service from API request payload."""
    return PRWorkflowService(
        repo_path=request.repo_path,
        organization=request.organization,
        project=request.project,
        repository_name=request.repository_name,
        azure_pat=request.azure_pat,
        defaults_path=request.defaults_path,
    )


def _execute_raise_new_pr(
    request: RaiseNewPRRequestModel,
    *,
    before_stage_approval: Any | None = None,
) -> dict:
    """Execute option-1 PR workflow synchronously and return payload."""
    service = _build_pr_workflow_service(request)
    return service.execute_raise_new_pr(
        feature_id=request.feature_id,
        selected_serials=request.selected_serials,
        reviewer_ids=request.reviewer_ids,
        reviewer_ids_by_branch=request.reviewer_ids_by_branch,
        target_branches=request.target_branches,
        additional_work_item_ids=request.additional_work_item_ids,
        commit_message=request.commit_message,
        before_stage_approval=before_stage_approval,
    )


@app.get("/")
async def read_root() -> FileResponse:
    """Serve the web UI index page."""
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI index file not found")
    return FileResponse(index_file, headers={"Cache-Control": "no-store"})


@app.get("/styles.css")
async def read_legacy_styles() -> FileResponse:
    """Backward-compatible route for older cached index pages."""
    styles_file = UI_DIR / "styles.css"
    if not styles_file.exists():
        raise HTTPException(status_code=404, detail="UI stylesheet not found")
    return FileResponse(styles_file, headers={"Cache-Control": "no-store"})


@app.get("/script.js")
async def read_legacy_script() -> FileResponse:
    """Backward-compatible route for older cached index pages."""
    script_file = UI_DIR / "script.js"
    if not script_file.exists():
        raise HTTPException(status_code=404, detail="UI script not found")
    return FileResponse(script_file, headers={"Cache-Control": "no-store"})


@app.get("/api/ui-defaults")
async def ui_defaults() -> dict:
    """Return UI bootstrap defaults."""
    return {
        "azure_pat": _resolve_default_azure_pat(),
        "default_reviewer_emails": _resolve_default_reviewer_emails(),
        "pr_workflow_defaults": _load_pr_workflow_defaults_for_ui(),
    }


@app.get("/api/config/pr-workflow-defaults")
async def get_pr_workflow_defaults_config() -> dict:
    """Return the editable PR workflow defaults JSON config used by the settings drawer."""
    try:
        config = _read_pr_workflow_defaults_file()
        return {
            "path": str(_pr_workflow_defaults_path().relative_to(BASE_DIR)).replace("\\", "/"),
            "config": config,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Unable to read PR workflow defaults config file")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/config/pr-workflow-defaults")
async def update_pr_workflow_defaults_config(request: PRWorkflowDefaultsUpdateModel) -> dict:
    """Persist settings-drawer changes back into config/pr_workflow_defaults.json."""
    try:
        saved = _write_pr_workflow_defaults_file(request.config)
        return {
            "message": "PR workflow defaults updated successfully.",
            "path": str(_pr_workflow_defaults_path().relative_to(BASE_DIR)).replace("\\", "/"),
            "config": saved,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Unable to update PR workflow defaults config file")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/review-diffs")
async def review_diffs(
    config: ConfigModel,
    async_job: bool = Query(default=False, description="Run in background and return job metadata."),
) -> dict:
    """
    Collect pull-request diffs and produce review comments.

    Args:
        config: Review configuration payload.

    Returns:
        Review details and token metrics.
    """
    try:
        if async_job:
            job_id = job_manager.submit(
                job_type="review-diffs",
                payload=_model_to_dict(config),
                runner=lambda payload: _execute_review_diffs(ConfigModel(**payload)),
            )
            return JSONResponse(status_code=202, content=_job_submission_payload(job_id))
        return _execute_review_diffs(config)
    except Exception as exc:
        LOGGER.exception("Review diff request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate-changes")
async def generate_changes(config: ConfigModel) -> dict:
    """
    Generate code changes from review feedback and PR diff.

    Args:
        config: Review configuration payload.

    Returns:
        Suggested code changes.
    """
    try:
        LOGGER.info("API request /api/generate-changes repo=%s", config.repository_name)
        controller = AgenticAICodeReviewCLI(config=config)
        result = controller.generate_changes(review=config.review or "")
        usage = usage_tracker.record(
            endpoint="/api/generate-changes",
            model=config.ai_model,
            tokens_used=int(result.get("tokens_used", 0)),
            token_source=str(result.get("token_source", "unknown")),
            token_usage=result.get("token_usage"),
        )
        result["usage"] = usage
        return result
    except Exception as exc:
        LOGGER.exception("Generate changes request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/run-full-review")
async def run_full_review(
    config: ConfigModel,
    async_job: bool = Query(default=False, description="Run in background and return job metadata."),
) -> dict:
    """
    Execute full review in one API call.

    Args:
        config: Review configuration payload.

    Returns:
        End-to-end review result.
    """
    try:
        if async_job:
            job_id = job_manager.submit(
                job_type="run-full-review",
                payload=_model_to_dict(config),
                runner=lambda payload: _execute_run_full_review(ConfigModel(**payload)),
            )
            return JSONResponse(status_code=202, content=_job_submission_payload(job_id))
        return _execute_run_full_review(config)
    except Exception as exc:
        LOGGER.exception("Run full review request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/apply-changes")
async def apply_changes(change: ApplyChangesModel) -> dict:
    """
    Apply a generated patch to a file and create a backup snapshot.

    Args:
        change: Patch application payload.

    Returns:
        Status and backup details.
    """
    try:
        allow_fallback_search = bool(change.allow_fallback_search)
        request = PatchApplyRequest(
            repo_path=change.repo_path,
            file_path=change.file_path,
            old_start_line_number=change.old_start_line_number,
            number_of_lines_removed_from_old=change.number_of_lines_removed_from_old,
            new_content=change.new_content,
            old_content=change.old_content,
            allow_fallback_search=allow_fallback_search,
        )
        LOGGER.info("API request /api/apply-changes file=%s", change.file_path)
        result = patch_applier.apply_change(request)
        if not result.get("success", False):
            message_text = str(result.get("message", "") or "").lower()
            can_retry_with_fallback = (
                not allow_fallback_search
                and "does not match expected old content" in message_text
            )
            if can_retry_with_fallback:
                fallback_request = PatchApplyRequest(
                    repo_path=change.repo_path,
                    file_path=change.file_path,
                    old_start_line_number=change.old_start_line_number,
                    number_of_lines_removed_from_old=change.number_of_lines_removed_from_old,
                    new_content=change.new_content,
                    old_content=change.old_content,
                    allow_fallback_search=True,
                )
                fallback_result = patch_applier.apply_change(fallback_request)
                if fallback_result.get("success", False):
                    fallback_result["applied_with_fallback_search"] = True
                    return fallback_result
                result = fallback_result

            message_text = str(result.get("message", "") or "").lower()
            can_retry_relaxed_old_content = (
                allow_fallback_search
                and bool((change.old_content or "").strip())
                and "does not match expected old content" in message_text
                and "no fallback match found" in message_text
            )
            if can_retry_relaxed_old_content:
                relaxed_request = PatchApplyRequest(
                    repo_path=change.repo_path,
                    file_path=change.file_path,
                    old_start_line_number=change.old_start_line_number,
                    number_of_lines_removed_from_old=change.number_of_lines_removed_from_old,
                    new_content=change.new_content,
                    old_content="",
                    allow_fallback_search=True,
                )
                relaxed_result = patch_applier.apply_change(relaxed_request)
                if relaxed_result.get("success", False):
                    relaxed_result["applied_with_relaxed_old_content"] = True
                    return relaxed_result
                result = relaxed_result
            raise HTTPException(
                status_code=400,
                detail=_build_apply_error_detail(result),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Apply changes request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
async def health_check() -> dict:
    """Return basic service health data."""
    return {"status": "healthy", "service": "agentic-ai-code-review"}


@app.get("/api/usage-metrics")
async def usage_metrics() -> dict:
    """Return in-memory token and estimated cost metrics."""
    return usage_tracker.snapshot()


@app.post("/api/static-checks")
async def run_static_checks(
    request: StaticChecksRequestModel,
    async_job: bool = Query(default=False, description="Run in background and return job metadata."),
) -> dict:
    """
    Execute command-based static checks for detected repo languages.

    Args:
        request: Static check request payload.

    Returns:
        Structured command executions and normalized issues.
    """
    try:
        if async_job:
            job_id = job_manager.submit(
                job_type="static-checks",
                payload=_model_to_dict(request),
                runner=lambda payload: _execute_static_checks(StaticChecksRequestModel(**payload)),
            )
            return JSONResponse(status_code=202, content=_job_submission_payload(job_id))
        return _execute_static_checks(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Static checks request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Return current status/result for an async job."""
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@app.get("/api/jobs/{job_id}/approval-preview")
async def get_job_approval_preview(
    job_id: str,
    request_id: str = Query(..., description="Active approval request id returned by the job poll payload."),
) -> dict:
    """Return the live diff preview for the current paused approval checkpoint."""
    try:
        approval_request = job_manager.get_pending_approval(job_id, request_id)
        return PRWorkflowService.build_approval_preview(
            workspace_repo_path=approval_request.get("workspace_repo_path", ""),
            target_branch=approval_request.get("target_branch", ""),
            selected_files=approval_request.get("selected_files", []),
            source_branch=approval_request.get("source_branch", ""),
            repo_root_label=approval_request.get("repo_root_label", ""),
            request_id=approval_request.get("request_id", ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Approval preview request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/proceed")
async def proceed_job(job_id: str, request: JobProceedRequestModel) -> dict:
    """Proceed one paused async job after manual branch review confirmation."""
    try:
        return job_manager.approve(job_id, request.request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/pr-workflow/feature-context")
async def pr_feature_context(request: PRFeatureContextRequestModel) -> dict:
    """Resolve feature title, parent/child work items, and derived branch names."""
    try:
        service = _build_pr_workflow_service(request)
        return service.get_feature_context(feature_id=request.feature_id)
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Feature context lookup failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/changed-files")
async def pr_changed_files(request: PRWorkflowBaseRequestModel) -> dict:
    """List local changed files with serial numbers for selection."""
    try:
        service = _build_pr_workflow_service(request)
        files = service.list_changed_files()
        return {"count": len(files), "files": files}
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Changed files lookup failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/reviewers")
async def pr_reviewer_candidates(request: PRReviewersRequestModel) -> dict:
    """List reviewer candidates from Azure DevOps identities."""
    try:
        service = _build_pr_workflow_service(request)
        reviewers = service.list_reviewer_candidates(
            limit=request.limit,
            preferred_emails=request.preferred_emails,
        )
        return {"count": len(reviewers), "reviewers": reviewers}
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Reviewer candidate lookup failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/work-item-family")
async def pr_work_item_family(request: PRWorkItemFamilyRequestModel) -> dict:
    """Resolve parent and child items for one work item ID."""
    try:
        service = _build_pr_workflow_service(request)
        return service.collect_work_item_family(request.work_item_id)
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Work item family lookup failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/raise-new-pr")
async def pr_raise_new(
    request: RaiseNewPRRequestModel,
    async_job: bool = Query(default=False, description="Run in background and return job metadata."),
) -> dict:
    """Execute option-1 workflow: create 2 branches, push selected files, raise 2 PRs."""
    try:
        if async_job:
            job_id = job_manager.submit(
                job_type="raise-new-pr",
                payload=_model_to_dict(request),
                runner=lambda payload, current_job_id: _execute_raise_new_pr(
                    RaiseNewPRRequestModel(**payload),
                    before_stage_approval=lambda approval_payload: job_manager.wait_for_approval(
                        current_job_id,
                        approval_payload,
                    ),
                ),
            )
            return JSONResponse(status_code=202, content=_job_submission_payload(job_id))
        return _execute_raise_new_pr(request)
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Raise new PR workflow failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/cherry-pick")
async def pr_cherry_pick(request: CherryPickRequestModel) -> dict:
    """Execute option-2 workflow: cherry-pick commits from one branch and push."""
    try:
        service = _build_pr_workflow_service(request)
        return service.execute_cherry_pick(
            source_branch=request.source_branch,
            target_branch=request.target_branch,
            commit_hashes=request.commit_hashes,
        )
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Cherry-pick workflow failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pr-workflow/commit-and-push")
async def pr_commit_and_push(request: CommitAndPushRequestModel) -> dict:
    """Execute option-3 workflow: commit selected files to branch and push."""
    try:
        service = _build_pr_workflow_service(request)
        return service.execute_commit_and_push(
            branch_name=request.branch_name,
            base_branch=request.base_branch,
            selected_serials=request.selected_serials,
            commit_message=request.commit_message,
        )
    except PRWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Commit and push workflow failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/ws/jobs/{job_id}")
async def stream_job_status(websocket: WebSocket, job_id: str) -> None:
    """Stream job status snapshots over WebSocket until terminal state."""
    await websocket.accept()
    try:
        while True:
            job = job_manager.get(job_id)
            if not job:
                await websocket.send_json(
                    {"job_id": job_id, "status": "missing", "error": {"message": "Job not found"}}
                )
                break

            await websocket.send_json(job)
            if job_manager.is_terminal(str(job.get("status", ""))):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            return


def _extract_changed_file_paths(diffs: list[dict[str, Any]]) -> list[str]:
    """Extract unique changed file paths from local/PR diff payload shapes."""
    paths: list[str] = []
    for item in diffs or []:
        if not isinstance(item, dict):
            continue
        candidate = item.get("file") or item.get("file_path")
        if not candidate and isinstance(item.get("diff"), dict):
            candidate = item["diff"].get("file_path")
        if isinstance(candidate, str) and candidate.strip():
            normalized = candidate.strip().lstrip("/\\")
            if normalized not in paths:
                paths.append(normalized)
    return paths

def _build_apply_error_detail(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize patch apply failures into stable API error payloads."""
    if not isinstance(result, dict):
        return {"message": "Patch failed"}

    detail: dict[str, Any] = {"message": str(result.get("message", "Patch failed"))}
    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        detail["diagnostics"] = diagnostics
    match_mode = result.get("match_mode")
    if isinstance(match_mode, str) and match_mode.strip():
        detail["match_mode"] = match_mode.strip()
    return detail


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
