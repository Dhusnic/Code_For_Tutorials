"""Tests for disk spool persistence and replay behavior."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.writer.disk_spool import DiskSpoolStore


def test_spool_enqueue_and_dequeue_roundtrip(tmp_path: Path) -> None:
    spool = DiskSpoolStore(
        directory=str(tmp_path / "spool"),
        max_bytes=1024 * 1024,
        logger=logging.getLogger("test_disk_spool"),
    )
    batch = [{"_index": "a", "_id": "1", "doc": {"k": "v"}}]

    spool.enqueue_batch(batch)
    assert spool.has_pending_batches() is True
    assert spool.pending_bytes() > 0

    loaded = spool.dequeue_oldest_batch()
    assert loaded == batch
    assert spool.has_pending_batches() is False
    assert spool.pending_bytes() == 0


def test_spool_respects_capacity_limit(tmp_path: Path) -> None:
    spool = DiskSpoolStore(
        directory=str(tmp_path / "spool"),
        max_bytes=32,
        logger=logging.getLogger("test_disk_spool"),
    )

    with pytest.raises(RuntimeError):
        spool.enqueue_batch([{"big": "x" * 100}])

