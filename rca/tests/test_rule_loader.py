"""Tests for rule loader caching and reload behavior."""

from __future__ import annotations

import time

from src.rules.rule_loader import RuleLoader


def _write_rules(path: str, rules_count: int) -> None:
    rules = [
        """
service: nginx
rules:
  - id: RULE_A
    signal_key: nginx_timeout
    level: critical
    condition:
      field: message
      op: contains
      value: timeout
"""
    ]
    if rules_count == 2:
        rules.append(
            """
  - id: RULE_B
    signal_key: nginx_5xx
    level: warning
    condition:
      field: http.response.status_code
      op: gte
      value: 500
"""
        )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(rules))


def test_rule_loader_uses_cache_when_file_unchanged(tmp_path) -> None:
    rules_file = tmp_path / "nginx.yml"
    _write_rules(str(rules_file), rules_count=1)
    loader = RuleLoader(str(tmp_path))

    first = loader.load("nginx", "nginx.yml")
    second = loader.load("nginx", "nginx.yml")

    assert first is second
    assert len(second.rules) == 1


def test_rule_loader_reloads_when_file_changes(tmp_path) -> None:
    rules_file = tmp_path / "nginx.yml"
    _write_rules(str(rules_file), rules_count=1)
    loader = RuleLoader(str(tmp_path))

    first = loader.load("nginx", "nginx.yml")
    time.sleep(0.02)
    _write_rules(str(rules_file), rules_count=2)
    second = loader.load("nginx", "nginx.yml")

    assert first is not second
    assert len(second.rules) == 2
