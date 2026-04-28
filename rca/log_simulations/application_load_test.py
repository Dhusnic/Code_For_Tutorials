#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import socket
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def detect_default_host_name() -> str:
    for resolver in (socket.gethostname, socket.getfqdn):
        try:
            candidate = resolver().strip()
        except OSError:
            continue
        if candidate and candidate.lower() not in {"localhost", "localhost.localdomain"}:
            return candidate
    return "localhost"


def detect_default_device_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as handle:
            handle.connect(("8.8.8.8", 80))
            candidate = handle.getsockname()[0].strip()
            if candidate and not candidate.startswith("127."):
                return candidate
    except OSError:
        pass

    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        addresses = []
    for candidate in addresses:
        candidate = candidate.strip()
        if candidate and not candidate.startswith("127."):
            return candidate

    return "10.0.6.79"


DEFAULT_HOST_NAME = detect_default_host_name()
DEFAULT_DEVICE_IP = detect_default_device_ip()
DEFAULT_ORG_ID = "135098068173316952064"
DEFAULT_RATE = 2000
DEFAULT_BATCH_INTERVAL_MS = 100
DEFAULT_DURATION_SECONDS = 60
DEFAULT_STATS_EVERY_SECONDS = 5

DEFAULT_MONGODB_LOG = Path("/var/log/mongodb/mongod.log")
DEFAULT_NGINX_ACCESS_LOG = Path("/var/log/nginx/access.log")
DEFAULT_NGINX_ERROR_LOG = Path("/var/log/nginx/error.log")
DEFAULT_AUTH_LOG = Path("/var/log/auth.log")
DEFAULT_SYSLOG_LOG = Path("/var/log/syslog")

USERS = ("appuser", "deploy", "apiuser", "svc_web", "svc_orders")
INVALID_USERS = ("backup", "deployx", "ghost", "unknown", "testroot")
REQUEST_PATHS = ("/api/orders", "/api/payments", "/api/profile", "/login", "/checkout")
UPSTREAMS = ("10.0.6.80:8080", "10.0.6.81:8080", "10.0.6.82:9000")


@dataclass
class Stats:
    batches: int = 0
    events_total: int = 0
    info_total: int = 0
    signal_total: int = 0
    warning_total: int = 0
    error_total: int = 0
    critical_total: int = 0
    file_write_ops: int = 0
    bytes_written: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "High-rate application log writer for local load testing. "
            "Writes 50%% info logs and 50%% signalizing-friendly warning/error/critical logs."
        )
    )
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE, help="Total events per second.")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_DURATION_SECONDS,
        help="How long to run. Use 0 to run until interrupted.",
    )
    parser.add_argument(
        "--batch-interval-ms",
        type=int,
        default=DEFAULT_BATCH_INTERVAL_MS,
        help="Batch interval in milliseconds. 100ms keeps the default 2000 eps split clean.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--organization-id", default=DEFAULT_ORG_ID)
    parser.add_argument("--device-ip", default=DEFAULT_DEVICE_IP)
    parser.add_argument("--host-name", default=DEFAULT_HOST_NAME)
    parser.add_argument("--mongodb-log", default=str(DEFAULT_MONGODB_LOG))
    parser.add_argument("--nginx-access-log", default=str(DEFAULT_NGINX_ACCESS_LOG))
    parser.add_argument("--nginx-error-log", default=str(DEFAULT_NGINX_ERROR_LOG))
    parser.add_argument("--auth-log", default=str(DEFAULT_AUTH_LOG))
    parser.add_argument("--syslog-log", default=str(DEFAULT_SYSLOG_LOG))
    parser.add_argument("--stats-every-seconds", type=int, default=DEFAULT_STATS_EVERY_SECONDS)
    parser.add_argument("--show-samples", type=int, default=0, help="Print the first N generated lines.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_lines(path: Path, lines: list[str], dry_run: bool) -> int:
    if not lines:
        return 0
    payload = "".join(line if line.endswith("\n") else line + "\n" for line in lines)
    if dry_run:
        return len(payload.encode("utf-8"))
    ensure_parent(path)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return len(payload.encode("utf-8"))


def iso_mongo(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def syslog_iso(ts: datetime) -> str:
    return ts.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def auth_time(ts: datetime) -> str:
    return ts.astimezone().strftime("%b %d %H:%M:%S")


def nginx_access_time(ts: datetime) -> str:
    return ts.astimezone().strftime("%d/%b/%Y:%H:%M:%S %z")


def nginx_error_time(ts: datetime) -> str:
    return ts.astimezone().strftime("%Y/%m/%d %H:%M:%S")


def render_mongodb_info(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str) -> tuple[Path, str, str]:
    line = {
        "t": {"$date": iso_mongo(ts)},
        "s": "I",
        "c": "NETWORK",
        "id": 22944,
        "ctx": f"conn{rng.randint(200, 999)}",
        "msg": f"Connection accepted from {args.device_ip}:{rng.randint(40000, 55000)} [run_id:{run_id}]",
        "attr": {
            "remote": f"{args.device_ip}:{rng.randint(40000, 55000)}",
            "organization": args.organization_id,
            "host_name": args.host_name,
            "host_ip": args.device_ip,
            "run_id": run_id,
        },
        "service": {"name": "mongodb"},
        "host": {"name": args.host_name, "ip": args.device_ip},
    }
    return Path(args.mongodb_log), json.dumps(line, separators=(",", ":"), ensure_ascii=True), "info"


def render_mongodb_auth_failed(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str) -> tuple[Path, str, str]:
    line = {
        "t": {"$date": iso_mongo(ts)},
        "s": "W",
        "c": "ACCESS",
        "id": 20249,
        "ctx": f"conn{rng.randint(200, 999)}",
        "msg": f"Failed to authenticate user root against admin database for client {args.device_ip} [run_id:{run_id}]",
        "code": 18,
        "attr": {
            "mechanism": "SCRAM-SHA-256",
            "principalName": "root",
            "authenticationDatabase": "admin",
            "remote": f"{args.device_ip}:{rng.randint(40000, 55000)}",
            "result": 18,
            "code": 18,
            "error": "AuthenticationFailed: bad credentials",
            "organization": args.organization_id,
            "host_name": args.host_name,
            "host_ip": args.device_ip,
            "run_id": run_id,
        },
        "service": {"name": "mongodb"},
        "host": {"name": args.host_name, "ip": args.device_ip},
    }
    return Path(args.mongodb_log), json.dumps(line, separators=(",", ":"), ensure_ascii=True), "warning"


def render_mongodb_host_unreachable(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str) -> tuple[Path, str, str]:
    target = rng.choice(UPSTREAMS)
    line = {
        "t": {"$date": iso_mongo(ts)},
        "s": "E",
        "c": "NETWORK",
        "id": 4712102,
        "ctx": "ReplicaSetMonitor-TaskExecutor",
        "msg": f"HostUnreachable: No route to host while connecting to upstream peer. Network is unreachable [run_id:{run_id}]",
        "code": 6,
        "attr": {
            "code": 6,
            "target": target,
            "organization": args.organization_id,
            "host_name": args.host_name,
            "host_ip": args.device_ip,
            "run_id": run_id,
        },
        "service": {"name": "mongodb"},
        "host": {"name": args.host_name, "ip": args.device_ip},
    }
    return Path(args.mongodb_log), json.dumps(line, separators=(",", ":"), ensure_ascii=True), "error"


def render_nginx_access(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str, status: int) -> tuple[Path, str, str]:
    path = rng.choice(REQUEST_PATHS)
    marker_path = f"{path}?org={args.organization_id}&run_id={run_id}"
    line = (
        f'rca_sim_nginx_access ts="{nginx_access_time(ts)}" '
        f"client_ip={args.device_ip} method=GET path={marker_path} status={status} "
        f'bytes_sent={rng.randint(180, 2048)} query_params="org={args.organization_id}&run_id={run_id}" '
        f'request_time={rng.uniform(0.01, 1.5):.3f} upstream_response_time={rng.uniform(0.01, 1.5):.3f} '
        'user_agent="load-test-client/1.0"'
    )
    severity = "critical" if status >= 500 else "info"
    return Path(args.nginx_access_log), line, severity


def render_nginx_error_connect_refused(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str) -> tuple[Path, str, str]:
    path = rng.choice(REQUEST_PATHS)
    upstream = rng.choice(UPSTREAMS)
    line = (
        f'{nginx_error_time(ts)} [error] 18452#0: *{rng.randint(900, 5000)} connect() failed '
        f'(111: Connection refused) while connecting to upstream, client: {args.device_ip}, server: _, '
        f'request: "GET {path}?run_id={run_id} HTTP/1.1", upstream: "http://{upstream}{path}", '
        f'host: "{args.host_name}"'
    )
    return Path(args.nginx_error_log), line, "error"


def render_nginx_error_upstream_disabled(ts: datetime, args: argparse.Namespace, rng: random.Random, run_id: str) -> tuple[Path, str, str]:
    path = rng.choice(REQUEST_PATHS)
    upstream = rng.choice(UPSTREAMS)
    line = (
        f'{nginx_error_time(ts)} [warn] 18452#0: *{rng.randint(900, 5000)} upstream server temporarily disabled '
        f'while connecting to upstream, client: {args.device_ip}, server: _, '
        f'request: "GET {path}?run_id={run_id} HTTP/1.1", upstream: "http://{upstream}{path}", '
        f'host: "{args.host_name}"'
    )
    return Path(args.nginx_error_log), line, "warning"


def render_auth_success(ts: datetime, args: argparse.Namespace, rng: random.Random, _: str) -> tuple[Path, str, str]:
    line = (
        f"{auth_time(ts)} {args.host_name} sshd[{rng.randint(2000, 32000)}]: "
        f"Accepted password for {rng.choice(USERS)} from {args.device_ip} port {rng.randint(40000, 55000)} ssh2"
    )
    return Path(args.auth_log), line, "info"


def render_auth_failed(ts: datetime, args: argparse.Namespace, rng: random.Random, _: str) -> tuple[Path, str, str]:
    line = (
        f"{auth_time(ts)} {args.host_name} sshd[{rng.randint(2000, 32000)}]: "
        f"Failed password for invalid user {rng.choice(INVALID_USERS)} from {args.device_ip} "
        f"port {rng.randint(40000, 55000)} ssh2"
    )
    return Path(args.auth_log), line, "warning"


def render_syslog_info(ts: datetime, args: argparse.Namespace, rng: random.Random, _: str) -> tuple[Path, str, str]:
    service_name = rng.choice(("api.service", "worker.service", "payments.service", "scheduler.service"))
    line = f"{syslog_iso(ts)} {args.host_name} systemd[1]: {service_name}: Deactivated successfully."
    return Path(args.syslog_log), line, "info"


def render_syslog_failed(ts: datetime, args: argparse.Namespace, rng: random.Random, _: str) -> tuple[Path, str, str]:
    service_name = rng.choice(("nginx.service", "mongodb.service", "payments.service"))
    line = (
        f"{syslog_iso(ts)} {args.host_name} systemd[1]: {service_name}: Main process exited, "
        f"code=exited, status={rng.randint(1, 9)}/FAILURE"
    )
    return Path(args.syslog_log), line, "critical"


def update_severity_counters(stats: Stats, severity: str) -> None:
    if severity == "info":
        stats.info_total += 1
    elif severity == "warning":
        stats.warning_total += 1
    elif severity == "error":
        stats.error_total += 1
    elif severity == "critical":
        stats.critical_total += 1


def main() -> int:
    args = parse_args()
    if args.rate <= 0:
        raise SystemExit("--rate must be greater than 0")
    if args.batch_interval_ms <= 0:
        raise SystemExit("--batch-interval-ms must be greater than 0")

    batch_interval_s = args.batch_interval_ms / 1000.0
    events_per_batch = max(2, int(round(args.rate * batch_interval_s)))
    if events_per_batch % 2 != 0:
        events_per_batch += 1

    rng = random.Random(args.seed)
    run_id = args.run_id.strip() or uuid.uuid4().hex[:12]
    info_renderers = (
        render_auth_success,
        render_mongodb_info,
        render_nginx_access,
        render_syslog_info,
    )
    signal_renderers = (
        render_auth_failed,
        render_mongodb_auth_failed,
        render_mongodb_host_unreachable,
        render_nginx_access,
        render_nginx_error_connect_refused,
        render_nginx_error_upstream_disabled,
        render_syslog_failed,
    )

    stats = Stats()
    start_wall = time.time()
    next_deadline = start_wall
    last_stats_at = start_wall
    sample_budget = max(args.show_samples, 0)

    print("Application load test writer")
    print("=" * 80)
    print(f"Run ID                : {run_id}")
    print(f"Rate                  : {args.rate} events/sec")
    print(f"Duration              : {args.duration_seconds}s")
    print(f"Batch interval        : {args.batch_interval_ms}ms")
    print(f"Batch size            : {events_per_batch} events")
    print(f"Split                 : {events_per_batch // 2} info + {events_per_batch // 2} signalizing-friendly")
    print(f"Host                  : {args.host_name}")
    print(f"Device IP             : {args.device_ip}")
    print(f"Organization ID       : {args.organization_id}")
    print(f"MongoDB log           : {Path(args.mongodb_log).resolve()}")
    print(f"Nginx access log      : {Path(args.nginx_access_log).resolve()}")
    print(f"Nginx error log       : {Path(args.nginx_error_log).resolve()}")
    print(f"Auth log              : {Path(args.auth_log).resolve()}")
    print(f"Syslog log            : {Path(args.syslog_log).resolve()}")
    print(f"Dry run               : {args.dry_run}")
    print("-" * 80)

    try:
        while True:
            now = time.time()
            if args.duration_seconds > 0 and (now - start_wall) >= args.duration_seconds:
                break
            if now < next_deadline:
                time.sleep(max(0.0, next_deadline - now))
                continue

            grouped_lines: dict[Path, list[str]] = defaultdict(list)
            batch_start_ts = datetime.now(timezone.utc)
            info_target = events_per_batch // 2
            signal_target = events_per_batch - info_target

            for index in range(info_target):
                ts = batch_start_ts + timedelta(microseconds=int(index * 1_000_000 / max(args.rate, 1)))
                renderer = rng.choice(info_renderers)
                if renderer is render_nginx_access:
                    path, line, severity = renderer(ts, args, rng, run_id, 200)
                else:
                    path, line, severity = renderer(ts, args, rng, run_id)
                grouped_lines[path].append(line)
                update_severity_counters(stats, severity)
                if sample_budget > 0:
                    print(f"[sample][{severity}] {path.name}: {line}")
                    sample_budget -= 1

            for index in range(signal_target):
                ts = batch_start_ts + timedelta(
                    microseconds=int((info_target + index) * 1_000_000 / max(args.rate, 1))
                )
                renderer = rng.choice(signal_renderers)
                if renderer is render_nginx_access:
                    path, line, severity = renderer(ts, args, rng, run_id, 502)
                else:
                    path, line, severity = renderer(ts, args, rng, run_id)
                grouped_lines[path].append(line)
                update_severity_counters(stats, severity)
                if sample_budget > 0:
                    print(f"[sample][{severity}] {path.name}: {line}")
                    sample_budget -= 1

            for path, lines in grouped_lines.items():
                stats.bytes_written += append_lines(path, lines, args.dry_run)
                stats.file_write_ops += 1

            stats.batches += 1
            stats.events_total += events_per_batch
            stats.signal_total += signal_target

            if args.stats_every_seconds > 0 and (time.time() - last_stats_at) >= args.stats_every_seconds:
                elapsed = time.time() - start_wall
                effective_rate = stats.events_total / elapsed if elapsed > 0 else 0.0
                print(
                    f"[stats] batches={stats.batches} events={stats.events_total} "
                    f"info={stats.info_total} signal={stats.signal_total} "
                    f"warning={stats.warning_total} error={stats.error_total} critical={stats.critical_total} "
                    f"writes={stats.file_write_ops} bytes={stats.bytes_written} rate={effective_rate:.1f}/sec"
                )
                last_stats_at = time.time()

            next_deadline = time.time() if args.rate <= 0 else next_deadline + batch_interval_s
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
    finally:
        elapsed = time.time() - start_wall
        effective_rate = stats.events_total / elapsed if elapsed > 0 else 0.0
        print("-" * 80)
        print(
            f"Completed batches={stats.batches} events={stats.events_total} "
            f"info={stats.info_total} signal={stats.signal_total} "
            f"warning={stats.warning_total} error={stats.error_total} critical={stats.critical_total}"
        )
        print(f"File write ops        : {stats.file_write_ops}")
        print(f"Bytes written         : {stats.bytes_written}")
        print(f"Effective rate        : {effective_rate:.1f} events/sec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
