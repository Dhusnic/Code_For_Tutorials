"""Console rendering helpers for review summaries and operational status."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

LOGGER = logging.getLogger(__name__)


class ConsoleUI:
    """Render review output in a compact terminal-friendly format."""

    def render_review_summary(self, review: str, token_estimate: int, tokens_used: int) -> str:
        """
        Build plain-text review summary block.

        Args:
            review: Review text.
            token_estimate: Estimated input token count.
            tokens_used: Actual token usage.

        Returns:
            Formatted summary string.
        """
        return (
            "=== Review Summary ===\n"
            f"Estimated Tokens: {token_estimate}\n"
            f"Used Tokens: {tokens_used}\n"
            f"Review:\n{review or 'No review available.'}\n"
        )

    def render_code_changes(self, code_changes: List[Dict[str, Any]]) -> str:
        """
        Render code change suggestions.

        Args:
            code_changes: Suggested changes list.

        Returns:
            Formatted changes.
        """
        if not code_changes:
            return "No code changes were generated."

        lines = ["=== Suggested Changes ==="]
        for index, change in enumerate(code_changes, start=1):
            diff = change.get("diff", {})
            lines.extend(
                [
                    f"{index}. {diff.get('file_path', 'unknown file')} "
                    f"(line {diff.get('line_number', '?')})",
                    f"   Severity: {', '.join(change.get('categories', [])) or 'n/a'}",
                    f"   Explanation: {change.get('explanation', 'n/a')}",
                ]
            )
        return "\n".join(lines)

    def print_safe(self, text: str) -> None:
        """
        Print text with runtime safety logging.

        Args:
            text: Message to print.
        """
        try:
            print(text)
        except Exception:
            LOGGER.exception("Failed to print console output")
