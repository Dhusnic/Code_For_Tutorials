#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REMOTE_DEPLOY_SCRIPT = r"""#!/usr/bin/env bash
set -Eeuo pipefail

STAGING_DIR="${1:?missing staging dir}"
REMOTE_DEPLOY_ROOT="${2:?missing remote deploy root}"
REMOTE_BACKUP_ROOT="${3:?missing remote backup root}"
KEEP_STAGING="${4:-0}"
KEEP_BACKUP="${5:-1}"
REBUILD_PROFILE="${6:-direct-stream}"
SKIP_PM2_START="${7:-0}"

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

require_command() {
    local name="$1"
    command -v "$name" >/dev/null 2>&1 || fail "Required command not found: $name"
}

cleanup() {
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        if [[ "$KEEP_STAGING" != "1" && -d "$STAGING_DIR" ]]; then
            rm -rf "$STAGING_DIR"
        fi
        if [[ "$KEEP_BACKUP" != "1" && -n "${BACKUP_PATH:-}" && -d "$BACKUP_PATH" ]]; then
            rm -rf "$BACKUP_PATH"
        fi
        return
    fi

    if [[ "${ROLLBACK_NEEDED:-0}" != "1" ]]; then
        return
    fi

    log "Deployment failed; attempting rollback."
    rm -rf "$REMOTE_DEPLOY_ROOT" || true

    if [[ -n "${BACKUP_PATH:-}" && -d "$BACKUP_PATH" ]]; then
        mv "$BACKUP_PATH" "$REMOTE_DEPLOY_ROOT" || true
        log "Rollback restored previous /opt/rca contents."
    else
        mkdir -p "$REMOTE_DEPLOY_ROOT" || true
        log "Rollback completed with no previous backup to restore."
    fi
}

trap cleanup EXIT

INCOMING_DIR="$STAGING_DIR/incoming"
BUNDLE_ZIP="$INCOMING_DIR/rca_bundle.zip"
BACKUP_PATH=""
ROLLBACK_NEEDED=0
EXTRACT_LIST_FILE="$STAGING_DIR/unzip-list.txt"

require_non_empty_file "$BUNDLE_ZIP"
require_command unzip
require_command bash
require_command chmod
require_command find

if [[ "$SKIP_PM2_START" != "1" ]]; then
    require_command pm2
fi

mkdir -p "$(dirname "$REMOTE_DEPLOY_ROOT")" "$REMOTE_BACKUP_ROOT"

if [[ -d "$REMOTE_DEPLOY_ROOT" ]] && [[ -n "$(find "$REMOTE_DEPLOY_ROOT" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    BACKUP_PATH="$REMOTE_BACKUP_ROOT/rca-$(date +%Y%m%d-%H%M%S)"
    log "Backing up existing deployment to $BACKUP_PATH"
    mv "$REMOTE_DEPLOY_ROOT" "$BACKUP_PATH"
fi

mkdir -p "$REMOTE_DEPLOY_ROOT"
ROLLBACK_NEEDED=1

log "Cleaning remote deployment folder $REMOTE_DEPLOY_ROOT"
find "$REMOTE_DEPLOY_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

log "Unpacking bundle into $REMOTE_DEPLOY_ROOT"
unzip -oq "$BUNDLE_ZIP" -d "$REMOTE_DEPLOY_ROOT"
unzip -Z1 "$BUNDLE_ZIP" >"$EXTRACT_LIST_FILE" || true

[[ -f "$REMOTE_DEPLOY_ROOT/rebuild_all.sh" ]] || fail "Bundle does not contain rebuild_all.sh at deploy root."
[[ -f "$REMOTE_DEPLOY_ROOT/ecosystem.config.js" ]] || fail "Bundle does not contain ecosystem.config.js at deploy root."

log "Fixing executable permissions."
chmod 755 "$REMOTE_DEPLOY_ROOT/rebuild_all.sh"
find "$REMOTE_DEPLOY_ROOT" -type f \( -name "*.sh" -o -path "*/bin/*.exe" \) -exec chmod 755 {} +

log "Running rebuild_all.sh with profile $REBUILD_PROFILE"
(
    cd "$REMOTE_DEPLOY_ROOT"
    bash ./rebuild_all.sh --profile "$REBUILD_PROFILE"
)

if [[ "$SKIP_PM2_START" == "1" ]]; then
    log "Skipping PM2 start because skip flag is enabled."
    ROLLBACK_NEEDED=0
    exit 0
fi

PM2_APPS=(
    "signalizing-engine"
    "log-config-syncer"
    "correlation-engine"
    "log-rca-engine"
)

for app in "${PM2_APPS[@]}"; do
    pm2 delete "$app" >/dev/null 2>&1 || true
done

log "Starting PM2 apps from ecosystem.config.js"
(
    cd "$REMOTE_DEPLOY_ROOT"
    pm2 start ./ecosystem.config.js
)

for app in "${PM2_APPS[@]}"; do
    pm2 describe "$app" >/dev/null 2>&1 || fail "PM2 app did not start correctly: $app"
done

log "PM2 status:"
pm2 status || true

ROLLBACK_NEEDED=0
"""


class DeployError(RuntimeError):
    pass


def step(message: str) -> None:
    print(f"\n==> {message}")


def info(message: str) -> None:
    print(message)


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def fail(message: str) -> "NoReturn":
    raise DeployError(message)


def normalize_exit_code(exit_code: int) -> int:
    if exit_code > 2147483647:
        return exit_code - 4294967296
    return exit_code


@dataclass
class DeployConfig:
    remote_host: str = "10.0.4.132"
    user: str = "root"
    port: int = 22
    password: str = ""
    identity_file: str = ""
    strict_host_key_checking: str = "accept-new"
    connect_timeout_seconds: int = 10
    ssh_retries: int = 2
    retry_delay_seconds: int = 2
    use_sudo: bool = True
    bundle_name: str = "rca_three_engines_bundle"
    package_rebuild: bool = False
    rebuild_profile: str = "direct-stream"
    keep_remote_staging: bool = False
    keep_remote_backup: bool = True
    skip_pm2_start: bool = False
    remote_deploy_root: str = "/opt/rca"
    remote_backup_root: str = "/opt/rca-backups"


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


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def load_config(config_path: Path) -> DeployConfig:
    config = DeployConfig()
    if not config_path.exists():
        return config

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        fail(f"Config file must contain a mapping: {config_path}")

    values = {
        "remote_host": str(raw.get("remote_host", config.remote_host)),
        "user": str(raw.get("user", config.user)),
        "port": int(raw.get("port", config.port)),
        "password": str(raw.get("password", config.password) or ""),
        "identity_file": str(raw.get("identity_file", config.identity_file) or ""),
        "strict_host_key_checking": str(raw.get("strict_host_key_checking", config.strict_host_key_checking) or config.strict_host_key_checking),
        "connect_timeout_seconds": int(raw.get("connect_timeout_seconds", config.connect_timeout_seconds)),
        "ssh_retries": int(raw.get("ssh_retries", config.ssh_retries)),
        "retry_delay_seconds": int(raw.get("retry_delay_seconds", config.retry_delay_seconds)),
        "use_sudo": to_bool(raw.get("use_sudo"), config.use_sudo),
        "bundle_name": str(raw.get("bundle_name", config.bundle_name) or config.bundle_name),
        "package_rebuild": to_bool(raw.get("package_rebuild"), config.package_rebuild),
        "rebuild_profile": str(raw.get("rebuild_profile", config.rebuild_profile) or config.rebuild_profile),
        "keep_remote_staging": to_bool(raw.get("keep_remote_staging"), config.keep_remote_staging),
        "keep_remote_backup": to_bool(raw.get("keep_remote_backup"), config.keep_remote_backup),
        "skip_pm2_start": to_bool(raw.get("skip_pm2_start"), config.skip_pm2_start),
        "remote_deploy_root": str(raw.get("remote_deploy_root", config.remote_deploy_root) or config.remote_deploy_root),
        "remote_backup_root": str(raw.get("remote_backup_root", config.remote_backup_root) or config.remote_backup_root),
    }

    if values["identity_file"] and not Path(values["identity_file"]).is_absolute():
        values["identity_file"] = str((config_path.parent / values["identity_file"]).resolve())

    return DeployConfig(**values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package and deploy the RCA three-engines bundle to a remote Linux host.")
    parser.add_argument("--config", default="deploy_rca_bundle.config.yaml", help="Path to YAML config file.")
    parser.add_argument("--remote-host")
    parser.add_argument("--user")
    parser.add_argument("--port", type=int)
    parser.add_argument("--password")
    parser.add_argument("--identity-file")
    parser.add_argument("--bundle-name")
    parser.add_argument("--package-rebuild", action="store_true")
    parser.add_argument("--rebuild-profile", choices=["direct-stream", "compatibility", "all"])
    parser.add_argument("--keep-remote-staging", action="store_true")
    parser.add_argument("--discard-remote-backup", action="store_true")
    parser.add_argument("--skip-pm2-start", action="store_true")
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
    if args.bundle_name:
        config.bundle_name = args.bundle_name
    if args.package_rebuild:
        config.package_rebuild = True
    if args.rebuild_profile:
        config.rebuild_profile = args.rebuild_profile
    if args.keep_remote_staging:
        config.keep_remote_staging = True
    if args.discard_remote_backup:
        config.keep_remote_backup = False
    if args.skip_pm2_start:
        config.skip_pm2_start = True
    if args.no_sudo:
        config.use_sudo = False
    return config


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"Required command not found in PATH: {name}")


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
    text = (stderr or "").lower()
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


def run_process(
    executable: str,
    arguments: list[str],
    *,
    password: str = "",
    askpass_path: Path | None = None,
    retries: int = 1,
    retry_delay_seconds: int = 1,
    cwd: Path | None = None,
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
    while attempt <= max(1, retries):
        result = subprocess.run(
            [executable, *arguments],
            text=True,
            capture_output=automated_password_mode,
            env=env,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL if automated_password_mode else None,
        )

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
        suffix = "\n\n" + "\n\n".join(details) if details else ""
        raise DeployError(
            f"Command failed with exit code {normalized_exit_code}: "
            f"{Path(executable).name} {' '.join(arguments)}{suffix}"
        )

    raise DeployError(f"Command failed: {Path(executable).name} {' '.join(arguments)}")


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


def package_bundle(repo_root: Path, config: DeployConfig) -> Path:
    package_script = repo_root / "scripts" / "package_three_engines_bundle.ps1"
    if not package_script.exists():
        fail(f"Packaging script not found: {package_script}")

    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if not powershell:
        fail("PowerShell executable not found in PATH.")

    step("Packaging RCA bundle locally")
    command = [
        powershell,
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(package_script),
        "-BundleName",
        config.bundle_name,
    ]
    if config.package_rebuild:
        command.extend(["-Rebuild", "-RebuildProfile", config.rebuild_profile])

    run_process(
        command[0],
        command[1:],
        retries=1,
        retry_delay_seconds=config.retry_delay_seconds,
        cwd=repo_root,
    )

    bundle_zip = repo_root / "dist" / f"{config.bundle_name}.zip"
    if not bundle_zip.exists():
        fail(f"Packaging completed but bundle zip was not found: {bundle_zip}")
    if bundle_zip.stat().st_size <= 0:
        fail(f"Bundle zip is empty: {bundle_zip}")
    normalize_bundle_zip(bundle_zip)
    assert_bundle_contains(bundle_zip, ["ca-cert"])
    return bundle_zip


def normalize_bundle_zip(bundle_zip: Path) -> None:
    normalized_zip = bundle_zip.with_suffix(bundle_zip.suffix + ".normalized")
    saw_backslash_paths = False

    with zipfile.ZipFile(bundle_zip, "r") as source_zip:
        with zipfile.ZipFile(normalized_zip, "w") as target_zip:
            target_zip.comment = source_zip.comment

            for source_info in source_zip.infolist():
                normalized_name = source_info.filename.replace("\\", "/")
                if normalized_name != source_info.filename:
                    saw_backslash_paths = True

                target_info = zipfile.ZipInfo(normalized_name, source_info.date_time)
                target_info.compress_type = source_info.compress_type
                target_info.comment = source_info.comment
                target_info.create_system = 3
                target_info.create_version = source_info.create_version
                target_info.extract_version = source_info.extract_version
                target_info.flag_bits = source_info.flag_bits
                target_info.volume = source_info.volume
                target_info.internal_attr = source_info.internal_attr
                target_info.external_attr = source_info.external_attr

                data = source_zip.read(source_info.filename)
                target_zip.writestr(target_info, data)

    shutil.move(str(normalized_zip), str(bundle_zip))
    if saw_backslash_paths:
        info(f"Normalized Windows-style archive paths in {bundle_zip.name} for Linux unzip compatibility.")


def assert_bundle_contains(bundle_zip: Path, required_entries: list[str]) -> None:
    with zipfile.ZipFile(bundle_zip, "r") as bundle:
        existing_entries = {name.rstrip("/") for name in bundle.namelist()}

    missing_entries = [entry for entry in required_entries if entry not in existing_entries]
    if missing_entries:
        fail(
            "Bundle packaging is incomplete. Missing required bundle entries: "
            + ", ".join(missing_entries)
        )


def deploy() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path

    config = apply_overrides(load_config(config_path), args)

    step("Validating local prerequisites")
    require_command("ssh")
    require_command("scp")

    bundle_zip = package_bundle(repo_root, config)
    remote_target = f"{config.user}@{config.remote_host}"

    with tempfile.TemporaryDirectory(prefix="rca-bundle-deploy-") as staging_text:
        local_staging_dir = Path(staging_text)
        askpass_path: Path | None = None
        remote_script_local = local_staging_dir / "remote_deploy_rca_bundle.sh"
        remote_script_local.write_text(REMOTE_DEPLOY_SCRIPT, encoding="utf-8", newline="\n")

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

        remote_staging_dir = f"/tmp/rca-bundle-deploy-{time.strftime('%Y%m%d-%H%M%S')}"
        remote_incoming_dir = f"{remote_staging_dir}/incoming"
        remote_script_path = f"{remote_staging_dir}/remote_deploy_rca_bundle.sh"

        run_process(
            "ssh",
            [*ssh_args, remote_target, f"mkdir -p {shell_quote(remote_incoming_dir)}"],
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Uploading bundle and remote deploy script")
        scp_target = f"{remote_target}:{remote_incoming_dir}/"
        scp_arguments = [
            *scp_args,
            str(bundle_zip),
            str(remote_script_local),
            scp_target,
        ]
        run_process(
            "scp",
            scp_arguments,
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Finalizing remote payload names")
        finalize_command = " && ".join(
            [
                f"mv {shell_quote(f'{remote_incoming_dir}/{bundle_zip.name}')} {shell_quote(f'{remote_incoming_dir}/rca_bundle.zip')}",
                f"mv {shell_quote(f'{remote_incoming_dir}/{remote_script_local.name}')} {shell_quote(remote_script_path)}",
                f"chmod 700 {shell_quote(remote_script_path)}",
            ]
        )
        run_process(
            "ssh",
            [*ssh_args, remote_target, finalize_command],
            password=config.password if use_password else "",
            askpass_path=askpass_path,
            retries=config.ssh_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )

        step("Running remote bundle deployment")
        remote_executor = "bash"
        if config.use_sudo and config.user != "root":
            remote_executor = "sudo bash"

        remote_command = " ".join(
            [
                remote_executor,
                shell_quote(remote_script_path),
                shell_quote(remote_staging_dir),
                shell_quote(config.remote_deploy_root),
                shell_quote(config.remote_backup_root),
                "'1'" if config.keep_remote_staging else "'0'",
                "'1'" if config.keep_remote_backup else "'0'",
                shell_quote(config.rebuild_profile),
                "'1'" if config.skip_pm2_start else "'0'",
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
        info(f"Bundle zip:          {bundle_zip}")
        info(f"Remote host:         {config.remote_host}")
        info(f"Remote deploy root:  {config.remote_deploy_root}")
        info(f"Remote backup root:  {config.remote_backup_root}")
        info(f"Remote staging dir:  {remote_staging_dir}")
        info(f"Rebuild profile:     {config.rebuild_profile}")
        info(f"PM2 start skipped:   {config.skip_pm2_start}")
        info(f"Keep remote staging: {config.keep_remote_staging}")
        info(f"Keep remote backup:  {config.keep_remote_backup}")


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
