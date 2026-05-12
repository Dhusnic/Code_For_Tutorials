#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass
class StepLatencyRecord:
    incident_id: str
    organization_id: str
    rule_id: str
    status: str
    classification: str
    log_count: int
    last_log_at: datetime | None
    last_signalized_at: datetime | None
    correlated_at: datetime | None
    rca_generated_at: datetime | None
    log_to_signalizing: timedelta | None
    signalizing_to_correlation: timedelta | None
    correlation_to_rca: timedelta | None
    total_latency: timedelta | None
    missing_stages: list[str]


@dataclass
class SkipReason:
    incident_id: str
    reason: str


@dataclass
class DataSource:
    label: str
    payload: Any
    notes: list[str]


class ElasticsearchHttpClient:
    def __init__(
        self,
        address: str,
        username: str = "",
        password: str = "",
        api_key: str = "",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.address = address.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.timeout_seconds = max(float(timeout_seconds), 0.1)

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

    def request_json(self, method: str, path: str, payload: Any | None = None) -> dict[str, Any]:
        url = self.address + path
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, method=method.upper(), headers=self._headers())
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Elasticsearch request failed ({exc.code} {exc.reason}): {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Elasticsearch at {self.address}: {exc}") from exc
        return json.loads(body) if body else {}

    def search(self, index: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.request_json("POST", f"/{index}/_search", payload)
        return response.get("hits", {}).get("hits", [])


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_results_file() -> Path:
    return repo_root() / "log_rca_engine" / "data" / "results" / "rca_results.json"


def default_rca_config() -> Path:
    return repo_root() / "log_rca_engine" / "config" / "config.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print a step-wise RCA latency summary using persisted stage timestamps: "
            "log generation -> signalizing -> correlation -> RCA."
        )
    )
    parser.add_argument(
        "--results-file",
        default=str(default_results_file()),
        help="Path to the RCA results JSON file.",
    )
    parser.add_argument(
        "--incident-id",
        default="",
        help="Optional comma-separated incident_id filter.",
    )
    parser.add_argument(
        "--doc-ids",
        default="",
        help="Optional comma-separated matched log doc IDs. Records must contain all listed IDs.",
    )
    parser.add_argument(
        "--status",
        default="",
        help="Optional comma-separated status filter.",
    )
    parser.add_argument(
        "--all-records",
        action="store_true",
        help="Disable dedupe-by-incident and include historical RCA snapshots for the same incident_id.",
    )
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="Show only incidents whose selected RCA snapshot is currently open.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum incidents to print. Use 0 to print all.",
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
        "--mongo-collection",
        default=os.getenv("RCA_RESULTS_COLLECTION") or "",
        help="Optional MongoDB collection override.",
    )
    parser.add_argument(
        "--mongo-timeout-seconds",
        type=float,
        default=5.0,
        help="MongoDB server selection timeout in seconds.",
    )
    parser.add_argument(
        "--rca-config",
        default=str(default_rca_config()),
        help="Path to log_rca_engine config.yml used to discover MongoDB settings.",
    )
    parser.add_argument(
        "--es-url",
        default=os.getenv("RCA_ES_URL") or "",
        help="Optional Elasticsearch URL override used to hydrate matched log doc IDs.",
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
        "--es-source-index",
        default=os.getenv("RCA_SOURCE_INDEX_FALLBACK") or "",
        help="Optional Elasticsearch source index fallback override for matched_doc_ids without source_index.",
    )
    parser.add_argument(
        "--es-correlation-index",
        default=os.getenv("RCA_CORRELATION_INDEX") or "",
        help="Optional correlation incident index override used to hydrate correlated_at by incident_id.",
    )
    parser.add_argument(
        "--es-timeout-seconds",
        type=float,
        default=20.0,
        help="Elasticsearch request timeout in seconds when hydrating log timestamps.",
    )
    parser.add_argument(
        "--no-es-lookup",
        action="store_true",
        help="Disable Elasticsearch log hydration and rely only on timestamps already stored in RCA results.",
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help="Include records with incomplete stage timestamps and show available latencies only. This is the default behavior.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require all stage timestamps and skip incomplete records.",
    )
    return parser.parse_args()


def parse_csv_filter(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def parse_timestamp(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value > 1_000_000_000_000:
            value /= 1000.0
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(raw, dict):
        if "$date" in raw:
            return parse_timestamp(raw.get("$date"))
        if "$numberLong" in raw:
            return parse_timestamp(raw.get("$numberLong"))
        return None
    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None
    if text.isdigit():
        return parse_timestamp(int(text))
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    if "." in text and ("+" in text[19:] or "-" in text[19:]):
        head, tail = text.split(".", 1)
        fraction = tail[:-6] if len(tail) > 6 and ("+" in tail or "-" in tail) else None
        if fraction is not None:
            sign_index = max(tail.rfind("+"), tail.rfind("-"))
            text = f"{head}.{tail[:min(sign_index, 6)]}{tail[sign_index:]}"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_go_zero_time(value: datetime | None) -> bool:
    if value is None:
        return False
    return (
        value.year == 1
        and value.month == 1
        and value.day == 1
        and value.hour == 0
        and value.minute == 0
        and value.second == 0
    )


def parse_stage_timestamp(raw: Any) -> datetime | None:
    parsed = parse_timestamp(raw)
    if is_go_zero_time(parsed):
        return None
    return parsed


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


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


def load_mongo_config_from_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    config: dict[str, Any] = {}
    in_section = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_section = stripped == "mongo_sync:"
            continue
        if not in_section or indent != 2 or ":" not in stripped:
            continue

        key, raw_value = stripped.split(":", 1)
        config[key.strip()] = parse_scalar(raw_value)
    return config


def load_elasticsearch_config_from_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    config: dict[str, Any] = {"addresses": []}
    in_section = False
    current_key = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_section = stripped == "elasticsearch:"
            current_key = ""
            continue
        if not in_section:
            continue
        if indent == 2 and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            current_key = key
            if key == "addresses":
                config[key] = []
                continue
            config[key] = parse_scalar(raw_value)
            continue
        if indent >= 4 and current_key == "addresses" and stripped.startswith("- "):
            config["addresses"].append(parse_scalar(stripped[2:]))
    return config


def resolve_mongo_settings(args: argparse.Namespace) -> dict[str, Any]:
    yaml_config = load_mongo_config_from_yaml(Path(args.rca_config).expanduser().resolve())
    uri = str(args.mongo_uri or yaml_config.get("uri") or "").strip()
    database = str(args.mongo_db or yaml_config.get("database") or "").strip()
    collection = str(args.mongo_collection or yaml_config.get("results_collection") or "rca_results").strip()
    enabled = bool(yaml_config.get("enabled", True))
    return {
        "enabled": enabled,
        "uri": uri,
        "database": database,
        "collection": collection,
        "timeout_seconds": max(float(args.mongo_timeout_seconds), 0.1),
    }


def resolve_elasticsearch_settings(args: argparse.Namespace) -> dict[str, Any]:
    yaml_config = load_elasticsearch_config_from_yaml(Path(args.rca_config).expanduser().resolve())
    addresses = [str(value).strip() for value in (yaml_config.get("addresses") or []) if str(value).strip()]
    address = str(args.es_url or (addresses[0] if addresses else "")).strip()
    return {
        "address": address,
        "username": str(args.es_username or yaml_config.get("username") or "").strip(),
        "password": str(args.es_password or yaml_config.get("password") or "").strip(),
        "api_key": str(args.es_api_key or yaml_config.get("api_key") or "").strip(),
        "correlation_index": str(args.es_correlation_index or yaml_config.get("correlation_index") or "").strip(),
        "source_index_fallback": str(args.es_source_index or yaml_config.get("source_index_fallback") or "*").strip()
        or "*",
        "timeout_seconds": max(float(args.es_timeout_seconds), 0.1),
    }


def load_payload_from_mongo(settings: dict[str, Any]) -> tuple[Any, str]:
    if not settings.get("enabled", True):
        raise RuntimeError("MongoDB is disabled in config.")
    uri = str(settings.get("uri") or "").strip()
    database = str(settings.get("database") or "").strip()
    collection = str(settings.get("collection") or "").strip()
    if not uri:
        raise RuntimeError("MongoDB URI is missing. Set it in config.yml or pass --mongo-uri.")
    if not database:
        raise RuntimeError("MongoDB database is missing. Set it in config.yml or pass --mongo-db.")
    if not collection:
        raise RuntimeError("MongoDB results collection is missing.")

    last_error: Exception | None = None
    try:
        return load_payload_from_mongo_via_pymongo(settings), f"MongoDB ({database}.{collection} via pymongo)"
    except Exception as exc:
        last_error = exc

    try:
        return load_payload_from_mongo_via_mongosh(settings), f"MongoDB ({database}.{collection} via mongosh)"
    except Exception as exc:
        if last_error is not None:
            raise RuntimeError(f"{last_error}; fallback via mongosh also failed: {exc}") from exc
        raise


def load_payload_from_mongo_via_pymongo(settings: dict[str, Any]) -> Any:
    try:
        from pymongo import DESCENDING, MongoClient
    except ImportError as exc:
        raise RuntimeError("pymongo is not installed") from exc

    timeout_ms = int(float(settings["timeout_seconds"]) * 1000)
    client = MongoClient(str(settings["uri"]), serverSelectionTimeoutMS=timeout_ms)
    try:
        collection = client[str(settings["database"])][str(settings["collection"])]
        docs = list(
            collection.find({"document_kind": "rca_result"}, {"_id": 0}).sort(
                [("updated_at", DESCENDING), ("last_persisted_at", DESCENDING)]
            )
        )
        if not docs:
            docs = list(
                collection.find({}, {"_id": 0}).sort(
                    [("updated_at", DESCENDING), ("last_persisted_at", DESCENDING)]
                )
            )
        return {"items": docs}
    finally:
        client.close()


def load_payload_from_mongo_via_mongosh(settings: dict[str, Any]) -> Any:
    mongosh_path = shutil.which("mongosh")
    if not mongosh_path:
        raise RuntimeError("mongosh command not found and pymongo is unavailable")

    database = json.dumps(str(settings["database"]))
    collection = json.dumps(str(settings["collection"]))
    query = (
        f"const dbName = {database};"
        f"const collName = {collection};"
        "const coll = db.getSiblingDB(dbName).getCollection(collName);"
        "let docs = coll.find({document_kind:'rca_result'},{_id:0}).sort({updated_at:-1,last_persisted_at:-1}).toArray();"
        "if (!docs.length) { docs = coll.find({}, {_id:0}).sort({updated_at:-1,last_persisted_at:-1}).toArray(); }"
        "print(EJSON.stringify({items: docs}));"
    )

    completed = subprocess.run(
        [mongosh_path, str(settings["uri"]), "--quiet", "--eval", query],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(stderr or "mongosh query failed")

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {"items": []}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"mongosh returned invalid JSON: {exc}") from exc


def load_payload(path: Path) -> tuple[Any, str]:
    if not path.exists():
        raise FileNotFoundError(f"results file not found: {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"items": []}, f"Primary results file is empty: {path}"
    payload = json.loads(raw)
    return payload, f"Local file ({path})"


def aggregate_worker_payloads(results_file: Path) -> tuple[Any, str] | None:
    pattern = f"{results_file.stem}.worker-*.json"
    worker_files = sorted(results_file.parent.glob(pattern))
    if not worker_files:
        return None

    items: list[dict[str, Any]] = []
    latest_updated_at: datetime | None = None
    used_files = 0
    for worker_file in worker_files:
        raw = worker_file.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        payload = json.loads(raw)
        worker_items = extract_records(payload)
        if not worker_items:
            continue
        items.extend(worker_items)
        used_files += 1
        if isinstance(payload, dict):
            updated_at = parse_timestamp(payload.get("updated_at"))
            if updated_at is not None and (latest_updated_at is None or updated_at > latest_updated_at):
                latest_updated_at = updated_at

    if not items:
        return None

    items.sort(
        key=lambda item: parse_timestamp(item.get("rca_generated_at") or item.get("updated_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    payload: dict[str, Any] = {"items": items}
    if latest_updated_at is not None:
        payload["updated_at"] = latest_updated_at.isoformat().replace("+00:00", "Z")
    return payload, f"Local worker result files ({used_files} file(s), pattern {pattern})"


def resolve_data_source(args: argparse.Namespace, results_file: Path) -> DataSource:
    notes: list[str] = []

    try:
        mongo_payload, mongo_label = load_payload_from_mongo(resolve_mongo_settings(args))
        if extract_records(mongo_payload):
            return DataSource(label=mongo_label, payload=mongo_payload, notes=notes)
        notes.append("MongoDB returned no RCA items, falling back to local files.")
    except RuntimeError as exc:
        notes.append(f"MongoDB read failed, falling back to local files: {exc}")

    payload, label = load_payload(results_file)
    if extract_records(payload):
        return DataSource(label=label, payload=payload, notes=notes)

    worker_payload = aggregate_worker_payloads(results_file)
    if worker_payload is not None:
        worker_data, worker_label = worker_payload
        return DataSource(label=worker_label, payload=worker_data, notes=notes)

    return DataSource(label=label, payload=payload, notes=notes)


def normalize_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def matched_logs(record: dict[str, Any]) -> list[dict[str, Any]]:
    logs = record.get("matched_logs")
    if not isinstance(logs, list):
        return []
    return [item for item in logs if isinstance(item, dict)]


def chunked(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]
    return [values[index : index + size] for index in range(0, len(values), size)]


def collect_doc_refs_by_index(record: dict[str, Any], fallback_index: str) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}

    for item in matched_logs(record):
        doc_id = normalize_text(item.get("id") or item.get("doc_id"), "")
        source_index = normalize_text(item.get("source_index"), "")
        if doc_id and source_index:
            refs.setdefault(source_index, []).append(doc_id)

    if refs:
        return {index: sorted(set(doc_ids)) for index, doc_ids in refs.items()}

    matched_doc_ids = record.get("matched_doc_ids")
    if isinstance(matched_doc_ids, list):
        ids = sorted({normalize_text(value, "") for value in matched_doc_ids if normalize_text(value, "")})
        if ids:
            refs[fallback_index] = ids
    return refs


def fetch_source_doc_stage_fields(
    records: list[dict[str, Any]],
    es_settings: dict[str, Any],
) -> dict[tuple[str, str], dict[str, datetime]]:
    address = str(es_settings.get("address") or "").strip()
    if not address:
        raise RuntimeError("Elasticsearch lookup needs an address. Set it in config.yml or pass --es-url.")

    client = ElasticsearchHttpClient(
        address=address,
        username=str(es_settings.get("username") or ""),
        password=str(es_settings.get("password") or ""),
        api_key=str(es_settings.get("api_key") or ""),
        timeout_seconds=float(es_settings.get("timeout_seconds") or 20.0),
    )

    ids_by_index: dict[str, set[str]] = {}
    fallback_index = str(es_settings.get("source_index_fallback") or "*").strip() or "*"
    for record in records:
        for index_name, doc_ids in collect_doc_refs_by_index(record, fallback_index).items():
            ids_by_index.setdefault(index_name, set()).update(doc_ids)

    cache: dict[tuple[str, str], dict[str, datetime]] = {}
    for index_name, doc_ids in ids_by_index.items():
        ordered_ids = sorted(doc_ids)
        for batch in chunked(ordered_ids, 200):
            hits = client.search(
                index_name,
                {
                    "size": len(batch),
                    "_source": ["@timestamp", "timestamp", "signalized_at"],
                    "query": {"ids": {"values": batch}},
                },
            )
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                source = hit.get("_source") or {}
                if not isinstance(source, dict):
                    continue
                actual_index = normalize_text(hit.get("_index"), index_name)
                doc_id = normalize_text(hit.get("_id"), "")
                log_timestamp = parse_stage_timestamp(source.get("@timestamp") or source.get("timestamp"))
                signalized_at = parse_stage_timestamp(source.get("signalized_at"))
                if not doc_id:
                    continue
                fields: dict[str, datetime] = {}
                if log_timestamp is not None:
                    fields["timestamp"] = log_timestamp
                if signalized_at is not None:
                    fields["signalized_at"] = signalized_at
                if not fields:
                    continue
                cache[(actual_index, doc_id)] = fields
                cache.setdefault((index_name, doc_id), fields)
    return cache


def collect_resolved_stage_timestamps(
    record: dict[str, Any],
    source_doc_fields: dict[tuple[str, str], dict[str, datetime]],
    fallback_index: str,
) -> tuple[list[datetime], list[datetime]]:
    refs = collect_doc_refs_by_index(record, fallback_index)
    log_times: list[datetime] = []
    signalized_times: list[datetime] = []
    for index_name, doc_ids in refs.items():
        for doc_id in doc_ids:
            fields = source_doc_fields.get((index_name, doc_id))
            if not fields:
                continue
            log_timestamp = fields.get("timestamp")
            signalized_at = fields.get("signalized_at")
            if log_timestamp is not None:
                log_times.append(log_timestamp)
            if signalized_at is not None:
                signalized_times.append(signalized_at)
    return sorted(log_times), sorted(signalized_times)


def fetch_correlation_incident_fields(
    records: list[dict[str, Any]],
    es_settings: dict[str, Any],
) -> dict[str, dict[str, datetime]]:
    address = str(es_settings.get("address") or "").strip()
    if not address:
        raise RuntimeError("Elasticsearch lookup needs an address. Set it in config.yml or pass --es-url.")
    correlation_index = str(es_settings.get("correlation_index") or "").strip()
    if not correlation_index:
        raise RuntimeError(
            "Correlation incident lookup needs elasticsearch.correlation_index. Set it in config.yml or pass --es-correlation-index."
        )

    incident_ids = sorted(
        {
            normalize_text(record.get("incident_id"), "")
            for record in records
            if normalize_text(record.get("incident_id"), "")
        }
    )
    if not incident_ids:
        return {}

    client = ElasticsearchHttpClient(
        address=address,
        username=str(es_settings.get("username") or ""),
        password=str(es_settings.get("password") or ""),
        api_key=str(es_settings.get("api_key") or ""),
        timeout_seconds=float(es_settings.get("timeout_seconds") or 20.0),
    )

    cache: dict[str, dict[str, datetime]] = {}
    for batch in chunked(incident_ids, 200):
        hits = client.search(
            correlation_index,
            {
                "size": len(batch) * 5,
                "_source": ["incident_id", "matched_at", "correlated_at", "last_seen", "status"],
                "query": {"terms": {"incident_id.keyword": batch}},
                "sort": [
                    {"correlated_at": {"order": "desc", "format": "strict_date_optional_time_nanos", "missing": "_last"}},
                    {"last_seen": {"order": "desc", "format": "strict_date_optional_time_nanos", "missing": "_last"}},
                    {"matched_at": {"order": "desc", "format": "strict_date_optional_time_nanos", "missing": "_last"}},
                ],
            },
        )
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source") or {}
            if not isinstance(source, dict):
                continue
            incident_id = normalize_text(source.get("incident_id"), "")
            if not incident_id:
                incident_id = normalize_text(hit.get("_id"), "")
            if not incident_id or incident_id in cache:
                continue
            fields: dict[str, datetime] = {}
            correlated_at = parse_stage_timestamp(source.get("correlated_at"))
            matched_at = parse_stage_timestamp(source.get("matched_at"))
            last_seen = parse_stage_timestamp(source.get("last_seen"))
            if correlated_at is not None:
                fields["correlated_at"] = correlated_at
            if matched_at is not None:
                fields["matched_at"] = matched_at
            if last_seen is not None:
                fields["last_seen"] = last_seen
            if fields:
                cache[incident_id] = fields
    return cache


def record_doc_ids(record: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in matched_logs(record):
        doc_id = normalize_text(item.get("id") or item.get("doc_id"), "")
        if doc_id:
            ids.add(doc_id)
    matched_doc_ids = record.get("matched_doc_ids")
    if isinstance(matched_doc_ids, list):
        for value in matched_doc_ids:
            doc_id = normalize_text(value, "")
            if doc_id:
                ids.add(doc_id)
    return ids


def record_matches_filters(
    record: dict[str, Any],
    statuses: set[str],
    incident_ids: set[str],
    doc_ids: set[str],
) -> bool:
    if statuses:
        status = normalize_text(record.get("status"), "").lower()
        if status not in statuses:
            return False
    if incident_ids:
        if normalize_text(record.get("incident_id"), "") not in incident_ids:
            return False
    if doc_ids and not doc_ids.issubset(record_doc_ids(record)):
        return False
    return True


def record_effective_timestamp(record: dict[str, Any]) -> datetime:
    for key in ("rca_generated_at", "updated_at", "correlated_at", "matched_at"):
        parsed = parse_stage_timestamp(record.get(key))
        if parsed is not None:
            return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def select_latest_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_incident: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []

    for record in records:
        incident_id = normalize_text(record.get("incident_id"), "")
        if not incident_id:
            passthrough.append(record)
            continue
        existing = latest_by_incident.get(incident_id)
        if existing is None or record_effective_timestamp(record) >= record_effective_timestamp(existing):
            latest_by_incident[incident_id] = record

    selected = list(latest_by_incident.values())
    selected.extend(passthrough)
    selected.sort(key=record_effective_timestamp, reverse=True)
    return selected


def latest_timestamp(values: list[datetime]) -> datetime | None:
    return max(values) if values else None


def between(start: datetime | None, end: datetime | None) -> timedelta | None:
    if start is None or end is None:
        return None
    return end - start


def build_step_records(
    records: list[dict[str, Any]],
    statuses: set[str],
    incident_ids: set[str],
    doc_ids: set[str],
    allow_partial: bool,
    source_doc_fields: dict[tuple[str, str], dict[str, datetime]] | None = None,
    source_incident_fields: dict[str, dict[str, datetime]] | None = None,
    fallback_index: str = "*",
) -> tuple[list[StepLatencyRecord], list[SkipReason]]:
    analyzed: list[StepLatencyRecord] = []
    skipped: list[SkipReason] = []

    for record in records:
        if not record_matches_filters(record, statuses, incident_ids, doc_ids):
            continue

        incident_id = normalize_text(record.get("incident_id"), "(missing incident_id)")
        logs = matched_logs(record)
        doc_refs = record_doc_ids(record)
        if not logs and not doc_refs:
            skipped.append(SkipReason(incident_id, "missing matched_logs and matched_doc_ids"))
            continue

        log_times = [
            ts for ts in (parse_stage_timestamp(item.get("timestamp") or item.get("@timestamp")) for item in logs) if ts is not None
        ]
        signalized_times = [
            ts for ts in (parse_stage_timestamp(item.get("signalized_at")) for item in logs) if ts is not None
        ]
        if source_doc_fields:
            hydrated_log_times, hydrated_signalized_times = collect_resolved_stage_timestamps(
                record, source_doc_fields, fallback_index
            )
            if not log_times:
                log_times = hydrated_log_times
            if not signalized_times:
                signalized_times = hydrated_signalized_times
        correlated_at = parse_stage_timestamp(record.get("correlated_at"))
        if correlated_at is None and source_incident_fields:
            incident_fields = source_incident_fields.get(incident_id) or {}
            incident_correlated_at = incident_fields.get("correlated_at")
            if incident_correlated_at is not None:
                correlated_at = incident_correlated_at
        rca_generated_at = parse_stage_timestamp(record.get("rca_generated_at")) or parse_stage_timestamp(
            record.get("updated_at")
        )

        last_log_at = latest_timestamp(log_times)
        last_signalized_at = latest_timestamp(signalized_times)
        missing_stages: list[str] = []

        if last_log_at is None:
            missing_stages.append("log timestamp")
        if last_signalized_at is None:
            missing_stages.append("signalized_at")
        if correlated_at is None:
            missing_stages.append("correlated_at")
        if rca_generated_at is None:
            missing_stages.append("rca_generated_at/updated_at")

        if not allow_partial and missing_stages:
            skipped.append(SkipReason(incident_id, f"missing {', '.join(missing_stages)}"))
            continue

        if last_log_at is None and last_signalized_at is None and correlated_at is None and rca_generated_at is None:
            skipped.append(SkipReason(incident_id, "missing all step timestamps"))
            continue

        log_to_signalizing = between(last_log_at, last_signalized_at)
        signalizing_to_correlation = between(last_signalized_at, correlated_at)
        correlation_to_rca = between(correlated_at, rca_generated_at)
        total_latency = between(last_log_at, rca_generated_at)

        analyzed.append(
            StepLatencyRecord(
                incident_id=incident_id,
                organization_id=normalize_text(record.get("organization_id")),
                rule_id=normalize_text(record.get("rule_id")),
                status=normalize_text(record.get("status"), "open").lower(),
                classification=normalize_text(record.get("classification")),
                log_count=max(len(logs), len(doc_refs)),
                last_log_at=last_log_at,
                last_signalized_at=last_signalized_at,
                correlated_at=correlated_at,
                rca_generated_at=rca_generated_at,
                log_to_signalizing=log_to_signalizing,
                signalizing_to_correlation=signalizing_to_correlation,
                correlation_to_rca=correlation_to_rca,
                total_latency=total_latency,
                missing_stages=missing_stages,
            )
        )

    analyzed.sort(
        key=lambda item: item.total_latency.total_seconds() if item.total_latency is not None else float("-inf"),
        reverse=True,
    )
    return analyzed, skipped


def average_duration(values: list[timedelta]) -> timedelta | None:
    if not values:
        return None
    return timedelta(seconds=sum(value.total_seconds() for value in values) / len(values))


def median_duration(values: list[timedelta]) -> timedelta | None:
    if not values:
        return None
    ordered = sorted(value.total_seconds() for value in values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return timedelta(seconds=ordered[middle])
    return timedelta(seconds=(ordered[middle - 1] + ordered[middle]) / 2.0)


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(value: timedelta | None) -> str:
    if value is None:
        return "-"
    total_seconds = value.total_seconds()
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    if total_seconds < 1:
        return f"{sign}{total_seconds * 1000:.0f} ms"
    if total_seconds < 60:
        return f"{sign}{total_seconds:.2f} s"
    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{sign}{int(minutes)}m {seconds:04.1f}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{sign}{int(hours)}h {int(minutes):02d}m {seconds:04.1f}s"
    days, hours = divmod(hours, 24)
    return f"{sign}{int(days)}d {int(hours):02d}h {int(minutes):02d}m"


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
    return "\n".join([render_row(headers), separator, *[render_row(row) for row in rows]])


def print_report(
    results_file: Path,
    source: DataSource,
    payload: Any,
    selected_records: int,
    analyzed: list[StepLatencyRecord],
    skipped: list[SkipReason],
    limit: int,
    partial_mode: bool,
    latest_only: bool,
    open_only: bool,
) -> None:
    print("RCA Step Latency Report")
    print("=======================")
    print(f"Results file      : {results_file}")
    print(f"Data source       : {source.label}")
    print(f"RCA records found : {len(extract_records(payload))}")
    print(f"Records selected  : {selected_records}")
    print(f"Records analyzed  : {len(analyzed)}")
    print(f"Records skipped   : {len(skipped)}")
    print(f"Partial mode      : {'on' if partial_mode else 'off'}")
    print(f"Latest-only mode  : {'on' if latest_only else 'off'}")
    print(f"Open-only mode    : {'on' if open_only else 'off'}")
    if isinstance(payload, dict):
        updated_at = parse_timestamp(payload.get("updated_at"))
        if updated_at is not None:
            print(f"Store updated at  : {format_timestamp(updated_at)} UTC")
    for note in source.notes:
        print(f"Note              : {note}")
    print()

    if not analyzed:
        print("No records had all step-wise timestamps.")
        if skipped:
            print()
            print("Skipped records")
            print("---------------")
            for item in skipped[:10]:
                print(f"- {item.incident_id}: {item.reason}")
        return

    avg_log_to_signal = average_duration([item.log_to_signalizing for item in analyzed if item.log_to_signalizing is not None])
    avg_signal_to_corr = average_duration(
        [item.signalizing_to_correlation for item in analyzed if item.signalizing_to_correlation is not None]
    )
    avg_corr_to_rca = average_duration(
        [item.correlation_to_rca for item in analyzed if item.correlation_to_rca is not None]
    )
    avg_total = average_duration([item.total_latency for item in analyzed if item.total_latency is not None])
    median_total = median_duration([item.total_latency for item in analyzed if item.total_latency is not None])
    partial_records = sum(1 for item in analyzed if item.missing_stages)

    print("Step-wise summary")
    print("-----------------")
    print(f"Log generation -> signalizing : {format_duration(avg_log_to_signal)} average")
    print(f"Signalizing -> correlation    : {format_duration(avg_signal_to_corr)} average")
    print(f"Correlation -> RCA            : {format_duration(avg_corr_to_rca)} average")
    print(f"End-to-end total              : {format_duration(avg_total)} average")
    print(f"End-to-end median             : {format_duration(median_total)}")
    print(f"Partial records               : {partial_records}")
    print()

    visible = analyzed if limit == 0 else analyzed[: max(limit, 0)]
    rows: list[list[str]] = []
    for index, item in enumerate(visible, start=1):
        rows.append(
            [
                str(index),
                shorten(item.incident_id, 24),
                shorten(item.rule_id, 28),
                item.status,
                str(item.log_count),
                format_duration(item.log_to_signalizing),
                format_duration(item.signalizing_to_correlation),
                format_duration(item.correlation_to_rca),
                format_duration(item.total_latency),
                shorten(", ".join(item.missing_stages) if item.missing_stages else "-", 28),
            ]
        )

    print("Per-incident latency")
    print("--------------------")
    print(
        render_table(
            [
                "S/N",
                "Incident ID",
                "Rule ID",
                "Status",
                "Logs",
                "Log->Signal",
                "Signal->Corr",
                "Corr->RCA",
                "Total",
                "Missing",
            ],
            rows,
        )
    )

    if skipped:
        print()
        print("Skipped records")
        print("---------------")
        for item in skipped[:10]:
            print(f"- {item.incident_id}: {item.reason}")
        if len(skipped) > 10:
            print(f"- ... and {len(skipped) - 10} more")


def main() -> int:
    args = parse_args()
    results_file = Path(args.results_file).expanduser().resolve()
    partial_mode = True
    if args.strict:
        partial_mode = False
    elif args.partial:
        partial_mode = True

    try:
        source = resolve_data_source(args, results_file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in results file: {exc}")
        return 1

    payload = source.payload
    records = extract_records(payload)
    latest_only = not args.all_records
    selected_records = select_latest_records(records) if latest_only else list(records)
    statuses = parse_csv_filter(args.status.lower())
    if args.open_only:
        statuses = {"open"}
    source_doc_fields: dict[tuple[str, str], dict[str, datetime]] | None = None
    source_incident_fields: dict[str, dict[str, datetime]] | None = None
    fallback_index = "*"
    if not args.no_es_lookup and selected_records:
        try:
            es_settings = resolve_elasticsearch_settings(args)
            fallback_index = str(es_settings.get("source_index_fallback") or "*").strip() or "*"
            source_doc_fields = fetch_source_doc_stage_fields(selected_records, es_settings)
            source_incident_fields = fetch_correlation_incident_fields(selected_records, es_settings)
            source.notes.append(
                f"Elasticsearch hydration resolved {len(source_doc_fields)} doc/index timestamp entries."
            )
            source.notes.append(
                f"Correlation incident hydration resolved {len(source_incident_fields)} incident timestamp entries."
            )
        except RuntimeError as exc:
            source.notes.append(f"Elasticsearch hydration failed; using persisted RCA fields only: {exc}")
    analyzed, skipped = build_step_records(
        selected_records,
        statuses=statuses,
        incident_ids=parse_csv_filter(args.incident_id),
        doc_ids=parse_csv_filter(args.doc_ids),
        allow_partial=partial_mode,
        source_doc_fields=source_doc_fields,
        source_incident_fields=source_incident_fields,
        fallback_index=fallback_index,
    )
    print_report(
        results_file,
        source,
        payload,
        len(selected_records),
        analyzed,
        skipped,
        args.limit,
        partial_mode,
        latest_only,
        args.open_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
