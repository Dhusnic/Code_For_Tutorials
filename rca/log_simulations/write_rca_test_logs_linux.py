#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def detect_default_host_name() -> str:
    for resolver in (socket.gethostname, socket.getfqdn):
        try:
            candidate = resolver().strip()
        except OSError:
            continue
        if candidate and candidate.lower() not in {"localhost", "localhost.localdomain"}:
            return candidate
    return "localhost"


DEFAULT_ORG_ID = "135098068173316952064"
DEFAULT_DEVICE_IP = "10.0.6.79"
DEFAULT_HOST_NAME = detect_default_host_name()
DEFAULT_MONGODB_LOG = "/var/log/mongodb/mongod.log"
DEFAULT_NGINX_ACCESS_LOG = "/var/log/nginx/access.log"
DEFAULT_NGINX_ERROR_LOG = "/var/log/nginx/error.log"


SCENARIOS: dict[str, dict[str, Any]] = {
    "mongo_auth_chain_confirmed": {
        "description": "Three MongoDB auth failures followed by client disconnect and host unreachable.",
        "events": [
            {"service": "mongodb", "kind": "mongodb_auth_failed", "offset_seconds": 0},
            {"service": "mongodb", "kind": "mongodb_auth_failed", "offset_seconds": 121},
            {"service": "mongodb", "kind": "mongodb_auth_failed", "offset_seconds": 242},
            {"service": "mongodb", "kind": "mongodb_interrupted_client_disconnected", "offset_seconds": 300},
            {"service": "mongodb", "kind": "mongodb_host_unreachable", "offset_seconds": 360},
        ],
    },
    "mongo_auth_chain_partial": {
        "description": "Two MongoDB auth failures only.",
        "events": [
            {"service": "mongodb", "kind": "mongodb_auth_failed", "offset_seconds": 0},
            {"service": "mongodb", "kind": "mongodb_auth_failed", "offset_seconds": 121},
        ],
    },
    "nginx_failure_spike_confirmed": {
        "description": "Three nginx 5xx access logs followed by one nginx error log.",
        "events": [
            {"service": "nginx", "kind": "nginx_access_502", "offset_seconds": 0},
            {"service": "nginx", "kind": "nginx_access_502", "offset_seconds": 61},
            {"service": "nginx", "kind": "nginx_access_502", "offset_seconds": 122},
            {"service": "nginx", "kind": "nginx_error_failure", "offset_seconds": 180},
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write RCA test logs directly into Linux service log files for Filebeat module pickup."
    )
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="mongo_auth_chain_confirmed")
    parser.add_argument("--organization-id", default=DEFAULT_ORG_ID)
    parser.add_argument("--device-ip", default=DEFAULT_DEVICE_IP)
    parser.add_argument("--host-name", default=DEFAULT_HOST_NAME)
    parser.add_argument("--mongodb-log", default=DEFAULT_MONGODB_LOG)
    parser.add_argument("--nginx-access-log", default=DEFAULT_NGINX_ACCESS_LOG)
    parser.add_argument("--nginx-error-log", default=DEFAULT_NGINX_ERROR_LOG)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-lines", action="store_true")
    parser.add_argument("--base-time-minutes-ago", type=int, default=8)
    return parser.parse_args()


def iso_mongo(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def nginx_access_time(ts: datetime) -> str:
    local_ts = ts.astimezone()
    return local_ts.strftime("%d/%b/%Y:%H:%M:%S %z")


def nginx_error_time(ts: datetime) -> str:
    return ts.astimezone().strftime("%Y/%m/%d %H:%M:%S")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def format_mongodb_line(kind: str, ts: datetime, args: argparse.Namespace, run_id: str) -> str:
    marker = f"rca_run_id:{run_id}"
    base = {
        "t": {"$date": iso_mongo(ts)},
        "s": "I",
        "c": "CONTROL",
        "id": 1000,
        "ctx": "conn100",
        "msg": f"RCA simulation event [{marker}]",
        "attr": {
            "organization": args.organization_id,
            "host_name": args.host_name,
            "host_ip": args.device_ip,
            "run_id": run_id,
        },
        "event": {"organization": args.organization_id},
        "service": {"name": "mongodb"},
        "host": {"name": args.host_name, "ip": args.device_ip},
    }
    if kind == "mongodb_auth_failed":
        base.update(
            {
                "s": "W",
                "c": "ACCESS",
                "id": 20249,
                "ctx": "conn201",
                "msg": f"Failed to authenticate user root against admin database for client {args.device_ip} [{marker}]",
                "code": 18,
                "attr": {
                    **base["attr"],
                    "mechanism": "SCRAM-SHA-256",
                    "principalName": "root",
                    "authenticationDatabase": "admin",
                    "remote": f"{args.device_ip}:49152",
                    "result": 18,
                    "code": 18,
                    "error": "AuthenticationFailed: bad credentials",
                },
            }
        )
    elif kind == "mongodb_interrupted_client_disconnected":
        base.update(
            {
                "s": "W",
                "c": "NETWORK",
                "id": 20883,
                "ctx": "conn202",
                "msg": f"Interrupted operation as its client disconnected while waiting for upstream request completion [{marker}]",
                "attr": {**base["attr"], "remote": f"{args.device_ip}:49152"},
            }
        )
    elif kind == "mongodb_host_unreachable":
        base.update(
            {
                "s": "E",
                "c": "NETWORK",
                "id": 4712102,
                "ctx": "ReplicaSetMonitor-TaskExecutor",
                "msg": f"HostUnreachable: No route to host while connecting to upstream peer. Network is unreachable [{marker}]",
                "code": 6,
                "attr": {**base["attr"], "code": 6, "target": f"{args.device_ip}:27017"},
            }
        )
    else:
        raise ValueError(f"unsupported mongodb event kind: {kind}")
    return json.dumps(base, separators=(",", ":"), ensure_ascii=True)


def format_nginx_access_line(ts: datetime, args: argparse.Namespace, run_id: str) -> str:
    marker_path = f"/api/orders?rca_run_id={run_id}&org={args.organization_id}"
    return (
        f'{args.device_ip} - - [{nginx_access_time(ts)}] '
        f'"GET {marker_path} HTTP/1.1" 502 182 "-" "curl/8.5.0" "-"'
    )


def format_nginx_error_line(ts: datetime, args: argparse.Namespace, run_id: str) -> str:
    marker_path = f"/api/orders?rca_run_id={run_id}&org={args.organization_id}"
    return (
        f'{nginx_error_time(ts)} [error] 18452#0: *903 worker process exited unexpectedly after repeated 5xx spike, '
        f'client: {args.device_ip}, server: _, request: "GET {marker_path} HTTP/1.1", '
        f'host: "{args.host_name}"'
    )


def render_event(event: dict[str, Any], ts: datetime, args: argparse.Namespace, run_id: str) -> tuple[Path, str]:
    if event["service"] == "mongodb":
        return Path(args.mongodb_log), format_mongodb_line(event["kind"], ts, args, run_id)
    if event["kind"] == "nginx_access_502":
        return Path(args.nginx_access_log), format_nginx_access_line(ts, args, run_id)
    if event["kind"] == "nginx_error_failure":
        return Path(args.nginx_error_log), format_nginx_error_line(ts, args, run_id)
    raise ValueError(f"unsupported event: {event}")


def write_line(path: Path, line: str) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()


def main() -> int:
    args = parse_args()
    run_id = args.run_id.strip() or uuid.uuid4().hex[:12]
    scenario = SCENARIOS[args.scenario]
    base_time = datetime.now(timezone.utc) - timedelta(minutes=max(args.base_time_minutes_ago, 0))

    print("Linux RCA file writer")
    print("=" * 80)
    print(f"Run ID                : {run_id}")
    print(f"Scenario              : {args.scenario}")
    print(f"Description           : {scenario['description']}")
    print(f"Organization ID       : {args.organization_id}")
    print(f"Device IP             : {args.device_ip}")
    print(f"Host                  : {args.host_name}")
    print(f"MongoDB log file      : {Path(args.mongodb_log).resolve()}")
    print(f"Nginx access log file : {Path(args.nginx_access_log).resolve()}")
    print(f"Nginx error log file  : {Path(args.nginx_error_log).resolve()}")
    print("-" * 80)

    if not args.dry_run:
        print("This script appends lines into the target log files. On Red Hat you may need sudo if /var/log is root-owned.")
        print("-" * 80)

    for index, event in enumerate(scenario["events"], start=1):
        ts = base_time + timedelta(seconds=int(event["offset_seconds"]))
        path, line = render_event(event, ts, args, run_id)
        print(f"[write {index}/{len(scenario['events'])}] {event['kind']} -> {path}")
        if args.show_lines or args.dry_run:
            print(line)
        if not args.dry_run:
            write_line(path, line)
        if index != len(scenario["events"]):
            time.sleep(max(args.sleep_seconds, 0))

    print("-" * 80)
    if args.dry_run:
        print("Dry run only. No files were changed.")
    else:
        print("Finished writing service-specific test logs.")
        print("If Filebeat modules are watching these paths, they should pick up the new lines automatically.")
        print("Important: MongoDB JSON lines include event.organization. Nginx plain-text lines do not create that field by themselves.")
        print("If your RCA flow requires event.organization for nginx too, add it in Filebeat or Logstash processors.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
