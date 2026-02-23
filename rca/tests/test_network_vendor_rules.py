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


def test_dell_os10_bgp_backward_state_change_rule_matches() -> None:
    event = {
        "message": (
            "%Dell EMC (OS10) %BGP_NBR_BKWD_STATE_CHG: Backward state change occurred "
            "for peer [10.0.0.2], vrf [default], old state [ESTABLISHED], "
            "new state [IDLE], event [ADJCHANGE: Hold Time expired]"
        ),
        "observer": {"vendor": "Dell EMC"},
        "log": {"syslog": {"severity": {"code": 4, "name": "warning"}}},
    }
    assert _match_signal(event) == "network_dell_os10_bgp_neighbor_down"


def test_dell_os10_vlti_link_down_rule_matches() -> None:
    event = {
        "message": (
            "%Dell EMC (OS10) %VLT_VLTi_LINK_DOWN: VLTi is down between local unit "
            "and peer unit 2"
        ),
        "observer": {"vendor": "Dell EMC"},
        "log": {"syslog": {"severity": {"code": 4, "name": "warning"}}},
    }
    assert _match_signal(event) == "network_dell_os10_vlti_link_down"


def test_huawei_vrp_bfd_session_down_rule_matches() -> None:
    event = {
        "message": (
            "%%01BFD/4/STACHG_TODWN(l):OID [1],"
            " The status of BFD session changed from Up to Down."
            "(NeighborIp=[10.0.0.2], InterfaceName=[10GE1/0/1], SessionState=[Down],"
            " DownReason=[Control Detection Time Expired])"
        ),
        "observer": {"vendor": "Huawei"},
        "log": {"syslog": {"severity": {"code": 4, "name": "warning"}}},
    }
    assert _match_signal(event) == "network_huawei_vrp_bfd_session_down"


def test_huawei_vrp_lacp_member_not_selected_rule_matches() -> None:
    event = {
        "message": (
            "%%01LACP/3/LAG_DOWN_REASON_EVENT(l):"
            "The member port can not become Selected because optical fiber misconnected."
        ),
        "observer": {"vendor": "Huawei"},
        "log": {"syslog": {"severity": {"code": 4, "name": "warning"}}},
    }
    assert _match_signal(event) == "network_huawei_vrp_lacp_member_not_selected"


def test_aruba_aos_bgp_peer_down_rule_matches() -> None:
    event = {
        "message": (
            "BGP: BGP route count from peer exceeded maximum allowable prefix "
            "limit. Peer Ideled"
        ),
        "observer": {"vendor": "Aruba"},
        "log": {"syslog": {"severity": {"code": 4, "name": "warning"}}},
    }
    assert _match_signal(event) == "network_aruba_aos_bgp_peer_down"


def test_aruba_aos_central_connectivity_failure_rule_matches() -> None:
    event = {
        "message": (
            "Event|4640|LOG_ERR|AMM|1/1|Failed to connect to Aruba Central "
            "(https://device.arubanetworks.com:443)."
        ),
        "observer": {"vendor": "Aruba"},
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_aruba_aos_central_connectivity_failure"


def test_hpe_aruba_bgp_peer_down_rule_matches() -> None:
    event = {
        "message": (
            "10.0.0.2: Peer down. error-code: 4, error-sub-code: 0. "
            "vrf-name: default"
        ),
        "observer": {"vendor": "Hewlett Packard Enterprise"},
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_aruba_aos_bgp_peer_down"


def test_hpe_aruba_central_connectivity_failure_rule_matches() -> None:
    event = {
        "message": (
            "Failed to connect to HPE Aruba Networking Central on location "
            "device.arubanetworks.com:443 on VRF default with Source IP 10.0.0.10"
        ),
        "observer": {"vendor": "Hewlett Packard Enterprise"},
        "log": {"syslog": {"severity": {"code": 3, "name": "error"}}},
    }
    assert _match_signal(event) == "network_aruba_aos_central_connectivity_failure"
