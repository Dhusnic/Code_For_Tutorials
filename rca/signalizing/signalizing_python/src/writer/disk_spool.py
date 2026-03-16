"""Disk-backed spool for bulk batches when in-memory queue is saturated."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class DiskSpoolStore:
    """Persist queued bulk batches to disk and replay later."""

    def __init__(self, *, directory: str, max_bytes: int, logger: logging.Logger) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max(1, int(max_bytes))
        self._logger = logger
        self._lock = threading.Lock()
        self._current_bytes = self._scan_current_bytes()

    @property
    def directory(self) -> Path:
        """Return on-disk spool directory path."""
        return self._directory

    def enqueue_batch(self, actions: list[dict[str, Any]]) -> None:
        """Persist one action batch to disk using atomic file move."""
        payload = self._encode_batch(actions)
        payload_size = len(payload)
        ready_name = self._build_file_name()
        ready_path = self._directory / ready_name
        tmp_path = ready_path.with_suffix(".tmp")

        with self._lock:
            next_total = self._current_bytes + payload_size
            if next_total > self._max_bytes:
                raise RuntimeError(
                    "Disk spool capacity exceeded; increase bulk_spool_max_bytes or improve drain throughput"
                )

            with tmp_path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(ready_path)
            self._current_bytes = next_total

        self._logger.warning(
            "Bulk batch spooled to disk",
            extra={
                "spool_file": str(ready_path),
                "spool_batch_actions": len(actions),
                "spool_file_bytes": payload_size,
                "spool_total_bytes": self._current_bytes,
                "spool_max_bytes": self._max_bytes,
            },
        )

    def dequeue_oldest_batch(self) -> list[dict[str, Any]] | None:
        """Load and remove the oldest ready spool file, if present."""
        with self._lock:
            files = self._ready_files()
            if not files:
                return None
            path = files[0]
            size = path.stat().st_size
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self._logger.exception(
                    "Failed reading spooled batch; removing corrupt file",
                    extra={"spool_file": str(path)},
                )
                path.unlink(missing_ok=True)
                self._current_bytes = max(0, self._current_bytes - size)
                return None

            path.unlink(missing_ok=True)
            self._current_bytes = max(0, self._current_bytes - size)

        if not isinstance(payload, list):
            self._logger.warning(
                "Spooled batch payload has invalid shape; dropping",
                extra={"spool_file": str(path)},
            )
            return None
        return payload

    def has_pending_batches(self) -> bool:
        """Return True when spool has at least one ready batch."""
        with self._lock:
            return bool(self._ready_files())

    def pending_bytes(self) -> int:
        """Return total bytes currently occupied by ready spool files."""
        with self._lock:
            return self._current_bytes

    def _scan_current_bytes(self) -> int:
        return sum(path.stat().st_size for path in self._ready_files())

    def _ready_files(self) -> list[Path]:
        return sorted(self._directory.glob("*.json"))

    @staticmethod
    def _encode_batch(actions: list[dict[str, Any]]) -> bytes:
        return json.dumps(
            actions,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

    @staticmethod
    def _build_file_name() -> str:
        timestamp = time.time_ns()
        random = uuid.uuid4().hex[:8]
        return f"{timestamp}-{random}.json"
