#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REMOTE_DEPLOY_SCRIPT = r"""#!/usr/bin/env bash
set -euo pipefail

STAGING_DIR="${1:?missing staging dir}"
REMOTE_SCRIPTS_DIR="${2:?missing scripts dir}"
REMOTE_RULES_DIR="${3:?missing rules dir}"
REMOTE_RULES_ZIP="${4:?missing rules zip path}"
REMOTE_PIPELINE_CONF="${5:?missing pipeline conf path}"
REMOTE_BEATS_PIPELINE_CONF="${6:?missing beats pipeline conf path}"
REMOTE_PIPELINES_YML="${7:?missing pipelines.yml path}"
REMOTE_LOGSTASH_SETTINGS_DIR="${8:?missing logstash settings dir}"
REMOTE_LOGSTASH_BIN="${9:?missing logstash bin}"
REMOTE_LOGSTASH_STDOUT="${10:?missing logstash stdout path}"
SKIP_RESTART="${11:-0}"
KEEP_STAGING="${12:-0}"
REMOTE_RESTART_SCRIPT="${13:-/home/restart_logstash.sh}"
DEPLOYMENT_MODE="${14:-signal}"
REMOTE_TRUSTSTORE_PATH="${15:-}"
REMOTE_TRUSTSTORE_PASSWORD="${16:-}"

log() {
    printf '[remote] %s\n' "$*"
}

fail() {
    printf '[remote] ERROR: %s\n' "$*" >&2
    exit 1
}

require_non_empty_file() {
    local path="$1"
    [[ -s "$path" ]] || fail "Required file missing or empty: $path"
}

require_file() {
    local path="$1"
    [[ -f "$path" ]] || fail "Required file missing: $path"
}

ensure_parent_dir() {
    local path="$1"
    mkdir -p "$(dirname "$path")"
}

quote_for_shell() {
    printf "%q" "$1"
}

restart_logstash() {
    local restart_target="$1"

    if [[ -x "$restart_target" ]]; then
        "$restart_target"
        return
    fi

    if [[ -f "$restart_target" ]]; then
        bash "$restart_target"
        return
    fi

    fail "Restart script not found on remote host: $restart_target"
}

find_logstash_pid() {
    pgrep -o -f 'org\.logstash\.Logstash|/usr/share/logstash/bin/logstash' 2>/dev/null || true
}

ensure_kafka_truststore() {
    [[ "$DEPLOYMENT_MODE" == "kafka" ]] || return 0

    [[ -n "$REMOTE_TRUSTSTORE_PATH" ]] || fail "Kafka mode requires a truststore path."
    [[ -n "$REMOTE_TRUSTSTORE_PASSWORD" ]] || fail "Kafka mode requires a truststore password."

    if [[ -f "$REMOTE_TRUSTSTORE_PATH" ]]; then
        log "Kafka truststore already exists: $REMOTE_TRUSTSTORE_PATH"
        return 0
    fi

    require_file "$INCOMING_DIR/ca-cert"
    command -v keytool >/dev/null 2>&1 || fail "'keytool' is required to build the Kafka truststore."

    ensure_parent_dir "$REMOTE_TRUSTSTORE_PATH"
    log "Creating Kafka truststore at $REMOTE_TRUSTSTORE_PATH from uploaded ca-cert."
    keytool -importcert -trustcacerts -noprompt \
        -alias infraon-kafka-ca \
        -file "$INCOMING_DIR/ca-cert" \
        -keystore "$REMOTE_TRUSTSTORE_PATH" \
        -storepass "$REMOTE_TRUSTSTORE_PASSWORD"
}

cleanup() {
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        if [[ "$KEEP_STAGING" != "1" && -d "$STAGING_DIR" ]]; then
            rm -rf "$STAGING_DIR"
        fi
        return
    fi

    if [[ "${ROLLBACK_NEEDED:-0}" != "1" ]]; then
        return
    fi

    log "Deployment failed; attempting rollback."

    if [[ -n "${BACKUP_REDIS_STREAMER:-}" && -e "$BACKUP_REDIS_STREAMER" ]]; then
        cp -a "$BACKUP_REDIS_STREAMER" "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb"
    fi

    if [[ -n "${BACKUP_RULE_MATCHER:-}" && -e "$BACKUP_RULE_MATCHER" ]]; then
        cp -a "$BACKUP_RULE_MATCHER" "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb"
    fi

    if [[ -n "${BACKUP_PIPELINE_CONF:-}" && -e "$BACKUP_PIPELINE_CONF" ]]; then
        cp -a "$BACKUP_PIPELINE_CONF" "$REMOTE_PIPELINE_CONF"
    fi

    if [[ -n "${BACKUP_BEATS_PIPELINE_CONF:-}" && -e "$BACKUP_BEATS_PIPELINE_CONF" ]]; then
        cp -a "$BACKUP_BEATS_PIPELINE_CONF" "$REMOTE_BEATS_PIPELINE_CONF"
    fi

    if [[ -n "${BACKUP_PIPELINES_YML:-}" && -e "$BACKUP_PIPELINES_YML" ]]; then
        cp -a "$BACKUP_PIPELINES_YML" "$REMOTE_PIPELINES_YML"
    fi

    if [[ -n "${BACKUP_RULES_ZIP:-}" && -e "$BACKUP_RULES_ZIP" ]]; then
        cp -a "$BACKUP_RULES_ZIP" "$REMOTE_RULES_ZIP"
    fi

    if [[ -n "${BACKUP_RULES_DIR:-}" && -d "$BACKUP_RULES_DIR" ]]; then
        rm -rf "$REMOTE_RULES_DIR"
        mv "$BACKUP_RULES_DIR" "$REMOTE_RULES_DIR"
    fi

    if [[ "${SKIP_RESTART}" != "1" ]]; then
        log "Running restart script after rollback."
        restart_logstash "$REMOTE_RESTART_SCRIPT" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT

INCOMING_DIR="$STAGING_DIR/incoming"
BACKUP_ROOT="$REMOTE_LOGSTASH_SETTINGS_DIR/.deploy-backups/$(date +%Y%m%d-%H%M%S)"
RULES_EXTRACT_DIR="$STAGING_DIR/rules-extracted"
NEW_RULES_DIR="$STAGING_DIR/rules-next"

ROLLBACK_NEEDED=0
ORIGINAL_LOGSTASH_PID=""
LOGSTASH_RUN_USER=""
BACKUP_REDIS_STREAMER=""
BACKUP_RULE_MATCHER=""
BACKUP_PIPELINE_CONF=""
BACKUP_BEATS_PIPELINE_CONF=""
BACKUP_PIPELINES_YML=""
BACKUP_RULES_ZIP=""
BACKUP_RULES_DIR=""

if [[ "$DEPLOYMENT_MODE" == "signal" ]]; then
    require_non_empty_file "$INCOMING_DIR/signal_redis_streamer.rb"
    require_non_empty_file "$INCOMING_DIR/signal_rule_matcher.rb"
    require_non_empty_file "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf"
    require_non_empty_file "$INCOMING_DIR/rules.zip"
    require_non_empty_file "$INCOMING_DIR/Beats_Pipeline_135098068173316952064_pl.conf"
    require_file "$INCOMING_DIR/pipelines.yml"
elif [[ "$DEPLOYMENT_MODE" == "kafka" ]]; then
    require_non_empty_file "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf"
else
    fail "Unsupported deployment mode: $DEPLOYMENT_MODE"
fi

command -v pgrep >/dev/null 2>&1 || fail "'pgrep' is required on the remote host."
[[ -x "$REMOTE_LOGSTASH_BIN" ]] || fail "Logstash binary not found or not executable: $REMOTE_LOGSTASH_BIN"
[[ -f "$REMOTE_RESTART_SCRIPT" ]] || fail "Remote restart script not found: $REMOTE_RESTART_SCRIPT"

mkdir -p "$REMOTE_SCRIPTS_DIR" "$(dirname "$REMOTE_PIPELINE_CONF")" "$(dirname "$REMOTE_BEATS_PIPELINE_CONF")" "$(dirname "$REMOTE_PIPELINES_YML")" "$BACKUP_ROOT"

if [[ "$DEPLOYMENT_MODE" == "signal" ]]; then
    command -v unzip >/dev/null 2>&1 || fail "'unzip' is required on the remote host."
    rm -rf "$RULES_EXTRACT_DIR" "$NEW_RULES_DIR"
    mkdir -p "$RULES_EXTRACT_DIR" "$NEW_RULES_DIR"

    log "Unpacking rules zip in remote staging."
    unzip -oq "$INCOMING_DIR/rules.zip" -d "$RULES_EXTRACT_DIR"

    RULES_SOURCE_DIR="$RULES_EXTRACT_DIR"
    if [[ -d "$RULES_EXTRACT_DIR/rules" && -d "$RULES_EXTRACT_DIR/rules/services" ]]; then
        RULES_SOURCE_DIR="$RULES_EXTRACT_DIR/rules"
    fi

    [[ -d "$RULES_SOURCE_DIR/services" ]] || fail "Rules archive does not contain a services directory."
    cp -a "$RULES_SOURCE_DIR"/. "$NEW_RULES_DIR/"
fi

if pgrep -f 'org\.logstash\.Logstash|/usr/share/logstash/bin/logstash' >/dev/null 2>&1; then
    ORIGINAL_LOGSTASH_PID="$(find_logstash_pid)"
    LOGSTASH_RUN_USER="$(ps -o user= -p "$ORIGINAL_LOGSTASH_PID" | awk '{print $1}')"
fi

if [[ -z "$LOGSTASH_RUN_USER" ]]; then
    if id logstash >/dev/null 2>&1; then
        LOGSTASH_RUN_USER="logstash"
    else
        LOGSTASH_RUN_USER="root"
    fi
fi

log "Taking backups before replacement."

if [[ -e "$REMOTE_PIPELINE_CONF" ]]; then
    BACKUP_PIPELINE_CONF="$BACKUP_ROOT/$(basename "$REMOTE_PIPELINE_CONF")"
    cp -a "$REMOTE_PIPELINE_CONF" "$BACKUP_PIPELINE_CONF"
fi

if [[ "$DEPLOYMENT_MODE" == "signal" ]]; then
    if [[ -e "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb" ]]; then
        BACKUP_REDIS_STREAMER="$BACKUP_ROOT/signal_redis_streamer.rb"
        cp -a "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb" "$BACKUP_REDIS_STREAMER"
    fi

    if [[ -e "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb" ]]; then
        BACKUP_RULE_MATCHER="$BACKUP_ROOT/signal_rule_matcher.rb"
        cp -a "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb" "$BACKUP_RULE_MATCHER"
    fi

    if [[ -e "$REMOTE_BEATS_PIPELINE_CONF" ]]; then
        BACKUP_BEATS_PIPELINE_CONF="$BACKUP_ROOT/$(basename "$REMOTE_BEATS_PIPELINE_CONF")"
        cp -a "$REMOTE_BEATS_PIPELINE_CONF" "$BACKUP_BEATS_PIPELINE_CONF"
    fi

    if [[ -e "$REMOTE_PIPELINES_YML" ]]; then
        BACKUP_PIPELINES_YML="$BACKUP_ROOT/$(basename "$REMOTE_PIPELINES_YML")"
        cp -a "$REMOTE_PIPELINES_YML" "$BACKUP_PIPELINES_YML"
    fi

    if [[ -e "$REMOTE_RULES_ZIP" ]]; then
        BACKUP_RULES_ZIP="$BACKUP_ROOT/$(basename "$REMOTE_RULES_ZIP")"
        cp -a "$REMOTE_RULES_ZIP" "$BACKUP_RULES_ZIP"
    fi

    if [[ -d "$REMOTE_RULES_DIR" ]]; then
        BACKUP_RULES_DIR="$BACKUP_ROOT/rules"
        mv "$REMOTE_RULES_DIR" "$BACKUP_RULES_DIR"
    fi
fi

ROLLBACK_NEEDED=1

if [[ "$DEPLOYMENT_MODE" == "signal" ]]; then
    log "Replacing Ruby scripts."
    install -m 0644 "$INCOMING_DIR/signal_redis_streamer.rb" "$REMOTE_SCRIPTS_DIR/.signal_redis_streamer.rb.new"
    mv -f "$REMOTE_SCRIPTS_DIR/.signal_redis_streamer.rb.new" "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb"

    install -m 0644 "$INCOMING_DIR/signal_rule_matcher.rb" "$REMOTE_SCRIPTS_DIR/.signal_rule_matcher.rb.new"
    mv -f "$REMOTE_SCRIPTS_DIR/.signal_rule_matcher.rb.new" "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb"

    if [[ -e "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf" ]]; then
        log "Replacing pipeline config."
        install -m 0644 "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf" "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new"
        mv -f "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new" "$REMOTE_PIPELINE_CONF"
    fi

    if [[ -e "$INCOMING_DIR/Beats_Pipeline_135098068173316952064_pl.conf" ]]; then
        log "Replacing beats pipeline config."
        install -m 0644 "$INCOMING_DIR/Beats_Pipeline_135098068173316952064_pl.conf" "$(dirname "$REMOTE_BEATS_PIPELINE_CONF")/.Beats_Pipeline_135098068173316952064_pl.conf.new"
        mv -f "$(dirname "$REMOTE_BEATS_PIPELINE_CONF")/.Beats_Pipeline_135098068173316952064_pl.conf.new" "$REMOTE_BEATS_PIPELINE_CONF"
    fi

    if [[ -f "$INCOMING_DIR/pipelines.yml" ]]; then
        log "Replacing pipelines.yml."
        install -m 0644 "$INCOMING_DIR/pipelines.yml" "$(dirname "$REMOTE_PIPELINES_YML")/.pipelines.yml.new"
        mv -f "$(dirname "$REMOTE_PIPELINES_YML")/.pipelines.yml.new" "$REMOTE_PIPELINES_YML"
    fi

    log "Replacing rules zip and extracted rules directory."
    install -m 0644 "$INCOMING_DIR/rules.zip" "$(dirname "$REMOTE_RULES_ZIP")/.rules.zip.new"
    mv -f "$(dirname "$REMOTE_RULES_ZIP")/.rules.zip.new" "$REMOTE_RULES_ZIP"
    mv "$NEW_RULES_DIR" "$REMOTE_RULES_DIR"
elif [[ "$DEPLOYMENT_MODE" == "kafka" ]]; then
    log "Replacing Kafka pipeline config."
    install -m 0644 "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf" "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new"
    mv -f "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new" "$REMOTE_PIPELINE_CONF"
    ensure_kafka_truststore
fi

if [[ "$SKIP_RESTART" == "1" ]]; then
    log "Deployment completed without restart because restart was skipped."
    ROLLBACK_NEEDED=0
    exit 0
fi

if [[ -n "$ORIGINAL_LOGSTASH_PID" ]]; then
    log "Current Logstash PID before restart: $ORIGINAL_LOGSTASH_PID."
else
    log "No running Logstash PID found before restart."
fi

log "Running remote restart script: $REMOTE_RESTART_SCRIPT"
restart_logstash "$REMOTE_RESTART_SCRIPT"

NEW_LOGSTASH_PID=""
for _ in $(seq 1 20); do
    NEW_LOGSTASH_PID="$(find_logstash_pid)"
    if [[ -n "$NEW_LOGSTASH_PID" ]]; then
        break
    fi
    sleep 1
done

if [[ -z "$NEW_LOGSTASH_PID" ]]; then
    tail -n 100 "$REMOTE_LOGSTASH_STDOUT" >&2 || true
    fail "Logstash did not appear after running the restart script."
fi

log "Logstash restarted successfully with PID $NEW_LOGSTASH_PID."
ROLLBACK_NEEDED=0
"""


class DeployError(RuntimeError):
    pass


def normalize_exit_code(exit_code: int) -> int:
    if exit_code > 2147483647:
        return exit_code - 4294967296
    return exit_code


def step(message: str) -> None:
    print(f"\n==> {message}")


def info(message: str) -> None:
    print(message)


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def fail(message: str) -> "NoReturn":
    raise DeployError(message)


@dataclass
class DeployConfig:
    remote_host: str = "10.0.4.132"
    user: str = "root"
    port: int = 22
    password: str = ""
    identity_file: str = ""
    deployment_mode: str = "signal"
    zip_mode: str = ""
    strict_host_key_checking: str = "accept-new"
    connect_timeout_seconds: int = 10
    ssh_retries: int = 2
    retry_delay_seconds: int = 2
    use_sudo: bool = True
    skip_restart: bool = False
    keep_remote_staging: bool = False
    remote_scripts_dir: str = "/etc/logstash/scripts"
    remote_rules_dir: str = "/etc/logstash/rules"
    remote_rules_zip: str = "/etc/logstash/rules.zip"
    remote_pipeline_conf: str = "/etc/logstash/conf.d/Linux_Pipeline_135098068173316952064_pl.conf"
    remote_beats_pipeline_conf: str = "/etc/logstash/conf.d/Beats_Pipeline_135098068173316952064_pl.conf"
    remote_pipelines_yml: str = "/etc/logstash/pipelines.yml"
    remote_logstash_settings_dir: str = "/etc/logstash"
    remote_logstash_bin: str = "/usr/share/logstash/bin/logstash"
    remote_logstash_stdout: str = "/var/log/logstash/manual-start.log"
    remote_restart_script: str = "/home/restart_logstash.sh"
    kafka_truststore_location: str = ""
    kafka_truststore_password: str = ""


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def load_config(config_path: Path) -> DeployConfig:
    config = DeployConfig()
    if not config_path.exists():
        return config

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        fail(f"Config file must contain a mapping: {config_path}")

    values = {
        "remote_host": raw.get("remote_host", config.remote_host),
        "user": raw.get("user", config.user),
        "port": int(raw.get("port", config.port)),
        "password": str(raw.get("password", config.password) or ""),
        "identity_file": str(raw.get("identity_file", config.identity_file) or ""),
        "deployment_mode": str(raw.get("deployment_mode", config.deployment_mode) or config.deployment_mode).strip().lower(),
        "zip_mode": str(raw.get("zip_mode", config.zip_mode) or ""),
        "strict_host_key_checking": str(raw.get("strict_host_key_checking", config.strict_host_key_checking) or config.strict_host_key_checking),
        "connect_timeout_seconds": int(raw.get("connect_timeout_seconds", config.connect_timeout_seconds)),
        "ssh_retries": int(raw.get("ssh_retries", config.ssh_retries)),
        "retry_delay_seconds": int(raw.get("retry_delay_seconds", config.retry_delay_seconds)),
        "use_sudo": to_bool(raw.get("use_sudo"), config.use_sudo),
        "skip_restart": to_bool(raw.get("skip_restart"), config.skip_restart),
        "keep_remote_staging": to_bool(raw.get("keep_remote_staging"), config.keep_remote_staging),
        "remote_scripts_dir": str(raw.get("remote_scripts_dir", config.remote_scripts_dir)),
        "remote_rules_dir": str(raw.get("remote_rules_dir", config.remote_rules_dir)),
        "remote_rules_zip": str(raw.get("remote_rules_zip", config.remote_rules_zip)),
        "remote_pipeline_conf": str(raw.get("remote_pipeline_conf", config.remote_pipeline_conf)),
        "remote_beats_pipeline_conf": str(raw.get("remote_beats_pipeline_conf", config.remote_beats_pipeline_conf)),
        "remote_pipelines_yml": str(raw.get("remote_pipelines_yml", config.remote_pipelines_yml)),
        "remote_logstash_settings_dir": str(raw.get("remote_logstash_settings_dir", config.remote_logstash_settings_dir)),
        "remote_logstash_bin": str(raw.get("remote_logstash_bin", config.remote_logstash_bin)),
        "remote_logstash_stdout": str(raw.get("remote_logstash_stdout", config.remote_logstash_stdout)),
        "remote_restart_script": str(raw.get("remote_restart_script", config.remote_restart_script)),
        "kafka_truststore_location": str(raw.get("kafka_truststore_location", config.kafka_truststore_location) or ""),
        "kafka_truststore_password": str(raw.get("kafka_truststore_password", config.kafka_truststore_password) or ""),
    }

    if values["identity_file"] and not Path(values["identity_file"]).is_absolute():
        values["identity_file"] = str((config_path.parent / values["identity_file"]).resolve())

    return DeployConfig(**values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Logstash signalization files to a remote host.")
    parser.add_argument("--config", default="deploy_logstash_signalization.config.yaml", help="Path to YAML config file.")
    parser.add_argument("--mode", choices=["signal", "kafka"], help="Deployment mode to use.")
    parser.add_argument("--zip-mode", choices=["old", "new"], help="Use existing rules.zip or rebuild from log_signalizing/rules.")
    parser.add_argument("--remote-host")
    parser.add_argument("--user")
    parser.add_argument("--port", type=int)
    parser.add_argument("--password")
    parser.add_argument("--identity-file")
    parser.add_argument("--skip-restart", action="store_true")
    parser.add_argument("--keep-remote-staging", action="store_true")
    parser.add_argument("--no-sudo", action="store_true")
    return parser.parse_args()


def apply_overrides(config: DeployConfig, args: argparse.Namespace) -> DeployConfig:
    if args.remote_host:
        config.remote_host = args.remote_host
    if args.user:
        config.user = args.user
    if args.port:
        config.port = args.port
    if args.password is not None:
        config.password = args.password
    if args.identity_file:
        config.identity_file = args.identity_file
    if args.mode:
        config.deployment_mode = args.mode
    if args.zip_mode:
        config.zip_mode = args.zip_mode
    if args.skip_restart:
        config.skip_restart = True
    if args.keep_remote_staging:
        config.keep_remote_staging = True
    if args.no_sudo:
        config.use_sudo = False
    return config


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"Required command not found in PATH: {name}")


def prompt_zip_mode(existing: str) -> str:
    if existing in {"old", "new"}:
        return existing

    while True:
        answer = input("Choose rules zip to deploy [new/old]: ").strip().lower()
        if answer in {"old", "new"}:
            return answer
        warn("Please enter either 'new' or 'old'.")


def prompt_deployment_mode(existing: str) -> str:
    if existing in {"signal", "kafka"}:
        return existing

    while True:
        answer = input("Choose deployment mode [signal/kafka]: ").strip().lower()
        if answer in {"signal", "kafka"}:
            return answer
        warn("Please enter either 'signal' or 'kafka'.")


def create_rules_zip(rules_dir: Path, destination_zip: Path) -> None:
    if not rules_dir.exists():
        fail(f"Signalizing rules directory not found: {rules_dir}")
    if not any(rules_dir.iterdir()):
        fail(f"Signalizing rules directory is empty: {rules_dir}")

    with zipfile.ZipFile(destination_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(rules_dir.rglob("*")):
            if file_path.is_dir():
                continue
            archive_name = Path("rules") / file_path.relative_to(rules_dir)
            archive.write(file_path, archive_name.as_posix())

    if destination_zip.stat().st_size <= 0:
        fail(f"Failed to create rules zip: {destination_zip}")


def create_askpass_helper(staging_dir: Path) -> Path:
    helper_py = staging_dir / "ssh_askpass_helper.py"
    helper_cmd = staging_dir / "ssh_askpass_helper.cmd"

    helper_py.write_text(
        "import os, sys\nsys.stdout.write(os.environ.get('CODEX_DEPLOY_SSH_PASSWORD', ''))\n",
        encoding="ascii",
    )

    python_exe = sys.executable.replace('"', '""')
    helper_cmd.write_text(
        f'@echo off\r\n"{python_exe}" "%~dp0ssh_askpass_helper.py"\r\n',
        encoding="ascii",
    )

    return helper_cmd


def parse_kafka_truststore_details(pipeline_conf: Path) -> tuple[str, str]:
    text = pipeline_conf.read_text(encoding="utf-8")

    location_match = re.search(r'ssl_truststore_location\s*=>\s*"([^"]+)"', text)
    password_match = re.search(r'ssl_truststore_password\s*=>\s*"([^"]+)"', text)

    if not location_match:
        fail(f"Kafka pipeline does not define ssl_truststore_location: {pipeline_conf}")
    if not password_match:
        fail(f"Kafka pipeline does not define ssl_truststore_password: {pipeline_conf}")

    return location_match.group(1).strip(), password_match.group(1)


def build_ssh_base_args(config: DeployConfig, use_password: bool = False) -> list[str]:
    args = [
        "-p",
        str(config.port),
        "-o",
        f"ConnectTimeout={config.connect_timeout_seconds}",
        "-o",
        f"StrictHostKeyChecking={config.strict_host_key_checking}",
    ]
    if config.identity_file:
        args.extend(["-i", config.identity_file])
    if use_password:
        args.extend(
            [
                "-o",
                "PreferredAuthentications=password,keyboard-interactive",
                "-o",
                "PubkeyAuthentication=no",
                "-o",
                "NumberOfPasswordPrompts=1",
            ]
        )
    return args


def build_scp_base_args(config: DeployConfig, use_password: bool = False) -> list[str]:
    args = [
        "-P",
        str(config.port),
        "-o",
        f"ConnectTimeout={config.connect_timeout_seconds}",
        "-o",
        f"StrictHostKeyChecking={config.strict_host_key_checking}",
    ]
    if config.identity_file:
        args.extend(["-i", config.identity_file])
    if use_password:
        args.extend(
            [
                "-o",
                "PreferredAuthentications=password,keyboard-interactive",
                "-o",
                "PubkeyAuthentication=no",
                "-o",
                "NumberOfPasswordPrompts=1",
            ]
        )
    return args


def classify_retryable(stderr: str) -> bool:
    text = stderr.lower()
    retryable_markers = [
        "connection reset",
        "connection timed out",
        "connection closed",
        "connection refused",
        "broken pipe",
        "no route to host",
        "network is unreachable",
        "connection aborted",
    ]
    return any(marker in text for marker in retryable_markers)


def run_process(
    executable: str,
    arguments: list[str],
    *,
    password: str = "",
    askpass_path: Path | None = None,
    retries: int = 1,
    retry_delay_seconds: int = 1,
    quiet_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    automated_password_mode = bool(password and askpass_path)
    if automated_password_mode:
        env["SSH_ASKPASS"] = str(askpass_path)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["DISPLAY"] = "codex"
        env["CODEX_DEPLOY_SSH_PASSWORD"] = password

    attempt = 1
    last_result: subprocess.CompletedProcess[str] | None = None

    while attempt <= max(1, retries):
        if automated_password_mode:
            result = subprocess.run(
                [executable, *arguments],
                text=True,
                capture_output=True,
                env=env,
                stdin=subprocess.DEVNULL,
            )
        else:
            result = subprocess.run(
                [executable, *arguments],
                text=True,
                env=env,
            )
        last_result = result

        normalized_exit_code = normalize_exit_code(result.returncode)

        if normalized_exit_code == 0:
            if result.stdout and result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr and result.stderr.strip() and not quiet_failure:
                warn(result.stderr.strip())
            return result

        retryable = classify_retryable(result.stderr or "")
        if attempt < max(1, retries) and retryable:
            warn(f"{Path(executable).name} failed transiently, retrying in {retry_delay_seconds}s.")
            time.sleep(retry_delay_seconds)
            attempt += 1
            continue

        if result.stdout and result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr and result.stderr.strip() and not quiet_failure:
            warn(result.stderr.strip())

        details: list[str] = []
        if result.stdout and result.stdout.strip():
            details.append(f"stdout:\n{result.stdout.strip()}")
        if result.stderr and result.stderr.strip():
            details.append(f"stderr:\n{result.stderr.strip()}")

        suffix = ""
        if details:
            suffix = "\n\n" + "\n\n".join(details)

        raise DeployError(
            f"Command failed with exit code {normalized_exit_code}: "
            f"{Path(executable).name} {' '.join(arguments)}{suffix}"
        )

    assert last_result is not None
    raise DeployError(f"Command failed: {Path(executable).name} {' '.join(arguments)}")


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def probe_passwordless(target: str, config: DeployConfig) -> bool:
    args = build_ssh_base_args(config, use_password=False)
    args.extend(
        [
            "-o",
            "BatchMode=yes",
            "-o",
            "PreferredAuthentications=publickey",
            target,
            "true",
        ]
    )

    result = subprocess.run(
        ["ssh", *args],
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    return result.returncode == 0


def build_local_payload(
    repo_root: Path,
    local_staging_dir: Path,
    deployment_mode: str,
    zip_mode: str,
) -> tuple[list[Path], Path, dict[str, str]]:
    logstash_dir = repo_root / "logstash_signalization"

    remote_script_path = local_staging_dir / "remote_deploy_logstash.sh"
    remote_script_path.write_text(REMOTE_DEPLOY_SCRIPT, encoding="utf-8", newline="\n")

    if deployment_mode == "signal":
        signalizing_rules_dir = repo_root / "log_signalizing" / "rules"
        redis_streamer = logstash_dir / "signal_redis_streamer.rb"
        rule_matcher = logstash_dir / "signal_rule_matcher.rb"
        pipeline_conf = logstash_dir / "Linux_Pipeline_135098068173316952064_pl.conf"
        beats_pipeline_conf = logstash_dir / "Beats_Pipeline_135098068173316952064_pl.conf"
        pipelines_yml = logstash_dir / "pipelines.yml"
        existing_rules_zip = logstash_dir / "rules.zip"

        for file_path, description in [
            (redis_streamer, "Redis streamer Ruby script"),
            (rule_matcher, "Rule matcher Ruby script"),
            (pipeline_conf, "Pipeline config"),
            (beats_pipeline_conf, "Beats pipeline config"),
        ]:
            if not file_path.exists():
                fail(f"{description} not found: {file_path}")

        if not pipelines_yml.exists():
            fail(f"pipelines.yml not found: {pipelines_yml}")
        if pipelines_yml.stat().st_size <= 0:
            fail(f"pipelines.yml is empty: {pipelines_yml}")

        if zip_mode == "new":
            step("Creating a fresh rules zip from log_signalizing\\rules")
            local_rules_zip = local_staging_dir / "rules.zip"
            create_rules_zip(signalizing_rules_dir, local_rules_zip)
        else:
            step("Using the existing rules zip from logstash_signalization")
            if not existing_rules_zip.exists():
                fail(f"Existing rules zip not found: {existing_rules_zip}")
            local_rules_zip = existing_rules_zip

        payload_files = [
            redis_streamer,
            rule_matcher,
            pipeline_conf,
            beats_pipeline_conf,
            pipelines_yml,
            local_rules_zip,
            remote_script_path,
        ]
        return payload_files, remote_script_path, {}

    if deployment_mode == "kafka":
        kafka_dir = logstash_dir / "kafka_output"
        pipeline_conf = kafka_dir / "Linux_Pipeline_135098068173316952064_pl.conf"
        ca_cert = kafka_dir / "ca-cert"

        for file_path, description in [
            (pipeline_conf, "Kafka pipeline config"),
            (ca_cert, "Kafka CA certificate"),
        ]:
            if not file_path.exists():
                fail(f"{description} not found: {file_path}")
            if file_path.stat().st_size <= 0:
                fail(f"{description} is empty: {file_path}")

        truststore_location, truststore_password = parse_kafka_truststore_details(pipeline_conf)
        payload_files = [
            pipeline_conf,
            ca_cert,
            remote_script_path,
        ]
        return payload_files, remote_script_path, {
            "kafka_truststore_location": truststore_location,
            "kafka_truststore_password": truststore_password,
        }

    fail(f"Unsupported deployment mode: {deployment_mode}")


def deploy() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path

    config = apply_overrides(load_config(config_path), args)
    config.deployment_mode = prompt_deployment_mode(config.deployment_mode)
    zip_mode = prompt_zip_mode(config.zip_mode) if config.deployment_mode == "signal" else "old"

    step("Validating local prerequisites")
    require_command("ssh")
    require_command("scp")

    remote_target = f"{config.user}@{config.remote_host}"

    with tempfile.TemporaryDirectory(prefix="logstash-signalization-deploy-") as staging_text:
        local_staging_dir = Path(staging_text)
        askpass_path: Path | None = None

        payload_files, _, payload_metadata = build_local_payload(
            repo_root,
            local_staging_dir,
            config.deployment_mode,
            zip_mode,
        )

        if config.deployment_mode == "kafka":
            if not config.kafka_truststore_location:
                config.kafka_truststore_location = payload_metadata["kafka_truststore_location"]
            if not config.kafka_truststore_password:
                config.kafka_truststore_password = payload_metadata["kafka_truststore_password"]

        step(f"Preparing remote staging on {config.remote_host}")
        passwordless = probe_passwordless(remote_target, config)
        if passwordless:
            info(f"Passwordless SSH is available for {remote_target}.")
        elif config.password:
            info(f"Using password from config file {config_path} for {remote_target}.")
            askpass_path = create_askpass_helper(local_staging_dir)
        else:
            warn("Passwordless SSH is not available and no password is configured. SSH/SCP may prompt interactively.")

        use_password = bool(config.password and not passwordless)
        ssh_args = build_ssh_base_args(config, use_password=use_password)
        scp_args = build_scp_base_args(config, use_password=use_password)

        remote_staging_dir = f"/tmp/logstash-signalization-deploy-{time.strftime('%Y%m%d-%H%M%S')}"
        remote_incoming_dir = f"{remote_staging_dir}/incoming"
        remote_script_path = f"{remote_staging_dir}/remote_deploy_logstash.sh"

        mkdir_command = f"mkdir -p {shell_quote(remote_incoming_dir)}"
        run_process(
            "ssh",
            [*ssh_args, remote_target, mkdir_command],
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Uploading deployment payload to remote staging")
        scp_target = f"{remote_target}:{remote_incoming_dir}/"
        scp_arguments = [*scp_args, *(str(path) for path in payload_files), scp_target]
        run_process(
            "scp",
            scp_arguments,
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Running remote deployment with staging, backups, replacement, and restart")
        move_command = (
            f"mv {shell_quote(f'{remote_incoming_dir}/remote_deploy_logstash.sh')} {shell_quote(remote_script_path)} "
            f"&& chmod 700 {shell_quote(remote_script_path)}"
        )
        run_process(
            "ssh",
            [*ssh_args, remote_target, move_command],
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        remote_executor = "bash"
        if config.use_sudo and config.user != "root":
            remote_executor = "sudo bash"

        remote_command = " ".join(
            [
                remote_executor,
                shell_quote(remote_script_path),
                shell_quote(remote_staging_dir),
                shell_quote(config.remote_scripts_dir),
                shell_quote(config.remote_rules_dir),
                shell_quote(config.remote_rules_zip),
                shell_quote(config.remote_pipeline_conf),
                shell_quote(config.remote_beats_pipeline_conf),
                shell_quote(config.remote_pipelines_yml),
                shell_quote(config.remote_logstash_settings_dir),
                shell_quote(config.remote_logstash_bin),
                shell_quote(config.remote_logstash_stdout),
                "'1'" if config.skip_restart else "'0'",
                "'1'" if config.keep_remote_staging else "'0'",
                shell_quote(config.remote_restart_script),
                shell_quote(config.deployment_mode),
                shell_quote(config.kafka_truststore_location),
                shell_quote(config.kafka_truststore_password),
            ]
        )

        run_process(
            "ssh",
            [*ssh_args, remote_target, remote_command],
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=1,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Deployment finished successfully")
        zip_mode_display = zip_mode if config.deployment_mode == "signal" else "n/a"
        info(f"Remote host:         {config.remote_host}")
        info(f"Deployment mode:     {config.deployment_mode}")
        info(f"Rules zip mode:      {zip_mode_display}")
        info(f"Remote staging dir:  {remote_staging_dir}")
        info(f"Restart skipped:     {config.skip_restart}")
        info(f"Keep remote staging: {config.keep_remote_staging}")


def main() -> int:
    try:
        deploy()
        return 0
    except KeyboardInterrupt:
        print("\nDeployment cancelled by user.", file=sys.stderr)
        return 130
    except DeployError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
