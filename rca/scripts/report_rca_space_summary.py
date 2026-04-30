#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


@dataclass
class MongoCollectionUsage:
    name: str
    count: int
    data_size: int
    storage_size: int
    index_size: int
    total_size: int
    avg_obj_size: int
    indexes: int
    exists: bool


@dataclass
class MongoSummary:
    database: str
    data_size: int
    storage_size: int
    index_size: int
    collections: list[MongoCollectionUsage]


@dataclass
class ElasticsearchIndexUsage:
    name: str
    docs_count: int
    store_size: int


@dataclass
class ElasticsearchSummary:
    address: str
    indices: list[ElasticsearchIndexUsage]


@dataclass
class RedisKeyUsage:
    key: str
    key_type: str
    memory_usage: int


@dataclass
class RedisSummary:
    address: str
    database: int
    pattern: str
    db_total_keys: int
    matched_keys: int
    total_memory: int
    sample_keys: list[str]
    connection_note: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_rca_config() -> Path:
    return repo_root() / "log_rca_engine" / "config" / "config.yml"


def default_correlation_config() -> Path:
    return repo_root() / "log_correlation_engine" / "config" / "config.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print a readable RCA storage-space summary across MongoDB collections, "
            "RCA-generated Elasticsearch indices, and the Redis RCA namespace."
        )
    )
    parser.add_argument(
        "--rca-config",
        default=str(default_rca_config()),
        help="Path to log_rca_engine config.yml.",
    )
    parser.add_argument(
        "--correlation-config",
        default=str(default_correlation_config()),
        help="Path to log_correlation_engine config.yml.",
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
        default="",
        help="Optional Redis key pattern override. Default is derived from redis.key_prefix.",
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
        default=50,
        help="Redis SCAN count hint used while walking RCA keys.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Network timeout for Elasticsearch and Redis calls.",
    )
    parser.add_argument(
        "--redis-timeout-seconds",
        type=float,
        default=75.0,
        help="Redis-specific timeout in seconds. Use this when Redis scans can take close to a minute.",
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


def load_sectioned_yaml(path: Path) -> dict[str, Any]:
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
                if key in {"addresses", "files"}:
                    section[key] = []
                    current_list_key = key
                    current_subsection = None
                else:
                    section[key] = {}
                    current_subsection = key
                    current_list_key = None
            else:
                if key == "addresses":
                    section[key] = []
                    current_list_key = key
                    current_subsection = None
                else:
                    section[key] = parse_scalar(raw_value)
                    current_subsection = None
                    current_list_key = None
            continue

        if indent == 4 and current_subsection and ":" in stripped:
            subsection = section.get(current_subsection)
            if isinstance(subsection, dict):
                key, raw_value = stripped.split(":", 1)
                subsection[key.strip()] = parse_scalar(raw_value)
            continue

        if indent >= 4 and stripped.startswith("- ") and current_list_key:
            list_value = section.get(current_list_key)
            if isinstance(list_value, list):
                list_value.append(parse_scalar(stripped[2:]))

    return data


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


def resolve_mongo_settings(args: argparse.Namespace, rca_cfg: dict[str, Any]) -> dict[str, Any]:
    mongo = rca_cfg.get("mongo_sync", {})
    return {
        "uri": str(args.mongo_uri or mongo.get("uri") or "").strip(),
        "database": str(args.mongo_db or mongo.get("database") or "").strip(),
        "collections": [
            str(value).strip()
            for value in [
                mongo.get("rules_collection"),
                mongo.get("topology_collection"),
                mongo.get("results_collection"),
                mongo.get("state_collection"),
                mongo.get("snapshot_collection"),
            ]
            if str(value or "").strip()
        ],
    }


def resolve_elasticsearch_settings(
    args: argparse.Namespace,
    rca_cfg: dict[str, Any],
    correlation_cfg: dict[str, Any],
) -> dict[str, Any]:
    correlation_es = correlation_cfg.get("elasticsearch", {})
    rca_es = rca_cfg.get("elasticsearch", {})
    addresses = correlation_es.get("addresses") or rca_es.get("addresses") or []
    address = str(args.es_url or (addresses[0] if addresses else "")).strip()
    index_patterns = []
    for value in [correlation_es.get("index"), correlation_es.get("current_index")]:
        pattern = str(value or "").strip()
        if pattern:
            if "*" not in pattern:
                pattern = pattern + "*"
            index_patterns.append(pattern)
    return {
        "address": address,
        "username": str(args.es_username or correlation_es.get("username") or rca_es.get("username") or "").strip(),
        "password": str(args.es_password or correlation_es.get("password") or rca_es.get("password") or "").strip(),
        "api_key": str(args.es_api_key or correlation_es.get("api_key") or rca_es.get("api_key") or "").strip(),
        "patterns": index_patterns,
        "timeout_seconds": max(float(args.timeout_seconds), 0.1),
    }


def resolve_redis_settings(args: argparse.Namespace, correlation_cfg: dict[str, Any]) -> dict[str, Any]:
    redis_cfg = correlation_cfg.get("redis", {})
    address = str(redis_cfg.get("address") or "").strip()
    host = str(args.redis_host or "").strip()
    port = int(args.redis_port or 0)
    if not host and address:
        if ":" in address:
            host, raw_port = address.rsplit(":", 1)
            if not port:
                try:
                    port = int(raw_port)
                except ValueError:
                    port = 6379
        else:
            host = address
    if not port:
        port = 6379

    key_prefix = str(redis_cfg.get("key_prefix") or "Rca").strip() or "Rca"
    configured_pattern = str(args.redis_pattern or f"{key_prefix}*").strip()
    patterns: list[str] = []
    for candidate in [configured_pattern, configured_pattern.upper(), configured_pattern.lower()]:
        candidate = candidate.strip()
        if candidate and candidate not in patterns:
            patterns.append(candidate)
    return {
        "host": host,
        "port": port,
        "db": int(args.redis_db if args.redis_db else redis_cfg.get("db") or 0),
        "username": str(args.redis_username or redis_cfg.get("username") or "").strip(),
        "password": str(args.redis_password or redis_cfg.get("password") or "").strip(),
        "pattern": configured_pattern,
        "patterns": patterns,
        "timeout_seconds": max(float(args.redis_timeout_seconds), 0.1),
        "scan_count": max(int(args.redis_scan_count), 1),
    }


def fetch_mongo_summary(settings: dict[str, Any]) -> MongoSummary:
    mongosh_path = shutil.which("mongosh")
    if not mongosh_path:
        raise RuntimeError("mongosh command not found in PATH.")

    uri = str(settings.get("uri") or "").strip()
    database = str(settings.get("database") or "").strip()
    collections = [str(value).strip() for value in settings.get("collections") or [] if str(value).strip()]
    if not uri:
        raise RuntimeError("MongoDB URI is missing.")
    if not database:
        raise RuntimeError("MongoDB database name is missing.")
    if not collections:
        raise RuntimeError("No MongoDB RCA collections were configured.")

    query = (
        f"const dbName = {json.dumps(database)};"
        f"const collNames = {json.dumps(collections)};"
        "const targetDb = db.getSiblingDB(dbName);"
        "const collStats = collNames.map((name) => {"
        "  const exists = targetDb.getCollectionInfos({name}).length > 0;"
        "  if (!exists) {"
        "    return {name, exists:false, count:0, size:0, storageSize:0, totalIndexSize:0, avgObjSize:0, nindexes:0};"
        "  }"
        "  const stats = targetDb.getCollection(name).stats();"
        "  return {"
        "    name,"
        "    exists:true,"
        "    count:Number(stats.count || 0),"
        "    size:Number(stats.size || 0),"
        "    storageSize:Number(stats.storageSize || 0),"
        "    totalIndexSize:Number(stats.totalIndexSize || 0),"
        "    avgObjSize:Number(stats.avgObjSize || 0),"
        "    nindexes:Number(stats.nindexes || 0)"
        "  };"
        "});"
        "const dbStats = targetDb.stats();"
        "print(JSON.stringify({"
        "  database: dbName,"
        "  dataSize: Number(dbStats.dataSize || 0),"
        "  storageSize: Number(dbStats.storageSize || 0),"
        "  indexSize: Number(dbStats.indexSize || 0),"
        "  collections: collStats"
        "}));"
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

    collections_summary: list[MongoCollectionUsage] = []
    for item in payload.get("collections", []):
        collections_summary.append(
            MongoCollectionUsage(
                name=normalize_text(item.get("name")),
                count=int(item.get("count") or 0),
                data_size=int(item.get("size") or 0),
                storage_size=int(item.get("storageSize") or 0),
                index_size=int(item.get("totalIndexSize") or 0),
                total_size=int(item.get("storageSize") or 0) + int(item.get("totalIndexSize") or 0),
                avg_obj_size=int(item.get("avgObjSize") or 0),
                indexes=int(item.get("nindexes") or 0),
                exists=bool(item.get("exists", True)),
            )
        )

    return MongoSummary(
        database=normalize_text(payload.get("database")),
        data_size=int(payload.get("dataSize") or 0),
        storage_size=int(payload.get("storageSize") or 0),
        index_size=int(payload.get("indexSize") or 0),
        collections=collections_summary,
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
            import base64

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
    patterns = [str(value).strip() for value in settings.get("patterns") or [] if str(value).strip()]
    if not address:
        raise RuntimeError("Elasticsearch address is missing.")
    if not patterns:
        raise RuntimeError("No RCA Elasticsearch index patterns were configured.")

    client = ElasticsearchHttpClient(
        address=address,
        username=str(settings.get("username") or ""),
        password=str(settings.get("password") or ""),
        api_key=str(settings.get("api_key") or ""),
        timeout_seconds=float(settings.get("timeout_seconds") or 20.0),
    )

    seen: dict[str, ElasticsearchIndexUsage] = {}
    for pattern in patterns:
        encoded_pattern = parse.quote(pattern, safe="*,-,_")
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
            seen[name] = ElasticsearchIndexUsage(
                name=name,
                docs_count=parse_intish(item.get("docs.count")),
                store_size=parse_intish(item.get("store.size")),
            )

    return ElasticsearchSummary(address=address, indices=sorted(seen.values(), key=lambda item: item.store_size, reverse=True))


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
                    self.connection_note = "Redis accepted an unauthenticated connection, so the configured AUTH step was skipped."
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
    if not host or not port:
        raise RuntimeError("Redis host/port is missing.")

    client = RedisRespClient(
        host=host,
        port=port,
        db=int(settings.get("db") or 0),
        username=str(settings.get("username") or ""),
        password=str(settings.get("password") or ""),
        timeout_seconds=float(settings.get("timeout_seconds") or 20.0),
    )

    pattern = str(settings.get("pattern") or "Rca*")
    patterns = [str(value).strip() for value in settings.get("patterns") or [pattern] if str(value).strip()]
    scan_count = max(int(settings.get("scan_count") or 50), 1)
    matched_keys = 0
    sample_keys: list[str] = []
    notes: list[str] = []
    seen_keys: set[str] = set()
    try:
        client.connect()
        used_memory = 0
        db_total_keys = 0

        try:
            memory_info_raw = str(client.command("INFO", "memory") or "")
            for line in memory_info_raw.splitlines():
                if line.startswith("used_memory:"):
                    used_memory = parse_intish(line.split(":", 1)[1])
                    break
        except Exception as exc:
            notes.append(f"Could not read Redis memory info: {exc}")

        try:
            db_total_keys = int(client.command("DBSIZE") or 0)
        except Exception as exc:
            notes.append(f"Could not read Redis DBSIZE: {exc}")

        for scan_pattern in patterns:
            cursor = "0"
            while True:
                try:
                    response = client.command("SCAN", cursor, "MATCH", scan_pattern, "COUNT", str(scan_count))
                except Exception as exc:
                    if matched_keys or sample_keys:
                        notes.append(f"Redis scan stopped early after collecting {matched_keys} matched key(s): {exc}")
                        cursor = "0"
                        break
                    raise
                if not isinstance(response, list) or len(response) != 2:
                    raise RuntimeError("Unexpected Redis SCAN response")
                cursor = str(response[0])
                keys = response[1] if isinstance(response[1], list) else []
                for key in keys:
                    key_name = str(key)
                    if key_name in seen_keys:
                        continue
                    seen_keys.add(key_name)
                    matched_keys += 1
                    if len(sample_keys) < max(top_limit, 0):
                        sample_keys.append(key_name)
                if cursor == "0":
                    break

        if matched_keys == 0 and db_total_keys > 0:
            notes.append(
                f"No keys matched the configured Redis namespace patterns ({', '.join(patterns)}). "
                "Showing DB-wide memory and a DB-wide key sample instead."
            )
            cursor = "0"
            while len(sample_keys) < max(top_limit, 0):
                response = client.command("SCAN", cursor, "COUNT", str(scan_count))
                if not isinstance(response, list) or len(response) != 2:
                    raise RuntimeError("Unexpected Redis SCAN response")
                cursor = str(response[0])
                keys = response[1] if isinstance(response[1], list) else []
                for key in keys:
                    key_name = str(key)
                    if key_name in seen_keys:
                        continue
                    seen_keys.add(key_name)
                    sample_keys.append(key_name)
                    if len(sample_keys) >= max(top_limit, 0):
                        break
                if cursor == "0":
                    break
    finally:
        client.close()

    if client.connection_note:
        notes.insert(0, client.connection_note)

    return RedisSummary(
        address=f"{host}:{port}",
        database=int(settings.get("db") or 0),
        pattern=pattern,
        db_total_keys=db_total_keys,
        matched_keys=matched_keys,
        total_memory=used_memory,
        sample_keys=sample_keys,
        connection_note=" ".join(note.strip() for note in notes if note.strip()),
    )


def print_summary_header(mongo: MongoSummary | None, es: ElasticsearchSummary | None, redis: RedisSummary | None) -> None:
    mongo_total = sum(item.total_size for item in mongo.collections) if mongo else 0
    es_total = sum(item.store_size for item in es.indices) if es else 0
    redis_total = redis.total_memory if redis else 0
    observed_total = mongo_total + es_total + redis_total

    print("RCA Space Summary")
    print("=================")
    print(f"Generated at (UTC)     : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Effective summary")
    print("-----------------")
    print(f"Observed RCA-owned total : {format_bytes(observed_total)}")
    if mongo:
        print(f"MongoDB collections      : {format_bytes(mongo_total)} across {len(mongo.collections)} collection(s)")
    if es:
        print(f"Elasticsearch indices    : {format_bytes(es_total)} across {len(es.indices)} index(es)")
    if redis:
        print(f"Redis selected DB        : {format_bytes(redis_total)} in db {redis.database}")
    print("Note                     : MongoDB and Elasticsearch totals are RCA-owned. Redis is reported at selected-DB level, with RCA key count shown separately.")
    print()

    print("Database-wise storage")
    print("---------------------")
    rows: list[list[str]] = []
    if mongo:
        rows.append(
            [
                "1",
                "MongoDB",
                mongo.database,
                "RCA collections",
                format_bytes(mongo_total),
            ]
        )
    if redis:
        redis_scope = (
            f"Selected DB memory ({redis.matched_keys} RCA keys matched)"
            if redis.matched_keys > 0
            else "Selected DB memory (DB-wide fallback)"
        )
        rows.append(
            [
                str(len(rows) + 1),
                "Redis",
                f"db {redis.database}",
                redis_scope,
                format_bytes(redis_total),
            ]
        )
    if es:
        rows.append(
            [
                str(len(rows) + 1),
                "Elasticsearch",
                "-",
                "RCA indices",
                format_bytes(es_total),
            ]
        )
    rows.append(
        [
            str(len(rows) + 1),
            "TOTAL",
            "-",
            "All observed RCA storage",
            format_bytes(observed_total),
        ]
    )
    print(render_table(["S/N", "Store", "DB / Scope", "What Was Counted", "Used"], rows))
    print()


def print_mongo_section(summary: MongoSummary) -> None:
    print("MongoDB")
    print("-------")
    print(f"Database                : {summary.database}")
    print(f"Database data size      : {format_bytes(summary.data_size)}")
    print(f"Database storage size   : {format_bytes(summary.storage_size)}")
    print(f"Database index size     : {format_bytes(summary.index_size)}")
    print()

    rows: list[list[str]] = []
    for item in summary.collections:
        rows.append(
            [
                item.name,
                "yes" if item.exists else "no",
                format_int(item.count),
                format_bytes(item.data_size),
                format_bytes(item.storage_size),
                format_bytes(item.index_size),
                format_bytes(item.total_size),
            ]
        )

    print(
        render_table(
            ["Collection", "Exists", "Docs", "Data", "Storage", "Indexes", "Total"],
            rows,
        )
    )
    print()


def print_elasticsearch_section(summary: ElasticsearchSummary) -> None:
    print("Elasticsearch")
    print("-------------")
    print(f"Address                 : {summary.address}")
    print(f"RCA index count         : {len(summary.indices)}")
    print(f"RCA total store size    : {format_bytes(sum(item.store_size for item in summary.indices))}")
    print()

    rows = [
        [item.name, format_int(item.docs_count), format_bytes(item.store_size)]
        for item in summary.indices
    ]
    if rows:
        print(render_table(["Index", "Docs", "Store"], rows))
    else:
        print("No RCA Elasticsearch indices were found.")
    print()


def print_redis_section(summary: RedisSummary) -> None:
    print("Redis")
    print("-----")
    print(f"Address                 : {summary.address}")
    print(f"Database                : {summary.database}")
    print(f"Key pattern             : {summary.pattern}")
    print(f"Total DB keys           : {summary.db_total_keys}")
    print(f"Matched RCA keys        : {summary.matched_keys}")
    print(f"Selected DB memory      : {format_bytes(summary.total_memory)}")
    if summary.connection_note:
        print(f"Connection note         : {summary.connection_note}")
    print()

    rows: list[list[str]] = []
    for index, key in enumerate(summary.sample_keys, start=1):
        rows.append([str(index), shorten(key, 72)])
    if rows:
        print(render_table(["S/N", "Sample RCA Key"], rows))
    else:
        print("No Redis keys were available to sample.")
    print()


def main() -> int:
    args = parse_args()
    rca_cfg = load_sectioned_yaml(Path(args.rca_config).expanduser().resolve())
    correlation_cfg = load_sectioned_yaml(Path(args.correlation_config).expanduser().resolve())

    mongo_summary: MongoSummary | None = None
    es_summary: ElasticsearchSummary | None = None
    redis_summary: RedisSummary | None = None
    warnings: list[str] = []

    if not args.no_mongo:
        try:
            mongo_summary = fetch_mongo_summary(resolve_mongo_settings(args, rca_cfg))
        except Exception as exc:
            warnings.append(f"MongoDB summary skipped: {exc}")

    if not args.no_elasticsearch:
        try:
            es_summary = fetch_elasticsearch_summary(resolve_elasticsearch_settings(args, rca_cfg, correlation_cfg))
        except Exception as exc:
            warnings.append(f"Elasticsearch summary skipped: {exc}")

    if not args.no_redis:
        try:
            redis_summary = fetch_redis_summary(resolve_redis_settings(args, correlation_cfg), args.top_redis_keys)
        except Exception as exc:
            warnings.append(f"Redis summary skipped: {exc}")

    print_summary_header(mongo_summary, es_summary, redis_summary)

    if mongo_summary:
        print_mongo_section(mongo_summary)
    if es_summary:
        print_elasticsearch_section(es_summary)
    if redis_summary:
        print_redis_section(redis_summary)

    if warnings:
        print("Warnings")
        print("--------")
        for warning in warnings:
            print(f"- {warning}")
        print()

    if not mongo_summary and not es_summary and not redis_summary:
        print("No storage summaries could be collected.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
