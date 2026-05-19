#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class WorkflowDetails:
    signalizing_input_source: str
    kafka_topic: str
    signalizing_checkpoint_provider: str
    signalizing_checkpoint_index: str
    signal_stream_enabled: bool
    signal_stream_key: str
    signal_stream_dedup_prefix: str
    correlation_input_mode: str
    correlation_current_index: str
    correlation_write_history_index: bool
    correlation_redis_prefix: str
    correlation_signal_stream_key: str
    rca_results_store: str
    notes: list[str] = field(default_factory=list)


@dataclass
class MongoCollectionUsage:
    name: str
    role: str
    count: int
    data_size: int
    storage_size: int
    index_size: int
    total_size: int
    indexes: int
    exists: bool


@dataclass
class MongoSummary:
    database: str
    collections: list[MongoCollectionUsage]


@dataclass
class ElasticsearchPattern:
    label: str
    pattern: str


@dataclass
class ElasticsearchIndexUsage:
    name: str
    docs_count: int
    store_size: int
    labels: list[str]


@dataclass
class ElasticsearchSummary:
    address: str
    patterns: list[ElasticsearchPattern]
    indices: list[ElasticsearchIndexUsage]


@dataclass
class RedisPatternBreakdown:
    pattern: str
    matched_keys: int


@dataclass
class RedisKeyUsage:
    key: str
    key_type: str
    memory_usage: int


@dataclass
class RedisSummary:
    address: str
    database: int
    patterns: list[str]
    pattern_breakdown: list[RedisPatternBreakdown]
    db_total_keys: int
    db_used_memory: int
    matched_keys: int
    matched_memory: int
    top_keys: list[RedisKeyUsage]
    connection_note: str = ""


@dataclass
class LocalFileUsage:
    path: Path
    exists: bool
    size: int
    roles: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_signalizing_config() -> Path:
    return repo_root() / "log_signalizing" / "config.yml"


def default_correlation_config() -> Path:
    return repo_root() / "log_correlation_engine" / "config" / "config.yml"


def default_rca_config() -> Path:
    return repo_root() / "log_rca_engine" / "config" / "config.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print a config-aware RCA space summary for the current three-engine workflow: "
            "signalizing -> Redis stream -> correlation -> RCA result persistence."
        )
    )
    parser.add_argument(
        "--signalizing-config",
        default=str(default_signalizing_config()),
        help="Path to log_signalizing config.yml.",
    )
    parser.add_argument(
        "--correlation-config",
        default=str(default_correlation_config()),
        help="Path to log_correlation_engine config/config.yml.",
    )
    parser.add_argument(
        "--rca-config",
        default=str(default_rca_config()),
        help="Path to log_rca_engine config/config.yml.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("RCA_MONGO_URI") or os.getenv("MONGO_URI") or "",
        help="Optional MongoDB URI override.",
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv("RCA_MONGO_DB") or "",
        help="Optional MongoDB database override.",
    )
    parser.add_argument(
        "--es-url",
        default=os.getenv("RCA_ES_URL") or "",
        help="Optional Elasticsearch URL override.",
    )
    parser.add_argument(
        "--es-username",
        default=os.getenv("RCA_ES_USERNAME") or "",
        help="Optional Elasticsearch username override.",
    )
    parser.add_argument(
        "--es-password",
        default=os.getenv("RCA_ES_PASSWORD") or "",
        help="Optional Elasticsearch password override.",
    )
    parser.add_argument(
        "--es-api-key",
        default=os.getenv("RCA_ES_API_KEY") or "",
        help="Optional Elasticsearch API key override.",
    )
    parser.add_argument(
        "--redis-host",
        default=os.getenv("RCA_REDIS_HOST") or "",
        help="Optional Redis host override.",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=int(os.getenv("RCA_REDIS_PORT") or "0"),
        help="Optional Redis port override.",
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        default=int(os.getenv("RCA_REDIS_DB") or "0"),
        help="Optional Redis DB override.",
    )
    parser.add_argument(
        "--redis-username",
        default=os.getenv("RCA_REDIS_USERNAME") or "",
        help="Optional Redis username override.",
    )
    parser.add_argument(
        "--redis-password",
        default=os.getenv("RCA_REDIS_PASSWORD") or "",
        help="Optional Redis password override.",
    )
    parser.add_argument(
        "--redis-pattern",
        action="append",
        default=[],
        help=(
            "Optional Redis key pattern override. Repeat this flag to add multiple patterns. "
            "When omitted, patterns are derived from the current workflow config."
        ),
    )
    parser.add_argument(
        "--top-redis-keys",
        type=int,
        default=10,
        help="Maximum Redis keys to show in the detailed table.",
    )
    parser.add_argument(
        "--redis-scan-count",
        type=int,
        default=200,
        help="Redis SCAN count hint used while walking RCA keys.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Network timeout for Elasticsearch and MongoDB calls.",
    )
    parser.add_argument(
        "--redis-timeout-seconds",
        type=float,
        default=45.0,
        help="Redis-specific timeout in seconds.",
    )
    parser.add_argument(
        "--no-mongo",
        action="store_true",
        help="Skip MongoDB summary.",
    )
    parser.add_argument(
        "--no-elasticsearch",
        action="store_true",
        help="Skip Elasticsearch summary.",
    )
    parser.add_argument(
        "--no-redis",
        action="store_true",
        help="Skip Redis summary.",
    )
    parser.add_argument(
        "--no-local-files",
        action="store_true",
        help="Skip local file mirror summary.",
    )
    return parser.parse_args()


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_sectioned_yaml_fallback(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    data: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None
    current_subsection: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            data[current_section] = {}
            current_list_key = None
            current_subsection = None
            continue

        if current_section is None:
            continue

        section = data[current_section]
        if indent == 2 and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value == "":
                section[key] = {}
                current_subsection = key
                current_list_key = None
            else:
                section[key] = parse_scalar(raw_value)
                current_subsection = None
                current_list_key = None
            continue

        if indent == 4 and stripped.endswith(":") and current_subsection:
            subsection = section.get(current_subsection)
            if isinstance(subsection, dict):
                subsection[stripped[:-1]] = []
                current_list_key = stripped[:-1]
            continue

        if indent == 4 and current_subsection and ":" in stripped:
            subsection = section.get(current_subsection)
            if isinstance(subsection, dict):
                key, raw_value = stripped.split(":", 1)
                subsection[key.strip()] = parse_scalar(raw_value)
            continue

        if indent >= 6 and stripped.startswith("- ") and current_subsection and current_list_key:
            subsection = section.get(current_subsection)
            if isinstance(subsection, dict):
                values = subsection.get(current_list_key)
                if isinstance(values, list):
                    values.append(parse_scalar(stripped[2:]))

    return data


def load_yaml_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is not None:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    return load_sectioned_yaml_fallback(path)


def normalize_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def parse_intish(value: Any) -> int:
    text = str(value or "").strip()
    if not text or text == "-":
        return 0
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return 0


def format_bytes(num_bytes: int) -> str:
    value = float(max(num_bytes, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TB"


def format_int(value: int) -> str:
    return f"{int(value):,}"


def shorten(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render_row(values: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    separator = "  ".join("-" * width for width in widths)
    lines = [render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def resolve_config_relative_path(config_path: Path, raw_value: Any) -> Path | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (config_path.parent / candidate).resolve()


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        result.append(trimmed)
    return result


def load_workflow_details(
    signalizing_config_path: Path,
    correlation_config_path: Path,
    rca_config_path: Path,
) -> tuple[WorkflowDetails, dict[str, Any], dict[str, Any], dict[str, Any]]:
    signalizing_cfg = load_yaml_document(signalizing_config_path)
    correlation_cfg = load_yaml_document(correlation_config_path)
    rca_cfg = load_yaml_document(rca_config_path)

    signalizing_input = signalizing_cfg.get("input") if isinstance(signalizing_cfg.get("input"), dict) else {}
    signalizing_kafka = signalizing_cfg.get("kafka") if isinstance(signalizing_cfg.get("kafka"), dict) else {}
    signal_stream = signalizing_cfg.get("signal_stream") if isinstance(signalizing_cfg.get("signal_stream"), dict) else {}
    checkpoints = signalizing_cfg.get("checkpoints") if isinstance(signalizing_cfg.get("checkpoints"), dict) else {}

    correlation_engine = correlation_cfg.get("engine") if isinstance(correlation_cfg.get("engine"), dict) else {}
    correlation_es = correlation_cfg.get("elasticsearch") if isinstance(correlation_cfg.get("elasticsearch"), dict) else {}
    correlation_redis = correlation_cfg.get("redis") if isinstance(correlation_cfg.get("redis"), dict) else {}

    rca_mongo = rca_cfg.get("mongo_sync") if isinstance(rca_cfg.get("mongo_sync"), dict) else {}
    rca_storage = rca_cfg.get("storage") if isinstance(rca_cfg.get("storage"), dict) else {}

    results_store_parts: list[str] = []
    mongo_db = str(rca_mongo.get("database") or "").strip()
    mongo_collection = str(rca_mongo.get("results_collection") or "").strip()
    if mongo_db and mongo_collection:
        results_store_parts.append(f"MongoDB {mongo_db}.{mongo_collection}")
    elif mongo_collection:
        results_store_parts.append(f"MongoDB collection {mongo_collection}")
    results_file = str(rca_storage.get("results_file") or "").strip()
    if results_file:
        results_store_parts.append(f"file mirror {results_file}")

    notes: list[str] = []
    if bool_value(signal_stream.get("enabled")):
        notes.append(
            "Signalizing publishes compact signal events into Redis streams and correlation reads from Redis-stream mode."
        )
    if str(signalizing_input.get("source") or "").strip().lower() == "kafka":
        notes.append("Signalizing source ingestion is Kafka-based, so source_indices/start_time do not drive the hot path.")
    if bool_value(correlation_es.get("write_history_index")):
        notes.append("Correlation history-index writes are enabled.")
    else:
        notes.append("Correlation keeps only the live current incident view in Elasticsearch.")
    if str(checkpoints.get("provider") or "").strip().lower() == "elasticsearch":
        notes.append("Signalizing checkpoints are stored in Elasticsearch, so checkpoint index size is part of the live footprint.")
    if str(rca_storage.get("results_file") or "").strip():
        notes.append("RCA also keeps local file mirrors/checkpoints in addition to MongoDB.")

    workflow = WorkflowDetails(
        signalizing_input_source=str(signalizing_input.get("source") or "unknown").strip() or "unknown",
        kafka_topic=str(signalizing_kafka.get("topic") or "").strip(),
        signalizing_checkpoint_provider=str(checkpoints.get("provider") or "").strip() or "unknown",
        signalizing_checkpoint_index=str(checkpoints.get("elasticsearch_index") or "").strip(),
        signal_stream_enabled=bool_value(signal_stream.get("enabled")),
        signal_stream_key=str(signal_stream.get("stream_key") or "").strip(),
        signal_stream_dedup_prefix=str(signal_stream.get("publish_dedup_key_prefix") or "").strip(),
        correlation_input_mode=str(correlation_engine.get("input_mode") or "").strip() or "unknown",
        correlation_current_index=str(correlation_es.get("current_index") or "").strip(),
        correlation_write_history_index=bool_value(correlation_es.get("write_history_index")),
        correlation_redis_prefix=str(correlation_redis.get("key_prefix") or "").strip() or "Rca",
        correlation_signal_stream_key=str(correlation_redis.get("signal_stream_key") or "").strip(),
        rca_results_store=", ".join(results_store_parts) if results_store_parts else "MongoDB / local file mirrors",
        notes=notes,
    )
    return workflow, signalizing_cfg, correlation_cfg, rca_cfg


def resolve_mongo_settings(args: argparse.Namespace, rca_cfg: dict[str, Any]) -> dict[str, Any]:
    mongo = rca_cfg.get("mongo_sync") if isinstance(rca_cfg.get("mongo_sync"), dict) else {}
    collection_roles: list[tuple[str, str]] = []
    mapping = [
        ("rules_collection", "Correlation rules"),
        ("topology_collection", "Topology data"),
        ("results_collection", "RCA results"),
        ("state_collection", "RCA config state"),
        ("snapshot_collection", "RCA config snapshots"),
    ]
    for key, role in mapping:
        name = str(mongo.get(key) or "").strip()
        if name:
            collection_roles.append((name, role))
    return {
        "enabled": bool_value(mongo.get("enabled", True)),
        "uri": str(args.mongo_uri or mongo.get("uri") or "").strip(),
        "database": str(args.mongo_db or mongo.get("database") or "").strip(),
        "collection_roles": collection_roles,
    }


def collect_signalizing_source_patterns(signalizing_cfg: dict[str, Any]) -> list[str]:
    pipeline = signalizing_cfg.get("pipeline") if isinstance(signalizing_cfg.get("pipeline"), dict) else {}
    patterns: list[str] = []

    for value in ensure_list(pipeline.get("source_indices")):
        text = str(value or "").strip()
        if text:
            patterns.append(text)

    services = pipeline.get("services")
    if isinstance(services, list):
        for service in services:
            if not isinstance(service, dict):
                continue
            for value in ensure_list(service.get("source_indices")):
                text = str(value or "").strip()
                if text:
                    patterns.append(text)

    normalized: list[str] = []
    for pattern in dedupe_strings(patterns):
        if pattern in {"*", "_all"}:
            continue
        normalized.append(pattern)
    return normalized


def derive_suffix_index_patterns(signalizing_cfg: dict[str, Any], suffix: str) -> list[str]:
    suffix = str(suffix or "").strip()
    if not suffix:
        return []
    patterns: list[str] = []
    for source_pattern in collect_signalizing_source_patterns(signalizing_cfg):
        if source_pattern.endswith(suffix):
            patterns.append(source_pattern)
        else:
            patterns.append(f"{source_pattern}{suffix}")
    return dedupe_strings(patterns)


def resolve_elasticsearch_settings(
    args: argparse.Namespace,
    workflow: WorkflowDetails,
    signalizing_cfg: dict[str, Any],
    correlation_cfg: dict[str, Any],
    rca_cfg: dict[str, Any],
) -> dict[str, Any]:
    signalizing_es = signalizing_cfg.get("elasticsearch") if isinstance(signalizing_cfg.get("elasticsearch"), dict) else {}
    correlation_es = correlation_cfg.get("elasticsearch") if isinstance(correlation_cfg.get("elasticsearch"), dict) else {}
    rca_es = rca_cfg.get("elasticsearch") if isinstance(rca_cfg.get("elasticsearch"), dict) else {}
    signalizing_pipeline = signalizing_cfg.get("pipeline") if isinstance(signalizing_cfg.get("pipeline"), dict) else {}

    addresses: list[str] = []
    for candidate in (
        correlation_es.get("addresses"),
        signalizing_es.get("addresses"),
        signalizing_es.get("hosts"),
        rca_es.get("addresses"),
        rca_es.get("hosts"),
    ):
        if isinstance(candidate, list):
            addresses.extend(str(value).strip() for value in candidate if str(value).strip())
    address = str(args.es_url or (addresses[0] if addresses else "")).strip()

    patterns: list[ElasticsearchPattern] = []
    if workflow.signalizing_checkpoint_provider.lower() == "elasticsearch" and workflow.signalizing_checkpoint_index:
        patterns.append(
            ElasticsearchPattern("Signalizing checkpoints", workflow.signalizing_checkpoint_index)
        )
    if workflow.correlation_current_index:
        patterns.append(
            ElasticsearchPattern("Correlation current incidents", workflow.correlation_current_index)
        )

    if bool_value(signalizing_pipeline.get("write_to_target_index")):
        target_suffix = str(signalizing_pipeline.get("target_suffix") or "").strip()
        for pattern in derive_suffix_index_patterns(signalizing_cfg, target_suffix):
            patterns.append(ElasticsearchPattern("Signalizing target copies", pattern))

    dead_letter_suffix = str(signalizing_pipeline.get("dead_letter_suffix") or "").strip()
    for pattern in derive_suffix_index_patterns(signalizing_cfg, dead_letter_suffix):
        patterns.append(ElasticsearchPattern("Signalizing dead-letter", pattern))

    deduped_patterns: list[ElasticsearchPattern] = []
    seen_patterns: set[tuple[str, str]] = set()
    for item in patterns:
        key = (item.label, item.pattern)
        if item.pattern and key not in seen_patterns:
            seen_patterns.add(key)
            deduped_patterns.append(item)

    return {
        "address": address,
        "username": str(
            args.es_username
            or correlation_es.get("username")
            or signalizing_es.get("username")
            or rca_es.get("username")
            or ""
        ).strip(),
        "password": str(
            args.es_password
            or correlation_es.get("password")
            or signalizing_es.get("password")
            or rca_es.get("password")
            or ""
        ).strip(),
        "api_key": str(
            args.es_api_key
            or correlation_es.get("api_key")
            or signalizing_es.get("api_key")
            or rca_es.get("api_key")
            or ""
        ).strip(),
        "patterns": deduped_patterns,
        "timeout_seconds": max(float(args.timeout_seconds), 0.1),
    }


def resolve_redis_settings(
    args: argparse.Namespace,
    workflow: WorkflowDetails,
    signalizing_cfg: dict[str, Any],
    correlation_cfg: dict[str, Any],
) -> dict[str, Any]:
    signal_stream = signalizing_cfg.get("signal_stream") if isinstance(signalizing_cfg.get("signal_stream"), dict) else {}
    correlation_redis = correlation_cfg.get("redis") if isinstance(correlation_cfg.get("redis"), dict) else {}

    configured_address = str(correlation_redis.get("address") or signal_stream.get("address") or "").strip()
    host = str(args.redis_host or "").strip()
    port = int(args.redis_port or 0)
    if not host and configured_address:
        if ":" in configured_address:
            host, raw_port = configured_address.rsplit(":", 1)
            if not port:
                try:
                    port = int(raw_port)
                except ValueError:
                    port = 6379
        else:
            host = configured_address
    if not port:
        port = 6379

    patterns = [str(value).strip() for value in args.redis_pattern if str(value).strip()]
    if not patterns:
        key_prefix = workflow.correlation_redis_prefix or "Rca"
        patterns.append(f"{key_prefix}*")
        if workflow.signal_stream_key:
            patterns.append(f"{workflow.signal_stream_key}*")
        dedup_prefix = workflow.signal_stream_dedup_prefix
        if dedup_prefix:
            patterns.append(f"{dedup_prefix}*")
    patterns = dedupe_strings(patterns)

    return {
        "host": host,
        "port": port,
        "db": int(args.redis_db if args.redis_db else correlation_redis.get("db") or signal_stream.get("db") or 0),
        "username": str(args.redis_username or correlation_redis.get("username") or signal_stream.get("username") or "").strip(),
        "password": str(args.redis_password or correlation_redis.get("password") or signal_stream.get("password") or "").strip(),
        "patterns": patterns,
        "timeout_seconds": max(float(args.redis_timeout_seconds), 0.1),
        "scan_count": max(int(args.redis_scan_count), 1),
    }


def resolve_local_file_settings(
    signalizing_config_path: Path,
    correlation_config_path: Path,
    rca_config_path: Path,
    signalizing_cfg: dict[str, Any],
    correlation_cfg: dict[str, Any],
    rca_cfg: dict[str, Any],
) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    correlation_root = correlation_config_path.parent.parent.resolve()

    checkpoints = signalizing_cfg.get("checkpoints") if isinstance(signalizing_cfg.get("checkpoints"), dict) else {}
    if str(checkpoints.get("provider") or "").strip().lower() == "file":
        checkpoint_path = resolve_config_relative_path(signalizing_config_path, checkpoints.get("path"))
        if checkpoint_path is not None:
            files.append((checkpoint_path, "Signalizing file checkpoints"))

    correlation_engine = correlation_cfg.get("engine") if isinstance(correlation_cfg.get("engine"), dict) else {}
    raw_rules_file = str(correlation_engine.get("rules_file") or "").strip()
    rules_file: Path | None = None
    if raw_rules_file:
        candidate = Path(raw_rules_file)
        rules_file = candidate if candidate.is_absolute() else (correlation_root / candidate).resolve()
    if rules_file is not None:
        files.append((rules_file, "Correlation local rules mirror"))

    rca_rules = rca_cfg.get("rules") if isinstance(rca_cfg.get("rules"), dict) else {}
    rca_topology = rca_cfg.get("topology") if isinstance(rca_cfg.get("topology"), dict) else {}
    rca_storage = rca_cfg.get("storage") if isinstance(rca_cfg.get("storage"), dict) else {}

    for raw_value, role in [
        (rca_rules.get("file"), "RCA rules input"),
        (rca_topology.get("file"), "RCA topology mirror"),
        (rca_storage.get("results_file"), "RCA local results mirror"),
        (rca_storage.get("checkpoint_file"), "RCA local checkpoint file"),
    ]:
        path = resolve_config_relative_path(rca_config_path, raw_value)
        if path is not None:
            files.append((path, role))

    return files


def fetch_mongo_summary(settings: dict[str, Any]) -> MongoSummary:
    if not settings.get("enabled", True):
        raise RuntimeError("MongoDB sync is disabled in RCA config.")

    mongosh_path = shutil.which("mongosh")
    if not mongosh_path:
        raise RuntimeError("mongosh command not found in PATH.")

    uri = str(settings.get("uri") or "").strip()
    database = str(settings.get("database") or "").strip()
    collection_roles = list(settings.get("collection_roles") or [])
    if not uri:
        raise RuntimeError("MongoDB URI is missing.")
    if not database:
        raise RuntimeError("MongoDB database name is missing.")
    if not collection_roles:
        raise RuntimeError("No MongoDB RCA collections were configured.")

    names = [name for name, _ in collection_roles]
    roles = {name: role for name, role in collection_roles}
    query = (
        f"const dbName = {json.dumps(database)};"
        f"const collNames = {json.dumps(names)};"
        "const targetDb = db.getSiblingDB(dbName);"
        "const collStats = collNames.map((name) => {"
        "  const exists = targetDb.getCollectionInfos({name}).length > 0;"
        "  if (!exists) {"
        "    return {name, exists:false, count:0, size:0, storageSize:0, totalIndexSize:0, nindexes:0};"
        "  }"
        "  const stats = targetDb.getCollection(name).stats();"
        "  return {"
        "    name,"
        "    exists:true,"
        "    count:Number(stats.count || 0),"
        "    size:Number(stats.size || 0),"
        "    storageSize:Number(stats.storageSize || 0),"
        "    totalIndexSize:Number(stats.totalIndexSize || 0),"
        "    nindexes:Number(stats.nindexes || 0)"
        "  };"
        "});"
        "print(JSON.stringify({database: dbName, collections: collStats}));"
    )

    result = subprocess.run(
        [mongosh_path, uri, "--quiet", "--eval", query],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(stderr or "mongosh query failed")

    stdout = (result.stdout or "").strip()
    if not stdout:
        raise RuntimeError("mongosh returned an empty response")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"mongosh returned invalid JSON: {exc}") from exc

    collections: list[MongoCollectionUsage] = []
    for item in payload.get("collections", []):
        name = normalize_text(item.get("name"), "")
        if not name:
            continue
        storage_size = int(item.get("storageSize") or 0)
        index_size = int(item.get("totalIndexSize") or 0)
        collections.append(
            MongoCollectionUsage(
                name=name,
                role=roles.get(name, "Configured collection"),
                count=int(item.get("count") or 0),
                data_size=int(item.get("size") or 0),
                storage_size=storage_size,
                index_size=index_size,
                total_size=storage_size + index_size,
                indexes=int(item.get("nindexes") or 0),
                exists=bool(item.get("exists", True)),
            )
        )

    collections.sort(key=lambda item: item.total_size, reverse=True)
    return MongoSummary(
        database=normalize_text(payload.get("database")),
        collections=collections,
    )


class ElasticsearchHttpClient:
    def __init__(self, address: str, username: str, password: str, api_key: str, timeout_seconds: float) -> None:
        self.address = address.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username or self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def request_json(self, method: str, path: str) -> Any:
        req = request.Request(self.address + path, method=method.upper(), headers=self._headers())
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Elasticsearch request failed ({exc.code} {exc.reason}): {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Elasticsearch at {self.address}: {exc}") from exc
        return json.loads(body) if body else {}


def fetch_elasticsearch_summary(settings: dict[str, Any]) -> ElasticsearchSummary:
    address = str(settings.get("address") or "").strip()
    patterns = list(settings.get("patterns") or [])
    if not address:
        raise RuntimeError("Elasticsearch address is missing.")
    if not patterns:
        raise RuntimeError("No RCA Elasticsearch index patterns were derived from config.")

    client = ElasticsearchHttpClient(
        address=address,
        username=str(settings.get("username") or ""),
        password=str(settings.get("password") or ""),
        api_key=str(settings.get("api_key") or ""),
        timeout_seconds=float(settings.get("timeout_seconds") or 20.0),
    )

    seen: dict[str, ElasticsearchIndexUsage] = {}
    for pattern in patterns:
        if not isinstance(pattern, ElasticsearchPattern) or not pattern.pattern:
            continue
        encoded_pattern = parse.quote(pattern.pattern, safe="*,-,_")
        payload = client.request_json(
            "GET",
            f"/_cat/indices/{encoded_pattern}?format=json&bytes=b&h=index,docs.count,store.size",
        )
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = normalize_text(item.get("index"), "")
            if not name:
                continue
            existing = seen.get(name)
            if existing is None:
                seen[name] = ElasticsearchIndexUsage(
                    name=name,
                    docs_count=parse_intish(item.get("docs.count")),
                    store_size=parse_intish(item.get("store.size")),
                    labels=[pattern.label],
                )
            elif pattern.label not in existing.labels:
                existing.labels.append(pattern.label)

    indices = sorted(seen.values(), key=lambda item: item.store_size, reverse=True)
    return ElasticsearchSummary(address=address, patterns=patterns, indices=indices)


class RedisRespClient:
    def __init__(
        self,
        host: str,
        port: int,
        db: int,
        username: str,
        password: str,
        timeout_seconds: float,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds
        self.sock: socket.socket | None = None
        self.file = None
        self.connection_note = ""

    @staticmethod
    def _is_optional_auth_error(message: str) -> bool:
        normalized = message.lower()
        return (
            "without any password configured for the default user" in normalized
            or "authentication not required" in normalized
        )

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
        self.file = self.sock.makefile("rb")
        if self.password:
            try:
                if self.username:
                    self.command("AUTH", self.username, self.password)
                else:
                    self.command("AUTH", self.password)
            except RuntimeError as exc:
                if self._is_optional_auth_error(str(exc)):
                    self.connection_note = (
                        "Redis accepted an unauthenticated connection, so the configured AUTH step was skipped."
                    )
                else:
                    raise
        if self.db:
            self.command("SELECT", str(self.db))

    def close(self) -> None:
        try:
            if self.file is not None:
                self.file.close()
        finally:
            self.file = None
            if self.sock is not None:
                self.sock.close()
                self.sock = None

    def _write(self, *parts: str) -> None:
        if self.sock is None:
            raise RuntimeError("Redis socket is not connected")
        payload = f"*{len(parts)}\r\n".encode("utf-8")
        for part in parts:
            encoded = str(part).encode("utf-8")
            payload += f"${len(encoded)}\r\n".encode("utf-8") + encoded + b"\r\n"
        self.sock.sendall(payload)

    def _read_line(self) -> bytes:
        if self.file is None:
            raise RuntimeError("Redis file handle is not connected")
        try:
            line = self.file.readline()
        except TimeoutError as exc:
            raise RuntimeError("Redis read timed out") from exc
        if not line:
            raise RuntimeError("Redis connection closed unexpectedly")
        return line.rstrip(b"\r\n")

    def _read_response(self) -> Any:
        prefix = self._read_line()
        token = prefix[:1]
        payload = prefix[1:]
        if token == b"+":
            return payload.decode("utf-8", errors="replace")
        if token == b"-":
            raise RuntimeError(payload.decode("utf-8", errors="replace"))
        if token == b":":
            return int(payload)
        if token == b"$":
            length = int(payload)
            if length < 0:
                return None
            if self.file is None:
                raise RuntimeError("Redis file handle is not connected")
            data = self.file.read(length)
            self.file.read(2)
            return data.decode("utf-8", errors="replace")
        if token == b"*":
            count = int(payload)
            if count < 0:
                return None
            return [self._read_response() for _ in range(count)]
        raise RuntimeError(f"Unsupported Redis response prefix: {token!r}")

    def command(self, *parts: str) -> Any:
        self._write(*parts)
        return self._read_response()


def fetch_redis_summary(settings: dict[str, Any], top_limit: int) -> RedisSummary:
    host = str(settings.get("host") or "").strip()
    port = int(settings.get("port") or 0)
    patterns = [str(value).strip() for value in settings.get("patterns") or [] if str(value).strip()]
    if not host or not port:
        raise RuntimeError("Redis host/port is missing.")
    if not patterns:
        raise RuntimeError("No Redis RCA key patterns were derived from config.")

    client = RedisRespClient(
        host=host,
        port=port,
        db=int(settings.get("db") or 0),
        username=str(settings.get("username") or ""),
        password=str(settings.get("password") or ""),
        timeout_seconds=float(settings.get("timeout_seconds") or 20.0),
    )

    scan_count = max(int(settings.get("scan_count") or 200), 1)
    notes: list[str] = []
    try:
        client.connect()

        db_used_memory = 0
        db_total_keys = 0
        memory_info_raw = str(client.command("INFO", "memory") or "")
        for line in memory_info_raw.splitlines():
            if line.startswith("used_memory:"):
                db_used_memory = parse_intish(line.split(":", 1)[1])
                break
        db_total_keys = int(client.command("DBSIZE") or 0)

        matched_by_pattern: dict[str, set[str]] = {pattern: set() for pattern in patterns}
        all_keys: set[str] = set()
        for pattern in patterns:
            cursor = "0"
            while True:
                response = client.command("SCAN", cursor, "MATCH", pattern, "COUNT", str(scan_count))
                if not isinstance(response, list) or len(response) != 2:
                    raise RuntimeError("Unexpected Redis SCAN response")
                cursor = str(response[0])
                keys = response[1] if isinstance(response[1], list) else []
                for key in keys:
                    key_name = str(key)
                    matched_by_pattern[pattern].add(key_name)
                    all_keys.add(key_name)
                if cursor == "0":
                    break

        key_details: list[RedisKeyUsage] = []
        matched_memory = 0
        for key in sorted(all_keys):
            try:
                key_type = str(client.command("TYPE", key) or "unknown")
            except Exception:
                key_type = "unknown"
            try:
                memory_usage = parse_intish(client.command("MEMORY", "USAGE", key) or 0)
            except Exception as exc:
                notes.append(f"Could not read MEMORY USAGE for {key}: {exc}")
                memory_usage = 0
            matched_memory += memory_usage
            key_details.append(
                RedisKeyUsage(
                    key=key,
                    key_type=key_type,
                    memory_usage=memory_usage,
                )
            )
    finally:
        connection_note = client.connection_note
        client.close()

    key_details.sort(key=lambda item: item.memory_usage, reverse=True)
    breakdown = [
        RedisPatternBreakdown(pattern=pattern, matched_keys=len(keys))
        for pattern, keys in matched_by_pattern.items()
    ]
    if connection_note:
        notes.insert(0, connection_note)

    return RedisSummary(
        address=f"{host}:{port}",
        database=int(settings.get("db") or 0),
        patterns=patterns,
        pattern_breakdown=breakdown,
        db_total_keys=db_total_keys,
        db_used_memory=db_used_memory,
        matched_keys=len(all_keys),
        matched_memory=matched_memory,
        top_keys=key_details[: max(top_limit, 0)],
        connection_note=" ".join(note.strip() for note in notes if note.strip()),
    )


def fetch_local_file_summary(file_roles: list[tuple[Path, str]]) -> list[LocalFileUsage]:
    by_path: dict[Path, LocalFileUsage] = {}
    for path, role in file_roles:
        existing = by_path.get(path)
        if existing is None:
            exists = path.exists()
            size = path.stat().st_size if exists and path.is_file() else 0
            by_path[path] = LocalFileUsage(
                path=path,
                exists=exists,
                size=size,
                roles=[role],
            )
        elif role not in existing.roles:
            existing.roles.append(role)

    usages = list(by_path.values())
    usages.sort(key=lambda item: item.size, reverse=True)
    return usages


def print_workflow_section(workflow: WorkflowDetails) -> None:
    print("Workflow Summary")
    print("----------------")
    print(f"Signalizing input source : {workflow.signalizing_input_source}")
    if workflow.kafka_topic:
        print(f"Kafka topic              : {workflow.kafka_topic}")
    print(f"Signal stream enabled    : {'yes' if workflow.signal_stream_enabled else 'no'}")
    if workflow.signal_stream_key:
        print(f"Signal stream key        : {workflow.signal_stream_key}")
    if workflow.signal_stream_dedup_prefix:
        print(f"Redis dedupe prefix      : {workflow.signal_stream_dedup_prefix}")
    print(f"Signalizing checkpoints  : {workflow.signalizing_checkpoint_provider}")
    if workflow.signalizing_checkpoint_index:
        print(f"Checkpoint index         : {workflow.signalizing_checkpoint_index}")
    print(f"Correlation input mode   : {workflow.correlation_input_mode}")
    if workflow.correlation_current_index:
        print(f"Current incident index   : {workflow.correlation_current_index}")
    print(f"Correlation Redis prefix : {workflow.correlation_redis_prefix}")
    print(f"RCA results store        : {workflow.rca_results_store}")
    if workflow.notes:
        print()
        for note in workflow.notes:
            print(f"- {note}")
    print()


def print_summary_header(
    mongo: MongoSummary | None,
    es: ElasticsearchSummary | None,
    redis: RedisSummary | None,
    local_files: list[LocalFileUsage] | None,
) -> None:
    mongo_total = sum(item.total_size for item in mongo.collections) if mongo else 0
    es_total = sum(item.store_size for item in es.indices) if es else 0
    redis_total = redis.matched_memory if redis else 0
    local_total = sum(item.size for item in local_files or []) if local_files else 0
    observed_total = mongo_total + es_total + redis_total + local_total

    print("RCA Space Summary")
    print("=================")
    print(f"Generated at (UTC)       : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Effective Summary")
    print("-----------------")
    print(f"Observed configured total: {format_bytes(observed_total)}")
    if mongo:
        print(f"MongoDB collections      : {format_bytes(mongo_total)} across {len(mongo.collections)} collection(s)")
    if es:
        print(f"Elasticsearch indices    : {format_bytes(es_total)} across {len(es.indices)} index(es)")
    if redis:
        print(f"Redis RCA key footprint  : {format_bytes(redis_total)} across {redis.matched_keys} matched key(s)")
    if local_files:
        print(f"Local file mirrors       : {format_bytes(local_total)} across {len(local_files)} file(s)")
    print()

    rows: list[list[str]] = []
    if mongo:
        rows.append(["1", "MongoDB", mongo.database, "Configured RCA collections", format_bytes(mongo_total)])
    if redis:
        rows.append(
            [
                str(len(rows) + 1),
                "Redis",
                f"db {redis.database}",
                f"Matched RCA key patterns ({redis.matched_keys} key(s))",
                format_bytes(redis_total),
            ]
        )
    if es:
        rows.append(
            [
                str(len(rows) + 1),
                "Elasticsearch",
                normalize_text(es.address, "-"),
                "Derived RCA-owned indices",
                format_bytes(es_total),
            ]
        )
    if local_files:
        rows.append(
            [
                str(len(rows) + 1),
                "Local files",
                repo_root().name,
                "Configured mirrors/checkpoints/rules",
                format_bytes(local_total),
            ]
        )
    rows.append(
        [
            str(len(rows) + 1),
            "TOTAL",
            "-",
            "All observed configured storage",
            format_bytes(observed_total),
        ]
    )
    print(render_table(["S/N", "Store", "Scope", "What Was Counted", "Used"], rows))
    print()


def print_mongo_section(summary: MongoSummary) -> None:
    print("MongoDB")
    print("-------")
    print(f"Database                : {summary.database}")
    print(f"Configured collections  : {len(summary.collections)}")
    print(f"Observed total          : {format_bytes(sum(item.total_size for item in summary.collections))}")
    print()

    rows = [
        [
            item.name,
            item.role,
            "yes" if item.exists else "no",
            format_int(item.count),
            format_bytes(item.data_size),
            format_bytes(item.storage_size),
            format_bytes(item.index_size),
            format_bytes(item.total_size),
        ]
        for item in summary.collections
    ]
    print(render_table(["Collection", "Role", "Exists", "Docs", "Data", "Storage", "Indexes", "Total"], rows))
    print()


def print_elasticsearch_section(summary: ElasticsearchSummary) -> None:
    print("Elasticsearch")
    print("-------------")
    print(f"Address                 : {summary.address}")
    print(f"Configured patterns     : {len(summary.patterns)}")
    print(f"Observed indices        : {len(summary.indices)}")
    print(f"Observed total          : {format_bytes(sum(item.store_size for item in summary.indices))}")
    print()

    pattern_rows = [[item.label, item.pattern] for item in summary.patterns]
    print(render_table(["Label", "Pattern"], pattern_rows))
    print()

    if summary.indices:
        rows = [
            [
                item.name,
                ", ".join(item.labels),
                format_int(item.docs_count),
                format_bytes(item.store_size),
            ]
            for item in summary.indices
        ]
        print(render_table(["Index", "Matched As", "Docs", "Store"], rows))
    else:
        print("No RCA-owned Elasticsearch indices matched the current config-derived patterns.")
    print()


def print_redis_section(summary: RedisSummary) -> None:
    print("Redis")
    print("-----")
    print(f"Address                 : {summary.address}")
    print(f"Database                : {summary.database}")
    print(f"Total DB keys           : {summary.db_total_keys}")
    print(f"Total DB used_memory    : {format_bytes(summary.db_used_memory)}")
    print(f"Matched RCA keys        : {summary.matched_keys}")
    print(f"Matched RCA memory      : {format_bytes(summary.matched_memory)}")
    if summary.connection_note:
        print(f"Connection note         : {summary.connection_note}")
    print()

    pattern_rows = [
        [item.pattern, format_int(item.matched_keys)]
        for item in summary.pattern_breakdown
    ]
    print(render_table(["Pattern", "Matched Keys"], pattern_rows))
    print()

    if summary.top_keys:
        rows = [
            [
                shorten(item.key, 72),
                item.key_type,
                format_bytes(item.memory_usage),
            ]
            for item in summary.top_keys
        ]
        print(render_table(["Top Key", "Type", "Memory"], rows))
    else:
        print("No Redis keys matched the current RCA patterns.")
    print()


def print_local_files_section(usages: list[LocalFileUsage]) -> None:
    print("Local Files")
    print("-----------")
    print(f"Observed files          : {len(usages)}")
    print(f"Observed total          : {format_bytes(sum(item.size for item in usages))}")
    print()

    rows = [
        [
            shorten(str(item.path), 88),
            ", ".join(item.roles),
            "yes" if item.exists else "no",
            format_bytes(item.size),
        ]
        for item in usages
    ]
    print(render_table(["Path", "Role", "Exists", "Size"], rows))
    print()


def main() -> int:
    args = parse_args()

    signalizing_config_path = Path(args.signalizing_config).expanduser().resolve()
    correlation_config_path = Path(args.correlation_config).expanduser().resolve()
    rca_config_path = Path(args.rca_config).expanduser().resolve()

    workflow, signalizing_cfg, correlation_cfg, rca_cfg = load_workflow_details(
        signalizing_config_path,
        correlation_config_path,
        rca_config_path,
    )

    mongo_summary: MongoSummary | None = None
    es_summary: ElasticsearchSummary | None = None
    redis_summary: RedisSummary | None = None
    local_files_summary: list[LocalFileUsage] | None = None
    warnings: list[str] = []

    if not args.no_mongo:
        try:
            mongo_summary = fetch_mongo_summary(resolve_mongo_settings(args, rca_cfg))
        except Exception as exc:
            warnings.append(f"MongoDB summary skipped: {exc}")

    if not args.no_elasticsearch:
        try:
            es_summary = fetch_elasticsearch_summary(
                resolve_elasticsearch_settings(args, workflow, signalizing_cfg, correlation_cfg, rca_cfg)
            )
        except Exception as exc:
            warnings.append(f"Elasticsearch summary skipped: {exc}")

    if not args.no_redis:
        try:
            redis_summary = fetch_redis_summary(
                resolve_redis_settings(args, workflow, signalizing_cfg, correlation_cfg),
                args.top_redis_keys,
            )
        except Exception as exc:
            warnings.append(f"Redis summary skipped: {exc}")

    if not args.no_local_files:
        try:
            local_files_summary = fetch_local_file_summary(
                resolve_local_file_settings(
                    signalizing_config_path,
                    correlation_config_path,
                    rca_config_path,
                    signalizing_cfg,
                    correlation_cfg,
                    rca_cfg,
                )
            )
        except Exception as exc:
            warnings.append(f"Local file summary skipped: {exc}")

    print_workflow_section(workflow)
    print_summary_header(mongo_summary, es_summary, redis_summary, local_files_summary)

    if mongo_summary:
        print_mongo_section(mongo_summary)
    if es_summary:
        print_elasticsearch_section(es_summary)
    if redis_summary:
        print_redis_section(redis_summary)
    if local_files_summary is not None:
        print_local_files_section(local_files_summary)

    if warnings:
        print("Warnings")
        print("--------")
        for warning in warnings:
            print(f"- {warning}")
        print()

    if not mongo_summary and not es_summary and not redis_summary and local_files_summary is None:
        print("No storage summaries could be collected.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
