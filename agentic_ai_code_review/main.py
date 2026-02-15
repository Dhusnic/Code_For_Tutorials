"""FastAPI application entry point for the Agentic AI code review service."""

from __future__ import annotations

import os
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

    def record(self, *, endpoint: str, model: str, tokens_used: int) -> dict:
        """Record one request usage and return request-level usage payload."""
        tokens = max(int(tokens_used or 0), 0)
        estimated_cost = self._cost_for(model, tokens)
        event = {
            "timestamp": int(time.time()),
            "endpoint": endpoint,
            "model": model,
            "tokens_used": tokens,
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


usage_tracker = UsageTracker()

app = FastAPI(title="Agentic AI Code Review API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


@app.get("/")
async def read_root() -> FileResponse:
    """Serve the web UI index page."""
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI index file not found")
    return FileResponse(index_file)


@app.post("/api/review-diffs")
async def review_diffs(config: ConfigModel) -> dict:
    """
    Collect pull-request diffs and produce review comments.

    Args:
        config: Review configuration payload.

    Returns:
        Review details and token metrics.
    """
    try:
        LOGGER.info("API request /api/review-diffs repo=%s", config.repository_name)
        controller = AgenticAICodeReviewCLI(config)
        result = controller.review_diffs()
        usage = usage_tracker.record(
            endpoint="/api/review-diffs",
            model=config.ai_model,
            tokens_used=int(result.get("tokens_used", 0)),
        )
        result["usage"] = usage
        return result
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
        )
        result["usage"] = usage
        return result
    except Exception as exc:
        LOGGER.exception("Generate changes request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/run-full-review")
async def run_full_review(config: ConfigModel) -> dict:
    """
    Execute full review in one API call.

    Args:
        config: Review configuration payload.

    Returns:
        End-to-end review result.
    """
    try:
        LOGGER.info("API request /api/run-full-review repo=%s", config.repository_name)
        controller = AgenticAICodeReviewCLI(config=config)
        result = controller.run_full_review()
        usage = usage_tracker.record(
            endpoint="/api/run-full-review",
            model=config.ai_model,
            tokens_used=int(result.get("tokens_used", 0)),
        )
        result["usage"] = usage
        return result
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
        request = PatchApplyRequest(
            repo_path=change.repo_path,
            file_path=change.file_path,
            old_start_line_number=change.old_start_line_number,
            number_of_lines_removed_from_old=change.number_of_lines_removed_from_old,
            new_content=change.new_content,
            old_content=change.old_content,
        )
        LOGGER.info("API request /api/apply-changes file=%s", change.file_path)
        result = patch_applier.apply_change(request)
        if not result.get("success", False):
            raise HTTPException(
                status_code=400,
                detail=result.get("diagnostics")
                or {"message": result.get("message", "Patch failed")},
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
async def run_static_checks(request: StaticChecksRequestModel) -> dict:
    """
    Execute command-based static checks for detected repo languages.

    Args:
        request: Static check request payload.

    Returns:
        Structured command executions and normalized issues.
    """
    try:
        LOGGER.info(
            "API request /api/static-checks repo=%s scope=%s",
            request.repo_path,
            request.scope,
        )
        runner = StaticCheckRunner(repo_path=request.repo_path)
        scope = (request.scope or "repo").strip().lower()
        target_files: list[str] | None = request.file_paths or None
        if scope not in {"repo", "changed"}:
            raise HTTPException(status_code=400, detail="Invalid static check scope. Use 'repo' or 'changed'.")

        if scope == "changed" and target_files is None:
            controller = AgenticAICodeReviewCLI(config=request)
            diffs = controller._collect_diffs()
            target_files = _extract_changed_file_paths(diffs)

        result = runner.run_checks(file_paths=target_files)
        result["scope"] = scope
        result["target_files_count"] = len(target_files or [])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Static checks request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
