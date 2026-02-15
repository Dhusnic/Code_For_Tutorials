"""Validation helpers for AI-generated diff suggestion payloads."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

LOGGER = logging.getLogger(__name__)


class DiffValidationError(ValueError):
    """Raised when a generated diff payload is invalid."""


class DiffValidator:
    """Validate and normalize AI suggested diff objects."""

    REQUIRED_DIFF_FIELDS = {
        "file_path",
        "line_number",
        "new_start_line_number",
        "change_type",
        "new_content",
        "old_content",
        "old_start_line_number",
        "number_of_lines_removed_from_old",
        "number_of_lines_added_in_new",
    }

    def validate(self, payload: Any) -> List[Dict[str, Any]]:
        """
        Validate generated diff payload.

        Args:
            payload: Parsed JSON from AI output.

        Returns:
            Normalized list of diff objects.
        """
        try:
            if isinstance(payload, dict) and "diffs" in payload:
                payload = payload["diffs"]

            if not isinstance(payload, list):
                raise DiffValidationError("Diff payload must be a list")

            normalized: List[Dict[str, Any]] = []
            for index, entry in enumerate(payload):
                normalized.append(self._validate_entry(entry, index))
            return normalized
        except DiffValidationError:
            raise
        except Exception as exc:
            LOGGER.exception("Unexpected diff validation failure")
            raise DiffValidationError(f"Failed to validate diffs: {exc}") from exc

    def _validate_entry(self, entry: Any, index: int) -> Dict[str, Any]:
        """Validate a single diff entry."""
        if not isinstance(entry, dict):
            raise DiffValidationError(f"Diff at index {index} must be an object")

        diff = entry.get("diff")
        if not isinstance(diff, dict):
            raise DiffValidationError(f"Diff at index {index} missing 'diff' object")

        missing_fields = sorted(self.REQUIRED_DIFF_FIELDS.difference(diff.keys()))
        if missing_fields:
            raise DiffValidationError(
                f"Diff at index {index} missing fields: {', '.join(missing_fields)}"
            )

        normalized_entry = dict(entry)
        normalized_entry["diff"] = dict(diff)
        normalized_entry.setdefault("categories", [])
        normalized_entry.setdefault("explanation", "")
        normalized_entry.setdefault("comments", "")
        return normalized_entry
