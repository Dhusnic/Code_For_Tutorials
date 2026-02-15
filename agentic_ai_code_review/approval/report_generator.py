"""Generate human-readable review reports for approvals and auditing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LOGGER = logging.getLogger(__name__)


@dataclass
class ReportMetadata:
    """Metadata describing a generated review report."""

    repository: str
    pull_request_id: str
    generated_at: str
    reviewer: str = "agentic-ai-code-review"


class ReportGenerator:
    """Build markdown and JSON reports from review output payloads."""

    def generate_markdown_report(
        self,
        repository_name: str,
        pull_request_id: str,
        review: str,
        code_changes: List[Dict[str, Any]],
    ) -> str:
        """
        Render a markdown summary report.

        Args:
            repository_name: Repository name.
            pull_request_id: Pull request identifier.
            review: Review markdown text.
            code_changes: Suggested code changes.

        Returns:
            Markdown report string.
        """
        metadata = ReportMetadata(
            repository=repository_name,
            pull_request_id=pull_request_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        lines = [
            "# AI Code Review Report",
            "",
            f"- Repository: `{metadata.repository}`",
            f"- Pull Request: `{metadata.pull_request_id}`",
            f"- Generated At (UTC): `{metadata.generated_at}`",
            f"- Reviewer: `{metadata.reviewer}`",
            "",
            "## Review",
            "",
            review or "_No review comments generated._",
            "",
            "## Suggested Changes",
            "",
        ]

        if not code_changes:
            lines.append("_No code changes generated._")
        else:
            for index, change in enumerate(code_changes, start=1):
                diff = change.get("diff", {})
                lines.extend(
                    [
                        f"### Change {index}",
                        f"- File: `{diff.get('file_path', 'unknown')}`",
                        f"- Line: `{diff.get('line_number', '?')}`",
                        f"- Category: `{', '.join(change.get('categories', []))}`",
                        f"- Explanation: {change.get('explanation', '')}",
                        "",
                        "```",
                        diff.get("new_content", ""),
                        "```",
                        "",
                    ]
                )

        return "\n".join(lines).strip()

    def generate_json_report(
        self,
        repository_name: str,
        pull_request_id: str,
        review: str,
        code_changes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build structured JSON report object.

        Args:
            repository_name: Repository name.
            pull_request_id: Pull request identifier.
            review: Review markdown.
            code_changes: Suggested code changes.

        Returns:
            Report dictionary.
        """
        return {
            "repository": repository_name,
            "pull_request_id": pull_request_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": "agentic-ai-code-review",
            "review": review,
            "code_changes": code_changes,
            "change_count": len(code_changes),
        }

    def save_report(self, output_path: str, content: str | Dict[str, Any]) -> str:
        """
        Persist report to disk.

        Args:
            output_path: Destination file path.
            content: Markdown text or JSON-compatible object.

        Returns:
            Resolved output file path.
        """
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            if isinstance(content, str):
                destination.write_text(content, encoding="utf-8")
            else:
                destination.write_text(json.dumps(content, indent=2), encoding="utf-8")
            LOGGER.info("Report saved to %s", destination)
            return str(destination)
        except Exception as exc:
            LOGGER.exception("Failed to save report to %s", destination)
            raise RuntimeError(f"Unable to save report: {exc}") from exc
