#!/usr/bin/env python3
"""
syslog_simulator.py

Config-driven multi-vendor syslog simulator for sending raw (non-normalized) text lines
to Logstash (or any UDP/TCP syslog listener).

Highlights
- --defaults PATH loads a JSON config (deep-merged over built-ins)
- CLI overrides for common settings + --set dot-path for arbitrary overrides
- Vendor profiles + device instances
- Per-device-category toggles: switch/router/firewall/loadbalancer/security-appliance/wireless/other
- RFC3164 + RFC5424 envelopes; optional PRI header (<PRI>)
- Real-time timestamps; configurable severity bias
- Stdlib-only validation

Config precedence (lowest -> highest):
1) Built-in defaults in this script
2) JSON defaults file (--defaults)
3) Explicit CLI flags
4) --set KEY=VALUE overrides
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import random
import re
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

CATEGORIES = [
    "switch",
    "router",
    "firewall",
    "loadbalancer",
    "security-appliance",
    "wireless",
    "other",
]

SEVERITIES = ["critical", "error", "warning", "info"]
SEV_TO_SYSLOG_NUM = {"critical": 2, "error": 3, "warning": 4, "info": 6}

VAR_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


class ConfigError(Exception):
    pass


@dataclass(slots=True)
class GeneratedLogEvent:
    """One generated syslog event plus metadata for trace logging."""

    line: str
    payload: str
    source_device_id: str
    source_hostname: str
    source_category: str
    source_vendor_id: str
    source_vendor_name: str
    source_ip: str
    severity: str
    facility: int
    envelope: str
    template_id: str


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def deep_merge(base: Any, override: Any) -> Any:
    """Deep-merge dictionaries; lists/scalars replaced (not concatenated)."""
    if override is None:
        return base
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = deep_merge(out.get(k), v) if k in out else v
        return out
    return override


def set_dot_path(cfg: Dict[str, Any], path: str, value: Any) -> None:
    """Set cfg[a][b][c] = value for dot-path 'a.b.c'."""
    parts = path.split(".")
    cur: Dict[str, Any] = cfg
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def parse_jsonish(s: str) -> Any:
    """Parse JSON if possible; otherwise return string."""
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        return s


def parse_csv_list(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def normalize_weights(weights: Dict[str, Any], path: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    total = 0.0
    for k in SEVERITIES:
        w = float(weights.get(k, 0.0) or 0.0)
        if w < 0:
            raise ConfigError(f"{path}: negative weight for '{k}'")
        out[k] = w
        total += w
    if total <= 0:
        raise ConfigError(f"{path}: weights sum to 0")
    for k in out:
        out[k] /= total
    return out


def choose_weighted(rng: random.Random, weights_norm: Dict[str, float]) -> str:
    keys = list(weights_norm.keys())
    vals = [weights_norm[k] for k in keys]
    return rng.choices(keys, weights=vals, k=1)[0]


def render(template: str, ctx: Dict[str, Any]) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        return str(ctx.get(key, f"{{{{{key}}}}}"))
    return VAR_RE.sub(repl, template)


def rfc3164_timestamp(dt: datetime) -> str:
    dt = dt.astimezone()
    month = dt.strftime("%b")
    day = str(dt.day).rjust(2, " ")
    return f"{month} {day} {dt.strftime('%H:%M:%S')}"


def rfc5424_timestamp(dt: datetime, tz_mode: str) -> str:
    # RFC5424 uses RFC3339 timestamps.
    if tz_mode == "utc":
        dt = dt.astimezone(timezone.utc)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return dt.astimezone().isoformat(timespec="milliseconds")


def calc_pri(facility: int, severity: str) -> int:
    return facility * 8 + SEV_TO_SYSLOG_NUM[severity]


def random_private_ip(rng: random.Random) -> str:
    pick = rng.choice(["10", "172", "192"])
    if pick == "10":
        return f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
    if pick == "172":
        return f"172.{rng.randint(16,31)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
    return f"192.168.{rng.randint(0,255)}.{rng.randint(1,254)}"


def random_public_ip(rng: random.Random) -> str:
    # Avoid common private/reserved prefixes; this is just simulation.
    while True:
        a = rng.randint(1, 223)
        if a in (10, 127, 172, 192):
            continue
        return f"{a}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def random_mac(rng: random.Random) -> str:
    return ":".join(f"{rng.randint(0,255):02x}" for _ in range(6))


def pick_seed(rng: random.Random, items: Any, fallback_fn) -> str:
    if isinstance(items, list) and items:
        return rng.choice(items)
    return fallback_fn(rng)


def validate_config(cfg: Dict[str, Any]) -> None:
    """Focused stdlib-only validation."""
    errors: List[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    if cfg.get("version") != 1:
        err("version: expected 1")

    target = cfg.get("target")
    if not isinstance(target, dict):
        err("target: object required")
    else:
        if not isinstance(target.get("host"), str) or not target["host"]:
            err("target.host: non-empty string required")
        if not isinstance(target.get("port"), int) or not (1 <= int(target["port"]) <= 65535):
            err("target.port: int 1..65535 required")
        if target.get("proto") not in ("udp", "tcp"):
            err("target.proto: udp|tcp required")
        if target.get("tcp_framing", "newline") not in ("newline", "octet-counting"):
            err("target.tcp_framing: newline|octet-counting required")

    runtime = cfg.get("runtime")
    if not isinstance(runtime, dict):
        err("runtime: object required")
    else:
        if not isinstance(runtime.get("rate"), (int, float)) or float(runtime["rate"]) < 0:
            err("runtime.rate: number >= 0 required")
        if not isinstance(runtime.get("batch_size"), int) or int(runtime["batch_size"]) <= 0:
            err("runtime.batch_size: int > 0 required")
        if not isinstance(runtime.get("count"), int) or int(runtime["count"]) < 0:
            err("runtime.count: int >= 0 required")
        if runtime.get("timestamp_timezone", "local") not in ("local", "utc"):
            err("runtime.timestamp_timezone: local|utc required")
        if not isinstance(runtime.get("include_pri"), bool):
            err("runtime.include_pri: bool required")
        if not isinstance(runtime.get("dry_run"), bool):
            err("runtime.dry_run: bool required")
        if "print_send_details" in runtime and not isinstance(runtime.get("print_send_details"), bool):
            err("runtime.print_send_details: bool required when provided")

    cats = cfg.get("categories")
    if not isinstance(cats, dict):
        err("categories: object required")
    else:
        for c in CATEGORIES:
            if c not in cats or not isinstance(cats[c], bool):
                err(f"categories.{c}: bool required")

    sw = cfg.get("severity_weights")
    if not isinstance(sw, dict):
        err("severity_weights: object required")
    else:
        try:
            normalize_weights(sw, "severity_weights")
        except ConfigError as ce:
            err(str(ce))

    defaults = cfg.get("defaults", {})
    if not isinstance(defaults, dict):
        err("defaults: object required")
    else:
        fac = defaults.get("facility", 23)
        if not isinstance(fac, int) or not (0 <= fac <= 23):
            err("defaults.facility: int 0..23 required")

    vendors = cfg.get("vendors")
    devices = cfg.get("devices")
    if not isinstance(vendors, dict) or not vendors:
        err("vendors: non-empty object required")
    if not isinstance(devices, list) or not devices:
        err("devices: non-empty list required")

    if isinstance(vendors, dict):
        for vid, vcfg in vendors.items():
            if not isinstance(vcfg, dict):
                err(f"vendors.{vid}: object required")
                continue
            if not isinstance(vcfg.get("display_name"), str) or not vcfg["display_name"]:
                err(f"vendors.{vid}.display_name: non-empty string required")
            templates = vcfg.get("templates")
            if not isinstance(templates, list) or not templates:
                err(f"vendors.{vid}.templates: non-empty list required")
                continue
            for i, t in enumerate(templates):
                if not isinstance(t, dict):
                    err(f"vendors.{vid}.templates[{i}]: object required")
                    continue
                if t.get("envelope") not in ("rfc3164", "rfc5424", "raw"):
                    err(f"vendors.{vid}.templates[{i}].envelope: rfc3164|rfc5424|raw required")
                if not isinstance(t.get("message"), str) or not t["message"]:
                    err(f"vendors.{vid}.templates[{i}].message: non-empty string required")
                sev = t.get("severity")
                if sev is not None and sev not in SEVERITIES:
                    err(f"vendors.{vid}.templates[{i}].severity: invalid")

    if isinstance(devices, list) and isinstance(vendors, dict):
        vset = set(vendors.keys())
        for i, d in enumerate(devices):
            if not isinstance(d, dict):
                err(f"devices[{i}]: object required")
                continue
            if not isinstance(d.get("id"), str) or not d["id"]:
                err(f"devices[{i}].id: non-empty string required")
            if d.get("vendor") not in vset:
                err(f"devices[{i}].vendor: must reference vendors key")
            if not isinstance(d.get("hostname"), str) or not d["hostname"]:
                err(f"devices[{i}].hostname: non-empty string required")
            if d.get("category") not in CATEGORIES:
                err(f"devices[{i}].category: must be one of {CATEGORIES}")

    if errors:
        raise ConfigError("Config validation failed:\n- " + "\n- ".join(errors))


def load_yaml_config(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise ConfigError("PyYAML is required to read config.yml for syslog_simulator controls.")
    with open(path, "r", encoding="utf-8") as f:
        parsed = yaml.safe_load(f)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError(f"YAML config must contain a top-level object: {path}")
    return parsed


def default_simulator_config_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "config.yml")
    )


def default_defaults_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "defaults.json")
    )


def parse_string_list(value: Any, path: str) -> Optional[List[str]]:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ConfigError(f"{path}: list of strings required")
    out: List[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{path}[{i}]: non-empty string required")
        out.append(item.strip())
    return out


def apply_shared_config_overrides(cfg: Dict[str, Any], shared_cfg: Dict[str, Any]) -> Dict[str, Any]:
    simulator_cfg = shared_cfg.get("syslog_simulator")
    if simulator_cfg is None:
        return cfg
    if not isinstance(simulator_cfg, dict):
        raise ConfigError("syslog_simulator: object required in config.yml")

    overrides = simulator_cfg.get("overrides")
    if overrides is None:
        return cfg
    if not isinstance(overrides, dict):
        raise ConfigError("syslog_simulator.overrides: object required in config.yml")
    return deep_merge(cfg, overrides)


def apply_shared_config_filters(cfg: Dict[str, Any], shared_cfg: Dict[str, Any]) -> None:
    simulator_cfg = shared_cfg.get("syslog_simulator")
    if simulator_cfg is None:
        return
    if not isinstance(simulator_cfg, dict):
        raise ConfigError("syslog_simulator: object required in config.yml")

    enabled_vendors = parse_string_list(
        simulator_cfg.get("enabled_vendors"),
        "syslog_simulator.enabled_vendors",
    )
    enabled_devices = parse_string_list(
        simulator_cfg.get("enabled_devices"),
        "syslog_simulator.enabled_devices",
    )
    if enabled_vendors is None and enabled_devices is None:
        return

    vendors = cfg.get("vendors")
    devices = cfg.get("devices")
    if not isinstance(vendors, dict) or not isinstance(devices, list):
        return

    known_vendor_ids = set(vendors.keys())
    known_device_ids = {
        str(device.get("id"))
        for device in devices
        if isinstance(device, dict) and isinstance(device.get("id"), str)
    }

    if enabled_vendors is not None:
        unknown_vendors = [vendor_id for vendor_id in enabled_vendors if vendor_id not in known_vendor_ids]
        if unknown_vendors:
            raise ConfigError(
                "syslog_simulator.enabled_vendors contains unknown vendor ids: "
                + ", ".join(unknown_vendors)
            )

    if enabled_devices is not None:
        unknown_devices = [device_id for device_id in enabled_devices if device_id not in known_device_ids]
        if unknown_devices:
            raise ConfigError(
                "syslog_simulator.enabled_devices contains unknown device ids: "
                + ", ".join(unknown_devices)
            )

    filtered_devices = [device for device in devices if isinstance(device, dict)]
    if enabled_vendors is not None:
        allowed_vendors = set(enabled_vendors)
        filtered_devices = [
            device for device in filtered_devices if device.get("vendor") in allowed_vendors
        ]
    if enabled_devices is not None:
        allowed_devices = set(enabled_devices)
        filtered_devices = [
            device for device in filtered_devices if device.get("id") in allowed_devices
        ]

    referenced_vendors = {
        str(device.get("vendor"))
        for device in filtered_devices
        if isinstance(device.get("vendor"), str)
    }

    cfg["devices"] = filtered_devices
    cfg["vendors"] = {
        vendor_id: vendor_cfg
        for vendor_id, vendor_cfg in vendors.items()
        if vendor_id in referenced_vendors
    }


def effective_now(cfg: Dict[str, Any]) -> datetime:
    tz_mode = cfg["runtime"].get("timestamp_timezone", "local")
    return datetime.now(timezone.utc) if tz_mode == "utc" else datetime.now().astimezone()


def resolve_iface(seed: Dict[str, Any], vendor_id: str, rng: random.Random) -> str:
    interfaces = seed.get("interfaces", {})
    if isinstance(interfaces, dict):
        cand = interfaces.get(vendor_id) or interfaces.get("default") or []
        if isinstance(cand, list) and cand:
            return rng.choice(cand)
    vendor_defaults: Dict[str, List[str]] = {
        "hpe_aruba": [
            "1/1/1",
            "1/1/2",
            "1/1/48",
            "lag10",
            "lag100",
            "vlan100",
        ],
        "dell_os10": [
            "Ethernet1/1/1",
            "Ethernet1/1/2",
            "Ethernet1/1/48",
            "Port-channel10",
            "Port-channel100",
            "mgmt1/1/1",
        ],
        "huawei_vrp": [
            "10GE1/0/1",
            "10GE1/0/2",
            "Eth-Trunk10",
            "GE0/0/1",
            "Vlanif100",
        ],
        "crontab_cron": [
            "lo",
            "eth0",
            "mgmt0",
            "vlan100",
        ],
    }
    return rng.choice(vendor_defaults.get(vendor_id, ["eth0", "eth1"]))


def select_device(cfg: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    cats = cfg["categories"]
    eligible = [d for d in cfg["devices"] if isinstance(d, dict) and cats.get(d.get("category"), False)]
    if not eligible:
        raise ConfigError("No eligible devices after category filtering.")
    return rng.choice(eligible)


def select_template(vendor_cfg: Dict[str, Any], device: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    cat = device.get("category")
    eligible: List[Dict[str, Any]] = []
    weights: List[float] = []
    for t in vendor_cfg.get("templates", []):
        if not isinstance(t, dict):
            continue
        cats = t.get("categories")
        if cats is not None and (not isinstance(cats, list) or cat not in cats):
            continue
        eligible.append(t)
        weights.append(float(t.get("weight", 1.0) or 1.0))
    if not eligible:
        raise ConfigError(f"No templates for vendor={device.get('vendor')} category={cat}")
    return rng.choices(eligible, weights=weights, k=1)[0]


def resolve_severity(cfg: Dict[str, Any], vendor_cfg: Dict[str, Any], device: Dict[str, Any], template: Dict[str, Any], rng: random.Random) -> str:
    fixed = template.get("severity")
    if fixed in SEVERITIES:
        return fixed
    for weights, p in (
        (device.get("severity_weights"), "device.severity_weights"),
        (vendor_cfg.get("default_severity_weights"), "vendor.default_severity_weights"),
        (cfg.get("severity_weights"), "severity_weights"),
    ):
        if isinstance(weights, dict):
            return choose_weighted(rng, normalize_weights(weights, p))
    return "error"


def resolve_facility(cfg: Dict[str, Any], vendor_cfg: Dict[str, Any], device: Dict[str, Any], template: Dict[str, Any]) -> int:
    for v in (
        template.get("facility"),
        device.get("facility"),
        vendor_cfg.get("default_facility"),
        cfg.get("defaults", {}).get("facility", 23),
    ):
        if isinstance(v, int) and 0 <= v <= 23:
            return v
    return 23


def resolve_include_pri(cfg: Dict[str, Any], template: Dict[str, Any]) -> bool:
    if "include_pri" in template:
        return bool(template["include_pri"])
    return bool(cfg["runtime"].get("include_pri", True))


def build_context(cfg: Dict[str, Any], vendor_id: str, device: Dict[str, Any], template: Dict[str, Any], now: datetime, rng: random.Random, facility: int, severity: str) -> Dict[str, Any]:
    seed = cfg.get("seed", {}) if isinstance(cfg.get("seed"), dict) else {}

    src_ip = pick_seed(rng, seed.get("private_ips"), random_private_ip)
    dst_ip_public = pick_seed(rng, seed.get("public_ips"), random_public_ip)
    dst_ip_private = pick_seed(rng, seed.get("private_ips"), random_private_ip)
    username = pick_seed(rng, seed.get("usernames"), lambda r: r.choice(["admin", "netops"]))
    domain = pick_seed(rng, seed.get("domains"), lambda r: "example.com")
    zone_src = pick_seed(rng, seed.get("zones"), lambda r: "trust")
    zone_dst = pick_seed(rng, seed.get("zones"), lambda r: "untrust")
    policy = pick_seed(rng, seed.get("policies"), lambda r: "default-deny")
    app = pick_seed(rng, seed.get("apps"), lambda r: "ssl")
    msg_text = pick_seed(rng, seed.get("messages"), lambda r: "test message")

    proto = rng.choice(["tcp", "udp", "icmp"])
    proto_num = {"tcp": 6, "udp": 17, "icmp": 1}[proto]
    src_port = rng.randint(1024, 65535)
    dst_port = rng.choice([22, 53, 80, 443, 123, 161, 514])
    icmp_type = rng.choice([0, 3, 8, 11])
    iface = resolve_iface(seed, vendor_id, rng)
    pid = rng.randint(1000, 65000)
    bytes_req = rng.choice([262144, 524288, 1048576, 2097152])
    hexaddr = f"{rng.randint(0, 0xFFFFFFFF):08X}"
    pkt_len = rng.choice([60, 64, 78, 100, 128, 256, 452, 512, 1500])
    src_mac = random_mac(rng)

    state = rng.choice(["up", "down"])
    action = rng.choice(["accept", "deny", "drop", "alert"])
    reason = rng.choice(["Denied by policy", "policy deny", "timeout", "signature match"])
    url = f"www.{domain}/path/{rng.randint(1,999)}"
    peer_ip = pick_seed(rng, seed.get("private_ips"), random_private_ip)
    peer_unit = rng.choice([1, 2])
    vlt_domain = rng.choice([1, 10, 100, 4000, 4094])
    port_channel = rng.choice([1, 10, 20, 100, 200])
    vrf = rng.choice(["default", "management", "tenant-a", "tenant-b"])
    old_state = rng.choice(["ESTABLISHED", "ACTIVE", "CONNECT", "OPENCONFIRM"])
    new_state = rng.choice(["IDLE", "DOWN", "ACTIVE", "CONNECT"])
    sensor = rng.choice(["TempSensor-1", "TempSensor-2", "ASIC-Core", "PSU-1"])
    temperature = rng.choice([78, 82, 87, 92, 96])
    fan_tray = rng.choice([1, 2, 3, 4])
    role = rng.choice(["netadmin", "operator", "secadmin", "sysadmin"])
    password_expiry_days = rng.choice([1, 3, 5, 7, 14])
    ospf_nbr_event = rng.choice([7, 9, 12, 13])
    cpu_usage_percent = rng.choice([85, 89, 92, 95, 98])
    board = rng.choice(["MPU0", "LPU1", "LPU2", "SFU1"])
    chassis = rng.choice(["CE12800", "CE6857", "NE40E"])
    command = pick_seed(
        rng,
        seed.get("commands"),
        lambda r: r.choice(
            [
                "display current-configuration",
                "display interface brief",
                "interface 10GE1/0/1",
                "bgp 65000",
            ]
        ),
    )
    cron_user = pick_seed(
        rng,
        seed.get("cron_users"),
        lambda r: r.choice(["root", "admin", "netops"]),
    )
    cron_command = pick_seed(
        rng,
        seed.get("cron_commands"),
        lambda r: r.choice(
            [
                "/usr/local/bin/config-backup.sh",
                "/usr/local/bin/export-telemetry.sh --push",
                "/usr/sbin/logrotate /etc/logrotate.conf",
                "/usr/lib/sa/sa1 1 1",
            ]
        ),
    )
    cron_file = pick_seed(
        rng,
        seed.get("cron_files"),
        lambda r: r.choice(
            [
                "/etc/crontab",
                "/etc/cron.d/network-maintenance",
                "/var/spool/cron/root",
            ]
        ),
    )
    cron_line = rng.choice([1, 3, 7, 12, 20, 31, 45])
    cron_uid = rng.choice([0, 1000, 1001, 1002])
    cron_mta_status = f"0x{rng.randint(1, 255):02x}"
    peer_asn = rng.choice([65001, 65002, 65100, 65200])
    dell_model = pick_seed(
        rng,
        seed.get("dell_models"),
        lambda r: r.choice(["S5248F-ON", "Z9432F-ON", "S5232F-ON", "S4148U-ON"]),
    )
    dell_os10_version = pick_seed(
        rng,
        seed.get("dell_os10_versions"),
        lambda r: r.choice(["10.5.4.6", "10.5.5.3", "10.5.6.1"]),
    )
    hpe_aruba_model = pick_seed(
        rng,
        seed.get("hpe_aruba_models"),
        lambda r: r.choice(["8360-48Y6C", "8325-48Y8C", "6300M", "6200F"]),
    )
    hpe_aruba_version = pick_seed(
        rng,
        seed.get("hpe_aruba_versions"),
        lambda r: r.choice(["10.14.1000", "10.13.1040", "10.12.1050", "WC.16.11"]),
    )
    aruba_central_host = pick_seed(
        rng,
        seed.get("aruba_central_hosts"),
        lambda r: "device.arubanetworks.com:443",
    )
    aruba_central_vrf = rng.choice(["default", "mgmt", "management"])
    dell_prefix = "%Dell EMC (OS10)"

    date_iso = now.astimezone().strftime("%Y-%m-%d")
    time_hms = now.astimezone().strftime("%H:%M:%S")
    pa_receive_time = now.astimezone().strftime("%Y/%m/%d %H:%M:%S")
    epoch_ms = int(now.timestamp() * 1000)

    ctx: Dict[str, Any] = {
        "vendor": vendor_id,
        "hostname": device.get("hostname", "device"),
        "device_id": device.get("device_id") or device.get("serial") or "",
        "serial": device.get("serial") or device.get("device_id") or "",
        "devicetype": device.get("devicetype", device.get("category", "")),
        "category": device.get("category", ""),
        "facility": facility,
        "severity": severity,
        "severity_num": SEV_TO_SYSLOG_NUM[severity],
        "pri": calc_pri(facility, severity),
        "ts_rfc3164": rfc3164_timestamp(now),
        "ts_rfc5424": rfc5424_timestamp(now, cfg["runtime"].get("timestamp_timezone", "local")),
        "date": date_iso,
        "time": time_hms,
        "eventtime": epoch_ms,
        "pa_receive_time": pa_receive_time,
        "src_ip": src_ip,
        "dst_ip_public": dst_ip_public,
        "dst_ip_private": dst_ip_private,
        "src_port": src_port,
        "dst_port": dst_port,
        "proto": proto,
        "proto_num": proto_num,
        "icmp_type": icmp_type,
        "username": username,
        "domain": domain,
        "zone_src": zone_src,
        "zone_dst": zone_dst,
        "policy": policy,
        "app": app,
        "msg_text": msg_text,
        "url": url,
        "iface": iface,
        "pid": pid,
        "bytes": bytes_req,
        "hex": hexaddr,
        "pkt_len": pkt_len,
        "src_mac": src_mac,
        "state": state,
        "action": action,
        "reason": reason,
        "peer_ip": peer_ip,
        "peer_unit": peer_unit,
        "vlt_domain": vlt_domain,
        "port_channel": port_channel,
        "vrf": vrf,
        "old_state": old_state,
        "new_state": new_state,
        "sensor": sensor,
        "temperature": temperature,
        "fan_tray": fan_tray,
        "role": role,
        "password_expiry_days": password_expiry_days,
        "ospf_nbr_event": ospf_nbr_event,
        "cpu_usage_percent": cpu_usage_percent,
        "board": board,
        "chassis": chassis,
        "command": command,
        "cron_user": cron_user,
        "cron_command": cron_command,
        "cron_file": cron_file,
        "cron_line": cron_line,
        "cron_uid": cron_uid,
        "cron_mta_status": cron_mta_status,
        "peer_asn": peer_asn,
        "dell_model": dell_model,
        "dell_os10_version": dell_os10_version,
        "hpe_aruba_model": hpe_aruba_model,
        "hpe_aruba_version": hpe_aruba_version,
        "aruba_central_host": aruba_central_host,
        "aruba_central_vrf": aruba_central_vrf,
        "dell_prefix": dell_prefix,
    }

    static_ctx = template.get("static_ctx")
    if isinstance(static_ctx, dict):
        # Static per-template values; can be referenced by {{key}} placeholders.
        ctx.update(static_ctx)

    return ctx


def build_line(cfg: Dict[str, Any], envelope: str, include_pri: bool, facility: int, severity: str, host: str, payload: str, now: datetime, rfc5424_fields: Optional[Dict[str, Any]]) -> str:
    if envelope == "raw":
        return payload

    if envelope == "rfc3164":
        pri_prefix = f"<{calc_pri(facility, severity)}>" if include_pri else ""
        return f"{pri_prefix}{rfc3164_timestamp(now)} {host} {payload}"

    # RFC5424: <PRI>1 TIMESTAMP HOST APP PROCID MSGID SD MSG
    f = rfc5424_fields or {}
    app = str(f.get("app", "-"))
    procid = str(f.get("procid", "-"))
    msgid = str(f.get("msgid", "-"))
    sd = str(f.get("structured_data", "-")) or "-"
    pri_prefix = f"<{calc_pri(facility, severity)}>" if include_pri else ""
    ts = rfc5424_timestamp(now, cfg["runtime"].get("timestamp_timezone", "local"))
    return f"{pri_prefix}1 {ts} {host} {app} {procid} {msgid} {sd} {payload}"


def generate_one(cfg: Dict[str, Any], rng: random.Random) -> GeneratedLogEvent:
    device = select_device(cfg, rng)
    vendor_id = device["vendor"]
    vendor_cfg = cfg["vendors"][vendor_id]
    template = select_template(vendor_cfg, device, rng)

    envelope = template.get("envelope", "rfc3164")
    if envelope not in ("rfc3164", "rfc5424", "raw"):
        envelope = "rfc3164"

    severity = resolve_severity(cfg, vendor_cfg, device, template, rng)
    facility = resolve_facility(cfg, vendor_cfg, device, template)
    include_pri = resolve_include_pri(cfg, template)

    now = effective_now(cfg)
    ctx = build_context(cfg, vendor_id, device, template, now, rng, facility, severity)

    payload = render(template["message"], ctx)

    # RFC5424 header fields can contain placeholders too.
    rfc5424_fields = None
    if envelope == "rfc5424":
        raw_fields = template.get("rfc5424") if isinstance(template.get("rfc5424"), dict) else {}
        # Fill defaults, then render placeholders.
        f = {
            "app": raw_fields.get("app", template.get("app", vendor_id)),
            "procid": raw_fields.get("procid", template.get("procid", str(ctx["pid"]))),
            "msgid": raw_fields.get("msgid", template.get("msgid", "-")),
            "structured_data": raw_fields.get("structured_data", template.get("structured_data", "-")),
        }
        rfc5424_fields = {k: render(str(v), ctx) for k, v in f.items()}

    host_field = template.get("host_field", "hostname")
    host_value = ctx.get(host_field, device.get("hostname", "device"))
    line = build_line(cfg, envelope, include_pri, facility, severity, str(host_value), payload, now, rfc5424_fields)
    return GeneratedLogEvent(
        line=line,
        payload=payload,
        source_device_id=str(device.get("id", "")),
        source_hostname=str(device.get("hostname", host_value)),
        source_category=str(device.get("category", "")),
        source_vendor_id=vendor_id,
        source_vendor_name=str(vendor_cfg.get("display_name", vendor_id)),
        source_ip=str(ctx.get("src_ip", "unknown")),
        severity=severity,
        facility=facility,
        envelope=envelope,
        template_id=str(template.get("id", "unknown")),
    )


def format_send_trace(
    event: GeneratedLogEvent,
    *,
    target_host: str,
    target_port: int,
    target_proto: str,
    dry_run: bool,
) -> str:
    """Build a readable per-event transmission trace line."""
    status = "DRY-RUN" if dry_run else "SENT"
    return (
        f"[{status}] "
        f"device={event.source_hostname} "
        f"(id={event.source_device_id}, vendor={event.source_vendor_id} - {event.source_vendor_name}, "
        f"category={event.source_category}, src_ip={event.source_ip}) "
        f"-> {target_host}:{target_port}/{target_proto} "
        f"[severity={event.severity}, facility={event.facility}, envelope={event.envelope}, template={event.template_id}] "
        f"message={event.payload}"
    )


class UDPSender:
    def __init__(self, host: str, port: int) -> None:
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_lines(self, lines: List[str]) -> None:
        for line in lines:
            self.sock.sendto(line.encode("utf-8"), self.addr)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


class TCPSender:
    def __init__(self, host: str, port: int, framing: str, timeout_s: float, reconnect_delay_s: float) -> None:
        self.host = host
        self.port = port
        self.framing = framing
        self.timeout_s = timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.sock: Optional[socket.socket] = None

    def _connect(self) -> None:
        while True:
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
                return
            except Exception as e:
                eprint(f"[tcp] connect failed: {e}; retrying in {self.reconnect_delay_s}s")
                time.sleep(self.reconnect_delay_s)

    def send_lines(self, lines: List[str]) -> None:
        if self.sock is None:
            self._connect()
        assert self.sock is not None

        for line in lines:
            if self.framing == "octet-counting":
                payload = f"{len(line)} {line}".encode("utf-8")
            else:
                payload = (line + "\n").encode("utf-8")

            try:
                self.sock.sendall(payload)
            except Exception:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
                self._connect()
                assert self.sock is not None
                self.sock.sendall(payload)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Multi-vendor syslog simulator (raw lines).")

    ap.add_argument("--defaults", help="Path to defaults JSON containing all configurable fields.")
    ap.add_argument(
        "--config",
        help="Optional YAML config path; reads syslog_simulator controls from log_simulations/config/config.yml.",
    )
    ap.add_argument("--host", help="Override target.host")
    ap.add_argument("--port", type=int, help="Override target.port")
    ap.add_argument("--proto", choices=["udp", "tcp"], help="Override target.proto")
    ap.add_argument("--tcp-framing", choices=["newline", "octet-counting"], help="Override target.tcp_framing")

    ap.add_argument("--rate", type=float, help="Override runtime.rate (msgs/sec; 0 => no pacing)")
    ap.add_argument("--batch-size", type=int, help="Override runtime.batch_size")
    ap.add_argument("--count", type=int, help="Override runtime.count (0 => infinite)")
    ap.add_argument("--dry-run", action="store_true", help="Print logs; do not send.")
    ap.add_argument("--print-send-details", action="store_true",
                    help="Print source device/vendor and destination target details for each log.")
    ap.add_argument("--no-print-send-details", action="store_true",
                    help="Disable per-log send detail traces.")
    ap.add_argument("--include-pri", action="store_true", help="Force include PRI header.")
    ap.add_argument("--no-include-pri", action="store_true", help="Force omit PRI header.")
    ap.add_argument("--timestamp-timezone", choices=["local", "utc"], help="Override runtime.timestamp_timezone")
    ap.add_argument("--random-seed", type=int, help="Override runtime.random_seed")

    ap.add_argument("--seed-private-ips", help="Override seed.private_ips (comma-separated)")
    ap.add_argument("--seed-public-ips", help="Override seed.public_ips (comma-separated)")
    ap.add_argument("--seed-usernames", help="Override seed.usernames (comma-separated)")
    ap.add_argument("--seed-domains", help="Override seed.domains (comma-separated)")

    for c in CATEGORIES:
        ap.add_argument(f"--{c}", dest=f"cat_{c}", action="store_true", help=f"Enable category '{c}'")
        ap.add_argument(f"--no-{c}", dest=f"cat_{c}", action="store_false", help=f"Disable category '{c}'")
        ap.set_defaults(**{f"cat_{c}": None})

    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="Override any config field via dot-path; VALUE parsed as JSON when possible.")
    ap.add_argument("--validate-only", action="store_true", help="Validate config and exit.")
    ap.add_argument("--print-effective-config", action="store_true", help="Print merged config and exit.")
    return ap


def load_defaults_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_cli_overrides(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    if args.host:
        set_dot_path(cfg, "target.host", args.host)
    if args.port is not None:
        set_dot_path(cfg, "target.port", args.port)
    if args.proto:
        set_dot_path(cfg, "target.proto", args.proto)
    if args.tcp_framing:
        set_dot_path(cfg, "target.tcp_framing", args.tcp_framing)

    if args.rate is not None:
        set_dot_path(cfg, "runtime.rate", args.rate)
    if args.batch_size is not None:
        set_dot_path(cfg, "runtime.batch_size", args.batch_size)
    if args.count is not None:
        set_dot_path(cfg, "runtime.count", args.count)
    if args.dry_run:
        set_dot_path(cfg, "runtime.dry_run", True)
    if args.print_send_details and args.no_print_send_details:
        raise ConfigError("Cannot set both --print-send-details and --no-print-send-details")
    if args.print_send_details:
        set_dot_path(cfg, "runtime.print_send_details", True)
    if args.no_print_send_details:
        set_dot_path(cfg, "runtime.print_send_details", False)
    if args.timestamp_timezone:
        set_dot_path(cfg, "runtime.timestamp_timezone", args.timestamp_timezone)
    if args.random_seed is not None:
        set_dot_path(cfg, "runtime.random_seed", args.random_seed)

    if args.include_pri and args.no_include_pri:
        raise ConfigError("Cannot set both --include-pri and --no-include-pri")
    if args.include_pri:
        set_dot_path(cfg, "runtime.include_pri", True)
    if args.no_include_pri:
        set_dot_path(cfg, "runtime.include_pri", False)

    if args.seed_private_ips:
        set_dot_path(cfg, "seed.private_ips", parse_csv_list(args.seed_private_ips))
    if args.seed_public_ips:
        set_dot_path(cfg, "seed.public_ips", parse_csv_list(args.seed_public_ips))
    if args.seed_usernames:
        set_dot_path(cfg, "seed.usernames", parse_csv_list(args.seed_usernames))
    if args.seed_domains:
        set_dot_path(cfg, "seed.domains", parse_csv_list(args.seed_domains))

    for c in CATEGORIES:
        val = getattr(args, f"cat_{c}")
        if val is None:
            continue
        set_dot_path(cfg, f"categories.{c}", bool(val))

    for item in args.set or []:
        if "=" not in item:
            raise ConfigError(f"--set expects KEY=VALUE, got: {item}")
        k, v = item.split("=", 1)
        set_dot_path(cfg, k.strip(), parse_jsonish(v))


def main() -> int:
    ap = build_arg_parser()
    args = ap.parse_args()

    if not args.defaults:
        print("You must provide --defaults <path/to/defaults.json> (see example in report).")
        print("Using the default simulator defaults file in log_simulations/syslog_simulation/defaults.json.")
        args.defaults = default_defaults_path()
    if not os.path.exists(args.defaults):
        raise ConfigError(f"Defaults file not found: {args.defaults}")

    cfg = load_defaults_file(args.defaults)
    shared_config_path = args.config or default_simulator_config_path()
    if shared_config_path and os.path.exists(shared_config_path):
        shared_cfg = load_yaml_config(shared_config_path)
        cfg = apply_shared_config_overrides(cfg, shared_cfg)
        apply_shared_config_filters(cfg, shared_cfg)
    elif args.config:
        raise ConfigError(f"YAML config not found: {args.config}")
    apply_cli_overrides(cfg, args)
    validate_config(cfg)

    if args.print_effective_config:
        print(json.dumps(cfg, indent=2, sort_keys=True))
        return 0

    if args.validate_only:
        eprint("Config OK.")
        return 0

    seed = cfg["runtime"].get("random_seed")
    rng = random.Random(int(seed)) if seed is not None else random.Random()

    dry_run = bool(cfg["runtime"].get("dry_run", False))
    target = cfg["target"]
    host, port = target["host"], int(target["port"])
    proto = target["proto"]
    framing = target.get("tcp_framing", "newline")
    timeout_s = float(target.get("connect_timeout_s", 5.0))
    reconnect_delay_s = float(target.get("reconnect_delay_s", 1.0))

    sender: Optional[Any] = None
    if not dry_run:
        sender = UDPSender(host, port) if proto == "udp" else TCPSender(host, port, framing, timeout_s, reconnect_delay_s)

    rate = float(cfg["runtime"]["rate"])
    batch_size = int(cfg["runtime"]["batch_size"])
    count = int(cfg["runtime"]["count"])
    print_send_details = bool(cfg["runtime"].get("print_send_details", True))

    sent = 0
    try:
        while count == 0 or sent < count:
            remaining = None if count == 0 else (count - sent)
            batch_n = batch_size if remaining is None else min(batch_size, remaining)

            events = [generate_one(cfg, rng) for _ in range(batch_n)]
            lines = [event.line for event in events]

            if dry_run:
                for event in events:
                    if print_send_details:
                        print(
                            format_send_trace(
                                event,
                                target_host=host,
                                target_port=port,
                                target_proto=proto,
                                dry_run=True,
                            )
                        )
                    print(event.line)
            else:
                assert sender is not None
                sender.send_lines(lines)
                if print_send_details:
                    for event in events:
                        print(
                            format_send_trace(
                                event,
                                target_host=host,
                                target_port=port,
                                target_proto=proto,
                                dry_run=False,
                            )
                        )

            sent += batch_n
            if rate > 0:
                time.sleep(batch_n / rate)
    except KeyboardInterrupt:
        pass
    finally:
        if sender is not None:
            sender.close()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigError as ce:
        eprint(str(ce))
        raise SystemExit(2)
