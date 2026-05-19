#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class WorkerSummary:
    worker_id: str
    signal_logs_read: int = 0
    cycle_count: int = 0
    active_cycle_count: int = 0
    owned_signal_load: int = 0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_log_path() -> Path:
    return repo_root() / "log_correlation_engine" / "logs" / "correlation-engine.out.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize recent correlation-engine worker load split from JSON logs."
        )
    )
    parser.add_argument(
        "--log-file",
        default=str(default_log_path()),
        help="Path to correlation-engine.out.log.",
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=2,
        help="How far back to inspect correlation cycle completions.",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=30000,
        help="How many lines to scan from the end of the log file.",
    )
    parser.add_argument(
        "--show-empty-workers",
        action="store_true",
        help="Show worker ids 0-9 even if they did not appear in the lookback window.",
    )
    return parser.parse_args()


def parse_timestamp(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def tail_lines(path: Path, count: int) -> list[str]:
    if count <= 0:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return [line.rstrip("\r\n") for line in lines[-count:]]


def summarize_log(lines: list[str], cutoff: datetime) -> dict[str, WorkerSummary]:
    summaries: dict[str, WorkerSummary] = {}
    for line in lines:
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if payload.get("msg") != "correlation cycle completed":
            continue

        timestamp = parse_timestamp(payload.get("time"))
        if timestamp is None or timestamp < cutoff:
            continue

        worker_id = str(payload.get("worker_id") or "").strip()
        if not worker_id:
            continue

        summary = summaries.setdefault(worker_id, WorkerSummary(worker_id=worker_id))
        signal_logs_read = int(payload.get("signal_logs_read") or 0)
        owned_signal_load = int(payload.get("owned_signal_load") or 0)

        summary.cycle_count += 1
        summary.signal_logs_read += signal_logs_read
        if signal_logs_read > 0:
            summary.active_cycle_count += 1
        summary.owned_signal_load = owned_signal_load
    return summaries


def render_summary(summaries: dict[str, WorkerSummary], lookback: timedelta) -> str:
    ordered = sorted(summaries.values(), key=lambda item: sort_worker_id(item.worker_id))
    total_logs = sum(item.signal_logs_read for item in ordered)

    lines = [f"Current load split for the last ~{humanize_lookback(lookback)}:", ""]
    for item in ordered:
        percent = (item.signal_logs_read * 100.0 / total_logs) if total_logs > 0 else 0.0
        lines.append(
            f"Worker {item.worker_id}: "
            f"{item.signal_logs_read:,} logs, "
            f"{percent:.2f}%, "
            f"owned_signal_load={item.owned_signal_load}"
        )
    if len(lines) == 2:
        lines.append("No recent correlation cycle completions were found in the lookback window.")
    return "\n".join(lines)


def sort_worker_id(worker_id: str) -> tuple[int, str]:
    try:
        return (0, f"{int(worker_id):08d}")
    except ValueError:
        return (1, worker_id)


def humanize_lookback(lookback: timedelta) -> str:
    total_minutes = int(round(lookback.total_seconds() / 60))
    if total_minutes == 1:
        return "1 minute"
    return f"{total_minutes} minutes"


def inject_default_workers(summaries: dict[str, WorkerSummary]) -> dict[str, WorkerSummary]:
    result = dict(summaries)
    for worker_id in map(str, range(10)):
        result.setdefault(worker_id, WorkerSummary(worker_id=worker_id))
    return result


def main() -> int:
    args = parse_args()
    log_file = Path(args.log_file).expanduser().resolve()
    if not log_file.exists():
        print(f"Error: log file not found: {log_file}")
        return 1

    lookback = timedelta(minutes=max(int(args.lookback_minutes), 1))
    cutoff = datetime.now(timezone.utc) - lookback
    lines = tail_lines(log_file, max(int(args.tail_lines), 0))
    summaries = summarize_log(lines, cutoff)
    if args.show_empty_workers:
        summaries = inject_default_workers(summaries)

    print(render_summary(summaries, lookback))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
