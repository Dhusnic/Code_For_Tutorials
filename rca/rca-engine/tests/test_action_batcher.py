"""Tests for action batching with count and byte limits."""

from __future__ import annotations

from src.writer.action_batcher import ActionBatcher


def test_flushes_on_action_count_limit() -> None:
    batcher = ActionBatcher(max_actions=2, max_bytes=10_000)

    assert batcher.add({"a": 1}) is None
    flushed = batcher.add({"b": 2})

    assert flushed is not None
    assert len(flushed) == 2
    assert batcher.flush_remaining() is None


def test_flushes_on_byte_limit() -> None:
    batcher = ActionBatcher(max_actions=100, max_bytes=80)

    assert batcher.add({"message": "x" * 30}) is None
    flushed = batcher.add({"message": "y" * 40})

    assert flushed is not None
    assert len(flushed) == 1

    remaining = batcher.flush_remaining()
    assert remaining is not None
    assert len(remaining) == 1

