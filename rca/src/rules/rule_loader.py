"""Load service rule sets from YAML files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.rules.models import ConditionNode, RuleCondition, RuleConditionGroup, RuleSet, SignalRule
from src.rules.schema_validator import RuleSchemaValidator


class RuleLoader:
    """Read YAML files, validate schema, and cache parsed rule sets by file mtime."""

    def __init__(self, rules_directory: str) -> None:
        self._rules_directory = Path(rules_directory)
        self._validator = RuleSchemaValidator()
        self._cache: dict[Path, tuple[int, RuleSet]] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self, service: str, file_name: str) -> RuleSet:
        """Load a rule file for one service, using cache when file is unchanged."""
        path = self._rules_directory / file_name
        mtime_ns = self._get_mtime_ns(path)

        cached = self._cache.get(path)
        if cached and cached[0] == mtime_ns:
            self._logger.debug("Using cached rules", extra={"service": service, "rule_file": str(path)})
            return cached[1]

        rule_set = self._load_uncached(path, service)
        self._cache[path] = (mtime_ns, rule_set)
        self._logger.info(
            "Rule file loaded",
            extra={
                "service": rule_set.service,
                "rule_file": str(path),
                "rule_count": len(rule_set.rules),
                "from_cache": False,
            },
        )
        return rule_set

    def _load_uncached(self, path: Path, service: str) -> RuleSet:
        """Read and parse rule file from disk."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            self._logger.exception("Failed reading rule file", extra={"service": service, "rule_file": str(path)})
            raise

        if not isinstance(raw, dict):
            raise ValueError(f"Rule file must contain mapping: {path}")

        try:
            self._validator.validate(raw, str(path))
        except Exception:
            self._logger.exception(
                "Rule schema validation failed",
                extra={"service": service, "rule_file": str(path)},
            )
            raise

        service_name = raw.get("service", service)
        rules: list[SignalRule] = []

        try:
            for item in raw.get("rules", []):
                condition = self._parse_rule_condition(item)
                rules.append(
                    SignalRule(
                        rule_id=item["id"],
                        signal_key=item["signal_key"],
                        level=item["level"],
                        description=item.get("description", item["id"]),
                        condition=condition,
                        tags=item.get("tags", []),
                    )
                )
        except Exception:
            self._logger.exception(
                "Rule parsing failed",
                extra={"service": service_name, "rule_file": str(path)},
            )
            raise

        return RuleSet(service=service_name, rules=rules)

    @staticmethod
    def _get_mtime_ns(path: Path) -> int:
        """Return file modification timestamp in nanoseconds."""
        try:
            return path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise ValueError(f"Rule file not found: {path}") from exc

    def _parse_rule_condition(self, rule_raw: dict[str, Any]) -> ConditionNode:
        """Parse nested strict `condition` tree."""
        return self._parse_condition_node(rule_raw["condition"])

    def _parse_condition_node(self, node_raw: dict[str, Any]) -> ConditionNode:
        if "and" in node_raw:
            children = [self._parse_condition_node(child) for child in node_raw["and"]]
            return RuleConditionGroup(op="and", conditions=children)
        if "or" in node_raw:
            children = [self._parse_condition_node(child) for child in node_raw["or"]]
            return RuleConditionGroup(op="or", conditions=children)
        return self._parse_condition_leaf(node_raw)

    @staticmethod
    def _parse_condition_leaf(cond: dict[str, Any]) -> RuleCondition:
        return RuleCondition(
            field=cond["field"],
            op=cond["op"],
            value=cond.get("value"),
            case_sensitive=cond.get("case_sensitive", False),
        )
