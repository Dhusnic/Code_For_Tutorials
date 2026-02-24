"""Tests for indexing guard behavior in signal enrichment service."""

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


def _build_service(tmp_path) -> SignalEnrichmentService:
    config = AppConfig(
        elasticsearch=ElasticsearchConfig(hosts=["http://localhost:9200"]),
        checkpoints=CheckpointConfig(path=str(tmp_path / "checkpoints.json")),
        logging=LoggingConfig(),
        pipeline=PipelineConfig(
            write_to_source_index=False,
            write_to_target_index=True,
            target_suffix="-rca",
        ),
        rules_directory="rules",
    )
    return SignalEnrichmentService(
        es_client=_StubClient(),  # type: ignore[arg-type]
        config=config,
        checkpoint_store=CheckpointStore(str(tmp_path / "checkpoints.json")),
    )


def test_does_not_append_target_suffix_twice(tmp_path) -> None:
    service = _build_service(tmp_path)
    try:
        destinations = service._resolve_destination_indices("linux_logs-2026.02.19-rca")
        assert destinations == ["linux_logs-2026.02.19-rca"]
    finally:
        service.shutdown()


def test_already_signaled_detection_handles_bool_and_string() -> None:
    assert SignalEnrichmentService._is_already_signaled_doc({"signal_present": True}) is True
    assert SignalEnrichmentService._is_already_signaled_doc({"signal_present": "true"}) is True
    assert SignalEnrichmentService._is_already_signaled_doc({"signal_present": 1}) is True
    assert SignalEnrichmentService._is_already_signaled_doc({"signal_present": False}) is False
    assert SignalEnrichmentService._is_already_signaled_doc({}) is False

