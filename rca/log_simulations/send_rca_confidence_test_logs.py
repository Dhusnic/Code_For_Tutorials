#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import socket
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_TARGET_HOST = "10.0.4.132"
DEFAULT_TARGET_PORT = 5048
DEFAULT_PROTO = "udp"
DEFAULT_PAYLOAD_FORMAT = "syslog-json"
DEFAULT_ORGANIZATION_ID = "135098068173316952064"
DEFAULT_DEVICE_IP = "10.0.6.79"
DEFAULT_HOST_NAME = "win-rca-lab"
DEFAULT_RAW_INDEX = "*,-rca_correlated_events*,-rca_correlated_incidents_current*,-rca-checkpoints*"
DEFAULT_VERIFY_TIMEOUT_SECONDS = 240
DEFAULT_VERIFY_INTERVAL_SECONDS = 5
DEFAULT_DELIVERY_MODE = "direct-network"
DEFAULT_FILEBEAT_SPOOL_FILE = "log_simulations/out/filebeat_rca_input.log"

FORBIDDEN_RAW_OUTPUT_PATHS = {
    "signal",
    "signal_present",
    "source_id",
    "source_index",
    "rule_completion",
    "sequence_match",
    "incident_id",
    "status",
    "matched_at",
    "result_signature",
    "group_by_values",
    "audit",
    "topology.identity",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_signalizing_config() -> Path:
    return repo_root() / "log_signalizing" / "config.yml"


def default_rca_config() -> Path:
    return repo_root() / "log_rca_engine" / "config" / "config.yml"


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
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None

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
            continue

        if current_section is None:
            continue

        section = data[current_section]
        if indent == 2 and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value == "":
                section[key] = []
                current_list_key = key
            else:
                section[key] = parse_scalar(raw_value)
                current_list_key = None
            continue

        if indent >= 4 and stripped.startswith("- ") and current_list_key:
            section[current_list_key].append(parse_scalar(stripped[2:]))

    return data


def load_signalizing_es_settings(config_path: Path) -> dict[str, Any]:
    config = load_sectioned_yaml(config_path)
    elasticsearch = config.get("elasticsearch", {})
    hosts = elasticsearch.get("hosts", [])
    if not hosts:
        raise ValueError(f"No elasticsearch.hosts found in {config_path}")
    return {
        "address": str(hosts[0]).rstrip("/"),
        "username": str(elasticsearch.get("username") or ""),
        "password": str(elasticsearch.get("password") or ""),
        "api_key": str(elasticsearch.get("api_key") or ""),
    }


def load_rca_settings(config_path: Path) -> dict[str, Any]:
    config = load_sectioned_yaml(config_path)
    elasticsearch = config.get("elasticsearch", {})
    storage = config.get("storage", {})
    openai = config.get("openai", {})
    correlation_index = str(elasticsearch.get("correlation_index") or "").strip()
    if correlation_index:
        parts = [part.strip() for part in correlation_index.split(",") if part.strip()]
        if "rca_correlated_events*" not in parts:
            parts.append("rca_correlated_events*")
        correlation_index = ",".join(parts)
    else:
        correlation_index = "rca_correlated_incidents_current*,rca_correlated_events*"
    return {
        "correlation_index": correlation_index,
        "results_file": str(storage.get("results_file") or "../data/results/rca_results.json"),
        "openai_enabled": bool(openai.get("enabled")),
        "openai_model": str(openai.get("model") or ""),
    }


class ElasticsearchHttpClient:
    def __init__(self, address: str, username: str = "", password: str = "", api_key: str = "") -> None:
        self.address = address.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key

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
            with request.urlopen(req, timeout=30) as response:
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


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    rule_id: str
    description: str
    expected_signals: list[str]
    expected_services: list[str]
    event_templates: list[dict[str, Any]]


@dataclass
class PipelineStatus:
    raw_docs: list[dict[str, Any]]
    raw_doc_ids: list[str]
    signaled_count: int
    signal_counts: Counter[str]
    correlation_hit: dict[str, Any] | None
    rca_record: dict[str, Any] | None
    llm_ready: bool
    llm_status: str
    diagnostics: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send RCA confidence test logs and verify the full pipeline in one run.")
    parser.add_argument("--scenario", choices=["mongo_auth_chain_confirmed", "mongo_auth_chain_partial", "nginx_failure_spike_confirmed"], default="mongo_auth_chain_confirmed")
    parser.add_argument("--delivery-mode", choices=["direct-network", "filebeat-file"], default=DEFAULT_DELIVERY_MODE)
    parser.add_argument("--target-host", default=DEFAULT_TARGET_HOST)
    parser.add_argument("--target-port", type=int, default=DEFAULT_TARGET_PORT)
    parser.add_argument("--proto", choices=["udp", "tcp"], default=DEFAULT_PROTO)
    parser.add_argument("--payload-format", choices=["syslog-json", "json-line"], default=DEFAULT_PAYLOAD_FORMAT)
    parser.add_argument("--spool-file", default=DEFAULT_FILEBEAT_SPOOL_FILE)
    parser.add_argument("--truncate-spool", action="store_true")
    parser.add_argument("--organization-id", default=DEFAULT_ORGANIZATION_ID)
    parser.add_argument("--device-ip", default=DEFAULT_DEVICE_IP)
    parser.add_argument("--host-name", default=DEFAULT_HOST_NAME)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--host-ip-mode", choices=["single", "comma-list", "array"], default="comma-list")
    parser.add_argument("--signalizing-config", default=str(default_signalizing_config()))
    parser.add_argument("--rca-config", default=str(default_rca_config()))
    parser.add_argument("--raw-index", default=DEFAULT_RAW_INDEX)
    parser.add_argument("--correlation-index", default="")
    parser.add_argument("--rca-results-file", default="")
    parser.add_argument("--verify-timeout-seconds", type=int, default=DEFAULT_VERIFY_TIMEOUT_SECONDS)
    parser.add_argument("--verify-interval-seconds", type=int, default=DEFAULT_VERIFY_INTERVAL_SECONDS)
    parser.add_argument("--sleep-seconds", type=float, default=0.15, help="Delay between sends. Timestamps are still embedded in the events.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-json", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    return parser.parse_args()


SCENARIOS: dict[str, ScenarioDefinition] = {}

SCENARIOS["mongo_auth_chain_confirmed"] = ScenarioDefinition(
    name="mongo_auth_chain_confirmed",
    rule_id="CORR_9XK2_MONGO_AUTH_CHAIN",
    description="Three MongoDB auth failures followed by client disconnect and host unreachable. Timings are spaced to avoid the 2m correlation dedupe window.",
    expected_signals=[
        "mongodb_auth_failed",
        "mongodb_auth_failed",
        "mongodb_auth_failed",
        "mongodb_interrupted_client_disconnected",
        "mongodb_host_unreachable",
    ],
    expected_services=["mongodb"],
    event_templates=[
        {
            "offset_seconds": 0,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79",
            "extra": {
                "c": "ACCESS",
                "code": 18,
                "attr": {"result": 18, "code": 18, "error": "AuthenticationFailed: bad credentials"},
                "mongodb": {"log": {"component": "ACCESS"}},
            },
        },
        {
            "offset_seconds": 121,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79",
            "extra": {
                "c": "ACCESS",
                "code": 18,
                "attr": {"result": 18, "code": 18, "error": "AuthenticationFailed: bad credentials"},
                "mongodb": {"log": {"component": "ACCESS"}},
            },
        },
        {
            "offset_seconds": 242,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79",
            "extra": {
                "c": "ACCESS",
                "code": 18,
                "attr": {"result": 18, "code": 18, "error": "AuthenticationFailed: bad credentials"},
                "mongodb": {"log": {"component": "ACCESS"}},
            },
        },
        {
            "offset_seconds": 300,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Interrupted operation as its client disconnected while waiting for upstream request completion",
            "extra": {
                "mongodb": {"log": {"component": "NETWORK"}},
            },
        },
        {
            "offset_seconds": 360,
            "module": "mongodb",
            "service": "mongodb",
            "level": "error",
            "message": "HostUnreachable: No route to host while connecting to upstream peer. Network is unreachable",
            "extra": {
                "code": 6,
                "attr": {"code": 6},
                "mongodb": {"log": {"component": "NETWORK"}},
            },
        },
    ],
)

SCENARIOS["mongo_auth_chain_partial"] = ScenarioDefinition(
    name="mongo_auth_chain_partial",
    rule_id="CORR_9XK2_MONGO_AUTH_CHAIN",
    description="Only two MongoDB auth failures, which should stay partial and typically remain a probable cause.",
    expected_signals=[
        "mongodb_auth_failed",
        "mongodb_auth_failed",
    ],
    expected_services=["mongodb"],
    event_templates=[
        {
            "offset_seconds": 0,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79",
            "extra": {
                "c": "ACCESS",
                "code": 18,
                "attr": {"result": 18, "code": 18, "error": "AuthenticationFailed: bad credentials"},
                "mongodb": {"log": {"component": "ACCESS"}},
            },
        },
        {
            "offset_seconds": 121,
            "module": "mongodb",
            "service": "mongodb",
            "level": "warning",
            "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79",
            "extra": {
                "c": "ACCESS",
                "code": 18,
                "attr": {"result": 18, "code": 18, "error": "AuthenticationFailed: bad credentials"},
                "mongodb": {"log": {"component": "ACCESS"}},
            },
        },
    ],
)

SCENARIOS["nginx_failure_spike_confirmed"] = ScenarioDefinition(
    name="nginx_failure_spike_confirmed",
    rule_id="CORR_T7Q1_WEB_FAILURE_SPIKE",
    description="Three nginx 5xx access logs followed by an nginx failure event. Timings are spaced beyond the 1m dedupe window.",
    expected_signals=[
        "nginx_access_5xx_any",
        "nginx_access_5xx_any",
        "nginx_access_5xx_any",
        "nginx_unclassified_failure",
    ],
    expected_services=["nginx"],
    event_templates=[
        {
            "offset_seconds": 0,
            "module": "nginx",
            "service": "nginx",
            "level": "warning",
            "message": "GET /api/orders upstream returned 502 after backend saturation",
            "extra": {
                "http": {"request": {"method": "GET"}, "response": {"status_code": 502}},
                "status": 502,
                "url": {"path": "/api/orders"},
            },
        },
        {
            "offset_seconds": 61,
            "module": "nginx",
            "service": "nginx",
            "level": "warning",
            "message": "GET /api/orders upstream returned 502 after backend saturation",
            "extra": {
                "http": {"request": {"method": "GET"}, "response": {"status_code": 502}},
                "status": 502,
                "url": {"path": "/api/orders"},
            },
        },
        {
            "offset_seconds": 122,
            "module": "nginx",
            "service": "nginx",
            "level": "warning",
            "message": "GET /api/orders upstream returned 502 after backend saturation",
            "extra": {
                "http": {"request": {"method": "GET"}, "response": {"status_code": 502}},
                "status": 502,
                "url": {"path": "/api/orders"},
            },
        },
        {
            "offset_seconds": 180,
            "module": "nginx",
            "service": "nginx",
            "level": "error",
            "message": "ERROR worker process exited unexpectedly after repeated 5xx spike",
            "extra": {
                "process": {"name": "nginx"},
            },
        },
    ],
)


def isoformat_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rfc3164_timestamp(dt: datetime) -> str:
    local_dt = dt.astimezone()
    month = local_dt.strftime("%b")
    day = str(local_dt.day).rjust(2, " ")
    return f"{month} {day} {local_dt.strftime('%H:%M:%S')}"


def nested_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = nested_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def flatten_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.append(next_prefix)
            paths.extend(flatten_paths(item, next_prefix))
        return paths
    if isinstance(value, list):
        paths: list[str] = []
        for item in value:
            paths.extend(flatten_paths(item, prefix))
        return paths
    return []


def assert_raw_input_payload(payload: dict[str, Any]) -> None:
    present_paths = set(flatten_paths(payload))
    forbidden = sorted(path for path in FORBIDDEN_RAW_OUTPUT_PATHS if path in present_paths)
    if forbidden:
        raise ValueError(
            "Outgoing test payload contains downstream-enriched RCA fields that must be produced by the pipeline, not by the sender: "
            + ", ".join(forbidden)
        )


def build_host_ip_value(device_ip: str, mode: str) -> Any:
    if mode == "single":
        return device_ip
    if mode == "array":
        return [device_ip, "127.0.0.1"]
    return f"{device_ip}, 127.0.0.1"


def build_event_payload(
    *,
    run_id: str,
    scenario: ScenarioDefinition,
    event_template: dict[str, Any],
    organization_id: str,
    device_ip: str,
    host_name: str,
    host_ip_mode: str,
    base_time: datetime,
) -> dict[str, Any]:
    timestamp = base_time + timedelta(seconds=int(event_template["offset_seconds"]))
    marker = f"rca_run_id:{run_id}"
    message = f'{event_template["message"]} [{marker}]'
    payload: dict[str, Any] = {
        "@timestamp": isoformat_utc(timestamp),
        "message": message,
        "msg": message,
        "event": {
            "organization": organization_id,
            "module": event_template["module"],
            "dataset": f'{event_template["module"]}.log',
        },
        "service": {
            "name": event_template["service"],
        },
        "host": {
            "name": host_name,
            "ip": build_host_ip_value(device_ip, host_ip_mode),
        },
        "log": {
            "level": event_template["level"],
        },
        "simulation": {
            "tool": "send_rca_confidence_test_logs.py",
            "scenario": scenario.name,
            "run_id": run_id,
            "marker": marker,
        },
        "tags": ["rca_test", "confidence_test", scenario.name],
    }
    merged = nested_merge(payload, event_template.get("extra", {}))
    assert_raw_input_payload(merged)
    return merged


def build_scenario_events(args: argparse.Namespace, scenario: ScenarioDefinition, run_id: str) -> list[dict[str, Any]]:
    base_time = datetime.now(timezone.utc) - timedelta(minutes=8)
    return [
        build_event_payload(
            run_id=run_id,
            scenario=scenario,
            event_template=event_template,
            organization_id=args.organization_id,
            device_ip=args.device_ip,
            host_name=args.host_name,
            host_ip_mode=args.host_ip_mode,
            base_time=base_time,
        )
        for event_template in scenario.event_templates
    ]


def encode_payload(event: dict[str, Any], payload_format: str, host_name: str) -> str:
    payload = json.dumps(event, separators=(",", ":"), ensure_ascii=True)
    if payload_format == "json-line":
        return payload
    now = datetime.now(timezone.utc)
    return f"{rfc3164_timestamp(now)} {host_name} {payload}"


class UDPSender:
    def __init__(self, host: str, port: int) -> None:
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, line: str) -> None:
        self.sock.sendto(line.encode("utf-8"), self.addr)

    def close(self) -> None:
        self.sock.close()


class TCPSender:
    def __init__(self, host: str, port: int) -> None:
        self.sock = socket.create_connection((host, port), timeout=5)

    def send(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode("utf-8"))

    def close(self) -> None:
        self.sock.close()


class FilebeatFileSender:
    def __init__(self, path: Path, truncate: bool) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if truncate else "a"
        self.handle = self.path.open(mode, encoding="utf-8", newline="\n")

    def send(self, line: str) -> None:
        self.handle.write(line + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def send_events(args: argparse.Namespace, encoded_events: list[str], structured_events: list[dict[str, Any]]) -> None:
    sender: UDPSender | TCPSender | FilebeatFileSender | None = None
    if not args.dry_run:
        if args.delivery_mode == "filebeat-file":
            sender = FilebeatFileSender(Path(args.spool_file).resolve(), args.truncate_spool)
        else:
            sender = UDPSender(args.target_host, args.target_port) if args.proto == "udp" else TCPSender(args.target_host, args.target_port)
    try:
        for index, (encoded, structured) in enumerate(zip(encoded_events, structured_events), start=1):
            if args.show_json or args.dry_run:
                print(f"[send {index}/{len(encoded_events)}] {json.dumps(structured, indent=2)}")
            else:
                destination = (
                    str(Path(args.spool_file).resolve())
                    if args.delivery_mode == "filebeat-file"
                    else f"{args.target_host}:{args.target_port}/{args.proto}"
                )
                print(
                    f"[send {index}/{len(encoded_events)}] "
                    f"{structured.get('@timestamp')} "
                    f"{structured.get('event', {}).get('module')} "
                    f"{structured.get('log', {}).get('level')} "
                    f"-> {destination}"
                )
            if not args.dry_run and sender is not None:
                sender.send(encoded)
            if index != len(encoded_events):
                time.sleep(max(args.sleep_seconds, 0))
    finally:
        if sender is not None:
            sender.close()


def iter_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(iter_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(iter_strings(item))
        return strings
    return [str(value)]


def source_matches_run(source: dict[str, Any], run_id: str) -> bool:
    simulation = source.get("simulation")
    if isinstance(simulation, dict) and str(simulation.get("run_id", "")).strip() == run_id:
        return True
    marker = f"rca_run_id:{run_id}"
    return any(marker in text for text in iter_strings(source))


def signal_names_from_source(source: dict[str, Any]) -> list[str]:
    signal = source.get("signal")
    if isinstance(signal, str) and signal.strip():
        return [signal.strip()]
    if isinstance(signal, list):
        return [str(item).strip() for item in signal if str(item).strip()]
    return []


def signal_present(source: dict[str, Any]) -> bool:
    value = source.get("signal_present")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return False


def detect_raw_doc_diagnostics(raw_docs: list[dict[str, Any]]) -> list[str]:
    diagnostics: list[str] = []
    grok_failures = 0
    wrapped_json = 0
    network_index_count = 0
    missing_module_count = 0

    for hit in raw_docs:
        if str(hit.get("_index", "")).startswith("network-"):
            network_index_count += 1
        source = hit.get("_source", {})
        if not isinstance(source, dict):
            continue
        tags = source.get("tags", [])
        if isinstance(tags, list) and "_grokparsefailure" in {str(tag) for tag in tags}:
            grok_failures += 1
        message = str(source.get("message", ""))
        event = source.get("event", {})
        if isinstance(event, dict) and not event.get("module"):
            missing_module_count += 1
        if "{\"@timestamp\"" in message or '{"@timestamp"' in message:
            wrapped_json += 1

    if raw_docs and grok_failures == len(raw_docs) and wrapped_json == len(raw_docs):
        diagnostics.append(
            "Raw payload was wrapped inside a syslog message and not JSON-parsed. The pipeline stored the whole JSON blob in `message`, so fields like `event.module`, `service.name`, `c`, and `attr.code` were not extracted."
        )
    if raw_docs and network_index_count == len(raw_docs):
        diagnostics.append(
            "These test docs landed in a `network-*` index, so the broad network rules can see them even when the intended MongoDB fields are missing."
        )
    if raw_docs and missing_module_count == len(raw_docs):
        diagnostics.append(
            "Stored raw docs are missing parsed `event.module`, which means the MongoDB service query (`event.module: mongodb`) cannot match them."
        )
    return diagnostics


def fetch_raw_docs(client: ElasticsearchHttpClient, index: str, run_id: str) -> list[dict[str, Any]]:
    hits = client.search(
        index,
        {
            "size": 200,
            "sort": [
                {"@timestamp": {"order": "asc", "unmapped_type": "date"}},
            ],
            "_source": True,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": "now-30m",
                                }
                            }
                        }
                    ],
                    "should": [
                        {"term": {"simulation.run_id.keyword": run_id}},
                        {"term": {"simulation.run_id": run_id}},
                        {"match_phrase": {"message": f"rca_run_id:{run_id}"}},
                        {"match_phrase": {"msg": f"rca_run_id:{run_id}"}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        },
    )
    matched = []
    for hit in hits:
        source = hit.get("_source", {})
        if isinstance(source, dict) and source_matches_run(source, run_id):
            matched.append(hit)
    return matched


def find_matching_correlation(
    client: ElasticsearchHttpClient,
    index: str,
    scenario: ScenarioDefinition,
    organization_id: str,
    raw_doc_ids: set[str],
) -> dict[str, Any] | None:
    hits = client.search(
        index,
        {
            "size": 50,
            "sort": [
                {"matched_at": {"order": "desc", "unmapped_type": "date"}},
                {"last_seen": {"order": "desc", "unmapped_type": "date"}},
            ],
            "_source": True,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "should": [
                                    {"term": {"rule_id.keyword": scenario.rule_id}},
                                    {"term": {"rule_id": scenario.rule_id}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {"term": {"organization_id.keyword": organization_id}},
                                    {"term": {"organization_id": organization_id}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {"range": {"matched_at": {"gte": "now-30m"}}},
                                    {"range": {"last_seen": {"gte": "now-30m"}}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
        },
    )
    best_hit: dict[str, Any] | None = None
    best_overlap = -1
    for hit in hits:
        source = hit.get("_source", {})
        evidence = source.get("log_id", [])
        matched_ids = {str(entry.get("id", "")).strip() for entry in evidence if isinstance(entry, dict)}
        overlap = len(raw_doc_ids.intersection(matched_ids))
        if overlap > best_overlap and overlap > 0:
            best_hit = hit
            best_overlap = overlap
    return best_hit


def load_rca_results(results_path: Path) -> list[dict[str, Any]]:
    if not results_path.exists():
        return []
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def find_matching_rca_record(results_path: Path, incident_id: str, raw_doc_ids: set[str]) -> dict[str, Any] | None:
    items = load_rca_results(results_path)
    for item in items:
        if str(item.get("incident_id", "")) == incident_id:
            return item
    best_item: dict[str, Any] | None = None
    best_overlap = -1
    for item in items:
        matched_doc_ids = {str(value).strip() for value in item.get("matched_doc_ids", [])}
        overlap = len(raw_doc_ids.intersection(matched_doc_ids))
        if overlap > best_overlap and overlap > 0:
            best_item = item
            best_overlap = overlap
    return best_item


def summarize_llm(record: dict[str, Any] | None, openai_enabled: bool) -> tuple[bool, str]:
    if record is None:
        return False, "waiting_for_rca"
    if not openai_enabled:
        return False, "openai_disabled"
    if str(record.get("classification", "")) != "confirmed_rca":
        return False, "not_confirmed_rca"
    llm = record.get("llm")
    if not isinstance(llm, dict):
        return False, "waiting_for_llm"
    if str(llm.get("error", "")).strip():
        return True, "llm_error"
    summary = str(llm.get("natural_language_summary", "")).strip()
    root_cause = str(llm.get("root_cause", "")).strip()
    if summary or root_cause:
        return True, "llm_ready"
    return False, "waiting_for_llm"


def collect_pipeline_status(
    *,
    client: ElasticsearchHttpClient,
    raw_index: str,
    correlation_index: str,
    results_path: Path,
    scenario: ScenarioDefinition,
    organization_id: str,
    run_id: str,
    openai_enabled: bool,
) -> PipelineStatus:
    raw_docs = fetch_raw_docs(client, raw_index, run_id)
    raw_doc_ids = [str(hit.get("_id", "")).strip() for hit in raw_docs]
    signal_counter: Counter[str] = Counter()
    signaled_count = 0
    for hit in raw_docs:
        source = hit.get("_source", {})
        if not isinstance(source, dict):
            continue
        if signal_present(source):
            signaled_count += 1
        for signal_name in signal_names_from_source(source):
            signal_counter[signal_name] += 1

    correlation_hit = None
    if raw_doc_ids:
        correlation_hit = find_matching_correlation(
            client=client,
            index=correlation_index,
            scenario=scenario,
            organization_id=organization_id,
            raw_doc_ids=set(raw_doc_ids),
        )

    rca_record = None
    if correlation_hit is not None:
        incident_id = str(correlation_hit.get("_source", {}).get("incident_id", "")).strip()
        if incident_id:
            rca_record = find_matching_rca_record(results_path, incident_id, set(raw_doc_ids))

    llm_ready, llm_status = summarize_llm(rca_record, openai_enabled)
    diagnostics = detect_raw_doc_diagnostics(raw_docs)
    return PipelineStatus(
        raw_docs=raw_docs,
        raw_doc_ids=raw_doc_ids,
        signaled_count=signaled_count,
        signal_counts=signal_counter,
        correlation_hit=correlation_hit,
        rca_record=rca_record,
        llm_ready=llm_ready,
        llm_status=llm_status,
        diagnostics=diagnostics,
    )


def print_status(status: PipelineStatus, scenario: ScenarioDefinition, openai_enabled: bool) -> None:
    print()
    print("Pipeline status")
    print("-" * 80)
    print(f"Raw docs found        : {len(status.raw_docs)}")
    print(f"Signalized docs       : {status.signaled_count}")
    if status.signal_counts:
        rendered = ", ".join(f"{name}={count}" for name, count in sorted(status.signal_counts.items()))
        print(f"Signals observed      : {rendered}")
    else:
        print("Signals observed      : none yet")

    if status.correlation_hit is None:
        print(f"Correlation ({scenario.rule_id}) : not found yet")
    else:
        source = status.correlation_hit.get("_source", {})
        audit = source.get("audit", {}) if isinstance(source.get("audit"), dict) else {}
        steps = audit.get("steps", []) if isinstance(audit.get("steps"), list) else []
        step_summary = ", ".join(
            f'{step.get("signal_key")}={step.get("matched_count", 0)}/{step.get("required_count", 0)}'
            for step in steps
            if isinstance(step, dict)
        ) or "none"
        print(f'Correlation incident  : {source.get("incident_id", "unknown")}')
        print(f'Rule completion       : {float(source.get("rule_completion", 0.0)):.4f}')
        print(f'Sequence match        : {float(source.get("sequence_match", 0.0)):.4f}')
        print(f"Audit step counts     : {step_summary}")

    if status.rca_record is None:
        print("RCA record            : not found yet")
    else:
        print(f'RCA classification    : {status.rca_record.get("classification", "unknown")}')
        print(f'RCA confidence score  : {float(status.rca_record.get("confidence_score", 0.0)):.4f}')
        reasons = status.rca_record.get("below_threshold_reasons", []) or []
        print(f"RCA reasons           : {'; '.join(str(reason) for reason in reasons) if reasons else 'none'}")

    if openai_enabled:
        print(f"LLM status            : {status.llm_status}")
        llm = status.rca_record.get("llm") if isinstance(status.rca_record, dict) else None
        if isinstance(llm, dict):
            root_cause = str(llm.get("root_cause", "")).strip()
            summary = str(llm.get("natural_language_summary", "")).strip()
            error_text = str(llm.get("error", "")).strip()
            if root_cause:
                print(f"LLM root cause        : {root_cause}")
            if summary:
                print(f"LLM summary           : {summary}")
            if error_text:
                print(f"LLM error             : {error_text}")
    else:
        print("LLM status            : openai_disabled")
    if status.diagnostics:
        print("Diagnostics           :")
        for line in status.diagnostics:
            print(f"  - {line}")


def completion_reached(status: PipelineStatus, openai_enabled: bool) -> bool:
    if status.rca_record is None:
        return False
    if not openai_enabled:
        return True
    classification = str(status.rca_record.get("classification", ""))
    if classification != "confirmed_rca":
        return True
    return status.llm_ready


def explain_timeout(status: PipelineStatus, scenario: ScenarioDefinition, openai_enabled: bool) -> None:
    print()
    print("Timeout diagnosis")
    print("-" * 80)
    if not status.raw_docs:
        print("No raw docs were found with this run ID. That usually means the sender did not reach Logstash or the input/pipeline did not index the documents.")
        return
    if not status.signal_counts:
        print("Raw docs arrived, but no signals were written yet. That usually means the signalizing rules did not match the payload fields or the signalizing cycle has not caught up.")
        return
    if status.correlation_hit is None:
        print(f"Signals were found, but correlation rule {scenario.rule_id} did not produce an incident yet. The common causes are dedupe, wrong timing, or mixed old/new events for the same topology identity.")
        return
    if status.rca_record is None:
        print("Correlation was found, but the RCA record was not written yet. That usually means the RCA scheduler has not reached the incident yet.")
        return
    if openai_enabled and str(status.rca_record.get("classification", "")) == "confirmed_rca" and not status.llm_ready:
        print("RCA confirmation exists, but the LLM result is still missing. That usually means the LLM call is still in flight or failed and has not been persisted yet.")
        return
    print("The pipeline progressed, but the expected final state was not observed inside the timeout.")


def wait_for_pipeline(
    *,
    client: ElasticsearchHttpClient,
    raw_index: str,
    correlation_index: str,
    results_path: Path,
    scenario: ScenarioDefinition,
    organization_id: str,
    run_id: str,
    openai_enabled: bool,
    timeout_seconds: int,
    interval_seconds: int,
) -> PipelineStatus:
    deadline = time.monotonic() + timeout_seconds
    last_signature: tuple[Any, ...] | None = None
    latest_status = PipelineStatus([], [], 0, Counter(), None, None, False, "waiting", [])
    while time.monotonic() < deadline:
        latest_status = collect_pipeline_status(
            client=client,
            raw_index=raw_index,
            correlation_index=correlation_index,
            results_path=results_path,
            scenario=scenario,
            organization_id=organization_id,
            run_id=run_id,
            openai_enabled=openai_enabled,
        )
        correlation_source = latest_status.correlation_hit.get("_source", {}) if latest_status.correlation_hit else {}
        rca_record = latest_status.rca_record or {}
        signature = (
            len(latest_status.raw_docs),
            latest_status.signaled_count,
            tuple(sorted(latest_status.signal_counts.items())),
            str(correlation_source.get("incident_id", "")),
            float(correlation_source.get("rule_completion", 0.0) or 0.0),
            float(correlation_source.get("sequence_match", 0.0) or 0.0),
            str(rca_record.get("classification", "")),
            float(rca_record.get("confidence_score", 0.0) or 0.0),
            latest_status.llm_status,
        )
        if signature != last_signature:
            print_status(latest_status, scenario, openai_enabled)
            last_signature = signature
        if completion_reached(latest_status, openai_enabled):
            return latest_status
        time.sleep(max(interval_seconds, 1))
    explain_timeout(latest_status, scenario, openai_enabled)
    return latest_status


def print_scenario_intro(
    *,
    run_id: str,
    scenario: ScenarioDefinition,
    args: argparse.Namespace,
    rca_settings: dict[str, Any],
    results_path: Path,
) -> None:
    print("RCA confidence test sender")
    print("=" * 80)
    print(f"Run ID                : {run_id}")
    print(f"Scenario              : {scenario.name}")
    print(f"Description           : {scenario.description}")
    print(f"Expected rule         : {scenario.rule_id}")
    if args.delivery_mode == "filebeat-file":
        print(f"Delivery mode         : {args.delivery_mode}")
        print(f"Spool file            : {Path(args.spool_file).resolve()}")
    else:
        print(f"Delivery mode         : {args.delivery_mode}")
        print(f"Target                : {args.target_host}:{args.target_port}/{args.proto}")
    print(f"Payload format        : {args.payload_format}")
    print(f"Organization ID       : {args.organization_id}")
    print(f"Host                  : {args.host_name}")
    print(f"Device IP             : {args.device_ip}")
    print(f"Host IP mode          : {args.host_ip_mode}")
    print(f"Raw index query       : {args.raw_index}")
    print(f"Correlation index     : {args.correlation_index or rca_settings['correlation_index']}")
    print(f"RCA results file      : {results_path}")
    print(f"OpenAI enabled        : {rca_settings['openai_enabled']}")
    if rca_settings["openai_model"]:
        print(f"OpenAI model          : {rca_settings['openai_model']}")
    print(f"Expected signals      : {', '.join(scenario.expected_signals)}")
    print("-" * 80)


def main() -> int:
    args = parse_args()
    run_id = args.run_id.strip() or uuid.uuid4().hex[:12]
    scenario = SCENARIOS[args.scenario]

    signalizing_config = Path(args.signalizing_config).resolve()
    rca_config = Path(args.rca_config).resolve()
    es_settings = load_signalizing_es_settings(signalizing_config)
    rca_settings = load_rca_settings(rca_config)
    correlation_index = args.correlation_index.strip() or rca_settings["correlation_index"]
    if args.rca_results_file:
        results_path = Path(args.rca_results_file).resolve()
    else:
        results_path = (rca_config.parent / Path(rca_settings["results_file"])).resolve()

    print_scenario_intro(
        run_id=run_id,
        scenario=scenario,
        args=args,
        rca_settings=rca_settings,
        results_path=results_path,
    )

    structured_events = build_scenario_events(args, scenario, run_id)
    encoded_events = [encode_payload(event, args.payload_format, args.host_name) for event in structured_events]
    send_events(args, encoded_events, structured_events)

    if args.dry_run or args.no_verify:
        print()
        print("Verification skipped.")
        if args.dry_run:
            print("The script did not send anything because --dry-run was enabled.")
        return 0

    client = ElasticsearchHttpClient(
        es_settings["address"],
        username=es_settings["username"],
        password=es_settings["password"],
        api_key=es_settings["api_key"],
    )
    final_status = wait_for_pipeline(
        client=client,
        raw_index=args.raw_index,
        correlation_index=correlation_index,
        results_path=results_path,
        scenario=scenario,
        organization_id=args.organization_id,
        run_id=run_id,
        openai_enabled=bool(rca_settings["openai_enabled"]),
        timeout_seconds=max(args.verify_timeout_seconds, 10),
        interval_seconds=max(args.verify_interval_seconds, 1),
    )

    print()
    print("Final result")
    print("=" * 80)
    if final_status.rca_record is None:
        print("RCA record was not found before timeout.")
        return 1

    classification = str(final_status.rca_record.get("classification", "unknown"))
    confidence = float(final_status.rca_record.get("confidence_score", 0.0) or 0.0)
    print(f"Classification        : {classification}")
    print(f"Confidence score      : {confidence:.4f}")
    if final_status.correlation_hit is not None:
        source = final_status.correlation_hit.get("_source", {})
        print(f'Incident ID           : {source.get("incident_id", "unknown")}')
        print(f'Rule completion       : {float(source.get("rule_completion", 0.0)):.4f}')
        print(f'Sequence match        : {float(source.get("sequence_match", 0.0)):.4f}')
    if final_status.signal_counts:
        rendered = ", ".join(f"{name}={count}" for name, count in sorted(final_status.signal_counts.items()))
        print(f"Observed signals      : {rendered}")
    if final_status.llm_status == "llm_ready":
        llm = final_status.rca_record.get("llm", {})
        print(f'LLM root cause        : {llm.get("root_cause", "")}')
        print(f'LLM summary           : {llm.get("natural_language_summary", "")}')
    elif bool(rca_settings["openai_enabled"]):
        print(f"LLM status            : {final_status.llm_status}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
