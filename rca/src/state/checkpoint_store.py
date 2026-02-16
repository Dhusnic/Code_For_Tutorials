"""Checkpoint persistence for per-service and per-index pagination state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CheckpointStore:
    """Persist and retrieve search_after sort values."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, service: str, index: str) -> list[Any] | None:
        """Load checkpoint sort array for the service/index pair."""
        state = self._read()
        return state.get(self._key(service, index))

    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        """Save checkpoint sort array for the service/index pair."""
        state = self._read()
        state[self._key(service, index)] = sort_values
        self._write(state)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _key(service: str, index: str) -> str:
        return f"{service}::{index}"
