"""Concurrent bulk writer with bounded queue for backpressure."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable


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
    ) -> None:
        self._flush_fn = flush_fn
        self._queue: queue.Queue[list[dict[str, Any]] | object] = queue.Queue(maxsize=queue_size)
        self._logger = logger
        self._lock = threading.Lock()
        self._first_error: Exception | None = None
        self._closed = False
        self._threads: list[threading.Thread] = []

        for idx in range(worker_count):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"bulk-writer-{idx}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def submit(self, actions: list[dict[str, Any]]) -> None:
        """Submit one batch, blocking when queue is full (backpressure)."""
        if not actions:
            return
        self._raise_if_failed()
        if self._closed:
            raise RuntimeError("Async bulk writer is already closed")
        self._queue.put(list(actions), block=True)
        self._raise_if_failed()

    def drain(self) -> None:
        """Block until queued batches are fully processed."""
        self._queue.join()
        self._raise_if_failed()

    def close(self) -> None:
        """Drain and stop worker threads."""
        if self._closed:
            return
        self.drain()
        self._closed = True
        for _ in self._threads:
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

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            if self._first_error is None:
                self._first_error = exc

    def _raise_if_failed(self) -> None:
        with self._lock:
            error = self._first_error
        if error is not None:
            raise RuntimeError("Async bulk writer failed") from error
