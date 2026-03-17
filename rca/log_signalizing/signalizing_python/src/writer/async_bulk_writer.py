"""Concurrent bulk writer with bounded queue for backpressure."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency in runtime environments
    psutil = None  # type: ignore[assignment]

from src.writer.disk_spool import DiskSpoolStore


class AsyncBulkWriter:
    """Process bulk action batches concurrently using worker threads."""

    _SENTINEL = object()

    def __init__(
        self,
        *,
        flush_fn: Callable[[list[dict[str, Any]]], None],
        worker_count: int,
        queue_size: int,
        logger: logging.Logger,
        autoscaling_enabled: bool = False,
        min_worker_count: int = 1,
        max_worker_count: int = 16,
        scale_up_queue_ratio: float = 0.75,
        scale_down_queue_ratio: float = 0.25,
        cpu_limit_percent: float = 85.0,
        memory_limit_percent: float = 85.0,
        autoscale_check_interval_seconds: float = 2.0,
        autoscale_cooldown_seconds: float = 10.0,
        spool_enabled: bool = False,
        spool_directory: str = "state/bulk_spool",
        spool_max_bytes: int = 10 * 1024 * 1024 * 1024,
        spool_replay_interval_seconds: float = 1.0,
        queue_enqueue_timeout_seconds: float = 0.25,
    ) -> None:
        self._flush_fn = flush_fn
        self._queue: queue.Queue[list[dict[str, Any]] | object] = queue.Queue(maxsize=queue_size)
        self._logger = logger
        self._lock = threading.Lock()
        self._first_error: Exception | None = None
        self._closed = False
        self._thread_seq = 0
        self._threads: list[threading.Thread] = []
        self._autoscaler_thread: threading.Thread | None = None
        self._spool_replayer_thread: threading.Thread | None = None
        self._autoscaling_enabled = bool(autoscaling_enabled)
        self._queue_enqueue_timeout_seconds = max(0.0, float(queue_enqueue_timeout_seconds))
        self._spool_replay_interval_seconds = max(0.1, float(spool_replay_interval_seconds))
        self._spool: DiskSpoolStore | None = (
            DiskSpoolStore(
                directory=spool_directory,
                max_bytes=spool_max_bytes,
                logger=self._logger,
            )
            if spool_enabled
            else None
        )
        if self._autoscaling_enabled:
            self._autoscale_min_workers = max(1, int(min_worker_count))
            self._autoscale_max_workers = max(self._autoscale_min_workers, int(max_worker_count))
        else:
            fixed_workers = max(1, int(worker_count))
            self._autoscale_min_workers = fixed_workers
            self._autoscale_max_workers = fixed_workers
        self._autoscale_up_ratio = min(1.0, max(0.0, float(scale_up_queue_ratio)))
        self._autoscale_down_ratio = min(1.0, max(0.0, float(scale_down_queue_ratio)))
        self._cpu_limit_percent = min(100.0, max(1.0, float(cpu_limit_percent)))
        self._memory_limit_percent = min(100.0, max(1.0, float(memory_limit_percent)))
        self._autoscale_check_interval = max(0.2, float(autoscale_check_interval_seconds))
        self._autoscale_cooldown = max(0.0, float(autoscale_cooldown_seconds))
        self._last_scale_at = 0.0

        if self._autoscale_down_ratio > self._autoscale_up_ratio:
            self._logger.warning(
                "bulk autoscale down ratio is above up ratio; swapping values",
                extra={
                    "scale_down_ratio": self._autoscale_down_ratio,
                    "scale_up_ratio": self._autoscale_up_ratio,
                },
            )
            self._autoscale_up_ratio, self._autoscale_down_ratio = (
                self._autoscale_down_ratio,
                self._autoscale_up_ratio,
            )

        initial_workers = max(self._autoscale_min_workers, min(self._autoscale_max_workers, int(worker_count)))
        for _ in range(initial_workers):
            self._start_worker()

        if self._autoscaling_enabled and self._autoscale_max_workers > self._autoscale_min_workers:
            if psutil is None:
                self._logger.warning(
                    "psutil is not installed; bulk autoscaling will ignore CPU/memory guardrails"
                )
            self._autoscaler_thread = threading.Thread(
                target=self._autoscaler_loop,
                name="bulk-writer-autoscaler",
                daemon=True,
            )
            self._autoscaler_thread.start()
            self._logger.info(
                "Bulk writer autoscaling enabled",
                extra={
                    "initial_workers": initial_workers,
                    "min_workers": self._autoscale_min_workers,
                    "max_workers": self._autoscale_max_workers,
                    "scale_up_queue_ratio": self._autoscale_up_ratio,
                    "scale_down_queue_ratio": self._autoscale_down_ratio,
                    "cpu_limit_percent": self._cpu_limit_percent,
                    "memory_limit_percent": self._memory_limit_percent,
                    "check_interval_seconds": self._autoscale_check_interval,
                    "cooldown_seconds": self._autoscale_cooldown,
                },
            )

        if self._spool is not None:
            self._spool_replayer_thread = threading.Thread(
                target=self._spool_replayer_loop,
                name="bulk-writer-spool-replayer",
                daemon=True,
            )
            self._spool_replayer_thread.start()
            self._logger.info(
                "Bulk writer disk spool enabled",
                extra={
                    "spool_directory": str(self._spool.directory),
                    "spool_max_bytes": spool_max_bytes,
                    "spool_replay_interval_seconds": self._spool_replay_interval_seconds,
                    "queue_enqueue_timeout_seconds": self._queue_enqueue_timeout_seconds,
                },
            )

    def submit(self, actions: list[dict[str, Any]]) -> None:
        """Submit one batch, blocking when queue is full (backpressure)."""
        if not actions:
            return
        self._raise_if_failed()
        if self._closed:
            raise RuntimeError("Async bulk writer is already closed")
        payload = list(actions)
        if self._spool is None:
            self._queue.put(payload, block=True)
            self._raise_if_failed()
            return

        try:
            self._queue.put(payload, block=True, timeout=self._queue_enqueue_timeout_seconds)
        except queue.Full:
            self._spool.enqueue_batch(payload)
        self._raise_if_failed()

    def drain(self) -> None:
        """Block until queued batches are fully processed."""
        while True:
            self._queue.join()
            if self._spool is None or not self._spool.has_pending_batches():
                break
            replayed = self._replay_one_spooled_batch(block=True)
            if not replayed:
                break
        self._raise_if_failed()

    def close(self) -> None:
        """Drain and stop worker threads."""
        if self._closed:
            return
        self._closed = True
        if self._autoscaler_thread and self._autoscaler_thread.is_alive():
            self._autoscaler_thread.join(timeout=max(1.0, self._autoscale_check_interval * 2))
        if self._spool_replayer_thread and self._spool_replayer_thread.is_alive():
            self._spool_replayer_thread.join(timeout=max(1.0, self._spool_replay_interval_seconds * 2))
        self.drain()
        for _ in range(self._active_worker_count()):
            self._queue.put(self._SENTINEL, block=True)
        for thread in self._threads:
            thread.join(timeout=5.0)
        self._raise_if_failed()

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._SENTINEL:
                    return
                self._flush_fn(item)  # type: ignore[arg-type]
            except Exception as exc:
                self._record_error(exc)
                self._logger.exception("Async bulk writer worker failed")
            finally:
                self._queue.task_done()

    def _start_worker(self) -> None:
        """Start one new worker thread."""
        idx = self._thread_seq
        self._thread_seq += 1
        thread = threading.Thread(
            target=self._worker_loop,
            name=f"bulk-writer-{idx}",
            daemon=True,
        )
        thread.start()
        self._threads.append(thread)

    def _active_worker_count(self) -> int:
        """Return number of alive worker threads."""
        return sum(1 for thread in self._threads if thread.is_alive())

    def _autoscaler_loop(self) -> None:
        """Continuously evaluate queue pressure and adjust thread count."""
        while not self._closed:
            time.sleep(self._autoscale_check_interval)
            if self._closed:
                return
            try:
                self._autoscale_once()
            except Exception:
                self._logger.exception("Bulk writer autoscaler iteration failed")

    def _autoscale_once(self) -> None:
        """Run one autoscaling decision cycle."""
        now = time.monotonic()
        if now - self._last_scale_at < self._autoscale_cooldown:
            return

        maxsize = self._queue.maxsize
        if maxsize <= 0:
            return
        queue_ratio = self._queue.qsize() / maxsize
        active_workers = self._active_worker_count()

        if queue_ratio >= self._autoscale_up_ratio and active_workers < self._autoscale_max_workers:
            if self._resource_pressure_high():
                self._logger.debug(
                    "Bulk writer scale-up blocked by resource guardrail",
                    extra={
                        "queue_ratio": queue_ratio,
                        "active_workers": active_workers,
                        "max_workers": self._autoscale_max_workers,
                    },
                )
                return
            self._start_worker()
            self._last_scale_at = now
            self._logger.info(
                "Bulk writer scaled up",
                extra={
                    "queue_ratio": queue_ratio,
                    "active_workers": self._active_worker_count(),
                    "max_workers": self._autoscale_max_workers,
                },
            )
            return

        if queue_ratio <= self._autoscale_down_ratio and active_workers > self._autoscale_min_workers:
            try:
                self._queue.put_nowait(self._SENTINEL)
            except queue.Full:
                return
            self._last_scale_at = now
            self._logger.info(
                "Bulk writer scaled down",
                extra={
                    "queue_ratio": queue_ratio,
                    "active_workers_before": active_workers,
                    "min_workers": self._autoscale_min_workers,
                },
            )

    def _spool_replayer_loop(self) -> None:
        """Continuously try replaying spooled batches back into memory queue."""
        while not self._closed:
            try:
                replayed = self._replay_one_spooled_batch(block=False)
                if not replayed:
                    time.sleep(self._spool_replay_interval_seconds)
            except Exception:
                self._logger.exception("Disk spool replay iteration failed")
                time.sleep(self._spool_replay_interval_seconds)

    def _replay_one_spooled_batch(self, *, block: bool) -> bool:
        """Replay one spooled batch into queue; return True when batch was queued."""
        if self._spool is None:
            return False
        if not self._spool.has_pending_batches():
            return False

        batch = self._spool.dequeue_oldest_batch()
        if not batch:
            return False

        try:
            if block:
                self._queue.put(batch, block=True)
            else:
                self._queue.put(
                    batch,
                    block=True,
                    timeout=self._queue_enqueue_timeout_seconds,
                )
        except queue.Full:
            # Queue still saturated; return batch to spool for later replay.
            self._spool.enqueue_batch(batch)
            return False

        self._logger.debug(
            "Replayed spooled bulk batch",
            extra={
                "batch_actions": len(batch),
                "spool_pending_bytes": self._spool.pending_bytes(),
            },
        )
        return True

    def _resource_pressure_high(self) -> bool:
        """Return True when CPU or memory usage exceeds autoscale guardrails."""
        if psutil is None:
            return False
        try:
            cpu_percent = float(psutil.cpu_percent(interval=None))
            memory_percent = float(psutil.virtual_memory().percent)
        except Exception:
            self._logger.warning("Failed sampling system resources for bulk autoscaling", exc_info=True)
            return False
        return cpu_percent >= self._cpu_limit_percent or memory_percent >= self._memory_limit_percent

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            if self._first_error is None:
                self._first_error = exc

    def _raise_if_failed(self) -> None:
        with self._lock:
            error = self._first_error
        if error is not None:
            raise RuntimeError("Async bulk writer failed") from error
