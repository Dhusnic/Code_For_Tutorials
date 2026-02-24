"""Tests for async bulk writer autoscaling behavior."""

from __future__ import annotations

import logging
import threading
import time

from src.writer.async_bulk_writer import AsyncBulkWriter


def _wait_until(predicate, timeout_seconds: float = 1.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_autoscale_scales_up_on_high_queue_pressure() -> None:
    release_flush = threading.Event()

    def slow_flush(_: list[dict[str, object]]) -> None:
        release_flush.wait(timeout=0.5)

    writer = AsyncBulkWriter(
        flush_fn=slow_flush,
        worker_count=1,
        queue_size=8,
        logger=logging.getLogger("test_async_bulk_writer_autoscaling"),
        autoscaling_enabled=False,
        min_worker_count=1,
        max_worker_count=3,
        scale_up_queue_ratio=0.5,
        scale_down_queue_ratio=0.1,
        autoscale_cooldown_seconds=0.0,
    )
    try:
        for _ in range(6):
            writer.submit([{"k": "v"}])  # type: ignore[list-item]
        before = writer._active_worker_count()
        writer._autoscale_max_workers = 3
        writer._autoscale_min_workers = 1
        writer._resource_pressure_high = lambda: False  # type: ignore[method-assign]

        writer._autoscale_once()

        assert _wait_until(lambda: writer._active_worker_count() > before)
    finally:
        release_flush.set()
        writer.close()


def test_autoscale_respects_resource_guardrail_on_scale_up() -> None:
    release_flush = threading.Event()

    def slow_flush(_: list[dict[str, object]]) -> None:
        release_flush.wait(timeout=0.5)

    writer = AsyncBulkWriter(
        flush_fn=slow_flush,
        worker_count=1,
        queue_size=8,
        logger=logging.getLogger("test_async_bulk_writer_autoscaling"),
        autoscaling_enabled=False,
        min_worker_count=1,
        max_worker_count=3,
        scale_up_queue_ratio=0.5,
        scale_down_queue_ratio=0.1,
        autoscale_cooldown_seconds=0.0,
    )
    try:
        for _ in range(6):
            writer.submit([{"k": "v"}])  # type: ignore[list-item]
        before = writer._active_worker_count()
        writer._autoscale_max_workers = 3
        writer._autoscale_min_workers = 1
        writer._resource_pressure_high = lambda: True  # type: ignore[method-assign]

        writer._autoscale_once()
        time.sleep(0.1)

        assert writer._active_worker_count() == before
    finally:
        release_flush.set()
        writer.close()


def test_autoscale_scales_down_on_low_queue_pressure() -> None:
    writer = AsyncBulkWriter(
        flush_fn=lambda _: None,
        worker_count=2,
        queue_size=8,
        logger=logging.getLogger("test_async_bulk_writer_autoscaling"),
        autoscaling_enabled=False,
        min_worker_count=1,
        max_worker_count=3,
        scale_up_queue_ratio=0.75,
        scale_down_queue_ratio=0.5,
        autoscale_cooldown_seconds=0.0,
    )
    try:
        writer._autoscale_max_workers = 3
        writer._autoscale_min_workers = 1
        writer._resource_pressure_high = lambda: False  # type: ignore[method-assign]
        assert _wait_until(lambda: writer._active_worker_count() >= 2)

        writer._autoscale_once()

        assert _wait_until(lambda: writer._active_worker_count() == 1)
    finally:
        writer.close()

