"""Application configuration models and loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
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

    provider: str = "file"
    path: str = "state/checkpoints.json"
    redis_url: str | None = None
    redis_prefix: str = "rca:checkpoint:"
    postgres_dsn: str | None = None
    postgres_table: str = "rca_checkpoints"
    elasticsearch_index: str = "rca-checkpoints"


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

    batch_size: int = 2000
    bulk_max_batch_bytes: int = 8 * 1024 * 1024
    worker_count: int = 1
    worker_id: int = 0
    bulk_worker_count: int = 4
    bulk_queue_size: int = 32
    bulk_queue_enqueue_timeout_seconds: float = 0.25
    bulk_spool_enabled: bool = False
    bulk_spool_directory: str = "state/bulk_spool"
    bulk_spool_max_bytes: int = 10 * 1024 * 1024 * 1024
    bulk_spool_replay_interval_seconds: float = 1.0
    bulk_autoscaling_enabled: bool = False
    bulk_autoscaling_min_workers: int = 2
    bulk_autoscaling_max_workers: int = 16
    bulk_autoscaling_scale_up_queue_ratio: float = 0.75
    bulk_autoscaling_scale_down_queue_ratio: float = 0.25
    bulk_autoscaling_cpu_limit_percent: float = 85.0
    bulk_autoscaling_memory_limit_percent: float = 85.0
    bulk_autoscaling_check_interval_seconds: float = 2.0
    bulk_autoscaling_cooldown_seconds: float = 10.0
    batch_size_mode: str = "static"
    dynamic_batch_min_size: int = 500
    dynamic_batch_max_size: int = 10000
    dynamic_batch_lookback_seconds: int = 30
    dynamic_batch_target_window_seconds: float = 1.0
    dynamic_batch_smoothing_alpha: float = 0.5
    autoscaling_enabled: bool = True
    autoscaling_target_events_per_worker_sec: float = 1500.0
    autoscaling_min_workers: int = 1
    autoscaling_max_workers: int = 64
    autoscaling_lag_scale_up_seconds: float = 60.0
    autoscaling_lag_scale_down_seconds: float = 10.0
    poll_interval_seconds: int = 10
    timestamp_field: str = "@timestamp"
    start_time: str = "now-15m"
    source_indices: list[str] = field(default_factory=list)
    write_to_source_index: bool = False
    write_to_target_index: bool = True
    target_suffix: str = "-rca"
    dead_letter_suffix: str = "-rca-dead-letter"
    retry_max_attempts: int = 4
    retry_initial_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    signal_max_per_event: int = 2
    signal_select_highest_only: bool = True
    services: list[ServiceConfig] = field(default_factory=list)


@dataclass(slots=True)
class RuleLearningConfig:
    """Auto-generation settings for unclassified critical signals."""

    enabled: bool = False
    mode: str = "suggest"
    output_directory: str = "rules/suggestions"
    min_occurrences: int = 10
    max_candidates_per_service: int = 20
    min_keyword_count: int = 2
    max_keywords_per_signal: int = 4
    condition_field: str = "message"
    condition_op: str = "contains"
    level: str = "critical"


@dataclass(slots=True)
class AppConfig:
    """Root application configuration."""

    elasticsearch: ElasticsearchConfig
    checkpoints: CheckpointConfig
    logging: LoggingConfig
    pipeline: PipelineConfig
    rules_directory: str = "rules"
    rule_learning: RuleLearningConfig = field(default_factory=RuleLearningConfig)


_SIZE_UNITS: dict[str, int] = {
    "b": 1,
    "kb": 1024,
    "mb": 1024 * 1024,
    "gb": 1024 * 1024 * 1024,
    "tb": 1024 * 1024 * 1024 * 1024,
}
_DURATION_UNITS_SECONDS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}
_SIZE_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(b|kb|mb|gb|tb)\s*$", re.IGNORECASE)
_DURATION_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)\s*$", re.IGNORECASE)


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required configuration key: {key}")
    return data[key]


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    """Return a mapping value or raise a configuration error."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _coerce_size_bytes(value: Any, key_name: str) -> int:
    """Parse bytes from numeric values or strings like 8MB/10GB."""
    if isinstance(value, bool):
        raise ValueError(f"{key_name} must be a size, not boolean")

    number: float
    unit: str
    if isinstance(value, (int, float)):
        number = float(value)
        unit = "b"
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{key_name} cannot be empty")
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            number = float(text)
            unit = "b"
        else:
            match = _SIZE_PATTERN.fullmatch(text)
            if not match:
                raise ValueError(
                    f"{key_name} must be numeric bytes or unit value like '8MB', got: {value!r}"
                )
            number = float(match.group(1))
            unit = match.group(2).lower()
    else:
        raise ValueError(f"{key_name} has unsupported type: {type(value).__name__}")

    result = int(number * _SIZE_UNITS[unit])
    if result < 1:
        raise ValueError(f"{key_name} must be at least 1 byte")
    return result


def _coerce_seconds_float(value: Any, key_name: str) -> float:
    """Parse duration to seconds from numeric values or strings like 250ms/10s/2m."""
    if isinstance(value, bool):
        raise ValueError(f"{key_name} must be a duration, not boolean")

    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{key_name} cannot be empty")
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            seconds = float(text)
        else:
            match = _DURATION_PATTERN.fullmatch(text)
            if not match:
                raise ValueError(
                    f"{key_name} must be numeric seconds or duration value like '10s', got: {value!r}"
                )
            number = float(match.group(1))
            unit = match.group(2).lower()
            seconds = number * _DURATION_UNITS_SECONDS[unit]
    else:
        raise ValueError(f"{key_name} has unsupported type: {type(value).__name__}")

    if seconds < 0:
        raise ValueError(f"{key_name} must be >= 0 seconds")
    return seconds


def _coerce_seconds_int(value: Any, key_name: str, minimum: int = 1) -> int:
    """Parse integer seconds from duration values, rounding sub-second up."""
    seconds = _coerce_seconds_float(value, key_name)
    coerced = int(math.ceil(seconds))
    if coerced < minimum:
        raise ValueError(f"{key_name} must be >= {minimum} second(s)")
    return coerced


def load_app_config(path: str) -> AppConfig:
    """Load application config from YAML file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a mapping")

    es_raw = _require_mapping(_require(raw, "elasticsearch"), "elasticsearch")
    pipe_raw = _require_mapping(_require(raw, "pipeline"), "pipeline")
    rule_learning_raw = raw.get("rule_learning", {})
    if not isinstance(rule_learning_raw, dict):
        raise ValueError("rule_learning must be a mapping when provided")

    services: list[ServiceConfig] = []
    for item in pipe_raw.get("services", []):
        if not isinstance(item, dict):
            raise ValueError("pipeline.services entries must be mappings")
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
            request_timeout_seconds=_coerce_seconds_int(
                es_raw.get("request_timeout_seconds", 30),
                "elasticsearch.request_timeout_seconds",
            ),
        ),
        checkpoints=CheckpointConfig(**raw.get("checkpoints", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
        pipeline=PipelineConfig(
            batch_size=pipe_raw.get("batch_size", 2000),
            bulk_max_batch_bytes=_coerce_size_bytes(
                pipe_raw.get("bulk_max_batch_bytes", 8 * 1024 * 1024),
                "pipeline.bulk_max_batch_bytes",
            ),
            worker_count=pipe_raw.get("worker_count", 1),
            worker_id=pipe_raw.get("worker_id", 0),
            bulk_worker_count=pipe_raw.get("bulk_worker_count", 4),
            bulk_queue_size=pipe_raw.get("bulk_queue_size", 32),
            bulk_queue_enqueue_timeout_seconds=_coerce_seconds_float(
                pipe_raw.get("bulk_queue_enqueue_timeout_seconds", 0.25),
                "pipeline.bulk_queue_enqueue_timeout_seconds",
            ),
            bulk_spool_enabled=pipe_raw.get("bulk_spool_enabled", False),
            bulk_spool_directory=pipe_raw.get("bulk_spool_directory", "state/bulk_spool"),
            bulk_spool_max_bytes=_coerce_size_bytes(
                pipe_raw.get("bulk_spool_max_bytes", 10 * 1024 * 1024 * 1024),
                "pipeline.bulk_spool_max_bytes",
            ),
            bulk_spool_replay_interval_seconds=_coerce_seconds_float(
                pipe_raw.get("bulk_spool_replay_interval_seconds", 1.0),
                "pipeline.bulk_spool_replay_interval_seconds",
            ),
            bulk_autoscaling_enabled=pipe_raw.get("bulk_autoscaling_enabled", False),
            bulk_autoscaling_min_workers=pipe_raw.get("bulk_autoscaling_min_workers", 2),
            bulk_autoscaling_max_workers=pipe_raw.get("bulk_autoscaling_max_workers", 16),
            bulk_autoscaling_scale_up_queue_ratio=pipe_raw.get("bulk_autoscaling_scale_up_queue_ratio", 0.75),
            bulk_autoscaling_scale_down_queue_ratio=pipe_raw.get("bulk_autoscaling_scale_down_queue_ratio", 0.25),
            bulk_autoscaling_cpu_limit_percent=pipe_raw.get("bulk_autoscaling_cpu_limit_percent", 85.0),
            bulk_autoscaling_memory_limit_percent=pipe_raw.get("bulk_autoscaling_memory_limit_percent", 85.0),
            bulk_autoscaling_check_interval_seconds=_coerce_seconds_float(
                pipe_raw.get("bulk_autoscaling_check_interval_seconds", 2.0),
                "pipeline.bulk_autoscaling_check_interval_seconds",
            ),
            bulk_autoscaling_cooldown_seconds=_coerce_seconds_float(
                pipe_raw.get("bulk_autoscaling_cooldown_seconds", 10.0),
                "pipeline.bulk_autoscaling_cooldown_seconds",
            ),
            batch_size_mode=pipe_raw.get("batch_size_mode", "static"),
            dynamic_batch_min_size=pipe_raw.get("dynamic_batch_min_size", 500),
            dynamic_batch_max_size=pipe_raw.get("dynamic_batch_max_size", 10000),
            dynamic_batch_lookback_seconds=_coerce_seconds_int(
                pipe_raw.get("dynamic_batch_lookback_seconds", 30),
                "pipeline.dynamic_batch_lookback_seconds",
            ),
            dynamic_batch_target_window_seconds=_coerce_seconds_float(
                pipe_raw.get("dynamic_batch_target_window_seconds", 1.0),
                "pipeline.dynamic_batch_target_window_seconds",
            ),
            dynamic_batch_smoothing_alpha=pipe_raw.get("dynamic_batch_smoothing_alpha", 0.5),
            autoscaling_enabled=pipe_raw.get("autoscaling_enabled", True),
            autoscaling_target_events_per_worker_sec=pipe_raw.get(
                "autoscaling_target_events_per_worker_sec",
                1500.0,
            ),
            autoscaling_min_workers=pipe_raw.get("autoscaling_min_workers", 1),
            autoscaling_max_workers=pipe_raw.get("autoscaling_max_workers", 64),
            autoscaling_lag_scale_up_seconds=_coerce_seconds_float(
                pipe_raw.get("autoscaling_lag_scale_up_seconds", 60.0),
                "pipeline.autoscaling_lag_scale_up_seconds",
            ),
            autoscaling_lag_scale_down_seconds=_coerce_seconds_float(
                pipe_raw.get("autoscaling_lag_scale_down_seconds", 10.0),
                "pipeline.autoscaling_lag_scale_down_seconds",
            ),
            poll_interval_seconds=_coerce_seconds_int(
                pipe_raw.get("poll_interval_seconds", 10),
                "pipeline.poll_interval_seconds",
            ),
            timestamp_field=pipe_raw.get("timestamp_field", "@timestamp"),
            start_time=pipe_raw.get("start_time", "now-15m"),
            source_indices=pipe_raw.get("source_indices", []),
            write_to_source_index=pipe_raw.get("write_to_source_index", False),
            write_to_target_index=pipe_raw.get("write_to_target_index", True),
            target_suffix=pipe_raw.get("target_suffix", "-rca"),
            dead_letter_suffix=pipe_raw.get("dead_letter_suffix", "-rca-dead-letter"),
            retry_max_attempts=pipe_raw.get("retry_max_attempts", 4),
            retry_initial_backoff_seconds=_coerce_seconds_float(
                pipe_raw.get("retry_initial_backoff_seconds", 1.0),
                "pipeline.retry_initial_backoff_seconds",
            ),
            retry_backoff_multiplier=pipe_raw.get("retry_backoff_multiplier", 2.0),
            signal_max_per_event=pipe_raw.get("signal_max_per_event", 2),
            signal_select_highest_only=pipe_raw.get("signal_select_highest_only", True),
            services=services,
        ),
        rules_directory=raw.get("rules_directory", "rules"),
        rule_learning=RuleLearningConfig(
            enabled=rule_learning_raw.get("enabled", False),
            mode=rule_learning_raw.get("mode", "suggest"),
            output_directory=rule_learning_raw.get("output_directory", "rules/suggestions"),
            min_occurrences=rule_learning_raw.get("min_occurrences", 10),
            max_candidates_per_service=rule_learning_raw.get("max_candidates_per_service", 20),
            min_keyword_count=rule_learning_raw.get("min_keyword_count", 2),
            max_keywords_per_signal=rule_learning_raw.get("max_keywords_per_signal", 4),
            condition_field=rule_learning_raw.get("condition_field", "message"),
            condition_op=rule_learning_raw.get("condition_op", "contains"),
            level=rule_learning_raw.get("level", "critical"),
        ),
    )

