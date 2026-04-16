#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beats_logsim.py — Cross-platform log-generation simulator for Filebeat modules and Winlogbeat.

What it does
- Single runnable Python entrypoint with OS auto-detection (overrideable).
- Linux:
  - Discovers filesets for selected Filebeat modules by reading module folders in either:
      * a local clone of elastic/beats, OR
      * the GitHub repository (directory listing via GitHub Contents API).
  - Reads each fileset's manifest.yml + input config template referenced by manifest.yml.
  - Resolves manifest variables (especially var.paths) including:
      * OS-specific overrides (os.darwin, os.windows) as described in Elastic's module
        developer guide
      * `{{.var}}` substitutions used by manifests/config templates
      * `${ENV:default}` substitutions used by some manifests (e.g., RabbitMQ)
  - If var.paths is missing/empty for a file-based fileset, infers likely Linux paths
    (assumptions are logged).
  - Generates authoritative, module-shaped source logs and writes them to:
      * official resolved paths (path_mode=official), or
      * sandbox paths (path_mode=sandbox), printing the var.paths you should set.

- Windows:
  - Creates real Windows Event Log entries (Winlogbeat-friendly):
      * Preferred: custom classic log via PowerShell New-EventLog + Write-EventLog
      * Fallback: eventcreate to Application log

Supported modules (explicitly scoped)
  activemq, auditd, kafka, mongodb, netflow (v5 generator), nginx, postgresql, rabbitmq, redis, system

Safe defaults
  path_mode defaults to "sandbox" to avoid modifying real /var/log/* unless you opt in.

Usage examples
  # Linux: sandbox mode (safe; point Filebeat var.paths at sandbox files)
  sudo python3 beats_logsim.py --config control.json --force-os linux --path-mode sandbox

  # Linux: official mode (writes into module default paths; usually needs root)
  sudo python3 beats_logsim.py --modules nginx,system --rate 5 --duration 120 --path-mode official

  # Windows: generate Event Log entries (admin recommended for New-EventLog)
  python beats_logsim.py --force-os windows --rate 5 --duration 60 --winlog-name SimLog
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import platform
import random
import re
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# --------------------------
# Runtime logging helpers
# --------------------------

def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return repr(value)

def _clip_text(value: str, max_len: int = 240) -> str:
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."

def log_line(level: str, state: str, **fields: Any) -> None:
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
    extras = " ".join(f"{k}={_safe_json(v)}" for k, v in sorted(fields.items()))
    msg = f"[{level}] {ts} state={state}"
    if extras:
        msg += f" {extras}"
    print(msg, flush=True)

def log_info(state: str, **fields: Any) -> None:
    log_line("INFO", state, **fields)

def log_warn(state: str, **fields: Any) -> None:
    log_line("WARN", state, **fields)

def log_error(state: str, err: Optional[Exception] = None, **fields: Any) -> None:
    if err is not None:
        fields["error"] = str(err)
        fields["error_type"] = type(err).__name__
    log_line("ERROR", state, **fields)

@dataclass
class SimulationStats:
    ticks: int = 0
    lines_written: int = 0
    file_write_ops: int = 0
    file_write_errors: int = 0
    network_send_ops: int = 0
    network_send_errors: int = 0
    events_emitted: int = 0
    events_failed: int = 0

# --------------------------
# Defaults (override via JSON control file or CLI)
# --------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "runtime": {
        "modules": "all",        # "all" or comma-list or array
        "rate": 2.0,             # events/sec per enabled fileset (approx)
        "duration_s": 60,        # 0 => forever
        "start_time": "now",     # ISO8601 or "now" (local)
        "seed": 1,
        "dry_run": False,
        "stats_every_s": 10,
    },
    "linux": {
        "path_mode": "sandbox",  # official|sandbox
        "sandbox_base": "/tmp/beats-sim",
        "modules_d_path": None,  # optional modules.d directory (e.g., /etc/filebeat/modules.d)
        "rotate_bytes": 10 * 1024 * 1024,
        "rotate_keep": 5,
        "file_mode": "append",   # append|overwrite
        "hostname": "host1",
        "tzword": "UTC",         # Postgres log TZ word token
        "system_emit_via_logger": False,  # best-effort syslog emission (non-deterministic)
        "beats_repo": {
            "local_path": None,  # optional: local elastic/beats clone
            "github": {
                "owner": "elastic",
                "repo": "beats",
                "ref": "main",
                "raw_base": "https://raw.githubusercontent.com",
                "api_base": "https://api.github.com",
                "cache_dir": os.path.join(os.path.expanduser("~"), ".cache", "beats_logsim"),
                "token_env": "GITHUB_TOKEN",
            },
        },
        "netflow": {
            "host": "localhost",
            "port": 2055,
            "records_per_packet": 10,
        },
        # Per-module knobs (templates + severity distributions)
        "modules": {
            "activemq": {
                "severity_weights": {"INFO": 0.85, "WARN": 0.10, "ERROR": 0.05},
                "messages": [
                    "KahaDB is version 6",
                    "PListStore:[{data_dir}] started",
                    "TransportConnector started on tcp://0.0.0.0:61616",
                    "Apache ActiveMQ started",
                ],
                "static_messages": [],
            },
            "auditd": {
                "type_weights": {"SYSCALL": 0.6, "USER_AUTH": 0.2, "USER_START": 0.2},
                "static_messages": [],
            },
            "kafka": {
                "severity_weights": {"INFO": 0.85, "WARN": 0.10, "ERROR": 0.05},
                "static_messages": [],
            },
            "mongodb": {
                "mode_weights": {"plaintext": 0.6, "json": 0.4},
                "severity_weights": {"I": 0.85, "W": 0.10, "E": 0.05},
                "static_messages": [],
            },
            "nginx": {
                "access_status_weights": {200: 0.85, 404: 0.10, 500: 0.05},
                "error_level_weights": {"error": 0.6, "warn": 0.35, "notice": 0.05},
                "static_messages": [],
            },
            "postgresql": {
                "severity_weights": {"LOG": 0.85, "ERROR": 0.10, "FATAL": 0.05},
                "static_messages": [],
            },
            "rabbitmq": {
                "level_weights": {"info": 0.85, "warning": 0.10, "error": 0.05},
                "static_messages": [],
            },
            "redis": {
                "log_symbol_weights": {"*": 0.8, ".": 0.1, "-": 0.08, "#": 0.02},
                "slowlog": {
                    "enabled": True,
                    "hosts": ["localhost:6379"],
                    "password": "",
                    "force_log_all_commands": True,
                    "slowlog_max_len": 128,
                    "client_name": "beats_logsim",
                },
                "static_messages": [],
            },
            "system": {
                "auth_templates": [
                    "{mon} {day} {time} {host} sshd[{pid}]: Accepted password for {user} from {ip} port {port} ssh2",
                    "{mon} {day} {time} {host} sudo: pam_unix(sudo:session): session opened for user root by {user}(uid=1000)",
                ],
                "syslog_templates": [
                    "{iso} {host} systemd[{pid}]: Started Simulated Service.",
                    "{iso} {host} systemd[{pid}]: Stopped target Basic System.",
                ],
                "static_messages": [],
            },
            "netflow": {
                "static_messages": [],
            },
        },
        # Optional explicit per-fileset override paths: module->fileset->list[str]
        "var_paths_overrides": {},
        # Other per-fileset var.* overrides: module->fileset->dict
        "var_overrides": {},
    },
    "windows": {
        "winlog": {
            "name": "SimLog",
            "source": "SimLogGenerator",
            "base_eventid": 1100,
            "fallback_to_application": True,
        }
    },
}

ALLOWED_MODULES = {
    "activemq", "auditd", "kafka", "mongodb", "netflow", "nginx",
    "postgresql", "rabbitmq", "redis", "system",
}

# Service/network-based filesets
SERVICE_FILESETS = {
    ("netflow", "log"),
    ("redis", "slowlog"),
}

# --------------------------
# Config helpers
# --------------------------

def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

def dotpath_set(d: Dict[str, Any], path: str, value: Any) -> None:
    cur = d
    parts = path.split(".")
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def parse_modules_list(v: Any) -> List[str]:
    if isinstance(v, list):
        mods = [str(x).strip().lower() for x in v]
    else:
        s = str(v).strip().lower()
        if s == "all":
            return sorted(ALLOWED_MODULES)
        mods = [x.strip().lower() for x in s.split(",") if x.strip()]
    bad = [m for m in mods if m not in ALLOWED_MODULES]
    if bad:
        raise SystemExit(f"Unsupported modules: {bad}. Allowed: {sorted(ALLOWED_MODULES)}")
    return mods

def module_static_messages(cfg: Dict[str, Any], module: str) -> List[str]:
    try:
        module_cfg = cfg["linux"]["modules"].get(module, {})
    except Exception:
        return []
    raw = module_cfg.get("static_messages", [])
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        log_warn("module_static_messages_invalid_type", module=module, value_type=type(raw).__name__)
        return []
    out: List[str] = []
    for item in items:
        s = str(item).strip()
        if s:
            out.append(s)
    return out

# --------------------------
# Time helpers
# --------------------------

def parse_start_time(v: str) -> dt.datetime:
    if v.strip().lower() == "now":
        return dt.datetime.now().astimezone()
    s = v.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s)

def fmt_ms_comma(ts: dt.datetime) -> str:
    ms = ts.microsecond // 1000
    return ts.strftime("%Y-%m-%d %H:%M:%S") + f",{ms:03d}"

def fmt_kafka_bracket(ts: dt.datetime) -> str:
    return f"[{fmt_ms_comma(ts)}]"

def fmt_mongo_plain(ts: dt.datetime) -> str:
    ms = ts.microsecond // 1000
    return ts.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}" + ts.strftime("%z")

def fmt_iso8601_with_colon_offset(ts: dt.datetime) -> str:
    ms = ts.microsecond // 1000
    off = ts.strftime("%z")
    off = off[:3] + ":" + off[3:]
    return ts.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}" + off

def fmt_nginx_access_time(ts: dt.datetime) -> str:
    return ts.strftime("%d/%b/%Y:%H:%M:%S %z")

def fmt_nginx_error_time(ts: dt.datetime) -> str:
    return ts.strftime("%Y/%m/%d %H:%M:%S")

def fmt_pg_prefix(ts: dt.datetime, tzword: str) -> str:
    ms = ts.microsecond // 1000
    return ts.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d} {tzword}"

# --------------------------
# Weighted random utility
# --------------------------

def weighted_choice(rng: random.Random, weights: Dict[Any, float]) -> Any:
    items = list(weights.items())
    total = sum(max(0.0, float(w)) for _, w in items)
    if total <= 0:
        return items[0][0]
    x = rng.random() * total
    acc = 0.0
    for k, w in items:
        acc += max(0.0, float(w))
        if x <= acc:
            return k
    return items[-1][0]

# --------------------------
# File rotation writer
# --------------------------

@dataclass
class RotationConfig:
    max_bytes: int
    keep: int

class RotatingFileWriter:
    def __init__(self, path: str, rot: RotationConfig, mode: str):
        self.path = path
        self.rot = rot
        self.mode = mode
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if mode == "overwrite":
            with open(self.path, "w", encoding="utf-8"):
                pass

    def _rotate_if_needed(self) -> None:
        if self.rot.max_bytes <= 0:
            return
        try:
            size = os.path.getsize(self.path)
        except FileNotFoundError:
            return
        if size < self.rot.max_bytes:
            return

        rotated = False
        for i in range(self.rot.keep, 0, -1):
            src = f"{self.path}.{i}"
            dst = f"{self.path}.{i+1}"
            if os.path.exists(src):
                if i >= self.rot.keep:
                    try:
                        os.remove(src)
                    except OSError as exc:
                        log_warn("file_rotate_cleanup_failed", path=src, error=_clip_text(str(exc)))
                else:
                    try:
                        os.replace(src, dst)
                    except OSError as exc:
                        log_warn("file_rotate_shift_failed", src=src, dst=dst, error=_clip_text(str(exc)))
        try:
            os.replace(self.path, f"{self.path}.1")
            rotated = True
        except OSError as exc:
            log_warn("file_rotate_main_failed", path=self.path, error=_clip_text(str(exc)))
        if rotated:
            with open(self.path, "w", encoding="utf-8"):
                pass
            log_info("file_rotated", path=self.path, max_bytes=self.rot.max_bytes, keep=self.rot.keep)

    def write_lines(self, lines: List[str], dry_run: bool = False) -> int:
        line_count = len(lines)
        if dry_run:
            log_info("dry_run_file_write_skipped", path=self.path, lines=line_count)
            return line_count
        self._rotate_if_needed()
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                for ln in lines:
                    if not ln.endswith("\n"):
                        ln += "\n"
                    f.write(ln)
        except Exception as exc:
            log_error("file_write_failed", err=exc, path=self.path, lines=line_count)
            raise
        return line_count

# --------------------------
# GitHub fetch helpers (raw files + directory listing)
# --------------------------

def fetch_url(url: str, cache_path: Optional[str], headers: Dict[str, str]) -> str:
    if cache_path and os.path.exists(cache_path):
        return open(cache_path, "r", encoding="utf-8", errors="replace").read()

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(body)
    return body

def github_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    gh = cfg["linux"]["beats_repo"]["github"]
    headers = {"User-Agent": "beats_logsim/1.0", "Accept": "application/vnd.github+json"}
    token_env = gh.get("token_env")
    token = os.environ.get(token_env) if token_env else None
    if token:
        headers["Authorization"] = f"token {token}"
    return headers

def github_cache_path(cfg: Dict[str, Any], kind: str, ref: str, repo_path: str) -> Optional[str]:
    cache_dir = cfg["linux"]["beats_repo"]["github"].get("cache_dir")
    if not cache_dir:
        return None
    safe = repo_path.replace("/", "__")
    return os.path.join(cache_dir, f"{kind}__{ref}__{safe}")

def github_list_dir(cfg: Dict[str, Any], repo_path: str) -> Optional[List[Dict[str, Any]]]:
    gh = cfg["linux"]["beats_repo"]["github"]
    api_base = gh["api_base"].rstrip("/")
    owner = gh["owner"]; repo = gh["repo"]; ref = gh["ref"]
    url = f"{api_base}/repos/{owner}/{repo}/contents/{repo_path}?ref={ref}"

    cache_path = github_cache_path(cfg, "api", ref, repo_path + ".json")
    try:
        txt = fetch_url(url, cache_path=cache_path, headers=github_headers(cfg))
        data = json.loads(txt)
        if isinstance(data, list):
            return data
        return None
    except Exception:
        return None

def repo_file_text(cfg: Dict[str, Any], repo_path: str) -> Tuple[str, str]:
    local_root = cfg["linux"]["beats_repo"]["local_path"]
    gh = cfg["linux"]["beats_repo"]["github"]
    raw_base = gh["raw_base"].rstrip("/")
    owner = gh["owner"]; repo = gh["repo"]; ref = gh["ref"]

    if local_root:
        local_path = os.path.join(local_root, repo_path)
        if os.path.exists(local_path):
            return (
                open(local_path, "r", encoding="utf-8", errors="replace").read(),
                f"local:{local_path}",
            )

    url = f"{raw_base}/{owner}/{repo}/{ref}/{repo_path}"
    cache_path = github_cache_path(cfg, "raw", ref, repo_path)
    text = fetch_url(url, cache_path=cache_path, headers=github_headers(cfg))
    return text, f"github:{url}"

# --------------------------
# Manifest + config template parsing (minimal, purpose-built)
# --------------------------

@dataclass
class FilesetRef:
    module: str
    fileset: str
    is_xpack: bool
    repo_path: str  # e.g. filebeat/module/nginx/access

@dataclass
class FilesetManifest:
    module_version: Optional[str]
    vars_raw: Dict[str, Dict[str, Any]]  # varname -> {"default": ..., "os.windows":..., ...}
    input_path: Optional[str]            # e.g. config/log.yml
    ingest_pipeline: Any                 # str or list

@dataclass
class InputTemplateInfo:
    path: Optional[str]
    multiline: Dict[str, Any]  # pattern/negate/match
    type_value: Optional[str]  # "log", "redis", "netflow", etc.

def _strip_yaml_comment(line: str) -> str:
    if "#" in line:
        return line.split("#", 1)[0]
    return line

def _parse_inline_list(s: str) -> Optional[List[str]]:
    s = s.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    inner = s[1:-1].strip()
    if not inner:
        return []
    parts = [p.strip() for p in inner.split(",")]
    out: List[str] = []
    for p in parts:
        if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
            p = p[1:-1]
        out.append(p)
    return out

def parse_manifest_minimal(yaml_text: str) -> FilesetManifest:
    lines = [_strip_yaml_comment(ln.rstrip("\n")) for ln in yaml_text.splitlines()]
    module_version = None
    input_path = None
    ingest_pipeline: Any = None

    for ln in lines:
        m = re.match(r'^\s*module_version:\s*"?([^"]+)"?\s*$', ln)
        if m:
            module_version = m.group(1).strip()
        m = re.match(r'^\s*input:\s*("?)([^"]+)\1\s*$', ln)
        if m:
            input_path = m.group(2).strip()

    in_ingest = False
    ingest_list: List[str] = []
    for ln in lines:
        if re.match(r"^\s*ingest_pipeline:\s*$", ln):
            in_ingest = True
            continue
        if in_ingest:
            if re.match(r"^\S", ln) and not ln.startswith("-"):
                in_ingest = False
                continue
            m = re.match(r'^\s*-\s*"?([^"]+)"?\s*$', ln)
            if m:
                ingest_list.append(m.group(1).strip())
                continue
        m2 = re.match(r'^\s*ingest_pipeline:\s*("?)([^"]+)\1\s*$', ln)
        if m2:
            ingest_pipeline = m2.group(2).strip()
            in_ingest = False
    if ingest_pipeline is None and ingest_list:
        ingest_pipeline = ingest_list

    in_var = False
    current_var: Optional[str] = None
    current_field: Optional[str] = None
    vars_raw: Dict[str, Dict[str, Any]] = {}

    def ensure(name: str) -> Dict[str, Any]:
        if name not in vars_raw:
            vars_raw[name] = {}
        return vars_raw[name]

    for ln in lines:
        if re.match(r"^\s*var:\s*$", ln):
            in_var = True
            continue
        if not in_var:
            continue
        if re.match(r"^\S", ln) and not ln.startswith("-") and not ln.startswith("var:"):
            in_var = False
            continue

        m_name = re.match(r'^\s*-\s*name:\s*("?)([^"]+)\1\s*$', ln)
        if m_name:
            current_var = m_name.group(2).strip()
            current_field = None
            ensure(current_var)
            continue

        if not current_var:
            continue

        m_field = re.match(r'^\s*(default|os\.darwin|os\.windows):\s*(.*)$', ln)
        if m_field:
            field = m_field.group(1)
            rest = m_field.group(2).strip()
            current_field = field
            varmap = ensure(current_var)
            if rest:
                as_list = _parse_inline_list(rest)
                if as_list is not None:
                    varmap[field] = as_list
                else:
                    if (rest.startswith('"') and rest.endswith('"')) or (rest.startswith("'") and rest.endswith("'")):
                        rest = rest[1:-1]
                    varmap[field] = rest
            else:
                varmap[field] = []
            continue

        if current_field:
            m_item = re.match(r'^\s*-\s*("?)([^"]+)\1\s*$', ln)
            if m_item:
                item = m_item.group(2)
                varmap = ensure(current_var)
                if not isinstance(varmap.get(current_field), list):
                    varmap[current_field] = []
                varmap[current_field].append(item)

    return FilesetManifest(
        module_version=module_version,
        vars_raw=vars_raw,
        input_path=input_path,
        ingest_pipeline=ingest_pipeline,
    )

def get_var_effective(manifest: FilesetManifest, varname: str, os_kind: str) -> Any:
    m = manifest.vars_raw.get(varname, {})
    if os_kind == "windows" and m.get("os.windows") not in (None, "", []):
        return m["os.windows"]
    if os_kind == "darwin" and m.get("os.darwin") not in (None, "", []):
        return m["os.darwin"]
    return m.get("default")

def expand_manifest_templates(s: str, vars_map: Dict[str, Any]) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1)
        return str(vars_map.get(name, ""))
    out = re.sub(r"\{\{\.(\w+)\}\}", repl, s)

    def env_repl(m: re.Match) -> str:
        env = m.group(1)
        default = m.group(2) or ""
        return os.environ.get(env, default)
    out = re.sub(r"\$\{([A-Za-z0-9_]+)(?::([^}]*))?\}", env_repl, out)
    return out

def parse_input_template_minimal(text: str) -> InputTemplateInfo:
    type_value = None
    m = re.search(r"(?m)^\s*type:\s*([^\s#]+)\s*$", text)
    if m:
        type_value = m.group(1).strip()

    multiline: Dict[str, Any] = {}
    m = re.search(r"(?ms)multiline:\s*(?:\r?\n|\s)+\s*pattern:\s*([^\r\n]+)", text)
    if m:
        multiline["pattern"] = m.group(1).strip().strip('"').strip("'")
    m = re.search(r"(?ms)multiline:\s*(?:\r?\n|\s)+\s*negate:\s*([^\r\n]+)", text)
    if m:
        multiline["negate"] = m.group(1).strip()
    m = re.search(r"(?ms)multiline:\s*(?:\r?\n|\s)+\s*match:\s*([^\r\n]+)", text)
    if m:
        multiline["match"] = m.group(1).strip()
    return InputTemplateInfo(path=None, multiline=multiline, type_value=type_value)

# --------------------------
# Fileset discovery
# --------------------------

def list_filesets(cfg: Dict[str, Any], module: str) -> List[FilesetRef]:
    local_root = cfg["linux"]["beats_repo"]["local_path"]
    found: List[FilesetRef] = []

    def scan_local(base: str, is_xpack: bool) -> None:
        root = os.path.join(local_root, base, module) if local_root else None
        if root and os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                p = os.path.join(root, name, "manifest.yml")
                if os.path.isfile(p):
                    repo_path = f"{base}/{module}/{name}".replace("\\", "/")
                    found.append(FilesetRef(module=module, fileset=name, is_xpack=is_xpack, repo_path=repo_path))

    if local_root:
        scan_local("filebeat/module", False)
        scan_local("x-pack/filebeat/module", True)
        if found:
            return found

    candidates = [("filebeat/module", False), ("x-pack/filebeat/module", True)]
    for base, is_xpack in candidates:
        listing = github_list_dir(cfg, f"{base}/{module}")
        if not listing:
            continue
        for item in listing:
            if item.get("type") != "dir":
                continue
            name = item.get("name")
            if not name or name.startswith("_"):
                continue
            repo_path = f"{base}/{module}/{name}"
            try:
                _txt, _src = repo_file_text(cfg, f"{repo_path}/manifest.yml")
            except Exception:
                continue
            found.append(FilesetRef(module=module, fileset=name, is_xpack=is_xpack, repo_path=repo_path))
        if found:
            return found

    # Built-in last resort
    known: Dict[str, Tuple[bool, List[str]]] = {
        "activemq": (True, ["log", "audit"]),
        "auditd": (False, ["log"]),
        "kafka": (False, ["log"]),
        "mongodb": (False, ["log"]),
        "netflow": (True, ["log"]),
        "nginx": (False, ["access", "error", "ingress_controller"]),
        "postgresql": (False, ["log"]),
        "rabbitmq": (True, ["log"]),
        "redis": (False, ["log", "slowlog"]),
        "system": (False, ["syslog", "auth"]),
    }
    if module not in known:
        return []
    is_xpack, filesets = known[module]
    base = "x-pack/filebeat/module" if is_xpack else "filebeat/module"
    return [FilesetRef(module=module, fileset=fs, is_xpack=is_xpack, repo_path=f"{base}/{module}/{fs}") for fs in filesets]

# --------------------------
# Path inference (only if manifest paths missing/empty)
# --------------------------

def infer_paths_for_fileset(module: str, fileset: str, os_kind: str) -> List[str]:
    linux_mapping = {
        ("activemq", "log"): ["/opt/apache-activemq-*/data/activemq.log*"],
        ("activemq", "audit"): ["/opt/apache-activemq-*/data/audit.log*"],
        ("auditd", "log"): ["/var/log/audit/audit.log*"],
        ("kafka", "log"): [
            "/opt/kafka*/logs/controller.log*",
            "/opt/kafka*/logs/server.log*",
            "/opt/kafka*/logs/state-change.log*",
            "/opt/kafka*/logs/kafka-*.log*",
        ],
        ("mongodb", "log"): ["/var/log/mongodb/mongodb.log"],
        ("nginx", "access"): ["/var/log/nginx/access.log*"],
        ("nginx", "error"): ["/var/log/nginx/error.log*"],
        ("nginx", "ingress_controller"): ["/var/log/nginx/access.log*"],
        ("postgresql", "log"): ["/var/log/postgresql/postgresql-*-*.log*", "/var/log/postgresql/postgresql-*-*.csv*"],
        ("rabbitmq", "log"): ["/var/log/rabbitmq/rabbit@localhost.log*"],
        ("redis", "log"): ["/var/log/redis/redis-server.log*"],
        ("system", "syslog"): ["/var/log/messages*", "/var/log/syslog*"],
        ("system", "auth"): ["/var/log/auth.log*", "/var/log/secure*"],
    }
    darwin_mapping = {
        ("system", "syslog"): ["/var/log/system.log*"],
        ("system", "auth"): ["/var/log/secure.log*"],
        ("nginx", "access"): ["/usr/local/var/log/nginx/access.log*"],
        ("nginx", "error"): ["/usr/local/var/log/nginx/error.log*"],
        ("mongodb", "log"): ["/usr/local/var/log/mongodb/mongo.log*"],
        ("redis", "log"): ["/usr/local/var/log/redis.log*"],
        ("postgresql", "log"): ["/usr/local/var/log/postgres*.log*"],
    }
    windows_mapping = {
        ("nginx", "access"): [r"C:\nginx\logs\access.log*"],
        ("nginx", "error"): [r"C:\nginx\logs\error.log*"],
        ("mongodb", "log"): [r"C:\Program Files\MongoDB\Server\*\log\mongod.log*"],
        ("redis", "log"): [r"C:\ProgramData\Redis\redis.log*"],
        ("kafka", "log"): [r"C:\kafka\logs\*.log*"],
    }
    os_map = {
        "linux": linux_mapping,
        "darwin": darwin_mapping,
        "windows": windows_mapping,
    }.get(os_kind, linux_mapping)
    return os_map.get((module, fileset), [])

def choose_concrete_path(module: str, fileset: str, pattern: str) -> str:
    p = pattern
    if not any(ch in p for ch in ["*", "?", "["]):
        return p

    # If the filename is fully wildcarded, pin it to a stable test filename in-place.
    slash_idx = max(p.rfind("/"), p.rfind("\\"))
    dirname = p[: slash_idx + 1] if slash_idx >= 0 else ""
    basename = p[slash_idx + 1 :] if slash_idx >= 0 else p
    if re.fullmatch(r"\*\.log\*?", basename):
        return dirname + "test.log"
    if re.fullmatch(r"\*\.csv\*?", basename):
        return dirname + "test.csv"

    if module == "activemq":
        p = p.replace("apache-activemq-*", "apache-activemq-sim")
        return p.replace("*", "")

    if module == "kafka":
        p = p.replace("/opt/kafka*", "/opt/kafka-sim")
        if "kafka-*.log" in p:
            return p.replace("kafka-*.log", "kafka-request.log").replace("*", "")
        return p.replace("*", "")

    if module == "postgresql":
        p = re.sub(r"postgresql-\*-\*\.log\*", "postgresql-14-main.log", p)
        p = re.sub(r"postgresql-\*-\*\.csv\*", "postgresql-14-main.csv", p)
        return p.replace("*", "")

    if module in {"nginx", "auditd", "redis", "rabbitmq", "system", "mongodb"}:
        return p.replace("*", "")

    return p.replace("*", "sim").replace("?", "x")

def sandbox_path_for(module: str, fileset: str, basename: str, sandbox_base: str) -> str:
    return os.path.join(sandbox_base, module, fileset, basename)

def _normalize_path_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    out: List[str] = []
    if isinstance(v, (list, tuple)):
        for item in v:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
    seen: set = set()
    dedup: List[str] = []
    for p in out:
        if p in seen:
            continue
        seen.add(p)
        dedup.append(p)
    return dedup

def _extract_var_paths(scope: Dict[str, Any]) -> Tuple[bool, List[str]]:
    if "var.paths" in scope:
        return True, _normalize_path_list(scope.get("var.paths"))
    var_obj = scope.get("var")
    if isinstance(var_obj, dict) and "paths" in var_obj:
        return True, _normalize_path_list(var_obj.get("paths"))
    return False, []

def _merge_paths(dst: Dict[str, List[str]], key: str, paths: List[str]) -> None:
    if key not in dst:
        dst[key] = list(paths)
        return
    if not dst[key]:
        if paths:
            dst[key] = list(paths)
        return
    for p in paths:
        if p not in dst[key]:
            dst[key].append(p)

def _modules_d_candidate_dirs(cfg: Dict[str, Any]) -> List[str]:
    linux_cfg = cfg.get("linux", {})
    raw = linux_cfg.get("modules_d_path")
    out: List[str] = []
    if isinstance(raw, str) and raw.strip():
        out.append(raw.strip())
    elif isinstance(raw, list):
        out.extend([str(x).strip() for x in raw if str(x).strip()])
    defaults = [
        "/etc/filebeat/modules.d",
        "/usr/local/etc/filebeat/modules.d",
        os.path.join(os.getcwd(), "modules.d"),
        os.path.join(os.path.dirname(__file__), "modules.d"),
    ]
    out.extend(defaults)
    seen: set = set()
    dedup: List[str] = []
    for p in out:
        pp = os.path.abspath(os.path.expanduser(p))
        if pp in seen:
            continue
        seen.add(pp)
        dedup.append(pp)
    return dedup

def load_modules_d_var_paths(cfg: Dict[str, Any], modules: List[str]) -> Dict[str, Dict[str, List[str]]]:
    if yaml is None:
        log_warn("modules_d_yaml_unavailable", reason="PyYAML is not installed; skipping modules.d parsing")
        return {}

    selected = {m.lower() for m in modules}
    reserved = {
        "module", "enabled", "period", "processors", "tags", "fields", "fields_under_root",
        "index", "when", "input", "hosts", "host", "metricsets", "ssl", "timeout",
        "username", "password", "xpack.enabled", "namespace", "dataset", "var", "var.paths",
    }

    result: Dict[str, Dict[str, List[str]]] = {}
    parsed_files = 0
    used_dirs: List[str] = []

    for modules_d in _modules_d_candidate_dirs(cfg):
        if not os.path.isdir(modules_d):
            continue
        used_dirs.append(modules_d)
        files = sorted(glob.glob(os.path.join(modules_d, "*.yml")))
        files.extend(sorted(glob.glob(os.path.join(modules_d, "*.yaml"))))
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    parsed_docs = list(yaml.safe_load_all(f.read()))
            except Exception as exc:
                log_warn("modules_d_file_parse_failed", file=fp, error=_clip_text(str(exc)))
                continue
            docs: List[Dict[str, Any]] = []
            for parsed in parsed_docs:
                if parsed is None:
                    continue
                if isinstance(parsed, list):
                    docs.extend([d for d in parsed if isinstance(d, dict)])
                elif isinstance(parsed, dict):
                    docs.append(parsed)
                else:
                    log_warn("modules_d_file_ignored", file=fp, reason=f"unsupported root type {type(parsed).__name__}")
            if not docs:
                continue

            for doc in docs:
                module = str(doc.get("module", "")).strip().lower()
                if not module or module not in selected:
                    continue
                mod_map = result.setdefault(module, {})

                found_module_paths, module_paths = _extract_var_paths(doc)
                if found_module_paths:
                    _merge_paths(mod_map, "*", module_paths)

                for key, value in doc.items():
                    fs = str(key).strip().lower()
                    if fs in reserved or fs.startswith("var."):
                        continue
                    if not isinstance(value, dict):
                        continue
                    if value.get("enabled") is False:
                        continue
                    found_fs_paths, fs_paths = _extract_var_paths(value)
                    if found_fs_paths:
                        _merge_paths(mod_map, fs, fs_paths)
            parsed_files += 1

    if not used_dirs:
        log_info("modules_d_not_found", searched=_modules_d_candidate_dirs(cfg))
        return {}

    matched = {
        mod: {fs: paths for fs, paths in fsmap.items()}
        for mod, fsmap in result.items()
    }
    log_info(
        "modules_d_loaded",
        directories=used_dirs,
        parsed_files=parsed_files,
        matched_modules=sorted(matched.keys()),
        matched_var_paths=matched,
    )
    return result

# --------------------------
# Generators (Linux)
# --------------------------

def rand_test_ip(rng: random.Random) -> str:
    return rng.choice(["192.0.2", "198.51.100", "203.0.113"]) + f".{rng.randint(1,254)}"

def gen_activemq_log(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    sev = weighted_choice(rng, cfg["linux"]["modules"]["activemq"]["severity_weights"])
    msg = rng.choice(cfg["linux"]["modules"]["activemq"]["messages"]).format(
        data_dir="/opt/activemq/data/localhost/tmp_storage"
    )
    clazz = rng.choice([
        "org.apache.activemq.store.kahadb.MessageDatabase",
        "org.apache.activemq.store.kahadb.plist.PListStoreImpl",
        "org.apache.activemq.broker.BrokerService",
    ])
    thread = rng.choice(["main", "qtp443290224-47", "ActiveMQ Transport"])
    return [f"{fmt_ms_comma(ts)} | {sev} | {msg} | {clazz} | {thread}"]

def gen_activemq_audit(ts: dt.datetime, rng: random.Random) -> List[str]:
    level = rng.choice(["INFO", "WARN"])
    user = rng.choice(["anonymous", "admin", "guest"])
    action = rng.choice([
        "called org.apache.activemq.broker.jmx.QueueView.retryMessages[]",
        "requested /admin/createDestination.action [JMSDestination='test' JMSDestinationType='queue' secret='deadbeef-0000-0000-0000-000000000000' ] from 127.0.0.1",
        "requested /admin/purgeDestination.action [JMSDestination='test' JMSDestinationType='queue' secret='deadbeef-1111-1111-1111-111111111111' ] from 127.0.0.1",
    ])
    t = ts.strftime("%d-%m-%Y %H:%M:%S") + f",{ts.microsecond//1000:03d}"
    thread = rng.choice(["qtp443290224-47", "qtp12205619-36"])
    if action.startswith("called"):
        return [f"{level} | {user} {action} at {t} | {thread}"]
    return [f"{level} | {user} {action} | {thread}"]

def gen_auditd(ts: dt.datetime, rng: random.Random, serial: int, cfg: Dict[str, Any]) -> Tuple[List[str], int]:
    evt_type = weighted_choice(rng, cfg["linux"]["modules"]["auditd"]["type_weights"])
    epoch = int(ts.timestamp())
    frac = ts.microsecond // 1000
    msgid = f"{epoch}.{frac:03d}:{serial}"
    if evt_type == "SYSCALL":
        line = (
            f"type=SYSCALL msg=audit({msgid}): arch=c000003e syscall=59 success=yes exit=0 "
            f"a0=0 a1=0 a2=0 a3=0 items=0 ppid=1 pid={rng.randint(1000,9999)} "
            f"auid=1000 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 "
            f"tty=(none) ses=1 comm=\"bash\" exe=\"/usr/bin/bash\" key=(null)"
        )
    else:
        line = (
            f"type={evt_type} msg=audit({msgid}): user pid={rng.randint(1000,9999)} uid=0 auid=1000 ses=1 "
            f"msg='op=success acct=\"simuser\" exe=\"/usr/sbin/sshd\" hostname=? addr=192.0.2.10 terminal=ssh res=success'"
        )
    return [line], serial + 1

def gen_kafka(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    sev = weighted_choice(rng, cfg["linux"]["modules"]["kafka"]["severity_weights"])
    logger = rng.choice([
        "kafka.server.KafkaServer",
        "org.apache.zookeeper.ZooKeeper",
        "kafka.log.LogManager",
        "org.apache.zookeeper.ClientCnxn",
    ])
    msg = rng.choice([
        "starting",
        "Connecting to zookeeper on localhost:2181",
        "Initiating client connection, connectString=localhost:2181 sessionTimeout=6000 watcher=org.I0Itec.zkclient.ZkClient@5ffead27",
        "Will not attempt to authenticate using SASL (unknown error)",
        "Log directory '/tmp/kafka-logs' not found, creating it.",
    ])
    head = f"{fmt_kafka_bracket(ts)} {sev} {msg} ({logger})"
    if rng.random() < 0.10:
        return [head, f"({logger})"]  # continuation line without bracket timestamp
    return [head]

def gen_mongodb(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    mode = weighted_choice(rng, cfg["linux"]["modules"]["mongodb"]["mode_weights"])
    if mode == "json":
        sev = weighted_choice(rng, {"I": 0.85, "W": 0.10, "E": 0.05})
        doc = {
            "t": {"$date": fmt_iso8601_with_colon_offset(ts)},
            "s": sev,
            "c": rng.choice(["NETWORK", "CONTROL", "COMMAND"]),
            "id": rng.randint(20000, 60000),
            "ctx": rng.choice(["initandlisten", "conn1", "main"]),
            "msg": rng.choice(["waiting for connections", "end connection", "Slow query"]),
            "attr": {"remote": f"{rand_test_ip(rng)}:{rng.randint(1024,65535)}"},
        }
        return [json.dumps(doc, separators=(",", ":"))]
    else:
        sev = weighted_choice(rng, cfg["linux"]["modules"]["mongodb"]["severity_weights"])
        comp = rng.choice(["CONTROL", "NETWORK", "STORAGE"])
        ctx = rng.choice(["initandlisten", "conn1", "signalProcessingThread"])
        msg = rng.choice([
            "waiting for connections on port 27017",
            "end connection 127.0.0.1:55404 (0 connections now open)",
            "shutdown: going to close sockets...",
        ])
        return [f"{fmt_mongo_plain(ts)} {sev} {comp} [{ctx}] {msg}"]

def gen_nginx_access(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    ip = rand_test_ip(rng)
    path = rng.choice(["/", "/health", "/api/v1/items", "/favicon.ico"])
    status = weighted_choice(rng, cfg["linux"]["modules"]["nginx"]["access_status_weights"])
    size = rng.randint(0, 5000)
    ua = rng.choice([
        "curl/8.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    ])
    return [f'{ip} - - [{fmt_nginx_access_time(ts)}] "GET {path} HTTP/1.1" {status} {size} "-" "{ua}"']

def gen_nginx_error(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    level = weighted_choice(rng, cfg["linux"]["modules"]["nginx"]["error_level_weights"])
    pid = rng.randint(1000, 65000)
    conn = rng.randint(1, 1000)
    msg = (
        f'open() "/usr/share/nginx/html/missing" failed (2: No such file or directory), '
        f'client: 127.0.0.1, server: localhost, request: "GET /missing HTTP/1.1", host: "localhost"'
    )
    head = f"{fmt_nginx_error_time(ts)} [{level}] {pid}#0: *{conn} {msg}"
    if rng.random() < 0.05:
        return [head, "stacktrace: java.lang.RuntimeException: simulated"]
    return [head]

def gen_nginx_ingress_controller(ts: dt.datetime, rng: random.Random) -> List[str]:
    ip = rand_test_ip(rng)
    user = rng.choice(["-", "alice", "bob"])
    req = rng.choice(["GET / HTTP/1.1", "GET /health HTTP/1.1", "POST /api/v1/items HTTP/1.1"])
    status = rng.choice([200, 200, 200, 404, 500])
    bytes_sent = rng.randint(0, 5000)
    referer = rng.choice(["-", "https://example.com/"])
    ua = rng.choice(["curl/8.0.0", "Mozilla/5.0"])
    req_len = rng.randint(100, 2000)
    req_time = round(rng.random() * 0.5, 3)
    upstream = rng.choice(["upstream-default-svc-80", "upstream-app-api-8080"])
    alt_upstream = "-"
    upstream_addr = f"{rand_test_ip(rng)}:{rng.choice([80, 8080, 9000])}"
    upstream_resp_len = rng.randint(0, 10000)
    upstream_resp_time = round(rng.random() * 0.3, 3)
    upstream_status = status
    req_id = f"{rng.randint(10000000,99999999):x}"
    return [(
        f'{ip} - {user} [{fmt_nginx_access_time(ts)}] "{req}" {status} {bytes_sent} "{referer}" "{ua}" '
        f'{req_len} {req_time} [{upstream}] [{alt_upstream}] {upstream_addr} {upstream_resp_len} '
        f'{upstream_resp_time} {upstream_status} {req_id}'
    )]

def gen_postgresql_log(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    tzword = cfg["linux"]["tzword"]
    pid = rng.randint(1000, 65000)
    sev = weighted_choice(rng, cfg["linux"]["modules"]["postgresql"]["severity_weights"])
    msg = rng.choice([
        "database system is ready to accept connections",
        "checkpoint complete: wrote 42 buffers (0.3%)",
        'password authentication failed for user "root"',
        'syntax error at or near "bad" at character 1',
    ])
    line = f"{fmt_pg_prefix(ts, tzword)} [{pid}] {sev}: {msg}"
    if sev in ("FATAL", "ERROR") and rng.random() < 0.25:
        return [line, f"{fmt_pg_prefix(ts, tzword)} [{pid}] DETAIL: Role \"root\" does not exist."]
    return [line]

def gen_postgresql_csv(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    tzword = cfg["linux"]["tzword"]
    ts_field = fmt_pg_prefix(ts, tzword)
    pid = rng.randint(1, 99999)
    session_id = f"{rng.randint(10000000,99999999):x}.{rng.randint(1,999):x}"
    msg = rng.choice([
        'automatic vacuum of table "postgres.public.t": index scans: 1 pages: 0 removed, 89 remain',
        "duration: 12.3 ms statement: SELECT 1",
    ])
    row = [
        ts_field, "", "", str(pid), "", session_id, "1", "", ts_field.split(".")[0],
        "1/1", "0", "LOG", "00000", msg,
        "", "", "", "", "", "", "", "", "", ""
    ]
    def q(x: str) -> str:
        if any(ch in x for ch in [",", '"']):
            return '"' + x.replace('"', '""') + '"'
        return x
    return [",".join(q(x) for x in row)]

def gen_rabbitmq(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    t = fmt_iso8601_with_colon_offset(ts).replace("T", " ")
    level = weighted_choice(rng, cfg["linux"]["modules"]["rabbitmq"]["level_weights"])
    pid = f"<0.{rng.randint(10,999)}.0>"
    msg = rng.choice([
        "Running boot step database defined by app rabbit",
        "Starting worker pool 'worker_pool' with 5 processes in it",
        "Node database directory is empty.",
        "Server startup complete; 4 plugins started.",
    ])
    head = f"{t} [{level}] {pid} {msg}"
    if rng.random() < 0.10:
        return [head, "  detail: simulated continuation line"]
    return [head]

def gen_redis_log(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    pid = rng.randint(1000, 65000)
    role = rng.choice(["M", "S"])
    stamp = ts.strftime("%d %b %Y %H:%M:%S") + f".{ts.microsecond//1000:03d}"
    sym = weighted_choice(rng, cfg["linux"]["modules"]["redis"]["log_symbol_weights"])
    msg = rng.choice([
        "Ready to accept connections",
        f"Synchronization with replica {rand_test_ip(rng)}:{rng.randint(1000,9999)} succeeded",
        "Background saving terminated with success",
    ])
    return [f"{pid}:{role} {stamp} {sym} {msg}"]

def gen_system_syslog(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    host = cfg["linux"]["hostname"]
    iso = fmt_iso8601_with_colon_offset(ts)
    pid = rng.randint(1, 5000)
    tmpl = rng.choice(cfg["linux"]["modules"]["system"]["syslog_templates"])
    return [tmpl.format(iso=iso, host=host, pid=pid)]

def gen_system_auth(ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any]) -> List[str]:
    host = cfg["linux"]["hostname"]
    mon = ts.strftime("%b")
    day = f"{ts.day:2d}"
    t = ts.strftime("%H:%M:%S")
    pid = rng.randint(1000, 9999)
    user = rng.choice(["simuser", "alice", "bob"])
    ip = rand_test_ip(rng)
    port = rng.randint(1024, 65535)
    tmpl = rng.choice(cfg["linux"]["modules"]["system"]["auth_templates"])
    return [tmpl.format(mon=mon, day=day, time=t, host=host, pid=pid, user=user, ip=ip, port=port)]

# --------------------------
# Redis slowlog service-backed generator (RESP minimal client)
# --------------------------

class RedisRESP:
    def __init__(self, host: str, port: int, password: str = "", timeout_s: float = 2.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout_s = timeout_s

    def _connect(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout_s)
        s.connect((self.host, self.port))
        return s

    @staticmethod
    def _encode_cmd(parts: List[str]) -> bytes:
        out = f"*{len(parts)}\r\n".encode()
        for p in parts:
            b = p.encode()
            out += f"${len(b)}\r\n".encode() + b + b"\r\n"
        return out

    def _readline(self, s: socket.socket) -> bytes:
        buf = b""
        while not buf.endswith(b"\r\n"):
            chunk = s.recv(1)
            if not chunk:
                break
            buf += chunk
        return buf

    def _readresp(self, s: socket.socket) -> Any:
        line = self._readline(s)
        if not line:
            raise IOError("empty response")
        prefix = line[:1]
        if prefix == b"+":
            return line[1:-2].decode(errors="replace")
        if prefix == b"-":
            raise RuntimeError(line[1:-2].decode(errors="replace"))
        if prefix == b":":
            return int(line[1:-2])
        if prefix == b"$":
            n = int(line[1:-2])
            if n == -1:
                return None
            data = b""
            while len(data) < n + 2:
                data += s.recv(n + 2 - len(data))
            return data[:-2].decode(errors="replace")
        if prefix == b"*":
            n = int(line[1:-2])
            if n == -1:
                return None
            arr = []
            for _ in range(n):
                arr.append(self._readresp(s))
            return arr
        raise RuntimeError(f"unknown RESP prefix: {prefix!r}")

    def call(self, *parts: str) -> Any:
        with self._connect() as s:
            if self.password:
                s.sendall(self._encode_cmd(["AUTH", self.password]))
                _ = self._readresp(s)
            s.sendall(self._encode_cmd(list(parts)))
            return self._readresp(s)

def redis_slowlog_generate_one(rng: random.Random, cfg: Dict[str, Any]) -> bool:
    sl = cfg["linux"]["modules"]["redis"]["slowlog"]
    if not sl.get("enabled", True):
        log_info("redis_slowlog_disabled")
        return False
    hosts = sl.get("hosts") or ["localhost:6379"]
    hp = rng.choice(hosts)
    host, port = (hp.rsplit(":", 1) + ["6379"])[:2] if ":" in hp else (hp, "6379")
    try:
        port_num = int(port)
    except ValueError as exc:
        log_error("redis_slowlog_invalid_port", err=exc, host_port=hp)
        return False
    client = RedisRESP(host=host, port=port_num, password=sl.get("password", ""))
    try:
        _ = client.call("CLIENT", "SETNAME", sl.get("client_name", "beats_logsim"))
    except Exception as exc:
        log_warn("redis_setname_failed", host=host, port=port_num, error=_clip_text(str(exc)))

    if sl.get("force_log_all_commands", False):
        try:
            _ = client.call("CONFIG", "SET", "slowlog-log-slower-than", "0")
        except Exception as exc:
            log_warn("redis_slowlog_config_failed", host=host, port=port_num, setting="slowlog-log-slower-than", error=_clip_text(str(exc)))
        try:
            _ = client.call("CONFIG", "SET", "slowlog-max-len", str(int(sl.get("slowlog_max_len", 128))))
        except Exception as exc:
            log_warn("redis_slowlog_config_failed", host=host, port=port_num, setting="slowlog-max-len", error=_clip_text(str(exc)))

    cmd = rng.choice([
        ("SET", f"sim:{rng.randint(1,999)}", str(rng.randint(1,999999))),
        ("GET", f"sim:{rng.randint(1,999)}"),
        ("INCR", f"counter:{rng.randint(1,10)}"),
        ("LPUSH", f"list:{rng.randint(1,10)}", str(rng.randint(1,999999))),
        ("LRANGE", f"list:{rng.randint(1,10)}", "0", "10"),
    ])
    try:
        _ = client.call(*cmd)
        log_info("redis_slowlog_command_sent", host=host, port=port_num, command=list(cmd))
        return True
    except Exception as exc:
        log_error("redis_slowlog_command_failed", err=exc, host=host, port=port_num, command=list(cmd))
        return False

# --------------------------
# NetFlow v5 generator (UDP)
# --------------------------

def ip_to_int(ip: str) -> int:
    return int.from_bytes(socket.inet_aton(ip), "big")

def pack_netflow_v5(ts: dt.datetime, sys_uptime_ms: int, flow_sequence: int,
                    records: List[Tuple[str, str, int, int, int, int, int]]) -> bytes:
    import struct
    unix_secs = int(ts.timestamp())
    unix_nsecs = int((ts.timestamp() - unix_secs) * 1_000_000_000)
    count = len(records)
    header = struct.pack("!HHIIIIBBH", 5, count, sys_uptime_ms, unix_secs, unix_nsecs, flow_sequence, 0, 0, 0)
    now_ms = sys_uptime_ms
    recs = []
    for (src_ip, dst_ip, sp, dp, proto, pkts, octs) in records:
        first = max(0, now_ms - 1000)
        last = now_ms
        rec = struct.pack(
            "!IIIHHIIIIHHBBBBHHBBH",
            ip_to_int(src_ip),
            ip_to_int(dst_ip),
            0, 0, 0,
            pkts,
            octs,
            first,
            last,
            sp,
            dp,
            0,
            0x10,
            proto,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        recs.append(rec)
    return header + b"".join(recs)

def send_netflow_v5_one(rng: random.Random, host: str, port: int, rpp: int,
                        start_monotonic: float, flow_seq: int, ts: dt.datetime) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sys_uptime_ms = int((time.monotonic() - start_monotonic) * 1000)
    records = []
    for _ in range(rpp):
        src_ip = rand_test_ip(rng)
        dst_ip = rand_test_ip(rng)
        sp = rng.randint(1024, 65535)
        dp = rng.choice([80, 443, 53, 22, 5432, 27017, 6379])
        proto = rng.choice([6, 17])
        pkts = rng.randint(1, 50)
        octs = pkts * rng.randint(60, 1400)
        records.append((src_ip, dst_ip, sp, dp, proto, pkts, octs))
    payload = pack_netflow_v5(ts, sys_uptime_ms, flow_seq, records)
    try:
        sent_bytes = sock.sendto(payload, (host, port))
    except Exception as exc:
        log_error("netflow_send_failed", err=exc, host=host, port=port, records=len(records), bytes=len(payload), flow_seq=flow_seq)
        raise
    finally:
        sock.close()
    log_info(
        "netflow_send_ok",
        host=host,
        port=port,
        records=len(records),
        bytes=sent_bytes,
        flow_seq_start=flow_seq,
        flow_seq_end=(flow_seq + len(records) - 1),
    )
    return flow_seq + len(records)

# --------------------------
# Windows Event Log generator
# --------------------------

def run_powershell(ps: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
    )

def windows_write_event(message: str, level: str, event_id: int, cfg: Dict[str, Any]) -> bool:
    win = cfg["windows"]["winlog"]
    log_name = win["name"]
    source = win["source"]

    ps_setup = f"""
    $ErrorActionPreference = 'Stop';
    if (-not [System.Diagnostics.EventLog]::Exists('{log_name}')) {{
      New-EventLog -LogName '{log_name}' -Source '{source}';
    }} else {{
      if (-not [System.Diagnostics.EventLog]::SourceExists('{source}')) {{
        New-EventLog -LogName '{log_name}' -Source '{source}';
      }}
    }}
    """
    setup = run_powershell(ps_setup)
    if setup.returncode == 0:
        ps_write = f"""
        $ErrorActionPreference = 'Stop';
        Write-EventLog -LogName '{log_name}' -Source '{source}' -EventId {event_id} -EntryType {level} -Message '{message.replace("'", "''")}';
        """
        res = run_powershell(ps_write)
        if res.returncode == 0:
            log_info("windows_event_write_ok", log_name=log_name, source=source, level=level, event_id=event_id)
            return True
        log_warn(
            "windows_event_write_failed",
            log_name=log_name,
            source=source,
            level=level,
            event_id=event_id,
            stderr=_clip_text(res.stderr or ""),
            stdout=_clip_text(res.stdout or ""),
        )
    else:
        log_warn(
            "windows_event_setup_failed",
            log_name=log_name,
            source=source,
            stderr=_clip_text(setup.stderr or ""),
            stdout=_clip_text(setup.stdout or ""),
        )

    if win.get("fallback_to_application", True):
        t = "INFORMATION" if level.lower().startswith("info") else ("WARNING" if level.lower().startswith("warn") else "ERROR")
        fallback = subprocess.run(
            ["eventcreate", "/l", "APPLICATION", "/so", source, "/t", t, "/id", str(event_id), "/d", message],
            capture_output=True,
            text=True,
        )
        if fallback.returncode == 0:
            log_info("windows_event_write_ok_fallback", log_name="APPLICATION", source=source, level=t, event_id=event_id)
            return True
        log_error(
            "windows_event_fallback_failed",
            log_name="APPLICATION",
            source=source,
            level=t,
            event_id=event_id,
            stderr=_clip_text(fallback.stderr or ""),
            stdout=_clip_text(fallback.stdout or ""),
        )
        return False

    log_error("windows_event_write_failed_no_fallback", log_name=log_name, source=source, level=level, event_id=event_id)
    return False

# --------------------------
# Sink wiring
# --------------------------

@dataclass
class FilesetSink:
    ref: FilesetRef
    manifest: FilesetManifest
    vars_effective: Dict[str, Any]
    input_info: InputTemplateInfo
    path_patterns: List[str]
    concrete_paths: List[str]
    writers: List[RotatingFileWriter]
    path_mode: str

def build_linux_sinks(cfg: Dict[str, Any], modules: List[str], os_kind: str = "linux") -> List[FilesetSink]:
    sinks: List[FilesetSink] = []
    rot = RotationConfig(max_bytes=int(cfg["linux"]["rotate_bytes"]), keep=int(cfg["linux"]["rotate_keep"]))
    file_mode = cfg["linux"]["file_mode"]
    path_mode = cfg["linux"]["path_mode"]
    sandbox_base = cfg["linux"]["sandbox_base"]
    overrides_paths = cfg["linux"].get("var_paths_overrides", {})
    overrides_vars = cfg["linux"].get("var_overrides", {})
    modules_d_var_paths = load_modules_d_var_paths(cfg, modules)
    gh_ref = cfg["linux"]["beats_repo"]["github"]["ref"]
    log_info("build_linux_sinks_start", modules=modules, os_kind=os_kind, path_mode=path_mode, file_mode=file_mode, github_ref=gh_ref)

    for module in modules:
        filesets = list_filesets(cfg, module)
        if not filesets:
            log_warn("module_has_no_filesets", module=module)
        for fs_ref in filesets:
            try:
                manifest_text, src1 = repo_file_text(cfg, f"{fs_ref.repo_path}/manifest.yml")
            except Exception as exc:
                log_error("sink_manifest_load_failed", err=exc, module=module, fileset=fs_ref.fileset, repo_path=fs_ref.repo_path)
                continue
            manifest = parse_manifest_minimal(manifest_text)

            input_info = InputTemplateInfo(path=None, multiline={}, type_value=None)
            src2 = None
            if manifest.input_path:
                try:
                    cfg_text, src2 = repo_file_text(cfg, f"{fs_ref.repo_path}/{manifest.input_path}")
                    input_info = parse_input_template_minimal(cfg_text)
                    input_info.path = manifest.input_path
                except Exception as exc:
                    log_warn(
                        "sink_input_template_parse_failed",
                        module=module,
                        fileset=fs_ref.fileset,
                        input_template=manifest.input_path,
                        error=_clip_text(str(exc)),
                    )

            vars_effective: Dict[str, Any] = {
                vn: get_var_effective(manifest, vn, os_kind) for vn in manifest.vars_raw.keys()
            }

            mod_over = overrides_vars.get(module, {})
            fs_over = mod_over.get(fs_ref.fileset, {})
            for k, v in fs_over.items():
                vars_effective[k] = v

            path_patterns: List[str] = []
            reason = "manifest"
            if (module, fs_ref.fileset) not in SERVICE_FILESETS:
                if module in overrides_paths and fs_ref.fileset in overrides_paths[module]:
                    path_patterns = list(overrides_paths[module][fs_ref.fileset])
                    reason = "override"
                else:
                    module_map = modules_d_var_paths.get(module, {})
                    from_modules_d = False
                    if fs_ref.fileset in module_map:
                        path_patterns = list(module_map.get(fs_ref.fileset, []))
                        reason = "modules.d"
                        from_modules_d = True
                    elif "*" in module_map:
                        path_patterns = list(module_map.get("*", []))
                        reason = "modules.d(module-level)"
                        from_modules_d = True

                    if not from_modules_d:
                        eff = vars_effective.get("paths")
                        if isinstance(eff, list):
                            path_patterns = [p for p in eff if p not in (None, "")]
                        elif isinstance(eff, str) and eff:
                            path_patterns = [eff]

                if not path_patterns:
                    path_patterns = infer_paths_for_fileset(module, fs_ref.fileset, os_kind=os_kind)
                    if reason.startswith("modules.d"):
                        reason = "modules.d_empty_inferred"
                    else:
                        reason = "inferred"

                path_patterns = [expand_manifest_templates(p, vars_effective) for p in path_patterns]

            concrete_paths: List[str] = []
            writers: List[RotatingFileWriter] = []
            if (module, fs_ref.fileset) not in SERVICE_FILESETS:
                for pat in path_patterns:
                    concrete = choose_concrete_path(module, fs_ref.fileset, pat)
                    if path_mode == "sandbox":
                        basename = os.path.basename(concrete) or f"{module}-{fs_ref.fileset}.log"
                        concrete = sandbox_path_for(module, fs_ref.fileset, basename, sandbox_base)
                    concrete_paths.append(concrete)
                    try:
                        writers.append(RotatingFileWriter(concrete, rot, file_mode))
                    except Exception as exc:
                        log_error("sink_writer_create_failed", err=exc, module=module, fileset=fs_ref.fileset, path=concrete)
                if not writers:
                    log_error("sink_skipped_no_writers", module=module, fileset=fs_ref.fileset, concrete_paths=concrete_paths)
                    continue

            log_info(
                "sink_ready",
                module=module,
                fileset=fs_ref.fileset,
                repo=("x-pack" if fs_ref.is_xpack else "filebeat"),
                github_ref=gh_ref,
                manifest_source=src1,
                sink_type=("service" if (module, fs_ref.fileset) in SERVICE_FILESETS else "file"),
            )
            if src2:
                log_info(
                    "sink_input_template",
                    module=module,
                    fileset=fs_ref.fileset,
                    input_template=manifest.input_path,
                    source=src2,
                    input_type=input_info.type_value,
                    input_multiline=input_info.multiline,
                )
            if (module, fs_ref.fileset) in SERVICE_FILESETS:
                log_info("sink_service_based", module=module, fileset=fs_ref.fileset)
            else:
                log_info(
                    "sink_paths_resolved",
                    module=module,
                    fileset=fs_ref.fileset,
                    var_paths_reason=reason,
                    var_paths=path_patterns,
                    path_mode=path_mode,
                    concrete_paths=concrete_paths,
                )
                if path_mode == "sandbox":
                    rec = [p + "*" for p in concrete_paths]
                    log_info("sink_sandbox_var_paths_recommended", module=module, fileset=fs_ref.fileset, var_paths=rec)

            sinks.append(FilesetSink(
                ref=fs_ref,
                manifest=manifest,
                vars_effective=vars_effective,
                input_info=input_info,
                path_patterns=path_patterns,
                concrete_paths=concrete_paths,
                writers=writers,
                path_mode=path_mode,
            ))
    log_info("build_linux_sinks_complete", sinks=len(sinks))
    return sinks

def emit_linux_one(sink: FilesetSink, ts: dt.datetime, rng: random.Random, cfg: Dict[str, Any],
                   audit_serial: int, netflow_state: Dict[str, Any], stats: Optional[SimulationStats] = None) -> int:
    m = sink.ref.module
    fs = sink.ref.fileset
    sink_name = f"{m}/{fs}"
    dry_run = bool(cfg["runtime"].get("dry_run", False))
    static_lines = module_static_messages(cfg, m)

    def writer_path(idx: int) -> str:
        if idx < len(sink.concrete_paths):
            return sink.concrete_paths[idx]
        return f"{sink_name}:writer#{idx}"

    if (m, fs) == ("redis", "slowlog"):
        if stats:
            stats.network_send_ops += 1
        ok = redis_slowlog_generate_one(rng, cfg)
        if stats:
            if ok:
                stats.events_emitted += 1
            else:
                stats.network_send_errors += 1
                stats.events_failed += 1
        return audit_serial

    if (m, fs) == ("netflow", "log"):
        nf = cfg["linux"]["netflow"]
        host = str(nf.get("host", "localhost"))
        port = int(nf.get("port", 2055))
        rpp = int(nf.get("records_per_packet", 10))
        flow_seq = netflow_state.get("flow_seq", 0)
        if stats:
            stats.network_send_ops += 1
        try:
            flow_seq = send_netflow_v5_one(rng, host, port, rpp, netflow_state["start_monotonic"], flow_seq, ts)
            netflow_state["flow_seq"] = flow_seq
            if stats:
                stats.events_emitted += 1
        except Exception as exc:
            log_error("sink_netflow_emit_failed", err=exc, sink=sink_name, host=host, port=port, records_per_packet=rpp)
            if stats:
                stats.network_send_errors += 1
                stats.events_failed += 1
        return audit_serial

    if m == "system" and cfg["linux"].get("system_emit_via_logger", False):
        cmd_prefix: List[str]
        if fs == "syslog":
            generated = gen_system_syslog(ts, rng, cfg)[0]
            cmd_prefix = ["logger", "--"]
        elif fs == "auth":
            generated = gen_system_auth(ts, rng, cfg)[0]
            cmd_prefix = ["logger", "-p", "auth.info", "--"]
        else:
            log_warn("system_logger_unsupported_fileset", sink=sink_name)
            return audit_serial
        messages_to_send = list(static_lines) if static_lines else [generated]
        for msg in messages_to_send:
            if stats:
                stats.network_send_ops += 1
            if dry_run:
                log_info("dry_run_system_logger_skipped", sink=sink_name, message=msg)
                if stats:
                    stats.events_emitted += 1
                continue
            try:
                res = subprocess.run(cmd_prefix + [msg], capture_output=True, text=True)
                if res.returncode != 0:
                    raise RuntimeError(_clip_text(res.stderr or res.stdout or "logger failed"))
                if static_lines:
                    log_info("system_logger_static_message_sent", sink=sink_name, message=msg)
                else:
                    log_info("system_logger_send_ok", sink=sink_name, message=msg)
                if stats:
                    stats.events_emitted += 1
            except Exception as exc:
                log_error("system_logger_send_failed", err=exc, sink=sink_name, message=msg)
                if stats:
                    stats.network_send_errors += 1
                    stats.events_failed += 1
        return audit_serial

    lines: List[str] = []
    if static_lines and (m, fs) not in SERVICE_FILESETS:
        lines = static_lines
        log_info("sink_static_messages_applied", sink=sink_name, lines=len(static_lines))
    elif (m, fs) == ("activemq", "log"):
        lines = gen_activemq_log(ts, rng, cfg)
    elif (m, fs) == ("activemq", "audit"):
        lines = gen_activemq_audit(ts, rng)
    elif (m, fs) == ("auditd", "log"):
        lines, audit_serial = gen_auditd(ts, rng, audit_serial, cfg)
    elif (m, fs) == ("kafka", "log"):
        lines = gen_kafka(ts, rng, cfg)
    elif (m, fs) == ("mongodb", "log"):
        lines = gen_mongodb(ts, rng, cfg)
    elif (m, fs) == ("nginx", "access"):
        lines = gen_nginx_access(ts, rng, cfg)
    elif (m, fs) == ("nginx", "error"):
        lines = gen_nginx_error(ts, rng, cfg)
    elif (m, fs) == ("nginx", "ingress_controller"):
        lines = gen_nginx_ingress_controller(ts, rng)
    elif (m, fs) == ("rabbitmq", "log"):
        lines = gen_rabbitmq(ts, rng, cfg)
    elif (m, fs) == ("redis", "log"):
        lines = gen_redis_log(ts, rng, cfg)
    elif (m, fs) == ("system", "syslog"):
        lines = gen_system_syslog(ts, rng, cfg)
    elif (m, fs) == ("system", "auth"):
        lines = gen_system_auth(ts, rng, cfg)
    elif (m, fs) == ("postgresql", "log"):
        if not sink.writers:
            log_error("sink_no_file_writers", sink=sink_name)
            if stats:
                stats.file_write_errors += 1
                stats.events_failed += 1
            return audit_serial
        for i, w in enumerate(sink.writers):
            path = writer_path(i)
            use_csv = path.lower().endswith(".csv") or ".csv" in os.path.basename(path).lower()
            out_lines = gen_postgresql_csv(ts, rng, cfg) if use_csv else gen_postgresql_log(ts, rng, cfg)
            if stats:
                stats.file_write_ops += 1
            try:
                written = w.write_lines(out_lines, dry_run=dry_run)
                log_info("sink_file_emit_ok", sink=sink_name, path=path, lines=written, dry_run=dry_run, format=("csv" if use_csv else "log"))
                if stats:
                    stats.lines_written += written
                    stats.events_emitted += 1
            except Exception as exc:
                log_error("sink_file_emit_failed", err=exc, sink=sink_name, path=path, attempted_lines=len(out_lines))
                if stats:
                    stats.file_write_errors += 1
                    stats.events_failed += 1
        return audit_serial
    else:
        return audit_serial

    if not lines:
        log_warn("sink_generated_no_lines", sink=sink_name)
        return audit_serial
    if not sink.writers:
        log_error("sink_no_file_writers", sink=sink_name)
        if stats:
            stats.file_write_errors += 1
            stats.events_failed += 1
        return audit_serial
    for i, w in enumerate(sink.writers):
        path = writer_path(i)
        if stats:
            stats.file_write_ops += 1
        try:
            written = w.write_lines(lines, dry_run=dry_run)
            log_info("sink_file_emit_ok", sink=sink_name, path=path, lines=written, dry_run=dry_run)
            if stats:
                stats.lines_written += written
                stats.events_emitted += 1
        except Exception as exc:
            log_error("sink_file_emit_failed", err=exc, sink=sink_name, path=path, attempted_lines=len(lines))
            if stats:
                stats.file_write_errors += 1
                stats.events_failed += 1
    return audit_serial

# --------------------------
# CLI + runners
# --------------------------

def make_json_schema() -> Dict[str, Any]:
    module_cfg_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "activemq": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "severity_weights": {"type": "object"},
                    "messages": {"type": "array", "items": {"type": "string"}},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "auditd": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "kafka": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "severity_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "mongodb": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "mode_weights": {"type": "object"},
                    "severity_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "nginx": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "access_status_weights": {"type": "object"},
                    "error_level_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "postgresql": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "severity_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "rabbitmq": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "level_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "redis": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "log_symbol_weights": {"type": "object"},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                    "slowlog": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "hosts": {"type": "array", "items": {"type": "string"}},
                            "password": {"type": "string"},
                            "force_log_all_commands": {"type": "boolean"},
                            "slowlog_max_len": {"type": "integer"},
                            "client_name": {"type": "string"},
                        },
                    },
                },
            },
            "system": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "auth_templates": {"type": "array", "items": {"type": "string"}},
                    "syslog_templates": {"type": "array", "items": {"type": "string"}},
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
            "netflow": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "static_messages": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "beats_logsim control schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "version": {"type": "integer", "const": 1},
            "runtime": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "modules": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "rate": {"type": "number", "minimum": 0},
                    "duration_s": {"type": "integer", "minimum": 0},
                    "start_time": {"type": "string"},
                    "seed": {"type": "integer"},
                    "dry_run": {"type": "boolean"},
                    "stats_every_s": {"type": "integer", "minimum": 0},
                },
                "required": ["modules", "rate", "duration_s", "start_time", "seed", "dry_run"],
            },
            "linux": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path_mode": {"type": "string", "enum": ["official", "sandbox"]},
                    "sandbox_base": {"type": "string"},
                    "modules_d_path": {"oneOf": [{"type": "string"}, {"type": "null"}, {"type": "array", "items": {"type": "string"}}]},
                    "rotate_bytes": {"type": "integer", "minimum": 0},
                    "rotate_keep": {"type": "integer", "minimum": 0},
                    "file_mode": {"type": "string", "enum": ["append", "overwrite"]},
                    "hostname": {"type": "string"},
                    "tzword": {"type": "string"},
                    "system_emit_via_logger": {"type": "boolean"},
                    "beats_repo": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "local_path": {"type": ["string", "null"]},
                            "github": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "owner": {"type": "string"},
                                    "repo": {"type": "string"},
                                    "ref": {"type": "string"},
                                    "raw_base": {"type": "string"},
                                    "api_base": {"type": "string"},
                                    "cache_dir": {"type": ["string", "null"]},
                                    "token_env": {"type": "string"},
                                },
                                "required": ["owner", "repo", "ref", "raw_base", "api_base"],
                            },
                        },
                        "required": ["local_path", "github"],
                    },
                    "netflow": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "host": {"type": "string"},
                            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                            "records_per_packet": {"type": "integer", "minimum": 1, "maximum": 30},
                        },
                        "required": ["host", "port", "records_per_packet"],
                    },
                    "modules": module_cfg_schema,
                    "var_paths_overrides": {"type": "object"},
                    "var_overrides": {"type": "object"},
                },
                "required": ["path_mode", "sandbox_base", "rotate_bytes", "rotate_keep", "file_mode", "hostname", "tzword", "beats_repo", "netflow", "modules"],
            },
            "windows": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "winlog": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "source": {"type": "string"},
                            "base_eventid": {"type": "integer"},
                            "fallback_to_application": {"type": "boolean"},
                        },
                        "required": ["name", "source", "base_eventid", "fallback_to_application"],
                    }
                },
                "required": ["winlog"],
            },
        },
        "required": ["version", "runtime", "linux", "windows"],
    }

def run_windows(cfg: Dict[str, Any], rng: random.Random, rate: float, duration_s: int) -> None:
    start = time.time()
    next_deadline = start
    stats_every = int(cfg["runtime"].get("stats_every_s", 0))
    last_stats = start
    stats = SimulationStats()
    dry_run = bool(cfg["runtime"].get("dry_run", False))
    i = 0
    winlog = cfg["windows"]["winlog"]
    base = int(winlog["base_eventid"])
    log_info(
        "windows_simulation_started",
        rate=rate,
        duration_s=duration_s,
        dry_run=dry_run,
        log_name=winlog["name"],
        source=winlog["source"],
        base_eventid=base,
    )
    while True:
        now = time.time()
        if duration_s > 0 and (now - start) >= duration_s:
            break
        if now < next_deadline:
            time.sleep(max(0.0, next_deadline - now))
            continue

        event_id = base + (i % 1000)
        level = rng.choice(["Information", "Warning", "Error"])
        msg = rng.choice([
            f"Simulated auth: login_failed user=alice src={rand_test_ip(rng)}",
            f"Simulated service: service_restart name=simsvc code={rng.randint(1,5)}",
            f"Simulated app: exception=RuntimeError trace_id={rng.randint(100000,999999)}",
        ])
        stats.network_send_ops += 1
        if dry_run:
            ok = True
            log_info("dry_run_windows_event_skipped", event_id=event_id, level=level, message=msg)
        else:
            ok = windows_write_event(msg, level, event_id, cfg)
        if ok:
            stats.events_emitted += 1
        else:
            stats.network_send_errors += 1
            stats.events_failed += 1

        i += 1
        stats.ticks += 1
        if stats_every > 0 and (now - last_stats) >= stats_every:
            log_info(
                "windows_simulation_stats",
                uptime_s=round(now - start, 1),
                ticks=stats.ticks,
                events_emitted=stats.events_emitted,
                events_failed=stats.events_failed,
                send_errors=stats.network_send_errors,
            )
            last_stats = now
        next_deadline = time.time() if rate <= 0 else next_deadline + 1.0 / rate
    total_uptime = time.time() - start
    log_info(
        "windows_simulation_completed",
        uptime_s=round(total_uptime, 1),
        ticks=stats.ticks,
        events_emitted=stats.events_emitted,
        events_failed=stats.events_failed,
        send_errors=stats.network_send_errors,
    )

def run_linux(cfg: Dict[str, Any], rng: random.Random, modules: List[str], rate: float, duration_s: int, start_time: dt.datetime) -> None:
    dry_run = bool(cfg["runtime"].get("dry_run", False))
    log_info(
        "linux_simulation_started",
        modules=modules,
        rate=rate,
        duration_s=duration_s,
        dry_run=dry_run,
        path_mode=cfg["linux"]["path_mode"],
        start_time=start_time.isoformat(),
    )
    sinks = build_linux_sinks(cfg, modules, os_kind="linux")
    if not sinks:
        log_error("linux_simulation_no_sinks", modules=modules)
        return

    start_wall = time.time()
    next_deadline = start_wall
    audit_serial = 1000
    netflow_state = {"start_monotonic": time.monotonic(), "flow_seq": 0}
    stats = SimulationStats()

    stats_every = int(cfg["runtime"].get("stats_every_s", 0))
    last_stats = start_wall

    while True:
        now = time.time()
        if duration_s > 0 and (now - start_wall) >= duration_s:
            break
        if now < next_deadline:
            time.sleep(max(0.0, next_deadline - now))
            continue

        ts = start_time + dt.timedelta(seconds=(now - start_wall))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)

        for sink in sinks:
            audit_serial = emit_linux_one(sink, ts, rng, cfg, audit_serial, netflow_state, stats=stats)

        stats.ticks += 1
        if stats_every > 0 and (now - last_stats) >= stats_every:
            log_info(
                "linux_simulation_stats",
                uptime_s=round(now - start_wall, 1),
                ticks=stats.ticks,
                sinks=len(sinks),
                lines_written=stats.lines_written,
                file_write_ops=stats.file_write_ops,
                file_write_errors=stats.file_write_errors,
                network_send_ops=stats.network_send_ops,
                network_send_errors=stats.network_send_errors,
                events_emitted=stats.events_emitted,
                events_failed=stats.events_failed,
            )
            last_stats = now

        next_deadline = time.time() if rate <= 0 else next_deadline + 1.0 / rate
    total_uptime = time.time() - start_wall
    log_info(
        "linux_simulation_completed",
        uptime_s=round(total_uptime, 1),
        ticks=stats.ticks,
        sinks=len(sinks),
        lines_written=stats.lines_written,
        file_write_ops=stats.file_write_ops,
        file_write_errors=stats.file_write_errors,
        network_send_ops=stats.network_send_ops,
        network_send_errors=stats.network_send_errors,
        events_emitted=stats.events_emitted,
        events_failed=stats.events_failed,
        final_audit_serial=audit_serial,
    )

def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-platform Beats log generator (Filebeat modules + Winlogbeat).")
    ap.add_argument("--config", default="application_default.json", help="JSON control file path.")
    ap.add_argument("--modules", default=None, help="Comma list or 'all'. Overrides config.runtime.modules.")
    ap.add_argument("--rate", type=float, default=None)
    ap.add_argument("--duration", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--start-time", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-os", choices=["linux", "windows"], default=None)
    ap.add_argument("--path-mode", choices=["official", "sandbox"], default=None)
    ap.add_argument("--sandbox-base", default=None)
    ap.add_argument("--modules-d-path", default=None, help="Directory containing modules.d/*.yml to read var.paths from.")
    ap.add_argument("--rotate-bytes", type=int, default=None)
    ap.add_argument("--rotate-keep", type=int, default=None)
    ap.add_argument("--beats-repo", default=None, help="Local elastic/beats clone path.")
    ap.add_argument("--github-ref", default=None, help="elastic/beats ref (tag/branch).")
    ap.add_argument("--netflow-host", default=None)
    ap.add_argument("--netflow-port", type=int, default=None)
    ap.add_argument("--netflow-records", type=int, default=None)
    ap.add_argument("--tzword", default=None)
    ap.add_argument("--winlog-name", default=None)
    ap.add_argument("--winlog-source", default=None)
    ap.add_argument("--winlog-base-eventid", type=int, default=None)
    ap.add_argument("--set", action="append", default=[], help="dot.path=value override (JSON parsed when possible).")
    ap.add_argument("--print-schema", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if args.config:
        try:
            config_path = args.config
            if not os.path.isabs(config_path) and not os.path.exists(config_path):
                local_cfg = os.path.join(os.path.dirname(__file__), config_path)
                if os.path.exists(local_cfg):
                    config_path = local_cfg
            with open(config_path, "r", encoding="utf-8") as f:
                deep_merge(cfg, json.load(f))
            log_info("config_loaded", config_path=config_path)
        except Exception as exc:
            log_error("config_load_failed", err=exc, config_path=args.config)
            raise SystemExit(2)

    if args.modules is not None:
        cfg["runtime"]["modules"] = args.modules
    if args.rate is not None:
        cfg["runtime"]["rate"] = args.rate
    if args.duration is not None:
        cfg["runtime"]["duration_s"] = args.duration
    if args.seed is not None:
        cfg["runtime"]["seed"] = args.seed
    if args.start_time is not None:
        cfg["runtime"]["start_time"] = args.start_time
    if args.dry_run:
        cfg["runtime"]["dry_run"] = True

    if args.path_mode is not None:
        cfg["linux"]["path_mode"] = args.path_mode
    if args.sandbox_base is not None:
        cfg["linux"]["sandbox_base"] = args.sandbox_base
    if args.modules_d_path is not None:
        cfg["linux"]["modules_d_path"] = args.modules_d_path
    if args.rotate_bytes is not None:
        cfg["linux"]["rotate_bytes"] = args.rotate_bytes
    if args.rotate_keep is not None:
        cfg["linux"]["rotate_keep"] = args.rotate_keep
    if args.beats_repo is not None:
        cfg["linux"]["beats_repo"]["local_path"] = args.beats_repo
    if args.github_ref is not None:
        cfg["linux"]["beats_repo"]["github"]["ref"] = args.github_ref
    if args.netflow_host is not None:
        cfg["linux"]["netflow"]["host"] = args.netflow_host
    if args.netflow_port is not None:
        cfg["linux"]["netflow"]["port"] = args.netflow_port
    if args.netflow_records is not None:
        cfg["linux"]["netflow"]["records_per_packet"] = args.netflow_records
    if args.tzword is not None:
        cfg["linux"]["tzword"] = args.tzword
    if args.winlog_name is not None:
        cfg["windows"]["winlog"]["name"] = args.winlog_name
    if args.winlog_source is not None:
        cfg["windows"]["winlog"]["source"] = args.winlog_source
    if args.winlog_base_eventid is not None:
        cfg["windows"]["winlog"]["base_eventid"] = args.winlog_base_eventid

    for item in args.set:
        if "=" not in item:
            raise SystemExit("--set requires dot.path=value")
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        try:
            v_parsed = json.loads(v)
        except Exception:
            v_parsed = v
        dotpath_set(cfg, k, v_parsed)

    if args.print_schema:
        print(json.dumps(make_json_schema(), indent=2, sort_keys=True))
        return

    sysname = platform.system().lower()
    os_kind = args.force_os or ("windows" if "windows" in sysname else "linux")

    modules = parse_modules_list(cfg["runtime"]["modules"])
    rate = float(cfg["runtime"]["rate"])
    duration_s = int(cfg["runtime"]["duration_s"])
    start_time = parse_start_time(str(cfg["runtime"]["start_time"]))
    rng = random.Random(int(cfg["runtime"]["seed"]))
    log_info(
        "simulator_configuration_resolved",
        os_kind=os_kind,
        modules=modules,
        rate=rate,
        duration_s=duration_s,
        dry_run=bool(cfg["runtime"].get("dry_run", False)),
        seed=int(cfg["runtime"]["seed"]),
        start_time=start_time.isoformat(),
        modules_d_path=cfg["linux"].get("modules_d_path"),
    )

    try:
        if os_kind == "windows":
            run_windows(cfg, rng, rate, duration_s)
        else:
            run_linux(cfg, rng, modules, rate, duration_s, start_time)
    except KeyboardInterrupt:
        log_warn("simulation_interrupted_by_user")
    except Exception as exc:
        log_error("simulation_fatal_error", err=exc)
        raise

if __name__ == "__main__":
    main()
