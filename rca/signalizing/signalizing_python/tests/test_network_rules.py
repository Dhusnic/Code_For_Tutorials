"""Tests for multi-vendor network rule matching."""

from __future__ import annotations

from pathlib import Path

from src.rules.rule_engine import RuleEngine
from src.rules.rule_loader import RuleLoader


def _load_network_rules():
    loader = RuleLoader(str(Path(__file__).resolve().parents[2] / "rules"))
    return loader.load("network", "services/network.yml")


def test_network_critical_syslog_severity_matches_fallback() -> None:
    event = {
        "message": "generic network fault without specific signature",
        "log": {"syslog": {"severity": {"code": 2, "name": "critical"}}},
    }
    signals = RuleEngine().evaluate(
        event,
        _load_network_rules(),
        highest_only=True,
        max_signals=1,
    )

    assert signals
    assert signals[0]["signal"] == "network_unclassified_failure"
    assert signals[0]["level"] == "critical"


def test_network_specific_link_down_preferred_over_fallback() -> None:
    event = {
        "message": "GigabitEthernet0/1 line protocol is down",
        "log": {"syslog": {"severity": {"code": 2, "name": "critical"}}},
    }
    signals = RuleEngine().evaluate(
        event,
        _load_network_rules(),
        highest_only=True,
        max_signals=1,
    )

    assert signals
    assert signals[0]["signal"] == "network_link_down"


def test_network_notice_without_pattern_has_no_signal() -> None:
    event = {
        "message": "Test log facility daemon severity warning random id 3169",
        "log": {"syslog": {"severity": {"code": 5, "name": "notice"}}},
    }
    signals = RuleEngine().evaluate(
        event,
        _load_network_rules(),
        highest_only=True,
        max_signals=1,
    )

    assert signals == []
