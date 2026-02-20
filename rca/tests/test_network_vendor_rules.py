"""Tests for vendor-specific network rules."""

from __future__ import annotations

from src.rules.rule_engine import RuleEngine
from src.rules.rule_loader import RuleLoader


def _load_network_rules():
    loader = RuleLoader("rules")
    return loader.load("network", "services/network.yml")


def _match_signal(event: dict[str, object]) -> str:
    signals = RuleEngine().evaluate(
        event,
        _load_network_rules(),
        highest_only=True,
        max_signals=1,
    )
    assert signals
    return signals[0]["signal"]


def test_cisco_ios_mallocfail_rule_matches() -> None:
    event = {
        "message": "%SYS-2-MALLOCFAIL: Memory allocation of 1048576 bytes failed from 0x1234",
        "log": {"syslog": {"severity": {"code": 2, "name": "critical"}}},
    }
    assert _match_signal(event) == "network_cisco_ios_mallocfail"


def test_juniper_commit_completed_rule_matches() -> None:
    event = {
        "message": "UI_COMMIT_COMPLETED: commit complete",
        "log": {"syslog": {"severity": {"code": 6, "name": "info"}}},
    }
    assert _match_signal(event) == "network_juniper_junos_commit_completed"


def test_fortinet_conserve_mode_rule_matches() -> None:
    event = {
        "message": (
            'date=2026-02-20 time=10:00:00 logid="0100022011" type="event" '
            'subtype="system" level="critical" msg="memory conserve mode entered"'
        ),
        "log": {"syslog": {"severity": {"code": 2, "name": "critical"}}},
    }
    assert _match_signal(event) == "network_fortinet_fortios_conserve_mode"


def test_checkpoint_drop_rule_matches() -> None:
    event = {
        "message": "action=Drop rule=default-deny src=10.0.0.1 dst=8.8.8.8 spt=1234 dpt=53 proto=udp",
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_checkpoint_traffic_drop"


def test_paloalto_traffic_deny_rule_matches() -> None:
    event = {
        "message": (
            "2026/02/20 10:05:00,0123456789,TRAFFIC,end,critical,10.0.0.10,1.1.1.1,"
            "54000,443,tcp,deny,default-deny,inside,outside,ssl,www.example.com"
        ),
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_paloalto_traffic_denied_or_reset"


def test_f5_pool_member_down_rule_matches() -> None:
    event = {
        "message": (
            "notice mcpd[5261]: 01070638:5: Pool /Common/app_pool_1 member "
            "/Common/10.0.10.25:443 monitor status down."
        ),
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_f5_bigip_pool_member_down"


def test_mikrotik_login_success_rule_matches() -> None:
    event = {
        "message": "system,info,account user admin logged in from 10.0.0.12 via ssh",
        "log": {"syslog": {"severity": {"code": 6, "name": "info"}}},
    }
    assert _match_signal(event) == "network_mikrotik_login_success"

