"""Utilities to safely apply generated code patches to repository files."""

from __future__ import annotations

import ast
import difflib
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatchApplyRequest:
    """Input payload for applying a generated patch block."""

    repo_path: str
    file_path: str
    old_start_line_number: int
    number_of_lines_removed_from_old: int
    new_content: str
    old_content: str = ""
    allow_fallback_search: bool = True


class PatchApplier:
    """Apply line-accurate patches with strict content checks and rollback safety."""

    SEARCH_WINDOW_LINES = 5_000
    SIMILARITY_SEARCH_WINDOW_LINES = 400
    MIN_SIMILARITY_RATIO = 0.82

    def apply_change(self, request: PatchApplyRequest) -> Dict[str, str | bool | int]:
        """
        Apply a patch by replacing a specific line range.

        Returns:
            Operation result with status and metadata.
        """
        try:
            file_path = self._resolve_file_path(request.repo_path, request.file_path)
            if not file_path.exists():
                return {"success": False, "message": f"File not found: {file_path}"}
            if not file_path.is_file():
                return {"success": False, "message": f"Target is not a file: {file_path}"}

            original_text = file_path.read_text(encoding="utf-8")
            newline_style = self._detect_newline_style(original_text)
            line_offsets = self._build_line_offsets(original_text)
            total_lines = len(line_offsets) - 1

            requested_start = int(request.old_start_line_number)
            removed_count = max(int(request.number_of_lines_removed_from_old), 0)
            if requested_start < 1:
                return {"success": False, "message": "old_start_line_number must be >= 1"}

            initial_bounds = self._line_range_to_char_bounds(
                line_offsets=line_offsets,
                start_line=requested_start,
                removed_count=removed_count,
                total_lines=total_lines,
            )
            if initial_bounds is None:
                return {"success": False, "message": "Invalid patch line range"}

            start_char, end_char = initial_bounds
            existing_block = original_text[start_char:end_char]
            expected_block = self._normalize_patch_content(request.old_content, newline_style)

            matched_line = requested_start
            if expected_block and not self._content_matches(existing_block, expected_block):
                if not request.allow_fallback_search:
                    return {
                        "success": False,
                        "message": "Existing content does not match expected old content",
                    }

                fallback = self._find_fallback_match(
                    text=original_text,
                    expected_block=expected_block,
                    line_offsets=line_offsets,
                    requested_start=requested_start,
                    total_lines=total_lines,
                    removed_count=removed_count,
                )
                if fallback is None:
                    preview_existing = self._preview_text(existing_block)
                    preview_expected = self._preview_text(expected_block)
                    return {
                        "success": False,
                        "message": (
                            "Existing content does not match expected old content. "
                            "No fallback match found."
                        ),
                        "diagnostics": {
                            "requested_start_line": requested_start,
                            "removed_line_count": removed_count,
                            "existing_preview": preview_existing,
                            "expected_preview": preview_expected,
                        },
                    }
                start_char, end_char, matched_line = fallback

            replacement_block = self._normalize_patch_content(request.new_content, newline_style)
            replacement_block = self._ensure_replacement_block_boundary(
                replacement_block=replacement_block,
                newline_style=newline_style,
                removed_count=removed_count,
                is_eof_replacement=(end_char >= len(original_text)),
            )
            updated_text = original_text[:start_char] + replacement_block + original_text[end_char:]
            syntax_error = self._validate_updated_file_syntax(file_path=file_path, content=updated_text)
            if syntax_error is not None:
                return {
                    "success": False,
                    "message": (
                        "Patch would produce invalid file syntax. "
                        f"{syntax_error}"
                    ),
                }

            backup_path = self._create_backup(file_path)
            file_path.write_text(updated_text, encoding="utf-8")

            preview = self._build_unified_preview(
                file_path=request.file_path,
                start_line=matched_line,
                old_block=original_text[start_char:end_char],
                new_block=replacement_block,
            )

            LOGGER.info("Applied patch to %s at line %s", file_path, matched_line)
            return {
                "success": True,
                "message": f"Patch applied at line {matched_line}",
                "backup_path": str(backup_path),
                "file_path": str(file_path),
                "applied_start_line_number": matched_line,
                "unified_diff": preview,
            }
        except Exception as exc:
            LOGGER.exception("Patch application failed for %s", request.file_path)
            return {"success": False, "message": f"Patch application failed: {exc}"}

    def _resolve_file_path(self, repo_path: str, file_path: str) -> Path:
        """Resolve and validate target file path within repository root."""
        repo = Path(repo_path).expanduser().resolve()
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = (repo / candidate.as_posix().lstrip("/\\")).resolve()
        else:
            candidate = candidate.resolve()

        if repo not in candidate.parents and candidate != repo:
            raise ValueError(f"Path traversal detected for file path: {file_path}")
        return candidate

    def _create_backup(self, file_path: Path) -> Path:
        """Write a timestamped backup file for rollback support."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{timestamp}")
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _build_line_offsets(self, text: str) -> List[int]:
        """Return start offsets for each line plus trailing EOF offset."""
        offsets = [0]
        for index, char in enumerate(text):
            if char == "\n":
                offsets.append(index + 1)
        if offsets[-1] != len(text):
            offsets.append(len(text))
        return offsets

    def _line_range_to_char_bounds(
        self,
        line_offsets: List[int],
        start_line: int,
        removed_count: int,
        total_lines: int,
    ) -> tuple[int, int] | None:
        """
        Convert 1-based line range to [start_char, end_char) bounds.

        Allows insertion at EOF when removed_count is zero.
        """
        max_start = total_lines + 1 if removed_count == 0 else total_lines
        if start_line > max_start:
            return None

        if removed_count == 0:
            line_index = min(start_line - 1, len(line_offsets) - 1)
            start_char = line_offsets[line_index]
            return start_char, start_char

        end_line = start_line + removed_count
        if end_line > total_lines + 1:
            return None

        if (start_line - 1) >= len(line_offsets) or (end_line - 1) >= len(line_offsets):
            return None

        start_char = line_offsets[start_line - 1]
        end_char = line_offsets[end_line - 1]
        return start_char, end_char

    def _detect_newline_style(self, content: str) -> str:
        """Detect dominant newline style, defaulting to LF."""
        if "\r\n" in content:
            return "\r\n"
        return "\n"

    def _normalize_patch_content(self, content: str, newline_style: str) -> str:
        """Normalize incoming patch text to target file newline style."""
        if not content:
            return ""
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        if newline_style != "\n":
            normalized = normalized.replace("\n", newline_style)
        return normalized

    def _content_matches(self, existing_block: str, expected_block: str) -> bool:
        """Compare two blocks with exact content, allowing one trailing newline variance."""
        if existing_block == expected_block:
            return True
        return existing_block.rstrip("\r\n") == expected_block.rstrip("\r\n")

    def _find_fallback_match(
        self,
        text: str,
        expected_block: str,
        line_offsets: List[int],
        requested_start: int,
        total_lines: int,
        removed_count: int,
    ) -> tuple[int, int, int] | None:
        """
        Locate fallback match near requested line.

        Returns:
            Tuple of (start_char, end_char, matched_start_line) when unique.
        """
        window_start_line = max(1, requested_start - self.SEARCH_WINDOW_LINES)
        window_end_line = min(total_lines + 1, requested_start + self.SEARCH_WINDOW_LINES)
        window_start_char = line_offsets[window_start_line - 1]
        window_end_char = line_offsets[window_end_line - 1]

        local_matches = self._find_all_matches(
            text=text,
            needle=expected_block,
            start=window_start_char,
            end=window_end_char,
            limit=50,
        )
        if len(local_matches) == 1:
            start_char = local_matches[0]
            return start_char, start_char + len(expected_block), self._line_for_offset(line_offsets, start_char)
        if len(local_matches) > 1:
            # Choose nearest exact match to requested line for stability in repeated code blocks.
            nearest = min(
                local_matches,
                key=lambda start: abs(self._line_for_offset(line_offsets, start) - requested_start),
            )
            return nearest, nearest + len(expected_block), self._line_for_offset(line_offsets, nearest)

        global_matches = self._find_all_matches(text=text, needle=expected_block, limit=50)
        if len(global_matches) == 1:
            start_char = global_matches[0]
            return start_char, start_char + len(expected_block), self._line_for_offset(line_offsets, start_char)
        if len(global_matches) > 1:
            nearest = min(
                global_matches,
                key=lambda start: abs(self._line_for_offset(line_offsets, start) - requested_start),
            )
            return nearest, nearest + len(expected_block), self._line_for_offset(line_offsets, nearest)

        fuzzy_match = self._find_fuzzy_line_range_match(
            text=text,
            expected_block=expected_block,
            line_offsets=line_offsets,
            requested_start=requested_start,
            total_lines=total_lines,
            removed_count=removed_count,
        )
        if fuzzy_match is not None:
            return fuzzy_match

        similar_match = self._find_similar_line_range_match(
            text=text,
            expected_block=expected_block,
            line_offsets=line_offsets,
            requested_start=requested_start,
            total_lines=total_lines,
            removed_count=removed_count,
        )
        return similar_match

    def _find_all_matches(
        self,
        text: str,
        needle: str,
        start: int = 0,
        end: int | None = None,
        limit: int = 10,
    ) -> List[int]:
        """Find up to `limit` exact matches for a string inside optional bounds."""
        if not needle:
            return []
        if end is None:
            end = len(text)
        matches: List[int] = []
        cursor = start
        while len(matches) < limit:
            found = text.find(needle, cursor, end)
            if found == -1:
                break
            matches.append(found)
            cursor = found + 1
        return matches

    def _line_for_offset(self, line_offsets: List[int], offset: int) -> int:
        """Convert character offset to 1-based line number."""
        left = 0
        right = len(line_offsets) - 1
        while left < right:
            middle = (left + right + 1) // 2
            if line_offsets[middle] <= offset:
                left = middle
            else:
                right = middle - 1
        return left + 1

    def _find_fuzzy_line_range_match(
        self,
        text: str,
        expected_block: str,
        line_offsets: List[int],
        requested_start: int,
        total_lines: int,
        removed_count: int,
    ) -> tuple[int, int, int] | None:
        """
        Find nearest normalized-content match by line window.

        This fallback tolerates indentation/whitespace drift while preserving location affinity.
        """
        expected_normalized = self._normalize_for_fuzzy_match(expected_block)
        if not expected_normalized:
            return None

        expected_line_count = max(len(expected_block.splitlines()), 0)
        candidate_counts = []
        if removed_count > 0:
            candidate_counts.append(removed_count)
        if expected_line_count > 0 and expected_line_count not in candidate_counts:
            candidate_counts.append(expected_line_count)
        if not candidate_counts:
            return None

        window_start_line = max(1, requested_start - self.SEARCH_WINDOW_LINES)
        window_end_line = min(total_lines, requested_start + self.SEARCH_WINDOW_LINES)
        matches: list[tuple[int, int, int]] = []

        for count in candidate_counts:
            max_start_line = window_end_line - count + 1
            if max_start_line < window_start_line:
                continue
            for start_line in range(window_start_line, max_start_line + 1):
                bounds = self._line_range_to_char_bounds(
                    line_offsets=line_offsets,
                    start_line=start_line,
                    removed_count=count,
                    total_lines=total_lines,
                )
                if bounds is None:
                    continue
                start_char, end_char = bounds
                candidate_text = text[start_char:end_char]
                if self._normalize_for_fuzzy_match(candidate_text) == expected_normalized:
                    matches.append((start_char, end_char, start_line))

        if not matches:
            return None

        return min(matches, key=lambda item: abs(item[2] - requested_start))

    def _normalize_for_fuzzy_match(self, text: str) -> str:
        """Normalize block text for tolerant line-based fallback matching."""
        normalized_lines: list[str] = []
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            normalized_lines.append(" ".join(line.strip().split()))
        return "\n".join(normalized_lines).strip()

    def _ensure_replacement_block_boundary(
        self,
        *,
        replacement_block: str,
        newline_style: str,
        removed_count: int,
        is_eof_replacement: bool,
    ) -> str:
        """
        Ensure replacement text does not accidentally concatenate with the next preserved line.

        When replacing one or more existing lines in the middle of a file, the inserted block
        should end with a newline.
        """
        if not replacement_block:
            return replacement_block
        if removed_count > 0 and not is_eof_replacement and not replacement_block.endswith(newline_style):
            return replacement_block + newline_style
        return replacement_block

    def _validate_updated_file_syntax(self, *, file_path: Path, content: str) -> str | None:
        """
        Validate syntax for known file types before writing patch result.

        Returns:
            None when valid; otherwise, a human-readable error message.
        """
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            try:
                ast.parse(content)
            except SyntaxError as exc:
                line = exc.lineno or "?"
                message = exc.msg or "invalid syntax"
                return f"Python syntax error at line {line}: {message}"
        return None

    def _find_similar_line_range_match(
        self,
        text: str,
        expected_block: str,
        line_offsets: List[int],
        requested_start: int,
        total_lines: int,
        removed_count: int,
    ) -> tuple[int, int, int] | None:
        """
        Find nearest high-similarity candidate by normalized text ratio.

        This is a last-resort fallback for minor drift in AI old_content snippets.
        """
        expected_normalized = self._normalize_for_fuzzy_match(expected_block)
        if not expected_normalized:
            return None

        expected_line_count = len(expected_block.splitlines())
        candidate_counts: list[int] = []
        for candidate in (
            removed_count,
            expected_line_count,
            max(removed_count - 1, 1),
            removed_count + 1,
            max(expected_line_count - 1, 1),
            expected_line_count + 1,
        ):
            if candidate > 0 and candidate not in candidate_counts:
                candidate_counts.append(candidate)
        if not candidate_counts:
            return None

        window_start_line = max(1, requested_start - self.SIMILARITY_SEARCH_WINDOW_LINES)
        window_end_line = min(total_lines, requested_start + self.SIMILARITY_SEARCH_WINDOW_LINES)

        best: tuple[float, int, int, int] | None = None
        for count in candidate_counts:
            max_start_line = window_end_line - count + 1
            if max_start_line < window_start_line:
                continue
            for start_line in range(window_start_line, max_start_line + 1):
                bounds = self._line_range_to_char_bounds(
                    line_offsets=line_offsets,
                    start_line=start_line,
                    removed_count=count,
                    total_lines=total_lines,
                )
                if bounds is None:
                    continue
                start_char, end_char = bounds
                candidate_text = text[start_char:end_char]
                candidate_normalized = self._normalize_for_fuzzy_match(candidate_text)
                if not candidate_normalized:
                    continue

                ratio = difflib.SequenceMatcher(None, expected_normalized, candidate_normalized).ratio()
                if ratio < self.MIN_SIMILARITY_RATIO:
                    continue

                distance = abs(start_line - requested_start)
                if best is None or ratio > best[0] or (ratio == best[0] and distance < abs(best[3] - requested_start)):
                    best = (ratio, start_char, end_char, start_line)

        if best is None:
            return None
        return best[1], best[2], best[3]

    def _preview_text(self, text: str, limit: int = 200) -> str:
        """Return compact preview of text for diagnostics."""
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + "...[truncated]"

    def _build_unified_preview(
        self,
        file_path: str,
        start_line: int,
        old_block: str,
        new_block: str,
    ) -> str:
        """Build a compact unified diff for UI preview/logging."""
        old_lines = old_block.splitlines(keepends=True)
        new_lines = new_block.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                fromfiledate="",
                tofiledate="",
                n=3,
                lineterm="",
            )
        )
