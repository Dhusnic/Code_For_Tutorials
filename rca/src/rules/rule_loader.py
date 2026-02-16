"""Load service rule sets from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.rules.models import ConditionNode, RuleCondition, RuleConditionGroup, RuleSet, SignalRule
from src.rules.schema_validator import RuleSchemaValidator


class RuleLoader:
    """Read YAML files and convert them to rule objects."""

    def __init__(self, rules_directory: str) -> None:
        self._rules_directory = Path(rules_directory)
        self._validator = RuleSchemaValidator()

    def load(self, service: str, file_name: str) -> RuleSet:
        """Load a rule file for one service."""
        path = self._rules_directory / file_name
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Rule file must contain mapping: {path}")
        self._validator.validate(raw, str(path))

        service_name = raw.get("service", service)
        rules: list[SignalRule] = []

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

        return RuleSet(service=service_name, rules=rules)

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
