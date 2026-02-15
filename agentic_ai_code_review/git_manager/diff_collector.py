"""Utilities for collecting structured local Git diffs."""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from git import InvalidGitRepositoryError, Repo

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
            diffs = repo.index.diff(None, create_patch=True)
            results: List[Dict[str, Any]] = []

            for diff in diffs:
                file_path = diff.a_path or diff.b_path or ""
                if self.is_excluded(file_path):
                    continue

                decoded_patch = diff.diff.decode("utf-8", errors="ignore")
                parsed_hunks = self._parse_patch_hunks(decoded_patch)
                if not parsed_hunks:
                    continue

                results.append(
                    {
                        "file": file_path,
                        "change_type": diff.change_type,
                        "hunks": parsed_hunks,
                    }
                )

            LOGGER.info("Collected %s changed files from local repository", len(results))
            return results
        except InvalidGitRepositoryError as exc:
            LOGGER.exception("Invalid git repository path: %s", self.repo_path)
            raise RuntimeError(f"Invalid repository path: {self.repo_path}") from exc
        except Exception as exc:
            LOGGER.exception("Failed to collect repository diff")
            raise RuntimeError("Unable to collect repository diff") from exc

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
                    "added": [],
                    "removed": [],
                }
                hunks.append(current_hunk)
                continue

            if not current_hunk:
                continue

            if line.startswith(" ") and not line.startswith("+++"):
                current_hunk["context"].append(
                    {"line": line[1:], "old_line": old_line, "new_line": new_line}
                )
                old_line += 1
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["removed"].append({"line": line[1:], "old_line": old_line})
                old_line += 1
            elif line.startswith("+") and not line.startswith("+++"):
                current_hunk["added"].append({"line": line[1:], "new_line": new_line})
                new_line += 1

        return hunks
