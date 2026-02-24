"""Tests for worker runtime overrides via process-manager environment variables."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import load_app_config


def _write_config(path: Path) -> None:
    path.write_text(
        """
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  worker_count: 1
  worker_id: 0
  services: []
""".strip(),
        encoding="utf-8",
    )


def test_worker_runtime_overrides_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yml"
    _write_config(config_file)

    monkeypatch.setenv("RCA_WORKER_COUNT", "4")
    monkeypatch.setenv("RCA_WORKER_ID", "2")

    config = load_app_config(str(config_file))
    assert config.pipeline.worker_count == 4
    assert config.pipeline.worker_id == 2


def test_worker_runtime_falls_back_to_node_app_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_file = tmp_path / "config.yml"
    _write_config(config_file)

    monkeypatch.setenv("RCA_WORKER_COUNT", "3")
    monkeypatch.setenv("NODE_APP_INSTANCE", "1")

    config = load_app_config(str(config_file))
    assert config.pipeline.worker_count == 3
    assert config.pipeline.worker_id == 1


def test_worker_runtime_rejects_invalid_env_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_file = tmp_path / "config.yml"
    _write_config(config_file)

    monkeypatch.setenv("RCA_WORKER_COUNT", "two")
    with pytest.raises(ValueError, match="RCA_WORKER_COUNT must be an integer"):
        load_app_config(str(config_file))
