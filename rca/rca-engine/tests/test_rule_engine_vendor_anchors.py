"""Tests for vendor-aware anchor enforcement in rule engine."""

from __future__ import annotations

from src.rules.models import RuleCondition, RuleSet, SignalRule
from src.rules.rule_engine import RuleEngine


def _build_cisco_rule_set() -> RuleSet:
    return RuleSet(
        service="network",
        rules=[
            SignalRule(
                rule_id="CISCO_LINK",
                signal_key="network_cisco_ios_link_updown",
                level="critical",
                description="Cisco-like link down signature",
                tags=["vendor", "cisco", "ios"],
                condition=RuleCondition(
                    field="message",
                    op="contains",
                    value="line protocol is down",
                ),
            ),
        ],
    )


def _build_dell_rule_set() -> RuleSet:
    return RuleSet(
        service="network",
        rules=[
            SignalRule(
                rule_id="DELL_VLTI_DOWN",
                signal_key="network_dell_os10_vlti_link_down",
                level="critical",
                description="Dell OS10 VLTi down signature",
                tags=["vendor", "dell", "os10"],
                condition=RuleCondition(
                    field="message",
                    op="contains",
                    value="VLT_VLTi_LINK_DOWN",
                ),
            ),
        ],
    )


def _build_huawei_rule_set() -> RuleSet:
    return RuleSet(
        service="network",
        rules=[
            SignalRule(
                rule_id="HUAWEI_BFD_DOWN",
                signal_key="network_huawei_vrp_bfd_session_down",
                level="critical",
                description="Huawei VRP BFD down signature",
                tags=["vendor", "huawei", "vrp"],
                condition=RuleCondition(
                    field="message",
                    op="contains",
                    value="BFD/4/STACHG_TODWN",
                ),
            ),
        ],
    )


def _build_aruba_rule_set() -> RuleSet:
    return RuleSet(
        service="network",
        rules=[
            SignalRule(
                rule_id="ARUBA_CENTRAL_DOWN",
                signal_key="network_aruba_aos_central_connectivity_failure",
                level="warning",
                description="Aruba Central connectivity failed",
                tags=["vendor", "aruba", "aos", "aoscx"],
                condition=RuleCondition(
                    field="message",
                    op="contains",
                    value="Failed to connect to Aruba Central",
                ),
            ),
        ],
    )


def test_vendor_anchor_blocks_mismatched_vendor_when_hints_present() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "GigabitEthernet0/1 line protocol is down",
        "observer": {"vendor": "juniper"},
    }

    signals = engine.evaluate(event, _build_cisco_rule_set(), highest_only=True, max_signals=1)
    assert signals == []


def test_vendor_anchor_allows_matching_vendor_when_hints_present() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "GigabitEthernet0/1 line protocol is down",
        "observer": {"vendor": "cisco"},
    }

    signals = engine.evaluate(event, _build_cisco_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_cisco_ios_link_updown"


def test_vendor_anchor_preserves_legacy_behavior_without_vendor_hints() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "GigabitEthernet0/1 line protocol is down",
    }

    signals = engine.evaluate(event, _build_cisco_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_cisco_ios_link_updown"


def test_vendor_anchor_can_be_disabled() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=False)
    event = {
        "message": "GigabitEthernet0/1 line protocol is down",
        "observer": {"vendor": "juniper"},
    }

    signals = engine.evaluate(event, _build_cisco_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_cisco_ios_link_updown"


def test_vendor_anchor_blocks_dell_rule_when_vendor_mismatch() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "VLT_VLTi_LINK_DOWN detected on peer link",
        "observer": {"vendor": "cisco"},
    }

    signals = engine.evaluate(event, _build_dell_rule_set(), highest_only=True, max_signals=1)
    assert signals == []


def test_vendor_anchor_allows_dell_rule_when_vendor_matches() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "VLT_VLTi_LINK_DOWN detected on peer link",
        "observer": {"vendor": "Dell EMC"},
    }

    signals = engine.evaluate(event, _build_dell_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_dell_os10_vlti_link_down"


def test_vendor_anchor_blocks_huawei_rule_when_vendor_mismatch() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "BFD/4/STACHG_TODWN session changed from Up to Down",
        "observer": {"vendor": "cisco"},
    }

    signals = engine.evaluate(event, _build_huawei_rule_set(), highest_only=True, max_signals=1)
    assert signals == []


def test_vendor_anchor_allows_huawei_rule_when_vendor_matches() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "BFD/4/STACHG_TODWN session changed from Up to Down",
        "observer": {"vendor": "Huawei"},
    }

    signals = engine.evaluate(event, _build_huawei_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_huawei_vrp_bfd_session_down"


def test_vendor_anchor_blocks_aruba_rule_when_vendor_mismatch() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "Failed to connect to Aruba Central due to timeout",
        "observer": {"vendor": "cisco"},
    }

    signals = engine.evaluate(event, _build_aruba_rule_set(), highest_only=True, max_signals=1)
    assert signals == []


def test_vendor_anchor_allows_aruba_rule_when_vendor_matches() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "Failed to connect to Aruba Central due to timeout",
        "observer": {"vendor": "HPE Aruba"},
    }

    signals = engine.evaluate(event, _build_aruba_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_aruba_aos_central_connectivity_failure"


def test_vendor_anchor_allows_aruba_rule_for_hpe_vendor_name() -> None:
    engine = RuleEngine(vendor_anchor_enforcement_enabled=True)
    event = {
        "message": "Failed to connect to Aruba Central due to timeout",
        "observer": {"vendor": "Hewlett Packard Enterprise"},
    }

    signals = engine.evaluate(event, _build_aruba_rule_set(), highest_only=True, max_signals=1)
    assert len(signals) == 1
    assert signals[0]["signal"] == "network_aruba_aos_central_connectivity_failure"
