"""Tests for rule engine behavior."""

from src.rules.models import RuleCondition, RuleConditionGroup, RuleSet, SignalRule
from src.rules.rule_engine import RuleEngine


def test_matches_multiple_rules() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="nginx",
        rules=[
            SignalRule(
                rule_id="A",
                signal_key="upstream_timeout",
                level="critical",
                description="contains timeout",
                condition=RuleCondition(field="message", op="contains", value="timeout"),
            ),
            SignalRule(
                rule_id="B",
                signal_key="server_error",
                level="warning",
                description="status high",
                condition=RuleCondition(field="http.response.status_code", op="gte", value=500),
            ),
        ],
    )

    event = {
        "message": "upstream timeout while connecting",
        "http": {"response": {"status_code": 502}},
    }

    signals = engine.evaluate(event, rule_set)
    assert len(signals) == 2
    assert signals[0]["signal"] == "upstream_timeout"


def test_nested_any_all_rule() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="rabbitmq",
        rules=[
            SignalRule(
                rule_id="C",
                signal_key="memory_alarm",
                level="critical",
                description="nested condition",
                condition=RuleConditionGroup(
                    op="and",
                    conditions=[
                        RuleCondition(field="message", op="contains", value="alarm"),
                        RuleConditionGroup(
                            op="or",
                            conditions=[
                                RuleCondition(field="log.level", op="equals", value="CRITICAL"),
                                RuleCondition(field="rabbitmq.node.mem.alarm", op="equals", value=True),
                            ],
                        ),
                    ],
                ),
            )
        ],
    )

    event = {
        "message": "queue memory alarm active",
        "log": {"level": "INFO"},
        "rabbitmq": {"node": {"mem": {"alarm": True}}},
    }

    signals = engine.evaluate(event, rule_set)
    assert len(signals) == 1


def test_strict_negative_ops() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="nginx",
        rules=[
            SignalRule(
                rule_id="D",
                signal_key="upstream_issue",
                level="warning",
                description="not contains",
                condition=RuleConditionGroup(
                    op="and",
                    conditions=[
                        RuleCondition(field="message", op="contains", value="nginx"),
                        RuleCondition(field="message", op="not_contains", value="healthy"),
                    ],
                ),
            )
        ],
    )

    event = {"message": "nginx upstream timeout"}
    signals = engine.evaluate(event, rule_set)
    assert len(signals) == 1


def test_highest_only_and_max_two() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="nginx",
        rules=[
            SignalRule(
                rule_id="LOW",
                signal_key="degraded",
                level="warning",
                description="warning match",
                condition=RuleCondition(field="message", op="contains", value="down"),
            ),
            SignalRule(
                rule_id="HIGH_A",
                signal_key="service_down",
                level="critical",
                description="critical match a",
                condition=RuleCondition(field="message", op="contains", value="down"),
            ),
            SignalRule(
                rule_id="HIGH_B",
                signal_key="dependency_down",
                level="critical",
                description="critical match b",
                condition=RuleCondition(field="message", op="contains", value="down"),
            ),
            SignalRule(
                rule_id="HIGH_C",
                signal_key="backend_down",
                level="critical",
                description="critical match c",
                condition=RuleCondition(field="message", op="contains", value="down"),
            ),
        ],
    )

    event = {"message": "service down"}
    signals = engine.evaluate(event, rule_set, max_signals=2, highest_only=True)
    assert len(signals) == 2
    assert all(item["level"] == "critical" for item in signals)
