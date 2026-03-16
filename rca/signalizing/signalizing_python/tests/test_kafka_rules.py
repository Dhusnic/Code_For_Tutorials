"""Tests for Kafka rule behavior against shared rule files."""

from __future__ import annotations

from pathlib import Path

from src.rules.rule_engine import RuleEngine
from src.rules.rule_loader import RuleLoader


def _load_kafka_rules():
    loader = RuleLoader(str(Path(__file__).resolve().parents[2] / "rules"))
    return loader.load("kafka", "services/kafka.yml")


def test_active_controller_invalid_does_not_match_when_fields_are_missing() -> None:
    event = {
        "message": "kafka broker healthy",
        "log": {"level": "INFO"},
    }

    signals = RuleEngine().evaluate(
        event,
        _load_kafka_rules(),
        highest_only=True,
        max_signals=5,
    )

    assert all(signal["signal"] != "kafka_active_controller_invalid" for signal in signals)


def test_active_controller_invalid_matches_when_present_value_is_not_one() -> None:
    event = {
        "kafka": {
            "metrics": {
                "controller": {
                    "active_controller_count": 0,
                }
            }
        }
    }

    signals = RuleEngine().evaluate(
        event,
        _load_kafka_rules(),
        highest_only=True,
        max_signals=5,
    )

    assert any(signal["signal"] == "kafka_active_controller_invalid" for signal in signals)
