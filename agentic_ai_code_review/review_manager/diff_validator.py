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
    VALID_CHANGE_TYPES = {"added", "removed", "modified"}
    CHANGE_TYPE_ALIASES = {
        "add": "added",
        "added": "added",
        "new": "added",
        "remove": "removed",
        "removed": "removed",
        "delete": "removed",
        "deleted": "removed",
        "edit": "modified",
        "modify": "modified",
        "modified": "modified",
        "update": "modified",
    }
    VALID_CATEGORIES = {"critical", "high", "medium", "low"}

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
        normalized_entry["diff"] = self._normalize_diff_fields(dict(diff), index)
        normalized_entry["categories"] = self._normalize_categories(entry.get("categories"))
        normalized_entry["explanation"] = str(entry.get("explanation", "") or "").strip()
        normalized_entry["comments"] = str(entry.get("comments", "") or "").strip()
        return normalized_entry

    def _normalize_diff_fields(self, diff: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Normalize and validate one `diff` object."""
        normalized: Dict[str, Any] = {}

        file_path = str(diff.get("file_path", "") or "").strip().lstrip("/\\")
        if not file_path:
            raise DiffValidationError(f"Diff at index {index} has empty file_path")
        normalized["file_path"] = file_path

        normalized["line_number"] = self._safe_positive_int(
            diff.get("line_number"),
            f"Diff at index {index} has invalid line_number",
        )
        normalized["new_start_line_number"] = self._safe_positive_int(
            diff.get("new_start_line_number"),
            f"Diff at index {index} has invalid new_start_line_number",
        )
        normalized["old_start_line_number"] = self._safe_positive_int(
            diff.get("old_start_line_number"),
            f"Diff at index {index} has invalid old_start_line_number",
        )

        raw_change_type = str(diff.get("change_type", "") or "").strip().lower()
        change_type = self.CHANGE_TYPE_ALIASES.get(raw_change_type, raw_change_type)
        if change_type not in self.VALID_CHANGE_TYPES:
            raise DiffValidationError(
                f"Diff at index {index} has invalid change_type '{raw_change_type}'"
            )
        normalized["change_type"] = change_type

        new_content = str(diff.get("new_content", "") or "")
        old_content = str(diff.get("old_content", "") or "")
        if not new_content.strip() and not old_content.strip():
            raise DiffValidationError(
                f"Diff at index {index} has empty new_content and old_content"
            )
        normalized["new_content"] = new_content
        normalized["old_content"] = old_content

        removed_count = self._safe_non_negative_int(
            diff.get("number_of_lines_removed_from_old"),
            f"Diff at index {index} has invalid number_of_lines_removed_from_old",
        )
        added_count = self._safe_non_negative_int(
            diff.get("number_of_lines_added_in_new"),
            f"Diff at index {index} has invalid number_of_lines_added_in_new",
        )

        inferred_removed = self._content_line_count(old_content)
        inferred_added = self._content_line_count(new_content)
        if change_type != "added" and removed_count == 0 and inferred_removed > 0:
            removed_count = inferred_removed
        if change_type != "removed" and added_count == 0 and inferred_added > 0:
            added_count = inferred_added

        normalized["number_of_lines_removed_from_old"] = removed_count
        normalized["number_of_lines_added_in_new"] = added_count
        return normalized

    def _normalize_categories(self, categories: Any) -> List[str]:
        """Normalize severity categories with stable ordering."""
        if not isinstance(categories, list):
            return ["medium"]

        normalized: List[str] = []
        for value in categories:
            item = str(value or "").strip().lower()
            if item in self.VALID_CATEGORIES and item not in normalized:
                normalized.append(item)

        if not normalized:
            return ["medium"]

        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        normalized.sort(key=lambda item: priority.get(item, 99))
        return normalized

    def _safe_positive_int(self, value: Any, message: str) -> int:
        """Parse positive integer fields."""
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise DiffValidationError(message) from exc
        if parsed <= 0:
            raise DiffValidationError(message)
        return parsed

    def _safe_non_negative_int(self, value: Any, message: str) -> int:
        """Parse non-negative integer fields."""
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise DiffValidationError(message) from exc
        if parsed < 0:
            raise DiffValidationError(message)
        return parsed

    def _content_line_count(self, content: str) -> int:
        """Count logical lines in code block content."""
        text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text:
            return 0
        return len(text.split("\n"))
