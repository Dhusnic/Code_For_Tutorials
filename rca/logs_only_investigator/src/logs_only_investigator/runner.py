from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runtime import InvestigatorRuntime, build_runtime


@dataclass(frozen=True)
class InvestigationRequest:
    query: str
    organization_id: str | None = None
    thread_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    service: str | None = None
    host: str | None = None
    ip: str | None = None


def run_investigation(runtime: InvestigatorRuntime, request: InvestigationRequest) -> dict[str, object]:
    return run_investigation_with_artifacts(runtime, request)["report"]


def run_investigation_with_artifacts(runtime: InvestigatorRuntime, request: InvestigationRequest) -> dict[str, object]:
    organization_id = request.organization_id or runtime.config.app.default_organization_id
    thread_id = request.thread_id or runtime.config.app.default_thread_id
    clear_cache = getattr(runtime.topology_source, "clear_cache", None)
    if callable(clear_cache):
        clear_cache(organization_id)
    result = runtime.agent.invoke(
        {
            "user_query": request.query,
            "organization_id": organization_id,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "service": request.service,
            "host": request.host,
            "ip": request.ip,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "report": result["report"],
        "tool_results": result.get("tool_results", {}),
        "planner_trace": result.get("planner_trace", []),
        "session_memory": result.get("session_memory", {}),
    }


def load_runtime_for_request(
    *,
    config_path: Path,
    env_path: Path | None,
    catalog_root: Path,
    max_hops_override: int | None = None,
) -> InvestigatorRuntime:
    return build_runtime(
        config_path=config_path,
        env_path=env_path,
        catalog_root=catalog_root,
        max_hops_override=max_hops_override,
    )


def default_config_file() -> Path:
    return Path(__file__).resolve().parents[2] / "config.yml"


def default_env_file() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def default_catalog_root() -> Path:
    return Path(__file__).resolve().parents[2] / "rag"
