"""Evaluate source events against service rules."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.rules.models import ConditionNode, RuleCondition, RuleConditionGroup, RuleSet, SignalRule
from src.utils.dicts import get_nested


class RuleEngine:
    """Evaluate all rules and return matching signals."""

    def evaluate(
        self,
        event: dict[str, Any],
        rule_set: RuleSet,
        *,
        max_signals: int = 0,
        highest_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return all matched signals for the provided event."""
        scored_matches: list[tuple[int, int, dict[str, Any]]] = []
        for rule in rule_set.rules:
            matched, matched_count = self._matches_rule(event, rule)
            if not matched:
                continue
            severity = self._severity_rank(rule.level)
            scored_matches.append(
                (
                    severity,
                    matched_count,
                    {
                        "rule_id": rule.rule_id,
                        "signal": rule.signal_key,
                        "level": rule.level,
                        "description": rule.description,
                        "service": rule_set.service,
                        "tags": rule.tags,
                        "matched_at": datetime.now(timezone.utc).isoformat(),
                        "matched_condition_count": matched_count,
                    },
                )
            )

        if not scored_matches:
            return []

        scored_matches = self._prefer_specific_matches(scored_matches)

        if highest_only:
            best_severity = max(item[0] for item in scored_matches)
            scored_matches = [item for item in scored_matches if item[0] == best_severity]

        scored_matches.sort(key=lambda item: (item[0], item[1], item[2]["rule_id"]), reverse=True)
        signals = [item[2] for item in scored_matches]

        if max_signals > 0:
            return signals[:max_signals]
        return signals

    @classmethod
    def _prefer_specific_matches(
        cls,
        scored_matches: list[tuple[int, int, dict[str, Any]]],
    ) -> list[tuple[int, int, dict[str, Any]]]:
        """Drop fallback matches when any non-fallback match exists."""
        has_non_fallback = any(not cls._is_fallback_signal(item[2]) for item in scored_matches)
        if not has_non_fallback:
            return scored_matches
        return [item for item in scored_matches if not cls._is_fallback_signal(item[2])]

    @staticmethod
    def _is_fallback_signal(signal: dict[str, Any]) -> bool:
        """Return True when signal is marked as fallback/unclassified."""
        tags = signal.get("tags")
        if isinstance(tags, list):
            lowered = {str(tag).strip().lower() for tag in tags}
            if "fallback" in lowered:
                return True
            if "unclassified" in lowered:
                return True
        signal_key = str(signal.get("signal", "")).strip().lower()
        return signal_key.endswith("_unclassified_failure")

    def _matches_rule(self, event: dict[str, Any], rule: SignalRule) -> tuple[bool, int]:
        if not rule.condition:
            return False, 0
        return self._matches_node(event, rule.condition)

    def _matches_node(self, event: dict[str, Any], node: ConditionNode) -> tuple[bool, int]:
        if isinstance(node, RuleConditionGroup):
            if not node.conditions:
                return False, 0
            if node.op.lower() == "or":
                outcomes = [self._matches_node(event, child) for child in node.conditions]
                matched_outcomes = [item for item in outcomes if item[0]]
                if not matched_outcomes:
                    return False, 0
                # For OR, retain the strongest satisfied branch as score.
                return True, max(item[1] for item in matched_outcomes)
            outcomes = [self._matches_node(event, child) for child in node.conditions]
            if not all(item[0] for item in outcomes):
                return False, 0
            # For AND, all sub-conditions contribute to match strength.
            return True, sum(item[1] for item in outcomes)
        matched = self._matches_condition(event, node)
        return matched, 1 if matched else 0

    def _matches_condition(self, event: dict[str, Any], condition: RuleCondition) -> bool:
        value = get_nested(event, condition.field)
        op = condition.op.lower()

        if op == "exists":
            return value is not None
        if op == "equals":
            return value == condition.value
        if op == "not_equals":
            return value != condition.value
        if op == "contains":
            return self._contains(value, condition.value, condition.case_sensitive)
        if op == "not_contains":
            return not self._contains(value, condition.value, condition.case_sensitive)
        if op == "regex":
            return self._regex(value, condition.value, condition.case_sensitive)
        if op == "not_regex":
            return not self._regex(value, condition.value, condition.case_sensitive)
        if op == "in":
            if not isinstance(condition.value, list):
                return False
            return value in condition.value
        if op == "not_in":
            if not isinstance(condition.value, list):
                return False
            return value not in condition.value
        if op in {"gt", "gte", "lt", "lte"}:
            return self._compare_numeric(value, condition.value, op)

        return False

    @staticmethod
    def _contains(left: Any, right: Any, case_sensitive: bool) -> bool:
        if left is None:
            return False
        left_s = str(left)
        right_s = str(right)
        if case_sensitive:
            return right_s in left_s
        return right_s.lower() in left_s.lower()

    @staticmethod
    def _regex(left: Any, pattern: Any, case_sensitive: bool) -> bool:
        if left is None:
            return False
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(str(pattern), str(left), flags=flags) is not None

    def _compare_numeric(self, left: Any, right: Any, op: str) -> bool:
        try:
            left_n = float(left)
            right_n = float(right)
        except (TypeError, ValueError):
            return False

        if op == "gt":
            return left_n > right_n
        if op == "gte":
            return left_n >= right_n
        if op == "lt":
            return left_n < right_n
        return left_n <= right_n

    @staticmethod
    def _severity_rank(level: str) -> int:
        normalized = level.lower()
        if normalized == "critical":
            return 3
        if normalized == "warning":
            return 2
        if normalized == "info":
            return 1
        return 0
