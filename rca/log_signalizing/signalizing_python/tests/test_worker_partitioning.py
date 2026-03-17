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


class _StubIndicesClient:
    def __init__(self, patterns: dict[str, list[str]], *, raises: bool = False) -> None:
        self._patterns = patterns
        self._raises = raises

    def get(
        self,
        *,
        index: str,
        allow_no_indices: bool = True,
        ignore_unavailable: bool = True,
        expand_wildcards: str = "open,hidden",
    ) -> dict[str, dict[str, str]]:
        del allow_no_indices, ignore_unavailable, expand_wildcards
        if self._raises:
            raise RuntimeError("boom")
        return {name: {} for name in self._patterns.get(index, [])}


class _StubClientWithIndices:
    def __init__(self, patterns: dict[str, list[str]], *, raises: bool = False) -> None:
        self.indices = _StubIndicesClient(patterns, raises=raises)


def _build_service(
    tmp_path,
    worker_id: int,
    worker_count: int,
    *,
    es_client: object | None = None,
) -> SignalEnrichmentService:
    config = AppConfig(
        elasticsearch=ElasticsearchConfig(hosts=["http://localhost:9200"]),
        checkpoints=CheckpointConfig(path=str(tmp_path / "checkpoints.json")),
        logging=LoggingConfig(),
        pipeline=PipelineConfig(worker_id=worker_id, worker_count=worker_count),
        rules_directory="rules",
    )
    return SignalEnrichmentService(
        es_client=(es_client or _StubClient()),  # type: ignore[arg-type]
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


def test_source_index_resolution_expands_wildcards(tmp_path) -> None:
    service = _build_service(
        tmp_path,
        worker_id=0,
        worker_count=2,
        es_client=_StubClientWithIndices(
            {"logs-*": ["logs-2026.02.22", "logs-2026.02.23"]}
        ),
    )
    try:
        resolved = service._resolve_source_indices("nginx", ["logs-*", "logs-2026.02.23"])
        assert resolved == ["logs-2026.02.22", "logs-2026.02.23"]
    finally:
        service.shutdown()


def test_source_index_resolution_falls_back_when_wildcard_expand_fails(tmp_path) -> None:
    service = _build_service(
        tmp_path,
        worker_id=0,
        worker_count=2,
        es_client=_StubClientWithIndices({}, raises=True),
    )
    try:
        resolved = service._resolve_source_indices("nginx", ["logs-*"])
        assert resolved == ["logs-*"]
    finally:
        service.shutdown()
