"""Shared utility helpers for configuration, JSON extraction, and diff normalization."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

LOGGER = logging.getLogger(__name__)


class CommonUtils:
    """Collection of reusable helper methods used across the review pipeline."""

    class JSONExtractionError(ValueError):
        """Raised when valid JSON cannot be extracted from AI output."""

    class ConfigurationError(RuntimeError):
        """Raised when required runtime configuration cannot be loaded."""

    def get_env_value(
        self,
        env_path: str,
        key: str,
        default: Any = None,
        *,
        required: bool = False,
    ) -> Any:
        """
        Read a key from a `.env` file.

        Args:
            env_path: Path to `.env`.
            key: Variable key to read.
            default: Value to return if key is absent.
            required: Whether absence should raise `ConfigurationError`.

        Returns:
            The value from the env file or `default`.
        """
        try:
            path = Path(env_path).expanduser()
            if not path.exists():
                message = f"Environment file not found: {path}"
                if required:
                    raise self.ConfigurationError(message)
                LOGGER.warning(message)
                return default

            with path.open("r", encoding="utf-8") as env_file:
                for line_number, raw_line in enumerate(env_file, start=1):
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" not in line:
                        raise self.ConfigurationError(
                            f"Malformed .env line {line_number} in {path}: {line}"
                        )

                    parsed_key, parsed_value = line.split("=", 1)
                    if parsed_key.strip() == key:
                        return parsed_value.strip().strip("\"'")
        except Exception as exc:
            LOGGER.exception("Failed to read environment value '%s'", key)
            if isinstance(exc, self.ConfigurationError):
                raise
            raise self.ConfigurationError(
                f"Unable to read environment value '{key}' from {env_path}"
            ) from exc

        if required:
            raise self.ConfigurationError(
                f"Required environment key '{key}' not found in {env_path}"
            )
        return default

    def extract_json_from_ai_output(self, text: str) -> Dict[str, Any]:
        """
        Extract the first valid JSON object from free-form AI output.

        Args:
            text: Raw AI output text.

        Returns:
            Parsed JSON object.
        """
        if not isinstance(text, str) or not text.strip():
            raise self.JSONExtractionError("Empty or invalid AI output")

        candidates = [text.strip()]
        candidates.extend(self._extract_fenced_json_blocks(text))
        candidates.extend(self._extract_brace_candidates(text))

        for candidate in candidates:
            normalized = self._sanitize_invalid_json_escapes(candidate.strip())
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        raise self.JSONExtractionError("No valid JSON object found in AI output")

    def merge_consecutive_diffs(self, diffs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge consecutive diff suggestions targeting adjacent line ranges.

        Args:
            diffs: List of AI generated diff recommendations.

        Returns:
            Merged diff list with contiguous items combined.
        """
        if not diffs:
            return []

        merged: List[Dict[str, Any]] = []
        current = dict(diffs[0])
        current["diff"] = dict(current.get("diff", {}))

        for candidate in diffs[1:]:
            if self._are_consecutive(current, candidate):
                current = self._merge_single_diff(current, candidate)
            else:
                merged.append(current)
                current = dict(candidate)
                current["diff"] = dict(current.get("diff", {}))

        merged.append(current)
        return merged

    def _extract_fenced_json_blocks(self, text: str) -> List[str]:
        """Extract fenced markdown blocks that might contain JSON."""
        pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
        return [block for block in pattern.findall(text) if block.strip()]

    def _extract_brace_candidates(self, text: str) -> List[str]:
        """Extract balanced `{...}` candidates from text."""
        candidates: List[str] = []
        stack: List[str] = []
        start_index: int | None = None
        in_string = False
        escape = False

        for index, char in enumerate(text):
            if char == '"' and not escape:
                in_string = not in_string
            elif not in_string and char == "{":
                if not stack:
                    start_index = index
                stack.append(char)
            elif not in_string and char == "}":
                if stack:
                    stack.pop()
                    if not stack and start_index is not None:
                        candidates.append(text[start_index : index + 1])
                        start_index = None
            escape = char == "\\" and not escape

        return candidates

    def _sanitize_invalid_json_escapes(self, value: str) -> str:
        """
        Normalize invalid escape sequences commonly produced by LLM output.

        Args:
            value: Potential JSON string.

        Returns:
            Sanitized string safe for `json.loads`.
        """
        value = value.strip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1].strip()

        value = value.replace("\\'", "'")
        value = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", value)
        return value

    def _are_consecutive(self, previous: Dict[str, Any], current: Dict[str, Any]) -> bool:
        """Check whether two diff objects can be safely merged."""
        prev_diff = previous.get("diff", {})
        curr_diff = current.get("diff", {})

        same_file = prev_diff.get("file_path") == curr_diff.get("file_path")
        prev_new_start = int(prev_diff.get("new_start_line_number", 0))
        prev_new_count = int(prev_diff.get("number_of_lines_added_in_new", 0))
        curr_new_start = int(curr_diff.get("new_start_line_number", -1))

        prev_old_start = int(prev_diff.get("old_start_line_number", 0))
        prev_old_count = int(prev_diff.get("number_of_lines_removed_from_old", 0))
        curr_old_start = int(curr_diff.get("old_start_line_number", -1))

        return (
            same_file
            and curr_new_start == prev_new_start + max(prev_new_count, 0)
            and curr_old_start == prev_old_start + max(prev_old_count, 0)
        )

    def _merge_single_diff(
        self,
        previous: Dict[str, Any],
        current: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge one candidate diff into the current accumulated diff."""
        merged = dict(previous)
        prev_diff = dict(merged.get("diff", {}))
        curr_diff = dict(current.get("diff", {}))

        prev_diff["number_of_lines_added_in_new"] = int(
            prev_diff.get("number_of_lines_added_in_new", 0)
        ) + int(curr_diff.get("number_of_lines_added_in_new", 0))
        prev_diff["number_of_lines_removed_from_old"] = int(
            prev_diff.get("number_of_lines_removed_from_old", 0)
        ) + int(curr_diff.get("number_of_lines_removed_from_old", 0))

        prev_diff["new_content"] = self._merge_content_blocks(
            prev_diff.get("new_content", ""),
            curr_diff.get("new_content", ""),
        )
        prev_diff["old_content"] = self._merge_content_blocks(
            prev_diff.get("old_content", ""),
            curr_diff.get("old_content", ""),
        )

        merged["diff"] = prev_diff
        merged["categories"] = self._merge_categories(
            previous.get("categories", []),
            current.get("categories", []),
        )
        merged["explanation"] = " ".join(
            segment.strip()
            for segment in [previous.get("explanation", ""), current.get("explanation", "")]
            if segment and segment.strip()
        ).strip()
        merged["comments"] = "\n".join(
            segment.strip()
            for segment in [previous.get("comments", ""), current.get("comments", "")]
            if segment and segment.strip()
        ).strip()
        return merged

    def _merge_content_blocks(self, first: str, second: str) -> str:
        """Join two optional multiline text blocks."""
        first = first or ""
        second = second or ""
        if first and second:
            return f"{first.rstrip()}\n{second.lstrip()}"
        return first or second

    def _merge_categories(self, first: Sequence[str], second: Sequence[str]) -> List[str]:
        """Merge and sort severity categories with deterministic priority."""
        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        unique_values = set(first or []).union(second or [])
        return sorted(unique_values, key=lambda value: priority.get(value, 99))
