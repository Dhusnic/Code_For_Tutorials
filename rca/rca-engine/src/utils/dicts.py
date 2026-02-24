"""Dictionary helper functions."""

from __future__ import annotations

from typing import Any


def get_nested(data: dict[str, Any], field_path: str) -> Any:
    """Return nested field value using dot notation, or None if missing."""
    current: Any = data
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
