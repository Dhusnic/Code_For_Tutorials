"""Git stash management helpers for safe local review workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from git import Repo

LOGGER = logging.getLogger(__name__)


class GitStashManager:
    """Wrap common stash operations with predictable return values."""

    def __init__(self, repo_path: str) -> None:
        """
        Initialize stash manager.

        Args:
            repo_path: Repository root directory.
        """
        self.repo_path = Path(repo_path).expanduser()

    def create_stash(self, message: str = "agentic-ai-review") -> str:
        """
        Stash current tracked and untracked changes.

        Args:
            message: Optional stash message.

        Returns:
            Git command output.
        """
        try:
            repo = Repo(self.repo_path)
            result = repo.git.stash("push", "-u", "-m", message)
            LOGGER.info("Created stash in %s with message='%s'", self.repo_path, message)
            return result
        except Exception as exc:
            LOGGER.exception("Failed to create stash")
            raise RuntimeError(f"Unable to create stash: {exc}") from exc

    def pop_stash(self, index: int = 0) -> str:
        """
        Pop a stash by index.

        Args:
            index: Stash index from `stash@{index}`.

        Returns:
            Git command output.
        """
        try:
            repo = Repo(self.repo_path)
            result = repo.git.stash("pop", f"stash@{{{index}}}")
            LOGGER.info("Popped stash index=%s from %s", index, self.repo_path)
            return result
        except Exception as exc:
            LOGGER.exception("Failed to pop stash index=%s", index)
            raise RuntimeError(f"Unable to pop stash {index}: {exc}") from exc

    def list_stashes(self) -> List[str]:
        """
        List available stash entries.

        Returns:
            Stash entries as text lines.
        """
        try:
            repo = Repo(self.repo_path)
            output = repo.git.stash("list")
            return [line for line in output.splitlines() if line.strip()]
        except Exception as exc:
            LOGGER.exception("Failed to list stashes")
            raise RuntimeError(f"Unable to list stashes: {exc}") from exc
