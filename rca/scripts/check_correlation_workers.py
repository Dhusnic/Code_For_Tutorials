#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class WorkerHeartbeat:
    worker_id: str
    updated_at: datetime | None
    age: timedelta | None
    alive: bool


@dataclass
class WorkerActivity:
    worker_id: str
    completed_shards: int
    failed_shards: int
    last_completed_at: datetime | None
    last_status: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config_path() -> Path:
    return repo_root() / "log_correlation_engine" / "config" / "config.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify distributed correlation-engine workers from Redis: "
            "active heartbeats, stale registry entries, and recent shard completions."
        )
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Path to log_correlation_engine config.yml.",
    )
    parser.add_argument("--redis-host", default="", help="Optional Redis host override.")
    parser.add_argument("--redis-port", type=int, default=0, help="Optional Redis port override.")
    parser.add_argument("--redis-db", type=int, default=-1, help="Optional Redis DB override.")
    parser.add_argument("--redis-username", default="", help="Optional Redis username override.")
    parser.add_argument("--redis-password", default="", help="Optional Redis password override.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="Socket timeout for Redis operations.",
    )
    parser.add_argument(
        "--expected-workers",
        type=int,
        default=0,
        help="Optional expected active worker count. Use 7 for your current deployment.",
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=30,
        help="How far back to scan shard completions for worker activity.",
    )
    parser.add_argument(
        "--max-shard-results",
        type=int,
        default=500,
        help="Maximum shard-result documents to inspect from Redis.",
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
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_duration(raw: Any, default_seconds: float) -> timedelta:
    text = str(raw or "").strip()
    if not text:
        return timedelta(seconds=default_seconds)
    total = 0.0
    number = ""
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    index = 0
    while index < len(text):
        char = text[index]
        if char.isdigit() or char == ".":
            number += char
            index += 1
            continue
        if not number:
            index += 1
            continue
        if text.startswith("ms", index):
            total += float(number) * units["ms"]
            number = ""
            index += 2
            continue
        if char in units:
            total += float(number) * units[char]
            number = ""
            index += 1
            continue
        index += 1
    if number:
        total += float(number)
    return timedelta(seconds=total if total > 0 else default_seconds)


def load_sectioned_config(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    config: dict[str, dict[str, Any]] = {}
    current_section = ""
    current_subsection = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1].strip()
            current_subsection = ""
            config.setdefault(current_section, {})
            continue
        if indent == 2 and stripped.endswith(":"):
            current_subsection = stripped[:-1].strip()
            continue
        if indent != 2 or ":" not in stripped or current_subsection:
            continue

        key, raw_value = stripped.split(":", 1)
        config.setdefault(current_section, {})[key.strip()] = parse_scalar(raw_value)
    return config


def resolve_settings(args: argparse.Namespace) -> dict[str, Any]:
    sections = load_sectioned_config(Path(args.config).expanduser().resolve())
    redis_cfg = sections.get("redis", {})
    distributed_cfg = sections.get("distributed", {})

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

    db = args.redis_db if args.redis_db >= 0 else int(redis_cfg.get("db") or 0)
    key_prefix = str(redis_cfg.get("key_prefix") or "Rca").strip() or "Rca"
    lease_ttl = parse_duration(distributed_cfg.get("lease_ttl"), 45.0)
    heartbeat_interval = parse_duration(distributed_cfg.get("lease_heartbeat_interval"), 15.0)
    return {
        "host": host,
        "port": port,
        "db": db,
        "username": str(args.redis_username or redis_cfg.get("username") or "").strip(),
        "password": str(args.redis_password or redis_cfg.get("password") or "").strip(),
        "timeout_seconds": max(float(args.timeout_seconds), 0.1),
        "key_prefix": key_prefix,
        "lease_ttl": lease_ttl,
        "heartbeat_interval": heartbeat_interval,
        "expected_workers": max(int(args.expected_workers), 0),
        "lookback": timedelta(minutes=max(int(args.lookback_minutes), 1)),
        "max_shard_results": max(int(args.max_shard_results), 1),
    }


def parse_timestamp(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, tail = text.split(".", 1)
        tz_index = max(tail.find("+"), tail.find("-"))
        if tz_index >= 0:
            fraction = tail[:tz_index]
            suffix = tail[tz_index:]
        else:
            fraction = tail
            suffix = ""
        digits = "".join(char for char in fraction if char.isdigit())
        if digits:
            digits = (digits[:6]).ljust(6, "0")
            text = f"{head}.{digits}{suffix}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(value: timedelta | None) -> str:
    if value is None:
        return "-"
    total_seconds = int(abs(value.total_seconds()))
    sign = "-" if value.total_seconds() < 0 else ""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{sign}{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{sign}{minutes}m {seconds:02d}s"
    return f"{sign}{seconds}s"


class RedisRespClient:
    def __init__(self, host: str, port: int, timeout_seconds: float) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout_seconds)
        self.sock.settimeout(timeout_seconds)
        self.reader = self.sock.makefile("rb")

    def close(self) -> None:
        try:
            self.reader.close()
        finally:
            self.sock.close()

    def execute(self, *parts: Any) -> Any:
        payload = self._encode(parts)
        self.sock.sendall(payload)
        return self._read()

    def _encode(self, parts: tuple[Any, ...]) -> bytes:
        chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            data = str(part).encode("utf-8")
            chunks.append(f"${len(data)}\r\n".encode("utf-8"))
            chunks.append(data + b"\r\n")
        return b"".join(chunks)

    def _readline(self) -> bytes:
        line = self.reader.readline()
        if not line:
            raise RuntimeError("Redis connection closed unexpectedly")
        return line.rstrip(b"\r\n")

    def _read(self) -> Any:
        prefix = self.reader.read(1)
        if not prefix:
            raise RuntimeError("Redis connection closed unexpectedly")
        if prefix == b"+":
            return self._readline().decode("utf-8")
        if prefix == b"-":
            raise RuntimeError(self._readline().decode("utf-8"))
        if prefix == b":":
            return int(self._readline())
        if prefix == b"$":
            length = int(self._readline())
            if length == -1:
                return None
            data = self.reader.read(length)
            self.reader.read(2)
            return data.decode("utf-8")
        if prefix == b"*":
            length = int(self._readline())
            if length == -1:
                return None
            return [self._read() for _ in range(length)]
        raise RuntimeError(f"Unsupported Redis response prefix: {prefix!r}")


def authenticate_redis(client: RedisRespClient, settings: dict[str, Any]) -> None:
    password = settings["password"]
    username = settings["username"]
    if not password:
        return
    try:
        if username:
            client.execute("AUTH", username, password)
        else:
            client.execute("AUTH", password)
    except RuntimeError as exc:
        message = str(exc)
        if "called without any password configured for the default user" in message:
            return
        raise


def worker_registry_key(prefix: str, worker_id: str) -> str:
    encoded = base64.urlsafe_b64encode(worker_id.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{prefix}:distributed:worker:{encoded}"


def fetch_worker_heartbeats(client: RedisRespClient, settings: dict[str, Any]) -> tuple[list[WorkerHeartbeat], list[str]]:
    prefix = settings["key_prefix"]
    registry_set = f"{prefix}:distributed:workers"
    raw_ids = client.execute("SMEMBERS", registry_set) or []
    worker_ids = sorted(str(item).strip() for item in raw_ids if str(item).strip())
    if not worker_ids:
        return [], []

    keys = [worker_registry_key(prefix, worker_id) for worker_id in worker_ids]
    raw_payloads = client.execute("MGET", *keys) or []
    now = datetime.now(timezone.utc)
    ttl = settings["lease_ttl"]

    active: list[WorkerHeartbeat] = []
    stale: list[str] = []
    for worker_id, raw_payload in zip(worker_ids, raw_payloads):
        if raw_payload is None:
            stale.append(worker_id)
            continue
        try:
            payload = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            stale.append(worker_id)
            continue
        updated_at = parse_timestamp(payload.get("updated_at"))
        age = now - updated_at if updated_at is not None else None
        alive = updated_at is not None and age is not None and age <= ttl
        active.append(
            WorkerHeartbeat(
                worker_id=worker_id,
                updated_at=updated_at,
                age=age,
                alive=alive,
            )
        )
    return active, stale


def scan_keys(client: RedisRespClient, pattern: str, limit: int) -> list[str]:
    cursor = "0"
    keys: list[str] = []
    while True:
        response = client.execute("SCAN", cursor, "MATCH", pattern, "COUNT", min(limit, 500))
        if not isinstance(response, list) or len(response) != 2:
            break
        cursor = str(response[0])
        batch = response[1] or []
        for key in batch:
            text = str(key).strip()
            if text:
                keys.append(text)
                if len(keys) >= limit:
                    return keys
        if cursor == "0":
            break
    return keys


def fetch_recent_worker_activity(client: RedisRespClient, settings: dict[str, Any]) -> dict[str, WorkerActivity]:
    prefix = settings["key_prefix"]
    pattern = f"{prefix}:distributed:shard_result:*"
    keys = scan_keys(client, pattern, settings["max_shard_results"])
    if not keys:
        return {}

    raw_payloads = client.execute("MGET", *keys) or []
    cutoff = datetime.now(timezone.utc) - settings["lookback"]
    by_worker: dict[str, WorkerActivity] = {}

    for raw_payload in raw_payloads:
        if raw_payload is None:
            continue
        try:
            payload = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            continue
        completed_at = parse_timestamp(payload.get("completed_at"))
        worker_id = str(payload.get("worker_id") or "").strip()
        status = str(payload.get("status") or "").strip().lower()
        if not worker_id or completed_at is None or completed_at < cutoff:
            continue
        current = by_worker.get(worker_id)
        completed_increment = 1 if status == "completed" else 0
        failed_increment = 1 if status == "failed" else 0
        if current is None:
            by_worker[worker_id] = WorkerActivity(
                worker_id=worker_id,
                completed_shards=completed_increment,
                failed_shards=failed_increment,
                last_completed_at=completed_at,
                last_status=status or "-",
            )
            continue
        current.completed_shards += completed_increment
        current.failed_shards += failed_increment
        if current.last_completed_at is None or completed_at > current.last_completed_at:
            current.last_completed_at = completed_at
            current.last_status = status or "-"
    return by_worker


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render_row(values: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    separator = "  ".join("-" * width for width in widths)
    return "\n".join([render_row(headers), separator, *[render_row(row) for row in rows]])


def main() -> int:
    args = parse_args()
    try:
        settings = resolve_settings(args)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    host = settings["host"]
    port = settings["port"]
    if not host:
        print("Error: Redis host is missing. Pass --redis-host or configure redis.address.")
        return 1

    client = None
    try:
        client = RedisRespClient(host, port, settings["timeout_seconds"])
        authenticate_redis(client, settings)
        if settings["db"]:
            client.execute("SELECT", settings["db"])

        heartbeats, stale = fetch_worker_heartbeats(client, settings)
        activity = fetch_recent_worker_activity(client, settings)
    except Exception as exc:
        print(f"Error: failed to query Redis at {host}:{port}: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    live_workers = [item for item in heartbeats if item.alive]
    expected = settings["expected_workers"]
    workers_with_recent_success = sorted(
        worker_id for worker_id, item in activity.items() if item.completed_shards > 0
    )
    workers_with_recent_failure = sorted(
        worker_id for worker_id, item in activity.items() if item.failed_shards > 0
    )

    print("Correlation Worker Health")
    print("=========================")
    print(f"Redis              : {host}:{port} (db {settings['db']})")
    print(f"Key prefix         : {settings['key_prefix']}")
    print(f"Lease TTL          : {format_duration(settings['lease_ttl'])}")
    print(f"Heartbeat interval : {format_duration(settings['heartbeat_interval'])}")
    print(f"Active workers     : {len(live_workers)}")
    print(f"Registry entries   : {len(heartbeats)}")
    print(f"Stale entries      : {len(stale)}")
    if expected > 0:
        verdict = "OK" if len(live_workers) == expected else "MISMATCH"
        print(f"Expected workers   : {expected} ({verdict})")
    print(f"Activity lookback  : {format_duration(settings['lookback'])}")
    print(f"Recent shard OK    : {len(workers_with_recent_success)} workers")
    print(f"Recent shard fail  : {len(workers_with_recent_failure)} workers")
    print()

    if heartbeats:
        rows: list[list[str]] = []
        for item in heartbeats:
            recent = activity.get(item.worker_id)
            rows.append(
                [
                    item.worker_id,
                    "yes" if item.alive else "no",
                    format_timestamp(item.updated_at),
                    format_duration(item.age),
                    str(recent.completed_shards if recent else 0),
                    str(recent.failed_shards if recent else 0),
                    str(recent.last_status if recent else "-"),
                    format_timestamp(recent.last_completed_at if recent else None),
                ]
            )
        print("Worker registry")
        print("---------------")
        print(
            render_table(
                [
                    "Worker ID",
                    "Alive",
                    "Heartbeat UTC",
                    "Age",
                    "Recent OK",
                    "Recent Fail",
                    "Last Status",
                    "Last Shard UTC",
                ],
                rows,
            )
        )
    else:
        print("No active worker registry entries were found.")

    if stale:
        print()
        print("Stale registry entries")
        print("----------------------")
        for worker_id in stale:
            print(f"- {worker_id}")

    alive_without_success = sorted(
        worker.worker_id
        for worker in live_workers
        if worker.worker_id not in activity or activity[worker.worker_id].completed_shards == 0
    )
    if alive_without_success:
        print()
        print("Alive But No Recent Successful Shard Completions")
        print("-----------------------------------------------")
        for worker_id in alive_without_success:
            print(f"- {worker_id}")
        print("This can be normal if one worker owns the hot organization and others had nothing to assist.")

    alive_with_only_failures = sorted(
        worker.worker_id
        for worker in live_workers
        if worker.worker_id in activity
        and activity[worker.worker_id].completed_shards == 0
        and activity[worker.worker_id].failed_shards > 0
    )
    if alive_with_only_failures:
        print()
        print("Alive Workers With Only Recent Failed Shards")
        print("-------------------------------------------")
        for worker_id in alive_with_only_failures:
            print(f"- {worker_id}")

    print()
    if expected > 0 and len(live_workers) != expected:
        print("Verdict: not all expected workers are currently alive in Redis.")
    elif alive_with_only_failures:
        print("Verdict: all expected workers appear alive, but some workers only show recent failed shard executions.")
    elif workers_with_recent_success:
        print("Verdict: worker cluster looks healthy. Redis sees live workers and recent successful shard executions.")
    elif live_workers:
        print("Verdict: workers appear alive, but Redis does not show recent successful shard executions in the lookback window.")
    else:
        print("Verdict: no live distributed workers were found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
