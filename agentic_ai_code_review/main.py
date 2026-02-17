"""FastAPI application entry point for the Agentic AI code review service."""

from __future__ import annotations

import asyncio
import os
import logging
import threading
import time
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
from review_manager.static_checks import StaticCheckRunner


def configure_logging() -> None:
    """Configure process-wide logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


configure_logging()
LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
patch_applier = PatchApplier()


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
            result = runner(payload)
            finished_at = int(time.time())
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "succeeded"
                job["result"] = result
                job["finished_at"] = finished_at
                job["updated_at"] = finished_at
        except Exception as exc:
            finished_at = int(time.time())
            LOGGER.exception("Background job failed job_id=%s", job_id)
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "failed"
                job["error"] = {"message": str(exc)}
                job["finished_at"] = finished_at
                job["updated_at"] = finished_at

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


@app.get("/")
async def read_root() -> FileResponse:
    """Serve the web UI index page."""
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI index file not found")
    return FileResponse(index_file)


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
