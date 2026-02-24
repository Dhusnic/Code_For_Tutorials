"""Batch action accumulator with both count and byte-size limits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BatcherStats:
    """Runtime stats for one action batcher instance."""

    flushed_batches: int = 0
    flushed_actions: int = 0
    flushed_bytes: int = 0


class ActionBatcher:
    """Accumulate actions and flush when count or byte threshold is reached."""

    def __init__(self, *, max_actions: int, max_bytes: int) -> None:
        self._max_actions = max(1, int(max_actions))
        self._max_bytes = max(1, int(max_bytes))
        self._actions: list[dict[str, Any]] = []
        self._bytes = 0
        self._stats = BatcherStats()

    @property
    def stats(self) -> BatcherStats:
        """Return batcher flush statistics."""
        return self._stats

    def add(self, action: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Add one action and flush current batch when limits are exceeded."""
        action_size = self._estimate_action_size(action)

        should_flush_before_add = bool(
            self._actions
            and (
                len(self._actions) >= self._max_actions
                or self._bytes + action_size > self._max_bytes
            )
        )
        if should_flush_before_add:
            flushed = self._flush_internal()
            self._actions.append(action)
            self._bytes += action_size
            return flushed

        self._actions.append(action)
        self._bytes += action_size

        if len(self._actions) >= self._max_actions or self._bytes >= self._max_bytes:
            return self._flush_internal()
        return None

    def flush_remaining(self) -> list[dict[str, Any]] | None:
        """Flush and return remaining in-memory actions, if any."""
        if not self._actions:
            return None
        return self._flush_internal()

    def _flush_internal(self) -> list[dict[str, Any]]:
        actions = self._actions
        bytes_size = self._bytes
        self._actions = []
        self._bytes = 0

        self._stats.flushed_batches += 1
        self._stats.flushed_actions += len(actions)
        self._stats.flushed_bytes += bytes_size
        return actions

    @staticmethod
    def _estimate_action_size(action: dict[str, Any]) -> int:
        """Estimate action size in bytes for batch sizing decisions."""
        try:
            encoded = json.dumps(
                action,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
            return len(encoded)
        except Exception:
            # Conservative fallback when JSON serialization fails unexpectedly.
            return len(str(action).encode("utf-8"))

