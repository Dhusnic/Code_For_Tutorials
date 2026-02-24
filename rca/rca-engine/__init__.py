"""Legacy run.py adapter for the RCA engine package."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_BASE_DIR = os.path.dirname(__file__)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

_appconf: Any = None
_service = None
_stop_requested = False

APP_NAME = "RCA Engine"
DATA_SRC_REQUIRED: list[str] = []
ARGS_REQUIRED = [
    ("config", "RCA config file path"),
    ("run_once", "Run single cycle true/false"),
]


def init(appconf: Any) -> None:
    """Capture run.py-provided app configuration module."""
    global _appconf, _stop_requested
    _appconf = appconf
    _stop_requested = False


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _resolve_config_path() -> str:
    if _appconf is None:
        return os.path.join(_BASE_DIR, "config.yml")

    configured = getattr(_appconf, "config", "") or ""
    configured = str(configured).strip()
    if configured:
        if os.path.isabs(configured):
            return configured
        return os.path.abspath(configured)

    return os.path.join(_BASE_DIR, "config.yml")


def _resolve_instances_from_app_json() -> int | None:
    """Read worker count from local PM2 app definition."""
    app_json_path = os.path.join(_BASE_DIR, "app.json")
    if not os.path.exists(app_json_path):
        return None

    try:
        with open(app_json_path, "r", encoding="utf-8") as fh:
            payload = json.loads(fh.read())
    except Exception:
        return None

    apps = payload.get("apps", []) if isinstance(payload, dict) else []
    if not isinstance(apps, list):
        return None

    app_name = str(getattr(_appconf, "app_name", "rca-engine")).strip() or "rca-engine"
    selected = None
    for app in apps:
        if not isinstance(app, dict):
            continue
        if str(app.get("name", "")).strip() == app_name:
            selected = app
            break
    if selected is None and apps and isinstance(apps[0], dict):
        selected = apps[0]
    if selected is None:
        return None

    instances = selected.get("instances")
    if isinstance(instances, int):
        return instances if instances > 0 else None

    if isinstance(instances, str):
        text = instances.strip().lower()
        if not text:
            return None
        if text == "max":
            return max(1, int(os.cpu_count() or 1))
        if text.isdigit():
            value = int(text)
            return value if value > 0 else None
    return None


def _prime_worker_count_from_instances() -> None:
    """Set RCA_WORKER_COUNT from app.json instances when running under PM2."""
    is_pm2_managed = any(
        os.getenv(key)
        for key in ("RCA_WORKER_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id")
    )
    if not is_pm2_managed:
        return

    instances = _resolve_instances_from_app_json()
    if instances is None:
        return
    os.environ["RCA_WORKER_COUNT"] = str(instances)


def run() -> None:
    """Run RCA enrichment loop under the legacy run.py lifecycle."""
    global _service
    from src.config.settings import load_app_config
    from src.connectors.elasticsearch_client import ElasticClientFactory
    from src.enrichment.signal_enricher import SignalEnrichmentService
    from src.state.checkpoint_store import create_checkpoint_store
    from src.utils.logging import configure_logging

    _prime_worker_count_from_instances()
    config_path = _resolve_config_path()
    config = load_app_config(config_path)
    configure_logging(config.logging)
    logger = logging.getLogger(__name__)

    run_once = _to_bool(getattr(_appconf, "run_once", False), default=False)
    es_client = ElasticClientFactory(config.elasticsearch).create()
    checkpoint_store = create_checkpoint_store(config.checkpoints, es_client=es_client)
    _service = SignalEnrichmentService(
        es_client=es_client,
        config=config,
        checkpoint_store=checkpoint_store,
    )

    try:
        while not _stop_requested:
            processed = _service.run_cycle()
            logger.info("Processing cycle completed", extra={"processed": processed})
            if run_once:
                break
            if _stop_requested:
                break
            # Keep stop latency low while honoring poll interval.
            for _ in range(max(1, int(config.pipeline.poll_interval_seconds * 10))):
                if _stop_requested:
                    break
                time.sleep(0.1)
    finally:
        if _service is not None:
            try:
                _service.shutdown()
            finally:
                _service = None


def stop(source: str = "NA") -> None:
    """Request graceful shutdown for signal handlers in run.py."""
    global _stop_requested
    _stop_requested = True


def runTest(flag: str = "0") -> None:  # noqa: N802 - keep legacy name
    """Legacy compatibility hook used by run.py -runtest."""
    if _appconf is not None:
        setattr(_appconf, "run_once", "true")
    run()
