"""Application orchestration layer for collecting diffs, reviewing, and suggesting fixes."""

from __future__ import annotations

import logging
import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure_manager.azure_manager import AzureDevOpsClient
from comman import CommonUtils
from config import prompts
from git_manager.diff_collector import DiffCollector
from review_manager.ai_reviewer import AIReviewer
from review_manager.diff_validator import DiffValidationError, DiffValidator

LOGGER = logging.getLogger(__name__)


class AgenticAICodeReviewCLI(CommonUtils):
    """Coordinates diff extraction, AI review generation, and remediation suggestions."""

    _SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

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
        self.diff_validator = DiffValidator()
        self.max_code_change_attempts = self._resolve_max_code_change_attempts()
        self.ai_context_window_lines = self._resolve_ai_context_window_lines()
        self.max_ai_hunks = self._resolve_max_ai_hunks()
        self.minimum_required_severity = self._resolve_minimum_required_severity()

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
            ai_diffs = self._prepare_diffs_for_ai(diffs)
            serialized_diffs = self._serialize_diffs_for_prompt(ai_diffs)
            token_estimate = self.ai_reviewer.estimate_tokens(serialized_diffs, self.ai_model)
            review, review_tokens_used, token_source = self._collect_or_generate_review(ai_diffs)
            return {
                "review": review,
                "token_estimate": token_estimate,
                "tokens_used": review_tokens_used,
                "token_source": token_source,
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
            ai_diffs = self._prepare_diffs_for_ai(diffs)
            review_text = review or self._collect_or_generate_review(ai_diffs)[0]
            conversation = self._build_code_correction_conversation(ai_diffs, review_text)
            generated = self._generate_validated_code_changes(
                base_conversation=conversation,
                source_hunks=ai_diffs,
            )
            generated_changes = generated.get("code_changes", [])
            required_changes = self._retain_required_changes(generated_changes)
            relaxed_to_generated = not required_changes and bool(generated_changes)
            final_changes = required_changes if required_changes else generated_changes
            review_output = self._normalize_review_with_status(
                review_text,
                no_changes_required=not final_changes,
            )

            return {
                "review": review_output,
                "code_changes": final_changes,
                "no_changes_required": not final_changes,
                "resolution_status": "no_changes_required" if not final_changes else "changes_required",
                "filter_relaxed_to_include_generated": relaxed_to_generated,
                "tokens_used": generated.get("tokens_used", 0),
                "token_source": generated.get("token_source", "estimated"),
                "token_usage": generated.get("token_usage", {}),
                "raw_response": generated.get("raw_response", ""),
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
            ai_diffs = self._prepare_diffs_for_ai(diffs)
            serialized_diffs = self._serialize_diffs_for_prompt(ai_diffs)
            token_estimate = self.ai_reviewer.estimate_tokens(serialized_diffs, self.ai_model)
            review, review_tokens, review_token_source = self._collect_or_generate_review(ai_diffs)
            conversation = self._build_code_correction_conversation(ai_diffs, review)
            changes_data = self._generate_validated_code_changes(
                base_conversation=conversation,
                source_hunks=ai_diffs,
            )
            generated_changes = changes_data.get("code_changes", [])
            required_changes = self._retain_required_changes(generated_changes)
            relaxed_to_generated = not required_changes and bool(generated_changes)
            final_changes = required_changes if required_changes else generated_changes
            review_output = self._normalize_review_with_status(
                review,
                no_changes_required=not final_changes,
            )
            changes_token_source = str(changes_data.get("token_source", "estimated"))
            combined_token_source = self._combine_token_source(
                review_token_source=review_token_source,
                changes_token_source=changes_token_source,
            )
            return {
                "review": review_output,
                "code_changes": final_changes,
                "no_changes_required": not final_changes,
                "resolution_status": "no_changes_required" if not final_changes else "changes_required",
                "filter_relaxed_to_include_generated": relaxed_to_generated,
                "token_estimate": token_estimate,
                "tokens_used": review_tokens + int(changes_data.get("tokens_used", 0)),
                "token_source": combined_token_source,
                "token_usage": self._merge_usage_objects(
                    {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": review_tokens,
                        "source": review_token_source,
                    },
                    changes_data.get("token_usage"),
                ),
                "raw_response": changes_data.get("raw_response", ""),
            }
        except Exception as exc:
            LOGGER.exception("Failed to run full review")
            raise RuntimeError("Unable to run full review workflow") from exc

    def _resolve_max_code_change_attempts(self) -> int:
        """Resolve retry count for correction generation quality gate."""
        raw_value = os.getenv("AI_CHANGE_GENERATION_ATTEMPTS", "3")
        try:
            return max(1, int(raw_value))
        except (TypeError, ValueError):
            return 3

    def _resolve_ai_context_window_lines(self) -> int:
        """Resolve number of context lines sent above and below each diff hunk."""
        raw_value = os.getenv("AI_DIFF_CONTEXT_LINES", "12")
        try:
            return max(2, min(int(raw_value), 100))
        except (TypeError, ValueError):
            return 12

    def _resolve_max_ai_hunks(self) -> int:
        """Resolve maximum number of diff hunks sent to AI in one request."""
        raw_value = os.getenv("AI_MAX_HUNKS", "250")
        try:
            return max(1, min(int(raw_value), 1000))
        except (TypeError, ValueError):
            return 250

    def _resolve_minimum_required_severity(self) -> str:
        """Resolve minimum severity level that is treated as required."""
        raw_value = str(os.getenv("AI_MIN_REQUIRED_SEVERITY", "low") or "").strip().lower()
        if raw_value in self._SEVERITY_RANK:
            return raw_value
        return "low"

    def _build_code_correction_conversation(
        self,
        diffs: List[Dict[str, Any]],
        review_text: str,
    ) -> List[Dict[str, str]]:
        """Create base prompt conversation for code correction generation."""
        serialized_diffs = self._serialize_diffs_for_prompt(diffs)
        normalized_review = (review_text or "").strip()
        if not normalized_review:
            normalized_review = "No pre-existing review notes."
        return [
            {"role": "system", "content": "You are a senior Angular + Django developer."},
            {
                "role": "user",
                "content": (
                    f"{prompts.Code_corrections_prompt}\n\n"
                    "Changed hunks (JSON):\n"
                    f"{serialized_diffs}\n\n"
                    "Review context:\n"
                    f"{normalized_review}"
                ),
            },
        ]

    def _generate_validated_code_changes(
        self,
        base_conversation: List[Dict[str, str]],
        source_hunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate code changes with strict validation and auto-repair retries.

        Returns:
            Dictionary with merged `code_changes`, token metrics, and optional raw output.
        """
        conversation = [dict(item) for item in base_conversation]
        total_tokens_used = 0
        aggregate_usage: Dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "source": "unknown",
        }
        token_sources: List[str] = []
        last_raw_output = ""
        last_error = "Unknown generation error"

        for attempt in range(1, self.max_code_change_attempts + 1):
            response = self.ai_reviewer.get_ai_response(
                conversation=conversation,
                model=self.ai_model,
                max_output_tokens=min(self.max_tokens, 20000),
            )
            total_tokens_used += int(response.get("tokens_used", 0))
            token_sources.append(str(response.get("token_source", "estimated")))
            self._accumulate_token_usage(aggregate_usage, response.get("token_usage"))

            raw_output = str(response.get("response", "") or "")
            last_raw_output = raw_output
            try:
                extracted_json = self.extract_json_from_ai_output(raw_output)
                normalized_payload = self._normalize_generated_diff_payload(extracted_json)
                validated_changes = self.diff_validator.validate(normalized_payload)
                expanded_changes = self._expand_changes_with_context(
                    validated_changes,
                    source_hunks=source_hunks or [],
                )
                merged_changes = self.merge_consecutive_diffs(expanded_changes)
                resolved_source = self._combine_many_token_sources(token_sources)
                aggregate_usage["total_tokens"] = total_tokens_used
                aggregate_usage["source"] = resolved_source
                return {
                    "code_changes": merged_changes,
                    "tokens_used": total_tokens_used,
                    "token_source": resolved_source,
                    "token_usage": aggregate_usage,
                    "raw_response": raw_output if not merged_changes else "",
                }
            except (self.JSONExtractionError, DiffValidationError, ValueError, TypeError) as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "Code correction quality gate failed attempt=%s/%s reason=%s",
                    attempt,
                    self.max_code_change_attempts,
                    last_error,
                )
                if attempt >= self.max_code_change_attempts:
                    break
                conversation = self._extend_correction_conversation_for_retry(
                    base_conversation=conversation,
                    invalid_output=raw_output,
                    validation_error=last_error,
                )

        resolved_source = self._combine_many_token_sources(token_sources)
        aggregate_usage["total_tokens"] = total_tokens_used
        aggregate_usage["source"] = resolved_source
        raise RuntimeError(
            "AI generated invalid correction payloads repeatedly. "
            f"Last validation error: {last_error}. "
            f"Raw response sample: {last_raw_output[:400]}"
        )

    def _extend_correction_conversation_for_retry(
        self,
        *,
        base_conversation: List[Dict[str, str]],
        invalid_output: str,
        validation_error: str,
    ) -> List[Dict[str, str]]:
        """Append correction feedback prompt to recover invalid AI JSON outputs."""
        retry_prompt = (
            "Your previous response failed validation.\n"
            f"Validation error: {validation_error}\n\n"
            "Return ONLY valid JSON matching the required schema.\n"
            "Rules:\n"
            "- No markdown fences.\n"
            "- No prose outside JSON.\n"
            "- Include full `diff` objects with all required fields.\n"
            "- Keep each replacement block complete and syntactically valid.\n"
            "- Do not omit `categories`, `explanation`, or `comments`.\n"
            "- If no required fixes exist, return exactly {\"diffs\":[]}.\n\n"
            "Invalid previous output sample:\n"
            f"{(invalid_output or '{}')[:4000]}"
        )
        return base_conversation + [{"role": "user", "content": retry_prompt}]

    def _accumulate_token_usage(self, aggregate: Dict[str, Any], usage: Any) -> None:
        """Accumulate input/output token counters across multiple AI attempts."""
        usage_obj = usage if isinstance(usage, dict) else {}
        aggregate["input_tokens"] = int(aggregate.get("input_tokens", 0)) + int(
            usage_obj.get("input_tokens", 0) or 0
        )
        aggregate["output_tokens"] = int(aggregate.get("output_tokens", 0)) + int(
            usage_obj.get("output_tokens", 0) or 0
        )

    def _combine_many_token_sources(self, token_sources: List[str]) -> str:
        """Combine many token sources into a single summary source label."""
        normalized = [str(source or "").strip().lower() for source in token_sources if str(source or "").strip()]
        if not normalized:
            return "unknown"
        if len(set(normalized)) == 1:
            return normalized[0]
        return "mixed"

    def _normalize_generated_diff_payload(self, payload: Any) -> Any:
        """Normalize AI correction payload shapes before strict validation."""
        required_fields = set(getattr(self.diff_validator, "REQUIRED_DIFF_FIELDS", set()))
        diffs = None

        if isinstance(payload, dict) and isinstance(payload.get("diffs"), list):
            diffs = payload.get("diffs")
        elif isinstance(payload, list):
            diffs = payload
        else:
            return payload

        normalized_entries: List[Dict[str, Any]] = []
        for item in diffs:
            if not isinstance(item, dict):
                normalized_entries.append(item)
                continue

            if isinstance(item.get("diff"), dict):
                normalized_entries.append(item)
                continue

            if required_fields and required_fields.issubset(set(item.keys())):
                normalized_entries.append(
                    {
                        "diff": item,
                        "categories": ["medium"],
                        "explanation": "AI suggested required fix.",
                        "comments": "",
                    }
                )
                continue

            normalized_entries.append(item)

        if isinstance(payload, dict):
            updated_payload = dict(payload)
            updated_payload["diffs"] = normalized_entries
            return updated_payload
        return normalized_entries

    def _serialize_diffs_for_prompt(self, diffs: List[Dict[str, Any]]) -> str:
        """Serialize AI diff context to compact JSON for lower prompt token usage."""
        compact_payload: List[Dict[str, Any]] = []
        for hunk in (diffs or [])[: self.max_ai_hunks]:
            if not isinstance(hunk, dict):
                continue
            compact_payload.append(
                {
                    "file_path": hunk.get("file_path"),
                    "hunk_index": hunk.get("hunk_index"),
                    "old_start_line": hunk.get("old_start_line"),
                    "old_end_line": hunk.get("old_end_line"),
                    "new_start_line": hunk.get("new_start_line"),
                    "new_end_line": hunk.get("new_end_line"),
                    "context_before": hunk.get("context_before", []),
                    "changed_old_block": hunk.get("changed_old_block", []),
                    "changed_new_block": hunk.get("changed_new_block", []),
                    "context_after": hunk.get("context_after", []),
                }
            )
        return json.dumps(compact_payload, separators=(",", ":"), ensure_ascii=False)

    def _retain_required_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop non-required, duplicate, or no-op changes before returning to UI/apply flow."""
        result: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, int, int, str, str]] = set()
        minimum_rank = self._SEVERITY_RANK.get(self.minimum_required_severity, 2)

        for entry in changes or []:
            if not isinstance(entry, dict):
                continue
            diff = entry.get("diff")
            if not isinstance(diff, dict):
                continue

            categories = entry.get("categories")
            normalized_categories = [
                str(item or "").strip().lower()
                for item in (categories or [])
                if str(item or "").strip().lower() in self._SEVERITY_RANK
            ]
            effective_severity = normalized_categories[0] if normalized_categories else "medium"
            if self._SEVERITY_RANK.get(effective_severity, 2) > minimum_rank:
                continue

            old_content = str(diff.get("old_content", "") or "")
            new_content = str(diff.get("new_content", "") or "")
            if not old_content.strip() and not new_content.strip():
                continue
            if old_content.replace("\r\n", "\n").strip() == new_content.replace("\r\n", "\n").strip():
                continue

            file_path = str(diff.get("file_path", "") or "").strip().lstrip("/\\")
            old_start = self._safe_int(diff.get("old_start_line_number")) or 1
            new_start = self._safe_int(diff.get("new_start_line_number")) or old_start
            dedupe_key = (
                file_path,
                old_start,
                new_start,
                old_content.strip(),
                new_content.strip(),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            normalized_entry = dict(entry)
            normalized_entry["categories"] = normalized_categories or ["medium"]
            normalized_entry["diff"] = dict(diff)
            normalized_entry["diff"]["file_path"] = file_path
            result.append(normalized_entry)

        return result

    def _normalize_review_with_status(self, review_text: str, *, no_changes_required: bool) -> str:
        """Append a deterministic resolution status block for UI clarity."""
        normalized = self._normalize_review_markdown(review_text or "")
        if no_changes_required:
            status_block = "## Resolution Status\n\nNo required code changes detected."
            if status_block not in normalized:
                normalized = f"{normalized}\n\n{status_block}".strip()
        return normalized

    def _merge_usage_objects(self, first: Any, second: Any) -> Dict[str, Any]:
        """Merge two token usage payloads while preserving conservative totals."""
        left = first if isinstance(first, dict) else {}
        right = second if isinstance(second, dict) else {}
        merged_input = int(left.get("input_tokens", 0) or 0) + int(right.get("input_tokens", 0) or 0)
        merged_output = int(left.get("output_tokens", 0) or 0) + int(right.get("output_tokens", 0) or 0)
        merged_total = int(left.get("total_tokens", 0) or 0) + int(right.get("total_tokens", 0) or 0)
        return {
            "input_tokens": merged_input,
            "output_tokens": merged_output,
            "total_tokens": merged_total,
            "source": self._combine_many_token_sources(
                [
                    str(left.get("source", "") or ""),
                    str(right.get("source", "") or ""),
                ]
            ),
        }

    def _prepare_diffs_for_ai(self, diffs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert raw local/PR diffs into AI-ready contextual blocks.

        Each hunk includes:
        - code block above diff start (`context_before`)
        - changed old/new blocks
        - code block below diff end (`context_after`)
        """
        prepared: List[Dict[str, Any]] = []
        for item in diffs or []:
            if not isinstance(item, dict):
                continue

            file_path = str(item.get("file") or item.get("file_path") or "").strip().lstrip("/\\")
            if not file_path:
                continue

            for hunk_index, hunk in enumerate(self._extract_hunks(item), start=1):
                normalized = self._normalize_hunk_for_ai(file_path=file_path, hunk=hunk, hunk_index=hunk_index)
                if normalized:
                    prepared.append(normalized)
                if len(prepared) >= self.max_ai_hunks:
                    return prepared
        return prepared

    def _extract_hunks(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract hunks from local (`hunks`) and Azure (`hunk`) payload shapes."""
        if isinstance(item.get("hunks"), list):
            return [hunk for hunk in item.get("hunks", []) if isinstance(hunk, dict)]
        if isinstance(item.get("hunk"), dict):
            return [item["hunk"]]
        return []

    def _normalize_hunk_for_ai(
        self,
        *,
        file_path: str,
        hunk: Dict[str, Any],
        hunk_index: int,
    ) -> Dict[str, Any] | None:
        """Normalize one hunk into a complete contextual block for AI prompts."""
        old_start = self._safe_int(hunk.get("old_start"))
        new_start = self._safe_int(hunk.get("new_start"))
        removed_lines = self._extract_code_lines(hunk.get("removed"))
        added_lines = self._extract_code_lines(hunk.get("added"))
        context_before = self._extract_context_lines(hunk.get("context_before"), tail=True)
        context_after = self._extract_context_lines(hunk.get("context_after"), tail=False)

        if not context_before and not context_after:
            legacy_context = self._extract_context_lines(hunk.get("context"), tail=False)
            before_legacy, after_legacy = self._split_legacy_context(legacy_context)
            if before_legacy:
                context_before = before_legacy[-self.ai_context_window_lines :]
            if after_legacy:
                context_after = after_legacy[: self.ai_context_window_lines]

        if not removed_lines and not added_lines:
            return None

        old_end = None
        if old_start is not None:
            removed_count = max(len(removed_lines), 1)
            old_end = old_start + removed_count - 1

        new_end = None
        if new_start is not None:
            added_count = max(len(added_lines), 1)
            new_end = new_start + added_count - 1

        return {
            "file_path": file_path,
            "hunk_index": hunk_index,
            "old_start_line": old_start,
            "old_end_line": old_end,
            "new_start_line": new_start,
            "new_end_line": new_end,
            "context_before": context_before,
            "changed_old_block": removed_lines,
            "changed_new_block": added_lines,
            "context_after": context_after,
        }

    def _extract_context_lines(self, value: Any, *, tail: bool) -> List[str]:
        """Normalize context entries into plain line arrays with window cap."""
        if not isinstance(value, list):
            return []

        lines: List[str] = []
        for entry in value:
            if isinstance(entry, dict):
                line_value = entry.get("line", "")
            else:
                line_value = entry
            text = str(line_value or "")
            lines.append(text)

        if tail:
            return lines[-self.ai_context_window_lines :]
        return lines[: self.ai_context_window_lines]

    def _extract_code_lines(self, value: Any) -> List[str]:
        """Normalize added/removed line collections into plain text lines."""
        if not isinstance(value, list):
            return []
        lines: List[str] = []
        for entry in value:
            if isinstance(entry, dict):
                text = str(entry.get("line", "") or "")
            else:
                text = str(entry or "")
            lines.append(text)
        return lines

    def _split_legacy_context(self, context_lines: List[str]) -> tuple[List[str], List[str]]:
        """Split legacy context list into before/after halves when no explicit windows exist."""
        if not context_lines:
            return [], []
        midpoint = len(context_lines) // 2
        return context_lines[:midpoint], context_lines[midpoint:]

    def _safe_int(self, value: Any) -> int | None:
        """Safely parse optional line-number integers."""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _expand_changes_with_context(
        self,
        changes: List[Dict[str, Any]],
        *,
        source_hunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Expand AI diffs to full meaningful blocks using before/after context windows."""
        if not changes:
            return []

        expanded: List[Dict[str, Any]] = []
        for entry in changes:
            if not isinstance(entry, dict):
                continue
            expanded_entry = dict(entry)
            diff = dict(expanded_entry.get("diff", {}))
            source_hunk = self._match_source_hunk(diff, source_hunks)
            if source_hunk is not None:
                diff = self._expand_single_diff(diff, source_hunk)
            expanded_entry["diff"] = diff
            expanded.append(expanded_entry)
        return expanded

    def _match_source_hunk(
        self,
        diff: Dict[str, Any],
        source_hunks: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Find nearest source hunk for one generated diff based on file path and line anchors."""
        file_path = str(diff.get("file_path", "") or "").strip().lstrip("/\\")
        if not file_path:
            return None

        old_start = self._safe_int(diff.get("old_start_line_number")) or self._safe_int(diff.get("line_number")) or 1
        best: Optional[Dict[str, Any]] = None
        best_distance: Optional[int] = None
        for source in source_hunks:
            if not isinstance(source, dict):
                continue
            if str(source.get("file_path", "")).strip().lstrip("/\\") != file_path:
                continue
            source_old_start = self._safe_int(source.get("old_start_line")) or old_start
            distance = abs(source_old_start - old_start)
            if best is None or best_distance is None or distance < best_distance:
                best = source
                best_distance = distance
        return best

    def _expand_single_diff(
        self,
        diff: Dict[str, Any],
        source_hunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply source before/after context around generated old/new diff blocks."""
        context_before = [line for line in source_hunk.get("context_before", []) if isinstance(line, str)]
        context_after = [line for line in source_hunk.get("context_after", []) if isinstance(line, str)]

        old_lines = self._split_code_lines(diff.get("old_content", ""))
        new_lines = self._split_code_lines(diff.get("new_content", ""))

        old_start = self._safe_int(diff.get("old_start_line_number")) or self._safe_int(diff.get("line_number")) or 1
        new_start = self._safe_int(diff.get("new_start_line_number")) or self._safe_int(diff.get("line_number")) or 1

        if context_before:
            if not self._has_context_prefix(old_lines, context_before):
                old_lines = context_before + old_lines
                old_start = max(1, old_start - len(context_before))
            if not self._has_context_prefix(new_lines, context_before):
                new_lines = context_before + new_lines
                new_start = max(1, new_start - len(context_before))

        if context_after:
            if not self._has_context_suffix(old_lines, context_after):
                old_lines = old_lines + context_after
            if not self._has_context_suffix(new_lines, context_after):
                new_lines = new_lines + context_after

        diff["old_content"] = self._join_code_lines(old_lines)
        diff["new_content"] = self._join_code_lines(new_lines)
        diff["old_start_line_number"] = old_start
        diff["new_start_line_number"] = new_start
        diff["line_number"] = new_start
        diff["number_of_lines_removed_from_old"] = len(old_lines)
        diff["number_of_lines_added_in_new"] = len(new_lines)
        return diff

    def _split_code_lines(self, content: Any) -> List[str]:
        """Split code block into normalized lines."""
        text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
        if text == "":
            return []
        return text.split("\n")

    def _join_code_lines(self, lines: List[str]) -> str:
        """Join normalized code lines to multiline string."""
        return "\n".join(lines)

    def _has_context_prefix(self, block_lines: List[str], context_lines: List[str]) -> bool:
        """Check whether block already starts with the tail of context_before."""
        if not block_lines or not context_lines:
            return False
        window = min(3, len(context_lines), len(block_lines))
        return (
            block_lines[:window] == context_lines[:window]
            or block_lines[:window] == context_lines[-window:]
        )

    def _has_context_suffix(self, block_lines: List[str], context_lines: List[str]) -> bool:
        """Check whether block already ends with the head of context_after."""
        if not block_lines or not context_lines:
            return False
        window = min(3, len(context_lines), len(block_lines))
        return block_lines[-window:] == context_lines[:window]

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

    def _collect_or_generate_review(self, diffs: List[Dict[str, Any]]) -> tuple[str, int, str]:
        """
        Return review text from existing PR comments or AI generation.

        Args:
            diffs: Structured diffs.

        Returns:
            Tuple of (review_text, tokens_used).
        """
        if self.is_local:
            return self._generate_ai_review(diffs)

        existing_review = ""
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
                    existing_review = review
                    LOGGER.info("Using existing PR comments as additional AI review context")
        except Exception:
            LOGGER.exception("Unable to fetch PR comments, continuing with AI review only")

        try:
            return self._generate_ai_review(diffs, existing_review_context=existing_review)
        except Exception:
            if existing_review:
                LOGGER.exception("AI review failed, falling back to existing PR comments")
                return self._normalize_review_markdown(existing_review), 0, "existing_pr_comments"
            raise

    def _generate_ai_review(
        self,
        diffs: List[Dict[str, Any]],
        existing_review_context: str = "",
    ) -> tuple[str, int, str]:
        """Generate review text from AI model."""
        serialized_diffs = self._serialize_diffs_for_prompt(diffs)
        existing_context_block = ""
        if existing_review_context.strip():
            existing_context_block = (
                "\n\nExisting PR reviewer comments (use as additional context, do not copy blindly):\n"
                f"{existing_review_context.strip()}"
            )
        conversation = [
            {"role": "system", "content": "You are a code review assistant."},
            {
                "role": "user",
                "content": (
                    f"{prompts.Review_prompt}\n\n"
                    "Diffs to review (JSON):\n"
                    f"{serialized_diffs}"
                    f"{existing_context_block}"
                ),
            },
        ]
        review_data = self.ai_reviewer.get_ai_response(
            conversation=conversation,
            model=self.ai_model,
            max_output_tokens=min(self.max_tokens, 20000),
        )
        normalized_review = self._normalize_review_markdown(review_data.get("response", ""))
        return (
            normalized_review,
            int(review_data.get("tokens_used", 0)),
            str(review_data.get("token_source", "estimated")),
        )

    def _combine_token_source(self, review_token_source: str, changes_token_source: str) -> str:
        """Combine token source labels for full-review telemetry."""
        if review_token_source == "existing_pr_comments":
            return changes_token_source
        if review_token_source == changes_token_source:
            return review_token_source
        return "mixed"

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
