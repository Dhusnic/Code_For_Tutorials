"""Prompt templates and standards loading for AI review workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

LOGGER = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent
STANDARDS_FILE = CONFIG_DIR / "standards.yaml"

Review_prompt = """
You are a Principal Angular + Django Architect performing enterprise-grade code review.

Scope:
- Analyze only changed lines from provided diff payload.
- Do not review unchanged code.
- Do not infer missing implementation details.

Objective:
- Identify correctness, security, reliability, performance, and maintainability issues.
- Provide concrete, production-grade replacement code for each finding.
- Keep reasoning concise and technical.

Output format:
- Return ONLY valid GitHub-flavored Markdown.
- Do not return JSON, XML, HTML, or plain text outside Markdown structure.
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


_standards = load_standards()
Code_corrections_prompt = (
    "Provide structured code corrections based on the standards below. "
    "Output must be valid JSON.\n"
    "Each `diff.new_content` must be a complete, syntactically valid replacement block "
    "for the specified old range, and must preserve correct line boundaries "
    "(avoid inline concatenation with neighboring code).\n\n"
    f"{_standards.get('standards', {})}"
)
