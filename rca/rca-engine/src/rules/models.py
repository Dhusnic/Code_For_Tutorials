"""Rule model definitions for YAML signal rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias


@dataclass(slots=True)
class RuleCondition:
    """Single condition statement in a rule."""

    field: str
    op: str
    value: Any = None
    case_sensitive: bool = False


@dataclass(slots=True)
class RuleConditionGroup:
    """Logical group of conditions using AND/OR semantics."""

    op: str
    conditions: list["ConditionNode"] = field(default_factory=list)


ConditionNode: TypeAlias = RuleCondition | RuleConditionGroup


@dataclass(slots=True)
class SignalRule:
    """In-memory representation of a matching rule."""

    rule_id: str
    signal_key: str
    level: str
    description: str
    condition: ConditionNode | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RuleSet:
    """Rule set bound to one service."""

    service: str
    rules: list[SignalRule] = field(default_factory=list)
