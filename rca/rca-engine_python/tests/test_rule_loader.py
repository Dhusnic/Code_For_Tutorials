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


def test_rule_loader_loads_imported_rule_files(tmp_path) -> None:
    base_file = tmp_path / "network.yml"
    vendor_file = tmp_path / "vendor.yml"

    base_file.write_text(
        """
service: network
imports:
  - vendor.yml
rules:
  - id: BASE_RULE
    signal_key: network_base_rule
    level: warning
    condition:
      field: message
      op: contains
      value: base
""",
        encoding="utf-8",
    )
    vendor_file.write_text(
        """
service: network
rules:
  - id: VENDOR_RULE
    signal_key: network_vendor_rule
    level: critical
    condition:
      field: message
      op: contains
      value: vendor
""",
        encoding="utf-8",
    )

    loader = RuleLoader(str(tmp_path))
    loaded = loader.load("network", "network.yml")

    assert len(loaded.rules) == 2
    assert {rule.rule_id for rule in loaded.rules} == {"BASE_RULE", "VENDOR_RULE"}


def test_rule_loader_reloads_when_imported_file_changes(tmp_path) -> None:
    base_file = tmp_path / "network.yml"
    vendor_file = tmp_path / "vendor.yml"

    base_file.write_text(
        """
service: network
imports:
  - vendor.yml
rules:
  - id: BASE_RULE
    signal_key: network_base_rule
    level: warning
    condition:
      field: message
      op: contains
      value: base
""",
        encoding="utf-8",
    )
    vendor_file.write_text(
        """
service: network
rules:
  - id: VENDOR_RULE_1
    signal_key: network_vendor_rule_1
    level: critical
    condition:
      field: message
      op: contains
      value: vendor
""",
        encoding="utf-8",
    )

    loader = RuleLoader(str(tmp_path))
    first = loader.load("network", "network.yml")

    time.sleep(0.02)
    vendor_file.write_text(
        """
service: network
rules:
  - id: VENDOR_RULE_1
    signal_key: network_vendor_rule_1
    level: critical
    condition:
      field: message
      op: contains
      value: vendor
  - id: VENDOR_RULE_2
    signal_key: network_vendor_rule_2
    level: warning
    condition:
      field: message
      op: contains
      value: vendor2
""",
        encoding="utf-8",
    )
    second = loader.load("network", "network.yml")

    assert first is not second
    assert len(second.rules) == 3
