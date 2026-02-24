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


def test_fallback_only_used_when_no_specific_rule_matches() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="nginx",
        rules=[
            SignalRule(
                rule_id="A_FALLBACK",
                signal_key="nginx_unclassified_failure",
                level="critical",
                description="fallback",
                tags=["fallback", "unclassified", "critical"],
                condition=RuleCondition(field="log.level", op="equals", value="error"),
            ),
            SignalRule(
                rule_id="Z_SPECIFIC",
                signal_key="nginx_upstream_timeout_connect",
                level="critical",
                description="specific",
                tags=["upstream", "timeout", "connect"],
                condition=RuleCondition(field="message", op="contains", value="upstream timed out"),
            ),
        ],
    )

    event = {"log": {"level": "error"}, "message": "upstream timed out while connecting"}
    signals = engine.evaluate(event, rule_set, highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "nginx_upstream_timeout_connect"


def test_fallback_kept_when_it_is_only_match() -> None:
    engine = RuleEngine()
    rule_set = RuleSet(
        service="nginx",
        rules=[
            SignalRule(
                rule_id="A_FALLBACK",
                signal_key="nginx_unclassified_failure",
                level="critical",
                description="fallback",
                tags=["fallback", "unclassified", "critical"],
                condition=RuleCondition(field="log.level", op="equals", value="error"),
            )
        ],
    )

    event = {"log": {"level": "error"}, "message": "unknown failure text"}
    signals = engine.evaluate(event, rule_set, highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "nginx_unclassified_failure"
