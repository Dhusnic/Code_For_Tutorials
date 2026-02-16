"""Validation for YAML rule schemas."""

from __future__ import annotations

import re
from typing import Any


class RuleSchemaValidator:
    """Validate rule file structure and supported operators."""

    SUPPORTED_OPS = {
        "exists",
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "regex",
        "not_regex",
        "in",
        "not_in",
        "gt",
        "gte",
        "lt",
        "lte",
    }
    SUPPORTED_LEVELS = {"critical", "warning", "info"}

    def validate(self, payload: dict[str, Any], file_name: str) -> None:
        """Raise ValueError when payload does not conform to rule schema."""
        if "rules" not in payload or not isinstance(payload["rules"], list):
            raise ValueError(f"{file_name}: 'rules' must be a list")

        for idx, rule in enumerate(payload["rules"]):
            self._validate_rule(rule, file_name, idx)

    def _validate_rule(self, rule: dict[str, Any], file_name: str, idx: int) -> None:
        prefix = f"{file_name}: rules[{idx}]"
        if not isinstance(rule, dict):
            raise ValueError(f"{prefix} must be an object")

        self._require_type(rule, "id", str, prefix)
        self._require_type(rule, "signal_key", str, prefix)
        self._require_type(rule, "level", str, prefix)

        level = str(rule["level"]).lower()
        if level not in self.SUPPORTED_LEVELS:
            raise ValueError(f"{prefix}.level unsupported: {rule['level']}")
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", rule["signal_key"]):
            raise ValueError(
                f"{prefix}.signal_key must be lowercase snake_case "
                "(example: nginx_upstream_timeout)"
            )

        tags = rule.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError(f"{prefix}.tags must be a list of strings")

        if "condition" not in rule:
            raise ValueError(f"{prefix}.condition is required")
        if "conditions" in rule or "match" in rule:
            raise ValueError(f"{prefix} must not use legacy 'conditions'/'match'; use nested 'condition' only")

        self._validate_condition_node(rule["condition"], f"{prefix}.condition")

    def _validate_condition_node(self, node: Any, prefix: str) -> None:
        if not isinstance(node, dict):
            raise ValueError(f"{prefix} must be an object")

        if "and" in node:
            self._validate_logical_group(node["and"], f"{prefix}.and")
            return
        if "or" in node:
            self._validate_logical_group(node["or"], f"{prefix}.or")
            return

        self._validate_condition_leaf(node, prefix)

    def _validate_logical_group(self, nodes: Any, prefix: str) -> None:
        if not isinstance(nodes, list) or len(nodes) < 2:
            raise ValueError(f"{prefix} must be a list with at least 2 conditions")
        for idx, child in enumerate(nodes):
            self._validate_condition_node(child, f"{prefix}[{idx}]")

    def _validate_condition_leaf(self, cond: dict[str, Any], prefix: str) -> None:
        if not isinstance(cond, dict):
            raise ValueError(f"{prefix} must be an object")

        self._require_type(cond, "field", str, prefix)
        self._require_type(cond, "op", str, prefix)
        op = str(cond["op"]).lower()
        if op not in self.SUPPORTED_OPS:
            raise ValueError(f"{prefix}.op unsupported: {op}")

        if op == "exists":
            if "value" in cond:
                raise ValueError(f"{prefix}.value must not be present for op='exists'")
        elif "value" not in cond:
            raise ValueError(f"{prefix}.value is required for op='{op}'")

        if "case_sensitive" in cond and not isinstance(cond["case_sensitive"], bool):
            raise ValueError(f"{prefix}.case_sensitive must be boolean")

        if op in {"contains", "not_contains", "regex", "not_regex", "equals", "not_equals"}:
            if "value" in cond and not isinstance(cond["value"], (str, int, float, bool)):
                raise ValueError(f"{prefix}.value must be scalar for op='{op}'")

        if op in {"regex", "not_regex"}:
            if not isinstance(cond.get("value"), str):
                raise ValueError(f"{prefix}.value must be string for op='{op}'")
            try:
                re.compile(cond["value"])
            except re.error as exc:
                raise ValueError(f"{prefix}.value invalid regex: {exc}") from exc

        if op in {"in", "not_in"}:
            value = cond.get("value")
            if not isinstance(value, list) or not value:
                raise ValueError(f"{prefix}.value must be non-empty list for op='{op}'")

        if op in {"gt", "gte", "lt", "lte"}:
            if not isinstance(cond.get("value"), (int, float)):
                raise ValueError(f"{prefix}.value must be numeric for op='{op}'")

    @staticmethod
    def _require_type(data: dict[str, Any], key: str, expected_type: type, prefix: str) -> None:
        if key not in data:
            raise ValueError(f"{prefix}.{key} is required")
        if not isinstance(data[key], expected_type):
            raise ValueError(f"{prefix}.{key} must be {expected_type.__name__}")
