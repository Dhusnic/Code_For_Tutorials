#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib import error, request


def log(state: str, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{state.upper()}] {message}")


def strip_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {"'", '"'}:
        return trimmed[1:-1]
    return trimmed


def read_yaml_section_value(path: Path, section: str, key: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    inside_section = False
    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            inside_section = line == f"{section}:"
            continue
        if not inside_section:
            continue
        if raw.startswith("  ") and not raw.startswith("    "):
            prefix = f"{key}:"
            stripped = line.strip()
            if stripped.startswith(prefix):
                return strip_quotes(stripped[len(prefix) :].strip())
    return ""


def read_yaml_section_list(path: Path, section: str, key: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    inside_section = False
    inside_list = False
    values: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            inside_section = line == f"{section}:"
            inside_list = False
            continue
        if not inside_section:
            continue
        if raw.startswith("  ") and not raw.startswith("    "):
            if line.strip() == f"{key}:":
                inside_list = True
                continue
            inside_list = False
            continue
        if inside_list and raw.startswith("    - "):
            values.append(strip_quotes(line.strip()[2:].strip()))
            continue
        if inside_list and not raw.startswith("    "):
            inside_list = False
    return values


def resolve_config_path(base_path: Path, raw_path: str) -> Path | None:
    if not raw_path.strip():
        return None
    candidate = Path(strip_quotes(raw_path))
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_path.parent / candidate).resolve()


def resolve_path_from_root(root: Path, raw_path: str) -> Path | None:
    if not raw_path.strip():
        return None
    candidate = Path(strip_quotes(raw_path))
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def resolve_executable(*candidates: str) -> str:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"executable not found: {', '.join(candidates)}")


def resolve_kafka_consumer_groups_executable() -> str:
    candidates = [
        "kafka-consumer-groups",
        "kafka-consumer-groups.bat",
        "kafka-consumer-groups.cmd",
        "kafka-consumer-groups.sh",
    ]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    kafka_home = os.environ.get("KAFKA_HOME", "").strip()
    if kafka_home:
        bin_dir = Path(kafka_home) / "bin"
        for candidate in candidates:
            path = bin_dir / candidate
            if path.exists():
                return str(path.resolve())

    raise RuntimeError("kafka-consumer-groups executable not found in PATH or KAFKA_HOME/bin")


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_duration_seconds(raw: str, default: float = 5.0) -> float:
    value = raw.strip().lower()
    if not value:
        return default
    units = {
        "ms": 0.001,
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
    }
    for suffix, multiplier in units.items():
        if value.endswith(suffix):
            number = value[: -len(suffix)].strip()
            return max(float(number) * multiplier, 0.1)
    return max(float(value), 0.1)


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def unique_non_empty(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


class RedisClient:
    def __init__(self, address: str, username: str, password: str, database: int) -> None:
        if ":" not in address:
            raise RuntimeError(f"unsupported redis address format: {address}")
        host, port_raw = address.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port_raw)), timeout=5)
        self.file = self.sock.makefile("rwb")
        if password:
            try:
                if username:
                    self.command("AUTH", username, password)
                else:
                    self.command("AUTH", password)
            except RuntimeError as exc:
                if is_redis_no_password_auth_error(str(exc)):
                    log("warn", "redis server has no password configured; continuing without AUTH")
                else:
                    raise
        self.command("SELECT", str(database))

    def close(self) -> None:
        try:
            self.file.close()
        finally:
            self.sock.close()

    def command(self, *args: str):
        payload = [f"*{len(args)}\r\n".encode("utf-8")]
        for arg in args:
            encoded = str(arg).encode("utf-8")
            payload.append(f"${len(encoded)}\r\n".encode("utf-8"))
            payload.append(encoded + b"\r\n")
        self.file.write(b"".join(payload))
        self.file.flush()
        return self._read_reply()

    def _read_line(self) -> bytes:
        line = self.file.readline()
        if not line:
            raise RuntimeError("unexpected end of stream while reading redis reply")
        if not line.endswith(b"\r\n"):
            raise RuntimeError("invalid redis line terminator")
        return line[:-2]

    def _read_reply(self):
        prefix = self.file.read(1)
        if not prefix:
            raise RuntimeError("unexpected end of stream while reading redis reply prefix")
        if prefix == b"+":
            return self._read_line().decode("utf-8")
        if prefix == b"-":
            raise RuntimeError(f"redis error: {self._read_line().decode('utf-8')}")
        if prefix == b":":
            return int(self._read_line().decode("utf-8"))
        if prefix == b"$":
            length = int(self._read_line().decode("utf-8"))
            if length < 0:
                return None
            data = self.file.read(length)
            trailer = self.file.read(2)
            if trailer != b"\r\n":
                raise RuntimeError("invalid redis bulk string terminator")
            return data.decode("utf-8")
        if prefix == b"*":
            count = int(self._read_line().decode("utf-8"))
            if count < 0:
                return None
            return [self._read_reply() for _ in range(count)]
        raise RuntimeError(f"unsupported redis response prefix: {prefix!r}")

    def scan_keys(self, pattern: str) -> list[str]:
        cursor = "0"
        keys: set[str] = set()
        while True:
            reply = self.command("SCAN", cursor, "MATCH", pattern, "COUNT", "500")
            if not isinstance(reply, list) or len(reply) < 2:
                raise RuntimeError("unexpected redis SCAN response")
            cursor = str(reply[0])
            batch = reply[1] or []
            for item in batch:
                if item:
                    keys.add(str(item))
            if cursor == "0":
                break
        return sorted(keys)

    def delete_keys(self, keys: list[str]) -> int:
        deleted = 0
        for batch in chunked(keys, 200):
            deleted += int(self.command("DEL", *batch))
        return deleted


def is_redis_no_password_auth_error(message: str) -> bool:
    normalized = message.lower()
    return "err auth" in normalized and "without any password configured" in normalized


@dataclass
class PhaseResult:
    name: str
    ok: bool
    message: str = ""


class Runner:
    def __init__(self) -> None:
        self.results: list[PhaseResult] = []

    def run_phase(self, name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            log("error", f"phase '{name}' failed: {message}")
            self.results.append(PhaseResult(name=name, ok=False, message=message))
        else:
            self.results.append(PhaseResult(name=name, ok=True))


def delete_elasticsearch_pattern(address: str, pattern: str, username: str, password: str) -> None:
    base = address.rstrip("/")
    url = f"{base}/{pattern}"
    req = request.Request(url=url, method="DELETE")
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    try:
        with request.urlopen(req, timeout=20) as response:
            log("info", f"deleted elasticsearch index pattern {pattern} from {base} (status {response.status})")
    except error.HTTPError as exc:
        if exc.code == 404:
            log("info", f"elasticsearch index pattern {pattern} not present on {base}")
            return
        raise RuntimeError(f"delete failed for {pattern} on {base}: HTTP {exc.code}") from exc


def clear_directory_contents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    log("info", f"cleared directory {path}")


def write_json_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log("info", f"cleared file {path}")


def clear_mongo_results(uri: str, database: str, collection: str, timeout_seconds: float) -> None:
    last_error: Exception | None = None
    try:
        clear_mongo_results_via_pymongo(uri, database, collection, timeout_seconds)
        return
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        log("warn", f"pymongo reset path unavailable: {exc}")

    try:
        clear_mongo_results_via_mongosh(uri, database, collection, timeout_seconds)
        return
    except Exception as exc:  # noqa: BLE001
        if last_error is None:
            raise
        raise RuntimeError(f"{last_error}; mongosh reset path also failed: {exc}") from exc


def clear_mongo_results_via_pymongo(uri: str, database: str, collection: str, timeout_seconds: float) -> None:
    try:
        from pymongo import MongoClient
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pymongo is not installed") from exc

    client = MongoClient(uri, serverSelectionTimeoutMS=max(int(timeout_seconds * 1000), 100))
    try:
        deleted = client[database][collection].delete_many({}).deleted_count
    finally:
        client.close()
    log("info", f"deleted {deleted} MongoDB RCA result documents from {database}.{collection} via pymongo")


def clear_mongo_results_via_mongosh(uri: str, database: str, collection: str, timeout_seconds: float) -> None:
    mongosh = resolve_executable("mongosh", "mongosh.exe")
    query = (
        f"const coll = db.getSiblingDB({json.dumps(database)}).getCollection({json.dumps(collection)});"
        "const result = coll.deleteMany({});"
        "print(JSON.stringify({deletedCount: result.deletedCount || 0}));"
    )
    completed = subprocess.run(
        [mongosh, uri, "--quiet", "--eval", query],
        check=False,
        capture_output=True,
        text=True,
        timeout=max(timeout_seconds, 1.0),
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(stderr or f"mongosh exited with code {completed.returncode}")
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError("mongosh returned an empty response")
    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"mongosh returned invalid JSON: {stdout}") from exc
    deleted = int(payload.get("deletedCount") or 0)
    log("info", f"deleted {deleted} MongoDB RCA result documents from {database}.{collection} via mongosh")


def classify_kafka_no_state(output: str) -> bool:
    normalized = output.lower()
    markers = [
        "does not exist",
        "group id not found",
        "group not found",
        "could not be deleted due to",
        "not a consumer group",
        "no offsets to reset",
        "no topic-partitions to reset offsets for",
    ]
    return any(marker in normalized for marker in markers)


def parse_kafka_group_state(output: str) -> str:
    match = re.search(r"\b(state|group state)\s*[:=]\s*([A-Za-z_]+)", output, re.IGNORECASE)
    if match:
        return match.group(2).strip().lower()
    return ""


def run_kafka_command(command: list[str], timeout_seconds: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(timeout_seconds, 1.0),
    )


def delete_kafka_consumer_group_state(brokers: list[str], group_id: str, topic: str, start_offset: str) -> None:
    if not brokers:
        log("info", "skipped Kafka state reset because no brokers are configured")
        return
    if not group_id.strip():
        log("info", "skipped Kafka state reset because no Kafka group_id is configured")
        return

    executable = resolve_kafka_consumer_groups_executable()
    bootstrap_servers = ",".join(brokers)
    delete_command = [
        executable,
        "--bootstrap-server",
        bootstrap_servers,
        "--delete",
        "--group",
        group_id,
    ]

    completed = run_kafka_command(delete_command)
    combined_output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part).strip()
    if completed.returncode == 0:
        log("info", f"deleted Kafka consumer group state for {group_id} on {bootstrap_servers}")
        return
    if classify_kafka_no_state(combined_output):
        log("info", f"no Kafka consumer group state present for {group_id}")
        return

    lower_start_offset = start_offset.strip().lower()
    reset_target = "earliest" if lower_start_offset == "earliest" else "latest"
    reset_command = [
        executable,
        "--bootstrap-server",
        bootstrap_servers,
        "--group",
        group_id,
        "--reset-offsets",
        f"--to-{reset_target}",
        "--execute",
    ]
    if topic.strip():
        reset_command.extend(["--topic", topic])
    else:
        reset_command.append("--all-topics")
    reset_result = run_kafka_command(reset_command)
    reset_output = "\n".join(part for part in [reset_result.stdout.strip(), reset_result.stderr.strip()] if part).strip()
    if reset_result.returncode == 0:
        log("info", f"reset Kafka consumer offsets for {group_id} to {reset_target}")
        return
    if classify_kafka_no_state(reset_output):
        log("info", f"no Kafka consumer offsets present for {group_id}")
        return

    group_state = parse_kafka_group_state(combined_output + "\n" + reset_output)
    if group_state in {"stable", "preparingrebalance", "completingrebalance"}:
        raise RuntimeError(
            f"Kafka consumer group {group_id} is active ({group_state}); stop consumers before resetting offsets"
        )
    raise RuntimeError(
        f"failed to reset Kafka state for group {group_id}: {reset_output or combined_output or 'unknown error'}"
    )


def run_command(command: list[str], cwd: Path, ignore_failure: bool = False) -> int:
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0 and not ignore_failure:
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {' '.join(command)}")
    return completed.returncode


def pm2_apps_for_profile(profile: str) -> list[str]:
    if profile == "compatibility":
        return ["signaled-logs-collector"]
    if profile == "all":
        return ["signalizing-engine", "correlation-engine", "log-rca-engine", "signaled-logs-collector"]
    return ["signalizing-engine", "correlation-engine", "log-rca-engine"]


def delete_pm2_apps(repo_root: Path, profile: str) -> None:
    pm2 = resolve_executable("pm2", "pm2.cmd")
    for app in pm2_apps_for_profile(profile):
        exit_code = run_command([pm2, "delete", app], cwd=repo_root, ignore_failure=True)
        if exit_code == 0:
            log("info", f"deleted PM2 app {app}")
        else:
            log("warn", f"PM2 app {app} was not deleted cleanly, continuing")


def start_pm2_apps(repo_root: Path, profile: str) -> None:
    pm2 = resolve_executable("pm2", "pm2.cmd")
    if profile == "compatibility":
        run_command(
            [
                pm2,
                "start",
                r".\bin\signaled-logs-collector.exe",
                "--name",
                "signaled-logs-collector",
                "--cwd",
                str((repo_root / "log_signal_processor").resolve()),
                "--",
                "--config",
                r".\config.yml",
            ],
            cwd=repo_root,
        )
        log("info", "started PM2 compatibility collector")
        return

    run_command([pm2, "start", r".\ecosystem.config.js"], cwd=repo_root)
    log("info", "started PM2 services from ecosystem.config.js")

    if profile == "all":
        run_command(
            [
                pm2,
                "start",
                r".\bin\signaled-logs-collector.exe",
                "--name",
                "signaled-logs-collector",
                "--cwd",
                str((repo_root / "log_signal_processor").resolve()),
                "--",
                "--config",
                r".\config.yml",
            ],
            cwd=repo_root,
        )
        log("info", "started PM2 compatibility collector")


def invoke_rebuild(repo_root: Path, profile: str, run_tests: bool, skip_clean: bool) -> None:
    powershell = resolve_executable("powershell", "powershell.exe")
    command = [
        powershell,
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r".\rebuild_all.ps1",
        "-Profile",
        profile,
    ]
    if run_tests:
        command.append("-RunTests")
    if skip_clean:
        command.append("-SkipClean")
    run_command(command, cwd=repo_root)
    log("info", f"rebuild completed for profile {profile}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset RCA/correlation state and optionally rebuild/restart services.")
    parser.add_argument("--correlation-config", default="log_correlation_engine/config/config.yml")
    parser.add_argument("--rca-config", default="log_rca_engine/config/config.yml")
    parser.add_argument("--signalizing-config", default="log_signalizing/config.yml")
    parser.add_argument("--profile", choices=["direct-stream", "compatibility", "all"], default="direct-stream")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--restart-pm2", "--restart-pm", dest="restart_pm2", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-redis", action="store_true")
    parser.add_argument("--skip-elasticsearch", action="store_true")
    parser.add_argument("--skip-kafka", action="store_true")
    parser.add_argument("--skip-local-files", action="store_true")
    parser.add_argument("--skip-mongo", action="store_true")
    parser.add_argument("--yes-mongo-results", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    correlation_config = (repo_root / args.correlation_config).resolve()
    rca_config = (repo_root / args.rca_config).resolve()
    signalizing_config = (repo_root / args.signalizing_config).resolve()

    if not correlation_config.exists():
        raise RuntimeError(f"correlation config not found at {correlation_config}")
    if not rca_config.exists():
        raise RuntimeError(f"RCA config not found at {rca_config}")
    if not signalizing_config.exists():
        raise RuntimeError(f"signalizing config not found at {signalizing_config}")

    redis_address = read_yaml_section_value(correlation_config, "redis", "address")
    redis_username = read_yaml_section_value(correlation_config, "redis", "username")
    redis_password = read_yaml_section_value(correlation_config, "redis", "password")
    redis_db_raw = read_yaml_section_value(correlation_config, "redis", "db")
    redis_db = int(redis_db_raw) if redis_db_raw else 0
    redis_key_prefix = read_yaml_section_value(correlation_config, "redis", "key_prefix") or "Rca"

    elastic_addresses = read_yaml_section_list(correlation_config, "elasticsearch", "addresses")
    if not elastic_addresses:
        single_address = read_yaml_section_value(correlation_config, "elasticsearch", "address")
        if single_address:
            elastic_addresses = [single_address]
    elastic_username = read_yaml_section_value(correlation_config, "elasticsearch", "username")
    elastic_password = read_yaml_section_value(correlation_config, "elasticsearch", "password")
    correlation_index = read_yaml_section_value(correlation_config, "elasticsearch", "index")
    current_correlation_index = read_yaml_section_value(correlation_config, "elasticsearch", "current_index")
    rca_correlation_index = read_yaml_section_value(rca_config, "elasticsearch", "correlation_index")

    correlation_project_root = correlation_config.parent.parent
    correlation_checkpoint_directory = resolve_path_from_root(
        correlation_project_root,
        read_yaml_section_value(correlation_config, "engine", "checkpoint_directory"),
    )
    rca_results_file = resolve_config_path(rca_config, read_yaml_section_value(rca_config, "storage", "results_file"))
    rca_checkpoint_file = resolve_config_path(
        rca_config,
        read_yaml_section_value(rca_config, "storage", "checkpoint_file"),
    )
    mongo_enabled = parse_bool(read_yaml_section_value(rca_config, "mongo_sync", "enabled"))
    mongo_uri = read_yaml_section_value(rca_config, "mongo_sync", "uri")
    mongo_database = read_yaml_section_value(rca_config, "mongo_sync", "database")
    mongo_results_collection = read_yaml_section_value(rca_config, "mongo_sync", "results_collection") or "rca_results"
    mongo_timeout_seconds = parse_duration_seconds(read_yaml_section_value(rca_config, "mongo_sync", "timeout"), 5.0)
    mongo_configured = mongo_enabled and bool(mongo_uri and mongo_database and mongo_results_collection)

    kafka_source = read_yaml_section_value(signalizing_config, "input", "source").strip().lower()
    kafka_brokers = read_yaml_section_list(signalizing_config, "kafka", "brokers")
    kafka_topic = read_yaml_section_value(signalizing_config, "kafka", "topic")
    kafka_group_id = read_yaml_section_value(signalizing_config, "kafka", "group_id")
    kafka_start_offset = read_yaml_section_value(signalizing_config, "kafka", "start_offset") or "latest"
    kafka_reset_enabled = kafka_source == "kafka" and bool(kafka_brokers and kafka_group_id)

    signal_stream_dedup_prefix = (
        read_yaml_section_value(signalizing_config, "signal_stream", "publish_dedup_key_prefix")
        or "Rca:signal_stream:dedupe:"
    )
    redis_patterns = unique_non_empty(
        [
            f"{redis_key_prefix.rstrip(':')}:*",
            f"{signal_stream_dedup_prefix.rstrip(':')}:*",
            "rca:signal_stream:dedupe:*",
            "Rca:signal_stream:dedupe:*",
        ]
    )
    elastic_patterns: set[str] = set()
    for value in (correlation_index, current_correlation_index, rca_correlation_index):
        if not value:
            continue
        elastic_patterns.add(value)
        if "*" not in value:
            elastic_patterns.add(f"{value}*")
    elastic_index_patterns = sorted(elastic_patterns)

    targets: list[str] = []
    if not args.skip_redis:
        targets.append(
            f"Redis keys matching {', '.join(redis_patterns)} on {redis_address} (db {redis_db})"
        )
    if not args.skip_elasticsearch:
        targets.append(f"Elasticsearch index patterns: {', '.join(elastic_index_patterns)}")
    if not args.skip_kafka and kafka_reset_enabled:
        targets.append(
            f"Kafka consumer group {kafka_group_id} on {', '.join(kafka_brokers)}"
            + (f" for topic {kafka_topic}" if kafka_topic else "")
        )
    if not args.skip_local_files:
        if correlation_checkpoint_directory:
            targets.append(f"Local path {correlation_checkpoint_directory}")
        if rca_checkpoint_file:
            targets.append(f"Local path {rca_checkpoint_file}")
        if rca_results_file:
            targets.append(f"Local path {rca_results_file}")
    if not args.skip_mongo and mongo_configured:
        targets.append(f"MongoDB collection {mongo_database}.{mongo_results_collection}")

    log("info", "planned RCA reset targets:")
    for target in targets:
        print(f"  - {target}")

    if not args.force:
        answer = input("Continue with RCA state reset? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            log("warn", "reset cancelled by user")
            return 1

    runner = Runner()

    if args.restart_pm2:
        runner.run_phase("pm2-delete", lambda: delete_pm2_apps(repo_root, args.profile))

    if not args.skip_redis:
        def redis_phase() -> None:
            log("info", f"resetting redis keys on {redis_address}")
            client = RedisClient(redis_address, redis_username, redis_password, redis_db)
            try:
                keys: set[str] = set()
                for pattern in redis_patterns:
                    for key in client.scan_keys(pattern):
                        keys.add(key)
                if not keys:
                    log("info", "no matching redis keys found")
                else:
                    deleted = client.delete_keys(sorted(keys))
                    log("info", f"deleted {deleted} redis keys across {len(redis_patterns)} redis patterns")
            finally:
                client.close()

        runner.run_phase("redis-reset", redis_phase)

    if not args.skip_elasticsearch:
        def es_phase() -> None:
            log("info", "resetting elasticsearch correlation indices")
            if not elastic_addresses:
                raise RuntimeError("no elasticsearch addresses configured")
            for address in elastic_addresses:
                for pattern in elastic_index_patterns:
                    try:
                        delete_elasticsearch_pattern(address, pattern, elastic_username, elastic_password)
                    except Exception as exc:  # noqa: BLE001
                        log("warn", f"failed to delete elasticsearch pattern {pattern} on {address}: {exc}")

        runner.run_phase("elasticsearch-reset", es_phase)

    if not args.skip_kafka:
        def kafka_phase() -> None:
            log("info", "resetting Kafka consumer group state")
            if not kafka_reset_enabled:
                log("info", "no Kafka consumer group state configured for reset")
                return
            delete_kafka_consumer_group_state(kafka_brokers, kafka_group_id, kafka_topic, kafka_start_offset)

        runner.run_phase("kafka-reset", kafka_phase)

    if not args.skip_local_files:
        def local_phase() -> None:
            log("info", "resetting local checkpoint and result files")
            if correlation_checkpoint_directory is not None:
                try:
                    clear_directory_contents(correlation_checkpoint_directory)
                except Exception as exc:  # noqa: BLE001
                    log("warn", f"failed to clear directory {correlation_checkpoint_directory}: {exc}")

            if rca_checkpoint_file is not None:
                try:
                    write_json_file(rca_checkpoint_file, "")
                except Exception as exc:  # noqa: BLE001
                    log("warn", f"failed to clear file {rca_checkpoint_file}: {exc}")

            if rca_results_file is not None:
                try:
                    write_json_file(rca_results_file, "")
                except Exception as exc:  # noqa: BLE001
                    log("warn", f"failed to clear file {rca_results_file}: {exc}")

        runner.run_phase("local-reset", local_phase)

    if not args.skip_mongo and mongo_configured:
        mongo_confirmed = args.yes_mongo_results
        if not mongo_confirmed:
            answer = input(
                f"Also delete MongoDB RCA results from {mongo_database}.{mongo_results_collection}? [y/N]: "
            ).strip().lower()
            mongo_confirmed = answer in {"y", "yes"}
        if mongo_confirmed:
            runner.run_phase(
                "mongo-results-reset",
                lambda: clear_mongo_results(
                    mongo_uri,
                    mongo_database,
                    mongo_results_collection,
                    mongo_timeout_seconds,
                ),
            )
        else:
            log("info", "skipped MongoDB RCA results reset")
    elif not args.skip_mongo and mongo_enabled:
        log("warn", "MongoDB RCA results reset skipped because mongo_sync configuration is incomplete")

    if args.rebuild:
        runner.run_phase("rebuild", lambda: invoke_rebuild(repo_root, args.profile, args.run_tests, args.skip_clean))

    if args.restart_pm2:
        runner.run_phase("pm2-start", lambda: start_pm2_apps(repo_root, args.profile))

    log("info", "RCA state script completed")
    print("\nPhase summary:")
    failures = 0
    for result in runner.results:
        if result.ok:
            print(f"  [OK] {result.name}")
        else:
            failures += 1
            print(f"  [FAILED] {result.name}: {result.message}")

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("warn", "operation cancelled")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        log("error", str(exc))
        sys.exit(1)
