#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ProcessSample:
    name: str
    pm_id: int
    pid: int
    status: str
    cpu_percent: float
    memory_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor CPU and RAM usage for all PM2 services on Linux."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Refresh interval in seconds when running in watch mode.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously refresh the PM2 resource view.",
    )
    parser.add_argument(
        "--show-instances",
        action="store_true",
        help="Also print per-instance rows under the app summary.",
    )
    parser.add_argument(
        "--csv",
        default="",
        help="Optional CSV file path to append raw samples.",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear the terminal between refreshes in watch mode.",
    )
    return parser.parse_args()


def run_pm2_jlist() -> list[dict]:
    pm2_path = shutil.which("pm2")
    if not pm2_path:
        raise RuntimeError("pm2 command not found in PATH.")

    result = subprocess.run(
        [pm2_path, "jlist"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"pm2 jlist failed: {stderr or 'unknown error'}")

    stdout = (result.stdout or "").strip()
    if not stdout:
        return []

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pm2 jlist returned invalid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise RuntimeError("pm2 jlist returned an unexpected payload shape.")
    return payload


def collect_samples(raw_processes: list[dict]) -> list[ProcessSample]:
    samples: list[ProcessSample] = []
    for entry in raw_processes:
        monit = entry.get("monit") or {}
        pm2_env = entry.get("pm2_env") or {}
        sample = ProcessSample(
            name=str(entry.get("name") or pm2_env.get("name") or "unknown"),
            pm_id=int(entry.get("pm_id") or 0),
            pid=int(entry.get("pid") or 0),
            status=str(pm2_env.get("status") or "unknown"),
            cpu_percent=float(monit.get("cpu") or 0.0),
            memory_bytes=int(monit.get("memory") or 0),
        )
        samples.append(sample)
    samples.sort(key=lambda item: (item.name.lower(), item.pm_id))
    return samples


def format_bytes(num_bytes: int) -> str:
    value = float(max(num_bytes, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def aggregate_by_name(samples: list[ProcessSample]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for sample in samples:
        bucket = grouped.setdefault(
            sample.name,
            {
                "name": sample.name,
                "instances": 0,
                "online": 0,
                "cpu_percent": 0.0,
                "memory_bytes": 0,
                "pm_ids": [],
                "statuses": set(),
            },
        )
        bucket["instances"] += 1
        if sample.status == "online":
            bucket["online"] += 1
        bucket["cpu_percent"] += sample.cpu_percent
        bucket["memory_bytes"] += sample.memory_bytes
        bucket["pm_ids"].append(sample.pm_id)
        bucket["statuses"].add(sample.status)
    rows = list(grouped.values())
    rows.sort(key=lambda item: item["name"].lower())
    return rows


def print_summary(samples: list[ProcessSample], show_instances: bool) -> None:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    app_rows = aggregate_by_name(samples)
    total_cpu = sum(sample.cpu_percent for sample in samples)
    total_memory = sum(sample.memory_bytes for sample in samples)
    total_online = sum(1 for sample in samples if sample.status == "online")

    print(f"PM2 Resource Monitor  {timestamp}")
    print("=" * 92)
    print(
        f"Apps: {len(app_rows)}  Instances: {len(samples)}  Online: {total_online}  "
        f"Total CPU: {total_cpu:.1f}%  Total RAM: {format_bytes(total_memory)}"
    )
    print("-" * 92)
    print(f"{'APP':<28} {'ONLINE':<8} {'CPU %':>8} {'RAM':>12} {'PM2 IDS':<28}")
    print("-" * 92)
    for row in app_rows:
        ids = ",".join(str(pm_id) for pm_id in row["pm_ids"])
        online_text = f"{row['online']}/{row['instances']}"
        print(
            f"{row['name']:<28} {online_text:<8} "
            f"{row['cpu_percent']:>8.1f} {format_bytes(row['memory_bytes']):>12} {ids:<28}"
        )

    if show_instances:
        print("-" * 92)
        print(f"{'APP':<28} {'PM2 ID':>6} {'PID':>8} {'STATUS':<12} {'CPU %':>8} {'RAM':>12}")
        print("-" * 92)
        for sample in samples:
            print(
                f"{sample.name:<28} {sample.pm_id:>6} {sample.pid:>8} {sample.status:<12} "
                f"{sample.cpu_percent:>8.1f} {format_bytes(sample.memory_bytes):>12}"
            )


def append_csv(csv_path: Path, samples: list[ProcessSample]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    timestamp = datetime.now(timezone.utc).isoformat()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if not file_exists:
            writer.writerow(
                [
                    "timestamp_utc",
                    "app_name",
                    "pm_id",
                    "pid",
                    "status",
                    "cpu_percent",
                    "memory_bytes",
                    "memory_mb",
                ]
            )
        for sample in samples:
            writer.writerow(
                [
                    timestamp,
                    sample.name,
                    sample.pm_id,
                    sample.pid,
                    sample.status,
                    f"{sample.cpu_percent:.2f}",
                    sample.memory_bytes,
                    f"{sample.memory_bytes / (1024 * 1024):.2f}",
                ]
            )


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than 0")

    csv_path = Path(args.csv).expanduser() if args.csv else None

    try:
        while True:
            raw_processes = run_pm2_jlist()
            samples = collect_samples(raw_processes)

            if args.watch and not args.no_clear:
                clear_screen()

            if not samples:
                print("No PM2 services found.")
            else:
                print_summary(samples, args.show_instances)
                if csv_path is not None:
                    append_csv(csv_path, samples)
                    print("-" * 92)
                    print(f"CSV appended: {csv_path}")

            if not args.watch:
                return 0

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
