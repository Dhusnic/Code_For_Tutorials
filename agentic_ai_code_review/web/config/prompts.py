"""Prompt templates and standards loading for AI review workflows."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

LOGGER = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent
STANDARDS_FILE = CONFIG_DIR / "standards.yaml"

Review_prompt = """
You are a senior code review assistant.

Scope:
- Analyze only changed lines from the provided diff payload.
- Use `context_before` and `context_after` only to understand the changed block.
- Do not review unchanged code.

Objective:
- Identify only required issues (correctness, security, reliability, breaking behavior).
- Skip style-only, optional refactors, and low-value suggestions.

Output format:
- Return GitHub-flavored Markdown.
- Group findings by file using `## File: <path>`.
- For each finding include exactly these fields:
  - **Severity**
  - **Category**
  - **Issue**
  - **Current Code**
  - **Enterprise Correction**
  - **Rationale**
- Use fenced code blocks with language tags for code snippets.
- Keep formatting consistent and readable for direct UI rendering.
- If no required changes are needed, return exactly:
  `## AI Review`
  `No required changes.`
"""


def load_standards() -> Dict[str, Any]:
    """
    Load standards configuration used in correction prompts.

    Returns:
        Parsed standards dictionary.
    """
    try:
        with STANDARDS_FILE.open("r", encoding="utf-8") as standards_file:
            return yaml.safe_load(standards_file) or {}
    except FileNotFoundError:
        LOGGER.warning("Standards file not found at %s", STANDARDS_FILE)
        return {}
    except Exception:
        LOGGER.exception("Failed to load standards configuration")
        return {}


_include_standards = os.getenv("AI_INCLUDE_STANDARDS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_standards_block = ""
if _include_standards:
    _standards = load_standards()
    _standards_block = yaml.safe_dump(
        _standards.get("standards", {}),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    ).strip()

Code_corrections_prompt = """
Return apply-ready code corrections for the provided changed hunks.

Critical rules:
- Output ONLY valid JSON object: {"diffs":[...]}.
- No markdown fences.
- No prose outside JSON.
- Include actionable fixes (critical/high/medium/low).
- Avoid cosmetic-only suggestions without concrete code impact.
- If truly no actionable fixes are needed, return exactly: {"diffs":[]}.
- If review context contains concrete findings, return at least one diff.

Each diff item must keep this structure:
- diff.file_path
- diff.line_number
- diff.new_start_line_number
- diff.change_type (added|removed|modified)
- diff.new_content
- diff.old_content
- diff.old_start_line_number
- diff.number_of_lines_removed_from_old
- diff.number_of_lines_added_in_new
- categories
- explanation
- comments

Use `context_before` and `context_after` only for accurate block reconstruction.
Every `new_content` must be a complete, runnable replacement block for the target range.
""".strip()

if _standards_block:
    Code_corrections_prompt = (
        f"{Code_corrections_prompt}\n\nStandards:\n{_standards_block}"
    )
