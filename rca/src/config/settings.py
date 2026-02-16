"""Application configuration models and loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ElasticsearchConfig:
    """Elasticsearch connection settings."""

    hosts: list[str]
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    verify_certs: bool = True
    request_timeout_seconds: int = 30


@dataclass(slots=True)
class CheckpointConfig:
    """Checkpoint persistence settings."""

    path: str = "state/checkpoints.json"


@dataclass(slots=True)
class LoggingConfig:
    """Application logging configuration."""

    level: str = "INFO"
    json: bool = True
    log_unmatched_events: bool = False


@dataclass(slots=True)
class ServiceConfig:
    """Service-specific processing settings."""

    name: str
    enabled: bool = True
    rule_file: str = ""
    source_indices: list[str] = field(default_factory=list)
    start_time: str | None = None
    query: dict[str, Any] | None = None


@dataclass(slots=True)
class PipelineConfig:
    """Pipeline runtime behavior settings."""

    batch_size: int = 500
    poll_interval_seconds: int = 10
    timestamp_field: str = "@timestamp"
    start_time: str = "now-15m"
    source_indices: list[str] = field(default_factory=list)
    target_suffix: str = "-rca"
    dead_letter_suffix: str = "-rca-dead-letter"
    retry_max_attempts: int = 4
    retry_initial_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    signal_max_per_event: int = 2
    signal_select_highest_only: bool = True
    services: list[ServiceConfig] = field(default_factory=list)


@dataclass(slots=True)
class AppConfig:
    """Root application configuration."""

    elasticsearch: ElasticsearchConfig
    checkpoints: CheckpointConfig
    logging: LoggingConfig
    pipeline: PipelineConfig
    rules_directory: str = "rules"


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required configuration key: {key}")
    return data[key]


def load_app_config(path: str) -> AppConfig:
    """Load application config from YAML file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a mapping")

    es_raw = _require(raw, "elasticsearch")
    pipe_raw = _require(raw, "pipeline")

    services: list[ServiceConfig] = []
    for item in pipe_raw.get("services", []):
        services.append(
            ServiceConfig(
                name=_require(item, "name"),
                enabled=item.get("enabled", True),
                rule_file=_require(item, "rule_file"),
                source_indices=item.get("source_indices", []),
                start_time=item.get("start_time"),
                query=item.get("query"),
            )
        )

    return AppConfig(
        elasticsearch=ElasticsearchConfig(
            hosts=_require(es_raw, "hosts"),
            username=es_raw.get("username"),
            password=es_raw.get("password"),
            api_key=es_raw.get("api_key"),
            verify_certs=es_raw.get("verify_certs", True),
            request_timeout_seconds=es_raw.get("request_timeout_seconds", 30),
        ),
        checkpoints=CheckpointConfig(**raw.get("checkpoints", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
        pipeline=PipelineConfig(
            batch_size=pipe_raw.get("batch_size", 500),
            poll_interval_seconds=pipe_raw.get("poll_interval_seconds", 10),
            timestamp_field=pipe_raw.get("timestamp_field", "@timestamp"),
            start_time=pipe_raw.get("start_time", "now-15m"),
            source_indices=pipe_raw.get("source_indices", []),
            target_suffix=pipe_raw.get("target_suffix", "-rca"),
            dead_letter_suffix=pipe_raw.get("dead_letter_suffix", "-rca-dead-letter"),
            retry_max_attempts=pipe_raw.get("retry_max_attempts", 4),
            retry_initial_backoff_seconds=pipe_raw.get("retry_initial_backoff_seconds", 1.0),
            retry_backoff_multiplier=pipe_raw.get("retry_backoff_multiplier", 2.0),
            signal_max_per_event=pipe_raw.get("signal_max_per_event", 2),
            signal_select_highest_only=pipe_raw.get("signal_select_highest_only", True),
            services=services,
        ),
        rules_directory=raw.get("rules_directory", "rules"),
    )
