"""Tests for rule schema validation."""

from src.rules.schema_validator import RuleSchemaValidator


def test_valid_rule_schema() -> None:
    validator = RuleSchemaValidator()
    payload = {
        "service": "nginx",
        "rules": [
            {
                "id": "RULE_A",
                "signal_key": "upstream_timeout",
                "level": "critical",
                "condition": {
                    "and": [
                        {"field": "message", "op": "contains", "value": "timeout"},
                        {
                            "or": [
                                {"field": "http.response.status_code", "op": "gte", "value": 500},
                                {"field": "status", "op": "gte", "value": 500},
                            ]
                        },
                    ]
                },
            }
        ],
    }
    validator.validate(payload, "rules/test.yml")


def test_valid_signal_key_multi_underscore() -> None:
    validator = RuleSchemaValidator()
    payload = {
        "service": "nginx",
        "rules": [
            {
                "id": "RULE_MULTI",
                "signal_key": "nginx_upstream_timeout_connect",
                "level": "critical",
                "condition": {"field": "message", "op": "contains", "value": "timeout"},
            }
        ],
    }
    validator.validate(payload, "rules/test.yml")


def test_invalid_missing_value_for_non_exists() -> None:
    validator = RuleSchemaValidator()
    payload = {
        "service": "rabbitmq",
        "rules": [
            {
                "id": "RULE_B",
                "signal_key": "auth_failed",
                "level": "warning",
                "condition": {"field": "message", "op": "contains"},
            }
        ],
    }
    try:
        validator.validate(payload, "rules/test.yml")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert ".value is required" in str(exc)


def test_invalid_condition_tree_group_size() -> None:
    validator = RuleSchemaValidator()
    payload = {
        "service": "nginx",
        "rules": [
            {
                "id": "RULE_C",
                "signal_key": "invalid_req",
                "level": "warning",
                "condition": {
                    "and": [
                        {"field": "message", "op": "contains", "value": "error"}
                    ]
                },
            }
        ],
    }
    try:
        validator.validate(payload, "rules/test.yml")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "at least 2 conditions" in str(exc)
