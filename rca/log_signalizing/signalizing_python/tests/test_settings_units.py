"""Tests for unit-aware configuration parsing."""

from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

from src.config.settings import load_app_config


def test_load_config_parses_size_and_duration_units(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
elasticsearch:
  hosts: ["http://localhost:9200"]
  request_timeout_seconds: "45s"

pipeline:
  batch_size: 100
  bulk_max_batch_bytes: "16MB"
  bulk_queue_enqueue_timeout_seconds: "250ms"
  bulk_spool_max_bytes: "2GB"
  bulk_spool_replay_interval_seconds: "1s"
  bulk_autoscaling_check_interval_seconds: "3s"
  bulk_autoscaling_cooldown_seconds: "12s"
  dynamic_batch_lookback_seconds: "30s"
  dynamic_batch_target_window_seconds: "1500ms"
  autoscaling_lag_scale_up_seconds: "2m"
  autoscaling_lag_scale_down_seconds: "15s"
  poll_interval_seconds: "10s"
  retry_initial_backoff_seconds: "500ms"
  start_time: "now-15m"
  services: []
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(str(config_file))

    assert config.elasticsearch.request_timeout_seconds == 45
    assert config.pipeline.bulk_max_batch_bytes == 16 * 1024 * 1024
    assert config.pipeline.bulk_queue_enqueue_timeout_seconds == 0.25
    assert config.pipeline.bulk_spool_max_bytes == 2 * 1024 * 1024 * 1024
    assert config.pipeline.bulk_spool_replay_interval_seconds == 1.0
    assert config.pipeline.bulk_autoscaling_check_interval_seconds == 3.0
    assert config.pipeline.bulk_autoscaling_cooldown_seconds == 12.0
    assert config.pipeline.dynamic_batch_lookback_seconds == 30
    assert config.pipeline.dynamic_batch_target_window_seconds == 1.5
    assert config.pipeline.autoscaling_lag_scale_up_seconds == 120.0
    assert config.pipeline.autoscaling_lag_scale_down_seconds == 15.0
    assert config.pipeline.poll_interval_seconds == 10
    assert config.pipeline.retry_initial_backoff_seconds == 0.5
    # Elasticsearch DSL time remains a raw string and is not unit-parsed by app code.
    assert config.pipeline.start_time == "now-15m"


def test_load_config_rejects_invalid_size_unit(tmp_path: Path) -> None:
    config_file = tmp_path / "config-invalid.yml"
    config_file.write_text(
        """
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  bulk_max_batch_bytes: "8XB"
  services: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pipeline.bulk_max_batch_bytes"):
        load_app_config(str(config_file))


def test_load_config_uses_settings_log_hosts_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_settings = types.ModuleType("settings")
    fake_settings.LOG_HOSTS = "10.0.0.10:9200,https://10.0.0.11:9200"
    monkeypatch.setitem(sys.modules, "settings", fake_settings)

    config_file = tmp_path / "config-settings-hosts.yml"
    config_file.write_text(
        """
elasticsearch:
  hosts: ["http://localhost:9200"]

pipeline:
  services: []
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(str(config_file))
    assert config.elasticsearch.hosts == [
        "http://10.0.0.10:9200",
        "https://10.0.0.11:9200",
    ]


def test_load_config_falls_back_to_yaml_hosts_without_settings_log_hosts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_settings = types.ModuleType("settings")
    monkeypatch.setitem(sys.modules, "settings", fake_settings)

    config_file = tmp_path / "config-fallback-hosts.yml"
    config_file.write_text(
        """
elasticsearch:
  hosts:
    - "es-a:9200"
    - "http://es-b:9200"

pipeline:
  services: []
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(str(config_file))
    assert config.elasticsearch.hosts == [
        "http://es-a:9200",
        "http://es-b:9200",
    ]


def test_rules_directory_is_resolved_relative_to_config_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_settings = types.ModuleType("settings")
    monkeypatch.setitem(sys.modules, "settings", fake_settings)

    cfg_dir = tmp_path / "signalizing-engine"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    config_file = cfg_dir / "config.yml"
    config_file.write_text(
        """
elasticsearch:
  hosts: ["http://localhost:9200"]

rules_directory: "rules"

pipeline:
  services: []
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(str(config_file))
    assert config.rules_directory == str((cfg_dir / "rules").resolve())
