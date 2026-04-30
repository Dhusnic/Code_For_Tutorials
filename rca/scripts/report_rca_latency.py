#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass
class LatencyRecord:
    incident_id: str
    organization_id: str
    rule_id: str
    status: str
    classification: str
    log_count: int
    first_log_at: datetime
    last_log_at: datetime
    matched_at: datetime | None
    generated_at: datetime
    latency_from_first: timedelta
    latency_from_last: timedelta
    latency_from_match: timedelta | None


@dataclass
class SkipReason:
    incident_id: str
    reason: str


@dataclass
class DataSource:
    label: str
    payload: Any
    local_file_message: str | None = None
    mongo_message: str | None = None


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
            "Print a readable RCA latency report from the local rca_results.json file. "
            "Primary latency is measured from the last matched log timestamp to RCA updated_at."
        )
    )
    parser.add_argument(
        "--results-file",
        default=str(default_results_file()),
        help="Path to the RCA results JSON file.",
    )
    parser.add_argument(
        "--status",
        default="",
        help="Optional comma-separated status filter, for example: open,updated,closed",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum incidents to print in the table. Use 0 to print all.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("RCA_MONGO_URI") or os.getenv("MONGO_URI") or "",
        help="Optional MongoDB URI override for fallback reads.",
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv("RCA_MONGO_DB") or "",
        help="Optional MongoDB database override for fallback reads.",
    )
    parser.add_argument(
        "--mongo-collection",
        default=os.getenv("RCA_RESULTS_COLLECTION") or "",
        help="Optional MongoDB collection override for fallback reads.",
    )
    parser.add_argument(
        "--mongo-timeout-seconds",
        type=float,
        default=5.0,
        help="MongoDB server selection timeout in seconds for fallback reads.",
    )
    parser.add_argument(
        "--rca-config",
        default=str(default_rca_config()),
        help="Path to log_rca_engine config.yml used to discover MongoDB settings.",
    )
    parser.add_argument(
        "--no-mongo-fallback",
        action="store_true",
        help="Disable MongoDB fallback even when the local results file is empty.",
    )
    parser.add_argument(
        "--es-url",
        default=os.getenv("RCA_ES_URL") or "",
        help="Optional Elasticsearch URL override used to resolve matched log doc IDs.",
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
        "--es-timeout-seconds",
        type=float,
        default=20.0,
        help="Elasticsearch request timeout in seconds when resolving log timestamps.",
    )
    parser.add_argument(
        "--no-es-lookup",
        action="store_true",
        help="Disable Elasticsearch log lookup and fall back to timestamps already stored in RCA results.",
    )
    return parser.parse_args()


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

    # Older Python versions reject ISO timestamps with more than 6 fractional
    # second digits. Normalize them so both local venvs and newer runtimes
    # parse the same RCA records.
    match = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})$", text)
    if match:
        prefix, fraction, suffix = match.groups()
        text = f"{prefix}.{fraction[:6]}{suffix}"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_payload(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        raise FileNotFoundError(f"results file not found: {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None, "Results file is empty."
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"results file contains invalid JSON: {exc}") from exc
    if len(extract_records(payload)) == 0:
        return payload, "Results file contains no RCA items."
    return payload, None


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []
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
        if not in_section:
            continue
        if indent != 2:
            continue
        if ":" not in stripped:
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
    addresses = [
        str(value).strip()
        for value in (yaml_config.get("addresses") or [])
        if str(value).strip()
    ]
    address = str(args.es_url or (addresses[0] if addresses else "")).strip()
    return {
        "address": address,
        "username": str(args.es_username or yaml_config.get("username") or "").strip(),
        "password": str(args.es_password or yaml_config.get("password") or "").strip(),
        "api_key": str(args.es_api_key or yaml_config.get("api_key") or "").strip(),
        "source_index_fallback": str(args.es_source_index or yaml_config.get("source_index_fallback") or "*").strip() or "*",
        "timeout_seconds": max(float(args.es_timeout_seconds), 0.1),
    }


def load_payload_from_mongo(settings: dict[str, Any]) -> tuple[Any, str]:
    if not settings.get("enabled", True):
        raise RuntimeError("MongoDB fallback is disabled in config.")
    uri = str(settings.get("uri") or "").strip()
    database = str(settings.get("database") or "").strip()
    collection = str(settings.get("collection") or "").strip()
    if not uri:
        raise RuntimeError("MongoDB fallback needs a URI. Set it in config.yml or pass --mongo-uri.")
    if not database:
        raise RuntimeError("MongoDB fallback needs a database name. Set it in config.yml or pass --mongo-db.")
    if not collection:
        raise RuntimeError("MongoDB fallback needs a results collection name.")

    last_error: Exception | None = None
    try:
        return load_payload_from_mongo_via_pymongo(settings), f"MongoDB ({database}.{collection} via pymongo)"
    except Exception as exc:  # pragma: no cover - best effort fallback
        last_error = exc

    try:
        return load_payload_from_mongo_via_mongosh(settings), f"MongoDB ({database}.{collection} via mongosh)"
    except Exception as exc:  # pragma: no cover - best effort fallback
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


def resolve_data_source(args: argparse.Namespace, results_file: Path) -> DataSource:
    payload, local_message = load_payload(results_file)
    if local_message is None or args.no_mongo_fallback:
        return DataSource(label=f"Local file ({results_file})", payload=payload, local_file_message=local_message)

    mongo_settings = resolve_mongo_settings(args)
    mongo_payload, mongo_label = load_payload_from_mongo(mongo_settings)
    return DataSource(
        label=mongo_label,
        payload=mongo_payload,
        local_file_message=local_message,
        mongo_message=f"Used MongoDB fallback because local results file was empty: {local_message}",
    )


def matched_log_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    matched_logs = record.get("matched_logs")
    if not isinstance(matched_logs, list):
        matched_logs = record.get("log_id")
    if not isinstance(matched_logs, list):
        return []
    return [item for item in matched_logs if isinstance(item, dict)]


def collect_log_timestamps(record: dict[str, Any]) -> list[datetime]:
    matched_logs = matched_log_entries(record)
    if not matched_logs:
        return []

    timestamps: list[datetime] = []
    for item in matched_logs:
        timestamp = parse_timestamp(item.get("timestamp") or item.get("@timestamp"))
        if timestamp is not None:
            timestamps.append(timestamp)
    return sorted(timestamps)


def chunked(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]
    return [values[index : index + size] for index in range(0, len(values), size)]


def collect_doc_refs_by_index(record: dict[str, Any], fallback_index: str) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}

    for item in matched_log_entries(record):
        doc_id = normalize_text(item.get("id"), "")
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


def fetch_source_doc_timestamps(
    records: list[dict[str, Any]],
    es_settings: dict[str, Any],
) -> dict[tuple[str, str], datetime]:
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

    cache: dict[tuple[str, str], datetime] = {}
    for index_name, doc_ids in ids_by_index.items():
        ordered_ids = sorted(doc_ids)
        for batch in chunked(ordered_ids, 200):
            hits = client.search(
                index_name,
                {
                    "size": len(batch),
                    "_source": ["@timestamp", "timestamp"],
                    "query": {
                        "ids": {
                            "values": batch,
                        }
                    },
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
                timestamp = parse_timestamp(source.get("@timestamp") or source.get("timestamp"))
                if doc_id and timestamp is not None:
                    cache[(actual_index, doc_id)] = timestamp
                    cache.setdefault((index_name, doc_id), timestamp)
    return cache


def collect_resolved_log_timestamps(
    record: dict[str, Any],
    source_doc_timestamps: dict[tuple[str, str], datetime],
    fallback_index: str,
) -> list[datetime]:
    refs = collect_doc_refs_by_index(record, fallback_index)
    timestamps: list[datetime] = []
    for index_name, doc_ids in refs.items():
        for doc_id in doc_ids:
            timestamp = source_doc_timestamps.get((index_name, doc_id))
            if timestamp is not None:
                timestamps.append(timestamp)
    return sorted(timestamps)


def normalize_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def build_latency_records(
    records: list[dict[str, Any]],
    allowed_statuses: set[str],
    source_doc_timestamps: dict[tuple[str, str], datetime] | None = None,
    fallback_index: str = "*",
) -> tuple[list[LatencyRecord], list[SkipReason]]:
    analyzed: list[LatencyRecord] = []
    skipped: list[SkipReason] = []

    for record in records:
        incident_id = normalize_text(record.get("incident_id"), "(missing incident_id)")
        status = normalize_text(record.get("status"), "open").lower()
        if allowed_statuses and status not in allowed_statuses:
            continue

        if source_doc_timestamps is not None:
            log_timestamps = collect_resolved_log_timestamps(record, source_doc_timestamps, fallback_index)
            if not log_timestamps:
                skipped.append(
                    SkipReason(
                        incident_id=incident_id,
                        reason="could not resolve source log @timestamp from Elasticsearch for matched doc IDs",
                    )
                )
                continue
        else:
            log_timestamps = collect_log_timestamps(record)
        if not log_timestamps:
            skipped.append(SkipReason(incident_id=incident_id, reason="missing matched log timestamps"))
            continue

        generated_at = parse_timestamp(record.get("updated_at")) or parse_timestamp(record.get("matched_at"))
        if generated_at is None:
            skipped.append(SkipReason(incident_id=incident_id, reason="missing RCA generated timestamp"))
            continue

        first_log_at = log_timestamps[0]
        last_log_at = log_timestamps[-1]
        matched_at = parse_timestamp(record.get("matched_at"))
        analyzed.append(
            LatencyRecord(
                incident_id=incident_id,
                organization_id=normalize_text(record.get("organization_id")),
                rule_id=normalize_text(record.get("rule_id")),
                status=status,
                classification=normalize_text(record.get("classification")),
                log_count=len(log_timestamps),
                first_log_at=first_log_at,
                last_log_at=last_log_at,
                matched_at=matched_at,
                generated_at=generated_at,
                latency_from_first=generated_at - first_log_at,
                latency_from_last=generated_at - last_log_at,
                latency_from_match=(generated_at - matched_at) if matched_at is not None else None,
            )
        )

    analyzed.sort(key=lambda item: item.latency_from_last.total_seconds(), reverse=True)
    return analyzed, skipped


def average_duration(durations: list[timedelta]) -> timedelta | None:
    if not durations:
        return None
    seconds = sum(duration.total_seconds() for duration in durations) / len(durations)
    return timedelta(seconds=seconds)


def median_duration(durations: list[timedelta]) -> timedelta | None:
    if not durations:
        return None
    ordered = sorted(duration.total_seconds() for duration in durations)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return timedelta(seconds=ordered[middle])
    return timedelta(seconds=(ordered[middle - 1] + ordered[middle]) / 2.0)


def count_by(items: list[LatencyRecord], field_name: str) -> str:
    counts: dict[str, int] = {}
    for item in items:
        key = normalize_text(getattr(item, field_name))
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return ", ".join(f"{name}: {count}" for name, count in ranked) if ranked else "-"


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
    lines = [render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def print_report(
    results_file: Path,
    source: DataSource,
    payload: Any,
    analyzed: list[LatencyRecord],
    skipped: list[SkipReason],
    limit: int,
    timestamp_basis: str,
) -> None:
    top_level_updated_at = None
    if isinstance(payload, dict):
        top_level_updated_at = parse_timestamp(payload.get("updated_at"))

    print("RCA Latency Report")
    print("=" * 18)
    print(f"Results file           : {results_file}")
    print(f"Data source            : {source.label}")
    print(f"RCA records found      : {len(extract_records(payload))}")
    print(f"Records analyzed       : {len(analyzed)}")
    print(f"Records skipped        : {len(skipped)}")
    print(f"Latency basis          : {timestamp_basis}")
    if top_level_updated_at is not None:
        print(f"Store updated at (UTC) : {format_timestamp(top_level_updated_at)}")
    if source.local_file_message:
        print(f"Local file note        : {source.local_file_message}")
    if source.mongo_message:
        print(f"Mongo fallback         : {source.mongo_message}")
    print()

    if not analyzed:
        print("No RCA records had enough timestamp data to calculate latency.")
        if skipped:
            print()
            print("Skipped records")
            print("---------------")
            for item in skipped[:10]:
                print(f"- {item.incident_id}: {item.reason}")
            if len(skipped) > 10:
                print(f"- ... and {len(skipped) - 10} more")
        return

    avg_from_last = average_duration([item.latency_from_last for item in analyzed])
    avg_from_first = average_duration([item.latency_from_first for item in analyzed])
    median_from_last = median_duration([item.latency_from_last for item in analyzed])
    avg_from_match = average_duration(
        [item.latency_from_match for item in analyzed if item.latency_from_match is not None]
    )
    negative_latencies = [item for item in analyzed if item.latency_from_last.total_seconds() < 0]
    fastest = min(analyzed, key=lambda item: item.latency_from_last.total_seconds())
    slowest = max(analyzed, key=lambda item: item.latency_from_last.total_seconds())

    print("Effective summary")
    print("-----------------")
    print(f"Primary average latency : {format_duration(avg_from_last)}")
    print(f"Median latency          : {format_duration(median_from_last)}")
    print(f"Fastest RCA             : {fastest.incident_id} in {format_duration(fastest.latency_from_last)}")
    print(f"Slowest RCA             : {slowest.incident_id} in {format_duration(slowest.latency_from_last)}")
    print(f"Status mix              : {count_by(analyzed, 'status')}")
    print(f"Classification mix      : {count_by(analyzed, 'classification')}")
    if negative_latencies:
        print(f"Clock skew warning      : {len(negative_latencies)} incident(s) had negative latency")
    print()

    print("Average latency")
    print("---------------")
    print(f"Last matched log -> RCA generated : {format_duration(avg_from_last)}")
    print(f"Median last log -> RCA generated  : {format_duration(median_from_last)}")
    print(f"First matched log -> RCA generated: {format_duration(avg_from_first)}")
    if avg_from_match is not None:
        print(f"Correlation matched_at -> RCA write: {format_duration(avg_from_match)}")
    print()

    visible = analyzed if limit == 0 else analyzed[: max(limit, 0)]
    rows: list[list[str]] = []
    for index, item in enumerate(visible, start=1):
        rows.append(
            [
                str(index),
                shorten(item.incident_id, 32),
                shorten(item.rule_id, 28),
                item.status,
                shorten(item.classification, 16),
                str(item.log_count),
                format_timestamp(item.last_log_at),
                format_timestamp(item.generated_at),
                format_duration(item.latency_from_last),
                format_duration(item.latency_from_first),
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
                "Classification",
                "Logs",
                "Last Log (UTC)",
                "RCA Generated (UTC)",
                "Latency",
                "From First",
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
    allowed_statuses = {
        status.strip().lower()
        for status in args.status.split(",")
        if status.strip()
    }

    try:
        source = resolve_data_source(args, results_file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    payload = source.payload
    records = extract_records(payload)
    source_doc_timestamps: dict[tuple[str, str], datetime] | None = None
    timestamp_basis = "Stored RCA evidence timestamps"

    if not args.no_es_lookup:
        try:
            es_settings = resolve_elasticsearch_settings(args)
            source_doc_timestamps = fetch_source_doc_timestamps(records, es_settings)
            timestamp_basis = "Source log @timestamp fetched from Elasticsearch using matched doc IDs"
            analyzed, skipped = build_latency_records(
                records,
                allowed_statuses,
                source_doc_timestamps=source_doc_timestamps,
                fallback_index=str(es_settings.get("source_index_fallback") or "*"),
            )
        except RuntimeError as exc:
            print(f"Warning: Elasticsearch lookup failed, falling back to stored RCA timestamps. {exc}")
            analyzed, skipped = build_latency_records(records, allowed_statuses)
    else:
        analyzed, skipped = build_latency_records(records, allowed_statuses)

    print_report(results_file, source, payload, analyzed, skipped, args.limit, timestamp_basis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
