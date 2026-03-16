"""Tests for static and dynamic batch-size resolution."""

from __future__ import annotations

from typing import Any

from src.config.settings import (
    AppConfig,
    CheckpointConfig,
    ElasticsearchConfig,
    LoggingConfig,
    PipelineConfig,
    ServiceConfig,
)
from src.enrichment.signal_enricher import SignalEnrichmentService
from src.state.checkpoint_store import CheckpointStore


class _CountClient:
    def __init__(self, count_value: int = 0, fail: bool = False) -> None:
        self._count_value = count_value
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    def count(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body})
        if self._fail:
            raise RuntimeError("count failed")
        return {"count": self._count_value}


def _build_config(tmp_path, mode: str) -> AppConfig:
    return AppConfig(
        elasticsearch=ElasticsearchConfig(hosts=["http://localhost:9200"]),
        checkpoints=CheckpointConfig(path=str(tmp_path / "checkpoints.json")),
        logging=LoggingConfig(level="INFO", json=True, log_unmatched_events=False),
        pipeline=PipelineConfig(
            batch_size=2000,
            batch_size_mode=mode,
            dynamic_batch_min_size=500,
            dynamic_batch_max_size=5000,
            dynamic_batch_lookback_seconds=20,
            dynamic_batch_target_window_seconds=2.0,
            dynamic_batch_smoothing_alpha=1.0,
        ),
        rules_directory="rules",
    )


def test_static_mode_uses_configured_batch_size(tmp_path) -> None:
    client = _CountClient(count_value=50000)
    service = SignalEnrichmentService(
        es_client=client,  # type: ignore[arg-type]
        config=_build_config(tmp_path, mode="static"),
        checkpoint_store=CheckpointStore(str(tmp_path / "checkpoints.json")),
    )

    batch = service._resolve_batch_size(
        ServiceConfig(name="nginx", query={"term": {"event.module": "nginx"}}),
        "linux-*",
    )

    assert batch == 2000
    assert client.calls == []


def test_dynamic_mode_uses_recent_events_per_second(tmp_path) -> None:
    client = _CountClient(count_value=30000)
    service = SignalEnrichmentService(
        es_client=client,  # type: ignore[arg-type]
        config=_build_config(tmp_path, mode="dynamic"),
        checkpoint_store=CheckpointStore(str(tmp_path / "checkpoints.json")),
    )
    svc = ServiceConfig(name="nginx", query={"term": {"event.module": "nginx"}})

    batch = service._resolve_batch_size(svc, "linux-*")

    # eps = 30000/20 = 1500; batch = eps * 2.0 = 3000, clamped to [500, 5000]
    assert batch == 3000
    assert client.calls[0]["index"] == "linux-*"
    query_bool = client.calls[0]["body"]["query"]["bool"]
    filters = query_bool["filter"]
    assert {"term": {"event.module": "nginx"}} in filters
    assert query_bool["must_not"] == [
        {"term": {"signal_present": True}},
        {"term": {"signal_present": "true"}},
    ]


def test_dynamic_mode_falls_back_to_static_on_error(tmp_path) -> None:
    client = _CountClient(fail=True)
    service = SignalEnrichmentService(
        es_client=client,  # type: ignore[arg-type]
        config=_build_config(tmp_path, mode="dynamic"),
        checkpoint_store=CheckpointStore(str(tmp_path / "checkpoints.json")),
    )

    batch = service._resolve_batch_size(ServiceConfig(name="nginx"), "linux-*")

    assert batch == 2000
