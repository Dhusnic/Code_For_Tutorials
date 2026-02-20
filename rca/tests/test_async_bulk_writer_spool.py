"""Tests for async bulk writer disk spool fallback and replay."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from src.writer.async_bulk_writer import AsyncBulkWriter


def test_spools_when_queue_is_saturated_and_replays(tmp_path: Path) -> None:
    replay_gate = threading.Event()
    flushed_counter = {"count": 0}

    def slow_flush(_: list[dict[str, object]]) -> None:
        flushed_counter["count"] += 1
        replay_gate.wait(timeout=0.5)

    writer = AsyncBulkWriter(
        flush_fn=slow_flush,
        worker_count=1,
        queue_size=1,
        logger=logging.getLogger("test_async_bulk_writer_spool"),
        autoscaling_enabled=False,
        spool_enabled=True,
        spool_directory=str(tmp_path / "spool"),
        spool_max_bytes=1024 * 1024,
        spool_replay_interval_seconds=0.05,
        queue_enqueue_timeout_seconds=0.01,
    )
    try:
        writer.submit([{"id": 1}])  # type: ignore[list-item]
        time.sleep(0.03)  # let worker consume first batch and block in flush
        writer.submit([{"id": 2}])  # type: ignore[list-item]
        writer.submit([{"id": 3}])  # type: ignore[list-item] expected to spool

        assert writer._spool is not None
        assert writer._spool.has_pending_batches() is True

        replay_gate.set()
        writer.drain()

        assert writer._spool.has_pending_batches() is False
        assert flushed_counter["count"] >= 3
    finally:
        replay_gate.set()
        writer.close()

