"""Tests for BatchReader query construction and pagination behavior."""

from __future__ import annotations

from typing import Any

from src.ingestion.batch_reader import BatchReader


class _StubClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body})
        return self._responses.pop(0)


def test_uses_configured_index_and_stable_sort() -> None:
    client = _StubClient([{"hits": {"hits": []}}])
    reader = BatchReader(
        client=client,  # type: ignore[arg-type]
        index="linux-*",
        batch_size=250,
        timestamp_field="@timestamp",
        start_time="now-15m",
    )

    list(reader.iter_hits())

    assert client.calls[0]["index"] == "linux-*"
    assert client.calls[0]["body"]["sort"] == [
        {"@timestamp": {"order": "asc"}},
        {"_shard_doc": {"order": "asc"}},
    ]
    assert client.calls[0]["body"]["track_total_hits"] is False


def test_ignores_legacy_single_value_checkpoint_sort() -> None:
    client = _StubClient([{"hits": {"hits": []}}])
    reader = BatchReader(
        client=client,  # type: ignore[arg-type]
        index="linux-*",
        batch_size=250,
        timestamp_field="@timestamp",
        start_time="now-15m",
    )

    list(reader.iter_hits(checkpoint_sort=["2026-02-18T00:00:00Z"]))

    assert "search_after" not in client.calls[0]["body"]
