"""Tests for checkpoint store backend factory behavior."""

from __future__ import annotations

from src.config.settings import CheckpointConfig
from src.state.checkpoint_store import (
    CheckpointStore,
    ElasticsearchCheckpointStore,
    create_checkpoint_store,
)


class _StubEsClient:
    pass


def test_factory_builds_file_backend() -> None:
    config = CheckpointConfig(provider="file", path="state/checkpoints.json")
    backend = create_checkpoint_store(config)
    assert isinstance(backend, CheckpointStore)


def test_factory_builds_elasticsearch_backend() -> None:
    config = CheckpointConfig(provider="elasticsearch", elasticsearch_index="rca-checkpoints")
    backend = create_checkpoint_store(config, es_client=_StubEsClient())  # type: ignore[arg-type]
    assert isinstance(backend, ElasticsearchCheckpointStore)


def test_factory_rejects_unsupported_provider() -> None:
    config = CheckpointConfig(provider="unknown")
    try:
        create_checkpoint_store(config)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unsupported checkpoint provider" in str(exc)
