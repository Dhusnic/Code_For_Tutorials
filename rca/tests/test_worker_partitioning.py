"""Tests for partition-based worker ownership."""

from __future__ import annotations

from src.config.settings import (
    AppConfig,
    CheckpointConfig,
    ElasticsearchConfig,
    LoggingConfig,
    PipelineConfig,
)
from src.enrichment.signal_enricher import SignalEnrichmentService
from src.state.checkpoint_store import CheckpointStore


class _StubClient:
    pass


def _build_service(tmp_path, worker_id: int, worker_count: int) -> SignalEnrichmentService:
    config = AppConfig(
        elasticsearch=ElasticsearchConfig(hosts=["http://localhost:9200"]),
        checkpoints=CheckpointConfig(path=str(tmp_path / "checkpoints.json")),
        logging=LoggingConfig(),
        pipeline=PipelineConfig(worker_id=worker_id, worker_count=worker_count),
        rules_directory="rules",
    )
    return SignalEnrichmentService(
        es_client=_StubClient(),  # type: ignore[arg-type]
        config=config,
        checkpoint_store=CheckpointStore(str(tmp_path / "checkpoints.json")),
    )


def test_partition_assignment_changes_by_worker_id(tmp_path) -> None:
    worker0 = _build_service(tmp_path, worker_id=0, worker_count=2)
    worker1 = _build_service(tmp_path, worker_id=1, worker_count=2)
    try:
        owns0 = worker0._owns_partition("nginx", "linux-*")
        owns1 = worker1._owns_partition("nginx", "linux-*")
        assert owns0 != owns1
    finally:
        worker0.shutdown()
        worker1.shutdown()
