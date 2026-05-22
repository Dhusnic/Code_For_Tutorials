from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass(frozen=True)
class AppConfig:
    default_organization_id: str
    max_hops: int
    default_thread_id: str


@dataclass(frozen=True)
class ElasticsearchConfig:
    hosts: tuple[str, ...]
    index: str
    username: str | None
    password: str | None
    api_key: str | None
    verify_certs: bool
    ca_certs: str | None
    request_timeout_seconds: int
    timestamp_field: str
    organization_field: str | None
    service_field: str
    host_field: str
    ip_field: str
    signal_field: str
    message_field: str
    severity_field: str
    vendor_field: str
    domain_field: str
    searchable_fields: tuple[str, ...]
    source_fields: tuple[str, ...]
    search_page_size: int
    max_records_per_query: int
    use_point_in_time: bool
    point_in_time_keep_alive: str


@dataclass(frozen=True)
class MongoConfig:
    uri: str
    database: str
    collection: str
    organization_field: str
    topology_field: str
    schema_version_field: str
    default_schema_version: int
    request_timeout_ms: int


@dataclass(frozen=True)
class OpenAIConfig:
    api_key_env: str
    model: str
    reasoning_effort: str
    text_verbosity: str
    max_output_tokens: int
    planner_enabled: bool
    planner_mode: str
    planner_max_output_tokens: int
    critic_enabled: bool
    critic_max_output_tokens: int
    scope_resolution_enabled: bool
    scope_resolution_max_output_tokens: int
    scope_resolution_confidence_threshold: float
    timeout_seconds: int
    instructions: str


@dataclass(frozen=True)
class RAGConfig:
    vector_enabled: bool
    vector_db_root: str
    semantic_top_k: int
    global_scope_fanout: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    logger_name: str
    log_inputs: bool
    log_outputs: bool
    payload_preview_chars: int


@dataclass(frozen=True)
class RuntimeConfig:
    app: AppConfig
    elasticsearch: ElasticsearchConfig
    mongo: MongoConfig
    openai: OpenAIConfig
    rag: RAGConfig
    logging: LoggingConfig


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        os.environ.setdefault(key, value)


def load_runtime_config(config_path: Path, env_path: Path | None = None) -> RuntimeConfig:
    if env_path is not None:
        load_env_file(env_path)

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    payload = _resolve_env_placeholders(payload)

    app = payload.get("app", {})
    elasticsearch = payload.get("elasticsearch", {})
    mongo = payload.get("mongo", {})
    openai = payload.get("openai", {})
    rag = payload.get("rag", {})
    logging = payload.get("logging", {})

    return RuntimeConfig(
        app=AppConfig(
            default_organization_id=str(app.get("default_organization_id", "demo-org")),
            max_hops=int(app.get("max_hops", 4)),
            default_thread_id=str(app.get("default_thread_id", "cli-thread")),
        ),
        elasticsearch=ElasticsearchConfig(
            hosts=tuple(str(item) for item in elasticsearch.get("hosts", ["http://localhost:9200"])),
            index=str(elasticsearch.get("index", "signalized-logs-*")),
            username=_optional_string(elasticsearch.get("username")),
            password=_optional_string(elasticsearch.get("password")),
            api_key=_optional_string(elasticsearch.get("api_key")),
            verify_certs=bool(elasticsearch.get("verify_certs", False)),
            ca_certs=_optional_string(elasticsearch.get("ca_certs")),
            request_timeout_seconds=int(elasticsearch.get("request_timeout_seconds", 30)),
            timestamp_field=str(elasticsearch.get("timestamp_field", "@timestamp")),
            organization_field=_optional_string(elasticsearch.get("organization_field")),
            service_field=str(elasticsearch.get("service_field", "service")),
            host_field=str(elasticsearch.get("host_field", "host")),
            ip_field=str(elasticsearch.get("ip_field", "ip")),
            signal_field=str(elasticsearch.get("signal_field", "signal")),
            message_field=str(elasticsearch.get("message_field", "message")),
            severity_field=str(elasticsearch.get("severity_field", "severity")),
            vendor_field=str(elasticsearch.get("vendor_field", "vendor")),
            domain_field=str(elasticsearch.get("domain_field", "domain")),
            searchable_fields=tuple(str(item) for item in elasticsearch.get("searchable_fields", [])),
            source_fields=tuple(str(item) for item in elasticsearch.get("source_fields", [])),
            search_page_size=int(elasticsearch.get("search_page_size", 250)),
            max_records_per_query=int(elasticsearch.get("max_records_per_query", 1000)),
            use_point_in_time=bool(elasticsearch.get("use_point_in_time", True)),
            point_in_time_keep_alive=str(elasticsearch.get("point_in_time_keep_alive", "2m")),
        ),
        mongo=MongoConfig(
            uri=str(mongo.get("uri", "mongodb://localhost:27017")),
            database=str(mongo.get("database", "rca")),
            collection=str(mongo.get("collection", "topology")),
            organization_field=str(mongo.get("organization_field", "organization_id")),
            topology_field=str(mongo.get("topology_field", "topology")),
            schema_version_field=str(mongo.get("schema_version_field", "schema_version")),
            default_schema_version=int(mongo.get("default_schema_version", 1)),
            request_timeout_ms=int(mongo.get("request_timeout_ms", 5000)),
        ),
        openai=OpenAIConfig(
            api_key_env=str(openai.get("api_key_env", "OPENAI_API_KEY")),
            model=str(openai.get("model", "gpt-4o-mini")),
            reasoning_effort=str(openai.get("reasoning_effort", "medium")),
            text_verbosity=str(openai.get("text_verbosity", "low")),
            max_output_tokens=int(openai.get("max_output_tokens", 800)),
            planner_enabled=bool(openai.get("planner_enabled", True)),
            planner_mode=str(openai.get("planner_mode", "hybrid")),
            planner_max_output_tokens=int(openai.get("planner_max_output_tokens", 260)),
            critic_enabled=bool(openai.get("critic_enabled", True)),
            critic_max_output_tokens=int(openai.get("critic_max_output_tokens", 260)),
            scope_resolution_enabled=bool(openai.get("scope_resolution_enabled", True)),
            scope_resolution_max_output_tokens=int(openai.get("scope_resolution_max_output_tokens", 220)),
            scope_resolution_confidence_threshold=float(openai.get("scope_resolution_confidence_threshold", 0.6)),
            timeout_seconds=int(openai.get("timeout_seconds", 60)),
            instructions=str(openai.get("instructions", "")),
        ),
        rag=RAGConfig(
            vector_enabled=bool(rag.get("vector_enabled", True)),
            vector_db_root=str(rag.get("vector_db_root", "rag_db")),
            semantic_top_k=int(rag.get("semantic_top_k", 8)),
            global_scope_fanout=int(rag.get("global_scope_fanout", 6)),
        ),
        logging=LoggingConfig(
            level=str(logging.get("level", "INFO")).upper(),
            logger_name=str(logging.get("logger_name", "logs_only_investigator")),
            log_inputs=bool(logging.get("log_inputs", True)),
            log_outputs=bool(logging.get("log_outputs", True)),
            payload_preview_chars=int(logging.get("payload_preview_chars", 1200)),
        ),
    )


def require_openai_api_key(config: OpenAIConfig) -> str:
    api_key = os.environ.get(config.api_key_env, "").strip()
    if not api_key:
        raise ValueError(
            f"Missing OpenAI API key. Set {config.api_key_env} in the environment or in the loaded .env file."
        )
    return api_key


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_env_value(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
