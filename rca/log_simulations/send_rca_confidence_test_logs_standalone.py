#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "y", "on"}


DEFAULTS = {
    "target_host": os.getenv("RCA_TARGET_HOST", "127.0.0.1"),
    "target_port": int(os.getenv("RCA_TARGET_PORT", "5048")),
    "proto": os.getenv("RCA_PROTO", "udp"),
    "payload_format": os.getenv("RCA_PAYLOAD_FORMAT", "syslog-json"),
    "delivery_mode": os.getenv("RCA_DELIVERY_MODE", "direct-network"),
    "spool_file": os.getenv("RCA_SPOOL_FILE", "filebeat_rca_input.log"),
    "organization_id": os.getenv("RCA_ORGANIZATION_ID", "135098068173316952064"),
    "device_ip": os.getenv("RCA_DEVICE_IP", "10.0.6.79"),
    "host_name": os.getenv("RCA_HOST_NAME", "win-rca-lab"),
    "raw_index": os.getenv("RCA_RAW_INDEX", "*,-rca_correlated_events*,-rca_correlated_incidents_current*,-rca-checkpoints*"),
    "correlation_index": os.getenv("RCA_CORRELATION_INDEX", "rca_correlated_incidents_current*,rca_correlated_events*"),
    "verify_timeout": int(os.getenv("RCA_VERIFY_TIMEOUT_SECONDS", "240")),
    "verify_interval": int(os.getenv("RCA_VERIFY_INTERVAL_SECONDS", "5")),
    "es_url": os.getenv("RCA_ES_URL", ""),
    "es_username": os.getenv("RCA_ES_USERNAME", ""),
    "es_password": os.getenv("RCA_ES_PASSWORD", ""),
    "es_api_key": os.getenv("RCA_ES_API_KEY", ""),
    "rca_results_file": os.getenv("RCA_RESULTS_FILE", ""),
    "openai_enabled": env_bool("RCA_OPENAI_ENABLED", False),
    "openai_model": os.getenv("RCA_OPENAI_MODEL", ""),
}

FORBIDDEN_PATHS = {
    "signal",
    "signal_present",
    "source_id",
    "source_index",
    "rule_completion",
    "sequence_match",
    "incident_id",
    "audit",
}

SCENARIOS = {
    "mongo_auth_chain_confirmed": {
        "rule_id": "CORR_9XK2_MONGO_AUTH_CHAIN",
        "description": "3 auth failures, then disconnect, then host unreachable.",
        "signals": [
            "mongodb_auth_failed",
            "mongodb_auth_failed",
            "mongodb_auth_failed",
            "mongodb_interrupted_client_disconnected",
            "mongodb_host_unreachable",
        ],
        "events": [
            {"offset": 0, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79", "extra": {"c": "ACCESS", "code": 18, "attr": {"result": 18, "code": 18}, "mongodb": {"log": {"component": "ACCESS"}}}},
            {"offset": 121, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79", "extra": {"c": "ACCESS", "code": 18, "attr": {"result": 18, "code": 18}, "mongodb": {"log": {"component": "ACCESS"}}}},
            {"offset": 242, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79", "extra": {"c": "ACCESS", "code": 18, "attr": {"result": 18, "code": 18}, "mongodb": {"log": {"component": "ACCESS"}}}},
            {"offset": 300, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Interrupted operation as its client disconnected while waiting for upstream request completion", "extra": {"mongodb": {"log": {"component": "NETWORK"}}}},
            {"offset": 360, "module": "mongodb", "service": "mongodb", "level": "error", "message": "HostUnreachable: No route to host while connecting to upstream peer. Network is unreachable", "extra": {"code": 6, "attr": {"code": 6}, "mongodb": {"log": {"component": "NETWORK"}}}},
        ],
    },
    "mongo_auth_chain_partial": {
        "rule_id": "CORR_9XK2_MONGO_AUTH_CHAIN",
        "description": "2 auth failures only.",
        "signals": ["mongodb_auth_failed", "mongodb_auth_failed"],
        "events": [
            {"offset": 0, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79", "extra": {"c": "ACCESS", "code": 18, "attr": {"result": 18, "code": 18}, "mongodb": {"log": {"component": "ACCESS"}}}},
            {"offset": 121, "module": "mongodb", "service": "mongodb", "level": "warning", "message": "Failed to authenticate user root against admin database. AuthenticationFailed for client 10.0.6.79", "extra": {"c": "ACCESS", "code": 18, "attr": {"result": 18, "code": 18}, "mongodb": {"log": {"component": "ACCESS"}}}},
        ],
    },
    "nginx_failure_spike_confirmed": {
        "rule_id": "CORR_T7Q1_WEB_FAILURE_SPIKE",
        "description": "3 nginx 5xx access logs, then nginx failure.",
        "signals": ["nginx_access_5xx_any", "nginx_access_5xx_any", "nginx_access_5xx_any", "nginx_unclassified_failure"],
        "events": [
            {"offset": 0, "module": "nginx", "service": "nginx", "level": "warning", "message": "GET /api/orders upstream returned 502 after backend saturation", "extra": {"http": {"request": {"method": "GET"}, "response": {"status_code": 502}}, "status": 502, "url": {"path": "/api/orders"}}},
            {"offset": 61, "module": "nginx", "service": "nginx", "level": "warning", "message": "GET /api/orders upstream returned 502 after backend saturation", "extra": {"http": {"request": {"method": "GET"}, "response": {"status_code": 502}}, "status": 502, "url": {"path": "/api/orders"}}},
            {"offset": 122, "module": "nginx", "service": "nginx", "level": "warning", "message": "GET /api/orders upstream returned 502 after backend saturation", "extra": {"http": {"request": {"method": "GET"}, "response": {"status_code": 502}}, "status": 502, "url": {"path": "/api/orders"}}},
            {"offset": 180, "module": "nginx", "service": "nginx", "level": "error", "message": "ERROR worker process exited unexpectedly after repeated 5xx spike", "extra": {"process": {"name": "nginx"}}},
        ],
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Portable single-file RCA confidence test sender.")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="mongo_auth_chain_confirmed")
    p.add_argument("--delivery-mode", choices=["direct-network", "filebeat-file"], default=DEFAULTS["delivery_mode"])
    p.add_argument("--target-host", default=DEFAULTS["target_host"])
    p.add_argument("--target-port", type=int, default=DEFAULTS["target_port"])
    p.add_argument("--proto", choices=["udp", "tcp"], default=DEFAULTS["proto"])
    p.add_argument("--payload-format", choices=["syslog-json", "json-line"], default=DEFAULTS["payload_format"])
    p.add_argument("--spool-file", default=DEFAULTS["spool_file"])
    p.add_argument("--truncate-spool", action="store_true")
    p.add_argument("--organization-id", default=DEFAULTS["organization_id"])
    p.add_argument("--device-ip", default=DEFAULTS["device_ip"])
    p.add_argument("--host-name", default=DEFAULTS["host_name"])
    p.add_argument("--host-ip-mode", choices=["single", "comma-list", "array"], default="comma-list")
    p.add_argument("--run-id", default="")
    p.add_argument("--sleep-seconds", type=float, default=0.15)
    p.add_argument("--es-url", default=DEFAULTS["es_url"])
    p.add_argument("--es-username", default=DEFAULTS["es_username"])
    p.add_argument("--es-password", default=DEFAULTS["es_password"])
    p.add_argument("--es-api-key", default=DEFAULTS["es_api_key"])
    p.add_argument("--raw-index", default=DEFAULTS["raw_index"])
    p.add_argument("--correlation-index", default=DEFAULTS["correlation_index"])
    p.add_argument("--rca-results-file", default=DEFAULTS["rca_results_file"])
    p.add_argument("--verify-timeout-seconds", type=int, default=DEFAULTS["verify_timeout"])
    p.add_argument("--verify-interval-seconds", type=int, default=DEFAULTS["verify_interval"])
    p.add_argument("--openai-enabled", dest="openai_enabled", action="store_true", default=DEFAULTS["openai_enabled"])
    p.add_argument("--openai-disabled", dest="openai_enabled", action="store_false")
    p.add_argument("--openai-model", default=DEFAULTS["openai_model"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--show-json", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    return p.parse_args()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rfc3164(dt: datetime) -> str:
    local_dt = dt.astimezone()
    return f"{local_dt.strftime('%b')} {str(local_dt.day).rjust(2, ' ')} {local_dt.strftime('%H:%M:%S')}"


def merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def flatten_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        items: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            items.append(path)
            items.extend(flatten_paths(child, path))
        return items
    if isinstance(value, list):
        items: list[str] = []
        for child in value:
            items.extend(flatten_paths(child, prefix))
        return items
    return []


def host_ip_value(device_ip: str, mode: str) -> Any:
    if mode == "single":
        return device_ip
    if mode == "array":
        return [device_ip, "127.0.0.1"]
    return f"{device_ip}, 127.0.0.1"


def build_events(args: argparse.Namespace, run_id: str) -> list[dict[str, Any]]:
    scenario = SCENARIOS[args.scenario]
    base_time = datetime.now(timezone.utc) - timedelta(minutes=8)
    events: list[dict[str, Any]] = []
    for item in scenario["events"]:
        marker = f"rca_run_id:{run_id}"
        timestamp = base_time + timedelta(seconds=int(item["offset"]))
        payload = {
            "@timestamp": iso(timestamp),
            "message": f'{item["message"]} [{marker}]',
            "msg": f'{item["message"]} [{marker}]',
            "event": {"organization": args.organization_id, "module": item["module"], "dataset": f'{item["module"]}.log'},
            "service": {"name": item["service"]},
            "host": {"name": args.host_name, "ip": host_ip_value(args.device_ip, args.host_ip_mode)},
            "log": {"level": item["level"]},
            "simulation": {"tool": Path(__file__).name, "scenario": args.scenario, "run_id": run_id, "marker": marker},
            "tags": ["rca_test", "confidence_test", args.scenario],
        }
        payload = merge(payload, item.get("extra", {}))
        forbidden = sorted(path for path in FORBIDDEN_PATHS if path in set(flatten_paths(payload)))
        if forbidden:
            raise ValueError("Payload contains downstream RCA fields: " + ", ".join(forbidden))
        events.append(payload)
    return events


def encode_event(event: dict[str, Any], payload_format: str, host_name: str) -> str:
    body = json.dumps(event, separators=(",", ":"), ensure_ascii=True)
    return body if payload_format == "json-line" else f"{rfc3164(datetime.now(timezone.utc))} {host_name} {body}"


class Sender:
    def send(self, line: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None


class UDPSender(Sender):
    def __init__(self, host: str, port: int) -> None:
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, line: str) -> None:
        self.sock.sendto(line.encode("utf-8"), self.addr)

    def close(self) -> None:
        self.sock.close()


class TCPSender(Sender):
    def __init__(self, host: str, port: int) -> None:
        self.sock = socket.create_connection((host, port), timeout=5)

    def send(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode("utf-8"))

    def close(self) -> None:
        self.sock.close()


class FileSender(Sender):
    def __init__(self, path: Path, truncate: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.handle = path.open("w" if truncate else "a", encoding="utf-8", newline="\n")

    def send(self, line: str) -> None:
        self.handle.write(line + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def make_sender(args: argparse.Namespace) -> Sender:
    if args.delivery_mode == "filebeat-file":
        return FileSender(Path(args.spool_file).resolve(), args.truncate_spool)
    return UDPSender(args.target_host, args.target_port) if args.proto == "udp" else TCPSender(args.target_host, args.target_port)


def es_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if args.es_api_key:
        headers["Authorization"] = f"ApiKey {args.es_api_key}"
    elif args.es_username or args.es_password:
        token = base64.b64encode(f"{args.es_username}:{args.es_password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def es_search(args: argparse.Namespace, index: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    req = request.Request(
        args.es_url.rstrip("/") + f"/{index}/_search",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=es_headers(args),
    )
    try:
        with request.urlopen(req, timeout=30) as res:
            body = res.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Elasticsearch request failed ({exc.code} {exc.reason}): {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to connect to Elasticsearch at {args.es_url}: {exc}") from exc
    return json.loads(body).get("hits", {}).get("hits", []) if body else []


def iter_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(iter_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(iter_strings(item))
        return out
    return [str(value)]


def matches_run(source: dict[str, Any], run_id: str) -> bool:
    sim = source.get("simulation")
    if isinstance(sim, dict) and str(sim.get("run_id", "")).strip() == run_id:
        return True
    marker = f"rca_run_id:{run_id}"
    return any(marker in text for text in iter_strings(source))


def fetch_raw_docs(args: argparse.Namespace, run_id: str) -> list[dict[str, Any]]:
    hits = es_search(args, args.raw_index, {
        "size": 200,
        "sort": [{"@timestamp": {"order": "asc", "unmapped_type": "date"}}],
        "_source": True,
        "query": {
            "bool": {
                "filter": [{"range": {"@timestamp": {"gte": "now-30m"}}}],
                "should": [
                    {"term": {"simulation.run_id.keyword": run_id}},
                    {"term": {"simulation.run_id": run_id}},
                    {"match_phrase": {"message": f"rca_run_id:{run_id}"}},
                    {"match_phrase": {"msg": f"rca_run_id:{run_id}"}},
                ],
                "minimum_should_match": 1,
            }
        },
    })
    return [hit for hit in hits if isinstance(hit.get("_source"), dict) and matches_run(hit["_source"], run_id)]


def find_correlation(args: argparse.Namespace, run_id: str, raw_ids: set[str]) -> dict[str, Any] | None:
    scenario = SCENARIOS[args.scenario]
    hits = es_search(args, args.correlation_index, {
        "size": 50,
        "sort": [{"matched_at": {"order": "desc", "unmapped_type": "date"}}, {"last_seen": {"order": "desc", "unmapped_type": "date"}}],
        "_source": True,
        "query": {
            "bool": {
                "filter": [
                    {"bool": {"should": [{"term": {"rule_id.keyword": scenario["rule_id"]}}, {"term": {"rule_id": scenario["rule_id"]}}], "minimum_should_match": 1}},
                    {"bool": {"should": [{"term": {"organization_id.keyword": args.organization_id}}, {"term": {"organization_id": args.organization_id}}], "minimum_should_match": 1}},
                    {"bool": {"should": [{"range": {"matched_at": {"gte": "now-30m"}}}, {"range": {"last_seen": {"gte": "now-30m"}}}], "minimum_should_match": 1}},
                ]
            }
        },
    })
    best = None
    overlap_best = -1
    for hit in hits:
        evidence = hit.get("_source", {}).get("log_id", [])
        ids = {str(item.get("id", "")).strip() for item in evidence if isinstance(item, dict)}
        overlap = len(raw_ids.intersection(ids))
        if overlap > overlap_best and overlap > 0:
            best = hit
            overlap_best = overlap
    return best


def load_results(path_text: str) -> list[dict[str, Any]]:
    if not path_text.strip():
        return []
    path = Path(path_text).resolve()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def find_rca_record(results_file: str, incident_id: str, raw_ids: set[str]) -> dict[str, Any] | None:
    items = load_results(results_file)
    for item in items:
        if str(item.get("incident_id", "")) == incident_id:
            return item
    best = None
    overlap_best = -1
    for item in items:
        ids = {str(x).strip() for x in item.get("matched_doc_ids", [])}
        overlap = len(raw_ids.intersection(ids))
        if overlap > overlap_best and overlap > 0:
            best = item
            overlap_best = overlap
    return best


def llm_state(record: dict[str, Any] | None, openai_enabled: bool) -> tuple[bool, str]:
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
    if str(llm.get("natural_language_summary", "")).strip() or str(llm.get("root_cause", "")).strip():
        return True, "llm_ready"
    return False, "waiting_for_llm"


def diagnose(raw_docs: list[dict[str, Any]]) -> list[str]:
    if not raw_docs:
        return []
    tags_all = []
    wrapped = 0
    network = 0
    missing_module = 0
    for hit in raw_docs:
        if str(hit.get("_index", "")).startswith("network-"):
            network += 1
        source = hit.get("_source", {})
        tags_all.append(isinstance(source.get("tags"), list) and "_grokparsefailure" in {str(x) for x in source.get("tags", [])})
        msg = str(source.get("message", ""))
        if "{\"@timestamp\"" in msg or '{"@timestamp"' in msg:
            wrapped += 1
        event = source.get("event", {})
        if isinstance(event, dict) and not event.get("module"):
            missing_module += 1
    out: list[str] = []
    if all(tags_all) and wrapped == len(raw_docs):
        out.append("Raw JSON was wrapped inside syslog and not parsed into fields.")
    if network == len(raw_docs):
        out.append("All docs landed in a network index, so generic network rules may win.")
    if missing_module == len(raw_docs):
        out.append("Parsed event.module is missing, so module-specific signal rules cannot match.")
    return out


def print_intro(args: argparse.Namespace, run_id: str) -> None:
    scenario = SCENARIOS[args.scenario]
    print("Portable RCA confidence test sender")
    print("=" * 80)
    print(f"Run ID                : {run_id}")
    print(f"Scenario              : {args.scenario}")
    print(f"Description           : {scenario['description']}")
    print(f"Expected rule         : {scenario['rule_id']}")
    print(f"Delivery mode         : {args.delivery_mode}")
    if args.delivery_mode == "filebeat-file":
        print(f"Spool file            : {Path(args.spool_file).resolve()}")
    else:
        print(f"Target                : {args.target_host}:{args.target_port}/{args.proto}")
    print(f"Payload format        : {args.payload_format}")
    print(f"Organization ID       : {args.organization_id}")
    print(f"Device IP             : {args.device_ip}")
    print(f"Host                  : {args.host_name}")
    print(f"Raw index query       : {args.raw_index}")
    print(f"Correlation index     : {args.correlation_index}")
    print(f"RCA results file      : {Path(args.rca_results_file).resolve() if args.rca_results_file else '(not provided)'}")
    print(f"Elasticsearch URL     : {args.es_url or '(not provided)'}")
    print(f"OpenAI enabled        : {args.openai_enabled}")
    if args.openai_model:
        print(f"OpenAI model          : {args.openai_model}")
    print(f"Expected signals      : {', '.join(scenario['signals'])}")
    print("-" * 80)


def print_status(raw_docs: list[dict[str, Any]], signals: Counter[str], corr: dict[str, Any] | None, rca: dict[str, Any] | None, llm_status_text: str, diagnostics: list[str], results_file: str) -> None:
    print()
    print("Pipeline status")
    print("-" * 80)
    print(f"Raw docs found        : {len(raw_docs)}")
    print(f"Signalized docs       : {sum(1 for hit in raw_docs if bool(hit.get('_source', {}).get('signal_present')))}")
    print(f"Signals observed      : {', '.join(f'{k}={v}' for k, v in sorted(signals.items())) if signals else 'none yet'}")
    if corr is None:
        print("Correlation           : not found yet")
    else:
        src = corr.get("_source", {})
        print(f"Correlation incident  : {src.get('incident_id', 'unknown')}")
        print(f"Rule completion       : {float(src.get('rule_completion', 0.0)):.4f}")
        print(f"Sequence match        : {float(src.get('sequence_match', 0.0)):.4f}")
    if not results_file:
        print("RCA record            : skipped (no --rca-results-file provided)")
    elif rca is None:
        print("RCA record            : not found yet")
    else:
        print(f"RCA classification    : {rca.get('classification', 'unknown')}")
        print(f"RCA confidence score  : {float(rca.get('confidence_score', 0.0)):.4f}")
    print(f"LLM status            : {llm_status_text}")
    if diagnostics:
        print("Diagnostics           :")
        for item in diagnostics:
            print(f"  - {item}")


def wait_for_pipeline(args: argparse.Namespace, run_id: str) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any] | None, dict[str, Any] | None, str, list[str]]:
    deadline = time.monotonic() + max(args.verify_timeout_seconds, 10)
    last_sig = None
    while time.monotonic() < deadline:
        raw_docs = fetch_raw_docs(args, run_id)
        signals: Counter[str] = Counter()
        for hit in raw_docs:
            src = hit.get("_source", {})
            signal = src.get("signal")
            if isinstance(signal, str) and signal.strip():
                signals[signal.strip()] += 1
            elif isinstance(signal, list):
                for item in signal:
                    text = str(item).strip()
                    if text:
                        signals[text] += 1
        raw_ids = {str(hit.get("_id", "")).strip() for hit in raw_docs}
        corr = find_correlation(args, run_id, raw_ids) if raw_ids else None
        rca = None
        llm_ready, llm_status_text = (False, "waiting_for_rca")
        if corr is not None and args.rca_results_file:
            incident_id = str(corr.get("_source", {}).get("incident_id", "")).strip()
            if incident_id:
                rca = find_rca_record(args.rca_results_file, incident_id, raw_ids)
            llm_ready, llm_status_text = llm_state(rca, args.openai_enabled)
        elif corr is not None and not args.rca_results_file:
            llm_status_text = "rca_results_file_not_provided"
        diagnostics = diagnose(raw_docs)
        sig = (len(raw_docs), tuple(sorted(signals.items())), str(corr.get("_source", {}).get("incident_id", "")) if corr else "", str((rca or {}).get("classification", "")), llm_status_text)
        if sig != last_sig:
            print_status(raw_docs, signals, corr, rca, llm_status_text, diagnostics, args.rca_results_file)
            last_sig = sig
        if not args.rca_results_file and corr is not None:
            return raw_docs, signals, corr, rca, llm_status_text, diagnostics
        if rca is not None and (not args.openai_enabled or str(rca.get("classification", "")) != "confirmed_rca" or llm_ready):
            return raw_docs, signals, corr, rca, llm_status_text, diagnostics
        time.sleep(max(args.verify_interval_seconds, 1))
    return raw_docs, signals, corr, rca, llm_status_text, diagnostics


def main() -> int:
    args = parse_args()
    run_id = args.run_id.strip() or uuid.uuid4().hex[:12]
    print_intro(args, run_id)

    events = build_events(args, run_id)
    lines = [encode_event(event, args.payload_format, args.host_name) for event in events]
    sender = None if args.dry_run else make_sender(args)
    try:
        for i, (event, line) in enumerate(zip(events, lines), start=1):
            if args.show_json or args.dry_run:
                print(f"[send {i}/{len(events)}] {json.dumps(event, indent=2)}")
            else:
                destination = str(Path(args.spool_file).resolve()) if args.delivery_mode == "filebeat-file" else f"{args.target_host}:{args.target_port}/{args.proto}"
                print(f"[send {i}/{len(events)}] {event['@timestamp']} {event['event']['module']} {event['log']['level']} -> {destination}")
            if sender is not None:
                sender.send(line)
            if i != len(events):
                time.sleep(max(args.sleep_seconds, 0))
    finally:
        if sender is not None:
            sender.close()

    if args.dry_run:
        print("\nVerification skipped because --dry-run is enabled.")
        return 0
    if args.no_verify:
        print("\nVerification skipped because --no-verify is enabled.")
        return 0
    if not args.es_url.strip():
        print("\nVerification skipped because no --es-url was provided.")
        return 0

    raw_docs, signals, corr, rca, llm_status_text, _ = wait_for_pipeline(args, run_id)
    print()
    print("Final result")
    print("=" * 80)
    if not args.rca_results_file:
        if corr is None:
            print("Correlation incident was not found before timeout.")
            return 1
        src = corr.get("_source", {})
        print("Correlation verified successfully.")
        print(f"Incident ID           : {src.get('incident_id', 'unknown')}")
        print(f"Rule completion       : {float(src.get('rule_completion', 0.0)):.4f}")
        print(f"Sequence match        : {float(src.get('sequence_match', 0.0)):.4f}")
        print(f"Observed signals      : {', '.join(f'{k}={v}' for k, v in sorted(signals.items())) if signals else 'none'}")
        print("RCA/LLM verification skipped because no --rca-results-file was provided.")
        return 0
    if rca is None:
        print("RCA record was not found before timeout.")
        return 1
    print(f"Classification        : {rca.get('classification', 'unknown')}")
    print(f"Confidence score      : {float(rca.get('confidence_score', 0.0)):.4f}")
    if corr is not None:
        src = corr.get("_source", {})
        print(f"Incident ID           : {src.get('incident_id', 'unknown')}")
        print(f"Rule completion       : {float(src.get('rule_completion', 0.0)):.4f}")
        print(f"Sequence match        : {float(src.get('sequence_match', 0.0)):.4f}")
    print(f"Observed signals      : {', '.join(f'{k}={v}' for k, v in sorted(signals.items())) if signals else 'none'}")
    if args.openai_enabled:
        print(f"LLM status            : {llm_status_text}")
        if llm_status_text == "llm_ready":
            llm = rca.get("llm", {})
            print(f"LLM root cause        : {llm.get('root_cause', '')}")
            print(f"LLM summary           : {llm.get('natural_language_summary', '')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
