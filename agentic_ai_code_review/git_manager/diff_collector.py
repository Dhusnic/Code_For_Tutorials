"""Utilities for collecting structured local Git diffs."""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from git import NULL_TREE, InvalidGitRepositoryError, Repo

LOGGER = logging.getLogger(__name__)


class DiffCollector:
    """Collect and normalize local repository diffs into hunk-level structures."""

    HUNK_PATTERN = re.compile(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")

    def __init__(self, repo_path: str, env_path: str = ".env") -> None:
        """
        Initialize diff collector configuration.

        Args:
            repo_path: Path to local Git repository.
            env_path: Reserved for compatibility with existing constructor usage.
        """
        self.repo_path = Path(repo_path).expanduser()
        self.env_path = env_path
        self.excluded_dirs = {".git", "node_modules", "__pycache__"}
        self.excluded_file_patterns = {
            ".DS_Store",
            "thumbs.db",
            ".env",
            "*.db",
            "*.sqlite3",
            "*.log",
            "*.pyc",
            "*.json",
            "*.ini",
            "environment.instance.ts",
            "requirements.txt",
            "*.png",
            "*.dat",
        }
        self.included_files = {"en.json", "hi.json", "ar.json"}

    def collect_repo_diff(self) -> List[Dict[str, Any]]:
        """
        Collect file diffs from working tree changes.

        Returns:
            Structured list with file path, change type, and parsed hunks.
        """
        try:
            LOGGER.info("Collecting local repository diff from %s", self.repo_path)
            repo = Repo(self.repo_path)
            unstaged_diffs = repo.index.diff(None, create_patch=True)
            if repo.head.is_valid():
                staged_diffs = repo.index.diff("HEAD", create_patch=True)
            else:
                staged_diffs = repo.index.diff(NULL_TREE, create_patch=True)

            results_by_file: Dict[str, Dict[str, Any]] = {}
            for diff in list(staged_diffs) + list(unstaged_diffs):
                parsed = self._parse_git_diff(diff)
                if not parsed:
                    continue
                self._merge_file_result(results_by_file, parsed)

            for relative_path in repo.untracked_files:
                parsed = self._parse_untracked_file(relative_path)
                if not parsed:
                    continue
                self._merge_file_result(results_by_file, parsed)

            results = sorted(results_by_file.values(), key=lambda item: item.get("file", ""))

            LOGGER.info("Collected %s changed files from local repository", len(results))
            return results
        except InvalidGitRepositoryError as exc:
            LOGGER.exception("Invalid git repository path: %s", self.repo_path)
            raise RuntimeError(f"Invalid repository path: {self.repo_path}") from exc
        except Exception as exc:
            LOGGER.exception("Failed to collect repository diff")
            raise RuntimeError("Unable to collect repository diff") from exc

    def _parse_git_diff(self, diff: Any) -> Dict[str, Any] | None:
        """Parse one GitPython diff item into normalized schema."""
        file_path = diff.a_path or diff.b_path or ""
        if not file_path or self.is_excluded(file_path):
            return None

        decoded_patch = (diff.diff or b"").decode("utf-8", errors="ignore")
        parsed_hunks = self._parse_patch_hunks(decoded_patch)
        if not parsed_hunks:
            return None

        return {
            "file": file_path,
            "change_type": diff.change_type,
            "hunks": parsed_hunks,
        }

    def _parse_untracked_file(self, relative_path: str) -> Dict[str, Any] | None:
        """Build synthetic diff payload for untracked files."""
        normalized = str(relative_path).replace("\\", "/")
        if not normalized or self.is_excluded(normalized):
            return None

        absolute_path = self.repo_path / normalized
        if not absolute_path.exists() or not absolute_path.is_file():
            return None

        try:
            content = absolute_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            LOGGER.exception("Unable to read untracked file for diff: %s", normalized)
            return None

        lines = content.splitlines()
        hunks = [
            {
                "old_start": 0,
                "old_count": 0,
                "new_start": 1,
                "new_count": len(lines),
                "context": [],
                "context_before": [],
                "context_after": [],
                "added": [{"line": line, "new_line": index} for index, line in enumerate(lines, start=1)],
                "removed": [],
            }
        ]

        return {
            "file": normalized,
            "change_type": "A",
            "hunks": hunks,
        }

    def _merge_file_result(self, results_by_file: Dict[str, Dict[str, Any]], item: Dict[str, Any]) -> None:
        """Merge diff payloads for the same file across staged/unstaged/untracked sets."""
        file_path = str(item.get("file", "")).replace("\\", "/").lstrip("/\\")
        if not file_path:
            return

        if file_path not in results_by_file:
            results_by_file[file_path] = {
                "file": file_path,
                "change_type": item.get("change_type", "M"),
                "hunks": list(item.get("hunks", [])),
            }
            return

        existing = results_by_file[file_path]
        existing_hunks = existing.get("hunks", [])
        existing_hunks.extend(item.get("hunks", []))
        existing["hunks"] = existing_hunks

    def is_excluded(self, file_path: str) -> bool:
        """
        Check whether a file should be excluded from review input.

        Args:
            file_path: Relative path from repository root.

        Returns:
            `True` if excluded by pattern and not explicitly included.
        """
        try:
            normalized = Path(file_path)
            if normalized.name in self.included_files:
                return False

            path_parts = set(normalized.parts)
            if self.excluded_dirs.intersection(path_parts):
                return True

            file_name = normalized.name
            for pattern in self.excluded_file_patterns:
                if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                    return True
            return False
        except Exception:
            LOGGER.exception("Error while evaluating exclusion for path: %s", file_path)
            return True

    def _parse_patch_hunks(self, patch: str) -> List[Dict[str, Any]]:
        """
        Parse unified diff text into structured hunks with line numbers.

        Args:
            patch: Unified diff text for a single file.

        Returns:
            List of parsed hunks.
        """
        hunks: List[Dict[str, Any]] = []
        current_hunk: Dict[str, Any] | None = None
        old_line = 0
        new_line = 0

        for line in patch.splitlines():
            header_match = self.HUNK_PATTERN.search(line)
            if header_match:
                old_start, old_count, new_start, new_count = header_match.groups()
                old_line = int(old_start)
                new_line = int(new_start)
                current_hunk = {
                    "old_start": int(old_start),
                    "old_count": int(old_count or "1"),
                    "new_start": int(new_start),
                    "new_count": int(new_count or "1"),
                    "context": [],
                    "context_before": [],
                    "context_after": [],
                    "added": [],
                    "removed": [],
                    "_ordered_hunk_lines": [],
                }
                hunks.append(current_hunk)
                continue

            if not current_hunk:
                continue

            if line.startswith(" ") and not line.startswith("+++"):
                context_line = {"line": line[1:], "old_line": old_line, "new_line": new_line}
                current_hunk["context"].append(context_line)
                current_hunk["_ordered_hunk_lines"].append({"kind": "context", **context_line})
                old_line += 1
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed_line = {"line": line[1:], "old_line": old_line}
                current_hunk["removed"].append(removed_line)
                current_hunk["_ordered_hunk_lines"].append({"kind": "removed", **removed_line})
                old_line += 1
            elif line.startswith("+") and not line.startswith("+++"):
                added_line = {"line": line[1:], "new_line": new_line}
                current_hunk["added"].append(added_line)
                current_hunk["_ordered_hunk_lines"].append({"kind": "added", **added_line})
                new_line += 1

        for hunk in hunks:
            self._attach_context_windows(hunk)

        return hunks

    def _attach_context_windows(self, hunk: Dict[str, Any]) -> None:
        """Split ordered hunk context lines into before/after change windows."""
        ordered_lines = hunk.pop("_ordered_hunk_lines", [])
        if not ordered_lines:
            hunk["context_before"] = []
            hunk["context_after"] = []
            return

        first_change_index = None
        last_change_index = None
        for index, item in enumerate(ordered_lines):
            if item.get("kind") in {"added", "removed"}:
                if first_change_index is None:
                    first_change_index = index
                last_change_index = index

        if first_change_index is None or last_change_index is None:
            context_entries = [self._strip_kind(item) for item in ordered_lines if item.get("kind") == "context"]
            hunk["context_before"] = context_entries
            hunk["context_after"] = []
            return

        context_before = [
            self._strip_kind(item)
            for item in ordered_lines[:first_change_index]
            if item.get("kind") == "context"
        ]
        context_after = [
            self._strip_kind(item)
            for item in ordered_lines[last_change_index + 1 :]
            if item.get("kind") == "context"
        ]
        hunk["context_before"] = context_before
        hunk["context_after"] = context_after

    def _strip_kind(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Remove internal keys from ordered hunk entries."""
        normalized = dict(item)
        normalized.pop("kind", None)
        return normalized
