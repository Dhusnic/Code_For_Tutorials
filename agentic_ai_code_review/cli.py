"""Application orchestration layer for collecting diffs, reviewing, and suggesting fixes."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure_manager.azure_manager import AzureDevOpsClient
from comman import CommonUtils
from config import prompts
from git_manager.diff_collector import DiffCollector
from review_manager.ai_reviewer import AIReviewer

LOGGER = logging.getLogger(__name__)


class AgenticAICodeReviewCLI(CommonUtils):
    """Coordinates diff extraction, AI review generation, and remediation suggestions."""

    def __init__(self, config: Optional[Any] = None) -> None:
        """
        Initialize runtime dependencies from a config object.

        Args:
            config: Optional object exposing expected fields used by API model.
        """
        self.env_path = str(Path(__file__).resolve().parent / "config" / ".env")
        self.repo_path = Path("D:\\Product\\Infraon")
        self.ai_model = "gpt-4o-mini"
        self.max_tokens = 30000
        self.organization = "infraon"
        self.project = "Infraon"
        self.repository_name = "Infraon"
        self.pull_request_id = "17070"
        self.is_local = False
        self.azure_pat = ""

        if config is not None:
            self.repo_path = Path(getattr(config, "repo_path", self.repo_path))
            self.ai_model = getattr(config, "ai_model", self.ai_model)
            self.max_tokens = int(getattr(config, "max_tokens", self.max_tokens))
            self.organization = getattr(config, "organization", self.organization)
            self.project = getattr(config, "project", self.project)
            self.repository_name = getattr(config, "repository_name", self.repository_name)
            self.pull_request_id = str(getattr(config, "pull_request_id", self.pull_request_id))
            self.is_local = bool(getattr(config, "is_local", self.is_local))
            self.azure_pat = getattr(config, "azure_pat", "") or ""

        if not self.azure_pat:
            self.azure_pat = self.get_env_value(
                env_path=self.env_path,
                key="AZURE_DEVOPS_PAT",
                default="",
            )

        self.diff_collector = DiffCollector(str(self.repo_path), env_path=self.env_path)
        self.ai_reviewer = AIReviewer(
            model_name=self.ai_model,
            max_tokens=self.max_tokens,
            env_path=self.env_path,
        )
        self.azure_manager = AzureDevOpsClient(
            organization=self.organization,
            project=self.project,
            pat_token=self.azure_pat,
        )

    def main(self) -> Dict[str, Any]:
        """
        Execute full review workflow for CLI usage.

        Returns:
            Full workflow response with review and proposed code changes.
        """
        return self.run_full_review()

    def review_diffs(self) -> Dict[str, Any]:
        """
        Collect diffs and generate review comments.

        Returns:
            Dictionary containing review text and token details.
        """
        try:
            diffs = self._collect_diffs()
            token_estimate = self.ai_reviewer.estimate_tokens(str(diffs), self.ai_model)
            review, review_tokens_used = self._collect_or_generate_review(diffs)
            return {
                "review": review,
                "token_estimate": token_estimate,
                "tokens_used": review_tokens_used,
                "ok": True,
            }
        except Exception as exc:
            LOGGER.exception("Failed to review diffs")
            raise RuntimeError("Unable to complete diff review") from exc

    def generate_changes(self, review: str = "") -> Dict[str, Any]:
        """
        Generate correction suggestions based on diffs and review.

        Args:
            review: Existing review text. If empty, review will be generated.

        Returns:
            Dictionary containing merged code changes and token usage.
        """
        try:
            diffs = self._collect_diffs()
            review_text = review or self._collect_or_generate_review(diffs)[0]

            conversation = [
                {"role": "system", "content": "You are a senior Angular + Django developer."},
                {
                    "role": "user",
                    "content": (
                        f"{prompts.Code_corrections_prompt}\n\n"
                        f"Diffs:\n{diffs}\n\n"
                        f"Review Comment:\n{review_text}"
                    ),
                },
            ]
            code_change_data = self.ai_reviewer.get_ai_response(
                conversation=conversation,
                model=self.ai_model,
                max_output_tokens=min(self.max_tokens, 20000),
            )

            raw_output = code_change_data.get("response", "")
            extracted_json = self.extract_json_from_ai_output(raw_output)
            changes = extracted_json.get("diffs", extracted_json)
            merged_changes = self.merge_consecutive_diffs(changes if isinstance(changes, list) else [])

            return {
                "review": review_text,
                "code_changes": merged_changes,
                "tokens_used": code_change_data.get("tokens_used", 0),
                "raw_response": raw_output if not merged_changes else "",
            }
        except Exception as exc:
            LOGGER.exception("Failed to generate code changes")
            raise RuntimeError("Unable to generate code changes") from exc

    def run_full_review(self) -> Dict[str, Any]:
        """
        Run full workflow: collect diffs, review, and generate code changes.

        Returns:
            Full pipeline output.
        """
        try:
            diffs = self._collect_diffs()
            token_estimate = self.ai_reviewer.estimate_tokens(str(diffs), self.ai_model)
            review, review_tokens = self._collect_or_generate_review(diffs)
            changes_data = self.generate_changes(review=review)
            return {
                "review": review,
                "code_changes": changes_data.get("code_changes", []),
                "token_estimate": token_estimate,
                "tokens_used": review_tokens + int(changes_data.get("tokens_used", 0)),
            }
        except Exception as exc:
            LOGGER.exception("Failed to run full review")
            raise RuntimeError("Unable to run full review workflow") from exc

    def _collect_diffs(self) -> List[Dict[str, Any]]:
        """
        Collect diffs from local repo or Azure pull request.

        Returns:
            Structured diff list.
        """
        try:
            if self.is_local:
                LOGGER.info("Collecting local changes from %s", self.repo_path)
                return self.diff_collector.collect_repo_diff()

            LOGGER.info(
                "Collecting PR changes org=%s project=%s repo=%s pr=%s",
                self.organization,
                self.project,
                self.repository_name,
                self.pull_request_id,
            )
            return self.azure_manager.get_pr_content_changes(
                repository_name=self.repository_name,
                pull_request_id=int(self.pull_request_id),
                instruction="Get full diff with line numbers and hunks.",
            )
        except Exception as exc:
            LOGGER.exception("Unable to collect diffs")
            raise RuntimeError("Failed to collect diffs") from exc

    def _collect_or_generate_review(self, diffs: List[Dict[str, Any]]) -> tuple[str, int]:
        """
        Return review text from existing PR comments or AI generation.

        Args:
            diffs: Structured diffs.

        Returns:
            Tuple of (review_text, tokens_used).
        """
        if self.is_local:
            return self._generate_ai_review(diffs)

        try:
            threads = self.azure_manager.get_pr_comments(
                repository_name=self.repository_name,
                pull_request_id=int(self.pull_request_id),
            )
            if threads:
                review_lines = [
                    comment.get("content", "").strip()
                    for thread in threads
                    for comment in thread.get("comments", [])
                    if comment and comment.get("content")
                ]
                review = "\n\n".join(line for line in review_lines if line)
                if review:
                    LOGGER.info("Using existing PR comments as review context")
                    return self._normalize_review_markdown(review), 0
        except Exception:
            LOGGER.exception("Unable to fetch PR comments, falling back to AI review")

        return self._generate_ai_review(diffs)

    def _generate_ai_review(self, diffs: List[Dict[str, Any]]) -> tuple[str, int]:
        """Generate review text from AI model."""
        conversation = [
            {"role": "system", "content": "You are a code review assistant."},
            {
                "role": "user",
                "content": f"{prompts.Review_prompt}\n\nDiffs to review:\n{diffs}",
            },
        ]
        review_data = self.ai_reviewer.get_ai_response(
            conversation=conversation,
            model=self.ai_model,
            max_output_tokens=min(self.max_tokens, 20000),
        )
        normalized_review = self._normalize_review_markdown(review_data.get("response", ""))
        return normalized_review, int(review_data.get("tokens_used", 0))

    def _normalize_review_markdown(self, text: str) -> str:
        """
        Normalize AI/PR review text into markdown safe for UI rendering.

        This handles common malformed output patterns from models:
        - Entire response wrapped in a single ```markdown ... ``` fence.
        - Escaped newline sequences (`\\n`) instead of real newlines.
        - Unbalanced fenced code blocks.
        - Plain text responses without markdown structure.
        """
        value = (text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if not value:
            return "## AI Review\n\nNo findings generated."

        # If the model returned markdown within a wrapping code fence, unwrap once.
        wrapped_match = re.fullmatch(
            r"```(?:markdown|md)?\s*\n?(.*?)\n?```",
            value,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if wrapped_match:
            value = wrapped_match.group(1).strip()

        # Convert escaped newline payloads into readable markdown when needed.
        if "\n" not in value and "\\n" in value:
            value = value.replace("\\n", "\n")

        # Add a predictable heading for plain-text outputs.
        if not re.search(r"(^|\n)\s*(#{1,6}\s|\-\s|\*\s|>\s|\d+\.\s|```|\|)", value):
            paragraphs = [line.strip() for line in value.split("\n") if line.strip()]
            if paragraphs:
                value = "## AI Review\n\n" + "\n\n".join(paragraphs)
            else:
                value = "## AI Review\n\nNo findings generated."

        # Close unmatched fenced code block to avoid broken markdown rendering.
        if value.count("```") % 2 != 0:
            value = f"{value}\n```"

        return value.strip()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cli = AgenticAICodeReviewCLI()
    print(cli.main())
