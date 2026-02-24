"""Vendor-aware anchor helpers for reducing cross-vendor rule noise."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.utils.dicts import get_nested


_RULE_TAG_TO_VENDOR: dict[str, str] = {
    "cisco": "cisco",
    "ios": "cisco",
    "nxos": "cisco",
    "juniper": "juniper",
    "junos": "juniper",
    "arista": "arista",
    "eos": "arista",
    "aruba": "aruba",
    "hpe": "aruba",
    "hewlett_packard_enterprise": "aruba",
    "aos": "aruba",
    "aoscx": "aruba",
    "aos_switch": "aruba",
    "procurve": "aruba",
    "huawei": "huawei",
    "vrp": "huawei",
    "cloudengine": "huawei",
    "netengine": "huawei",
    "quidway": "huawei",
    "dell": "dell",
    "os10": "dell",
    "powerswitch": "dell",
    "smartfabric": "dell",
    "dellos": "dell",
    "fortinet": "fortinet",
    "fortios": "fortinet",
    "fortigate": "fortinet",
    "checkpoint": "checkpoint",
    "paloalto": "paloalto",
    "panos": "paloalto",
    "f5": "f5",
    "bigip": "f5",
    "mikrotik": "mikrotik",
    "routeros": "mikrotik",
}

_VENDOR_TOKENS: dict[str, tuple[str, ...]] = {
    "cisco": ("cisco", "nx-os", "nxos", "ios", "cat9k", "c9300", "isr"),
    "juniper": ("juniper", "junos", "srx", "qfx", "mx", "ex"),
    "arista": ("arista", "eos"),
    "aruba": (
        "aruba",
        "aruba networks",
        "aruba networking",
        "hpe",
        "hpe aruba",
        "hpe aruba networking",
        "hewlett packard enterprise",
        "arubaos",
        "aos-cx",
        "aoscx",
        "aos-switch",
        "aos switch",
        "procurve",
        "aruba central",
    ),
    "huawei": (
        "huawei",
        "huawei technologies",
        "vrp",
        "cloudengine",
        "ce12800",
        "ce6800",
        "ce5800",
        "netengine",
        "ne40e",
        "quidway",
    ),
    "dell": (
        "dell",
        "dell emc",
        "powerswitch",
        "smartfabric",
        "smartfabric os10",
        "os10",
        "dellos",
        "n-series",
        "s-series",
        "z-series",
    ),
    "fortinet": ("fortinet", "fortigate", "fortios", "fgt"),
    "checkpoint": ("checkpoint", "check point", "cplogexporter", "gaia"),
    "paloalto": ("paloalto", "palo alto", "pan-os", "panos", "pa-vm"),
    "f5": ("f5", "big-ip", "bigip", "ltm", "mcpd", "tmm"),
    "mikrotik": ("mikrotik", "routeros", "ros", "mtk"),
}

_STRICT_HINT_FIELDS: tuple[str, ...] = (
    "observer.vendor",
    "observer.product",
    "observer.type",
    "observer.name",
    "observer.hostname",
    "event.module",
    "event.dataset",
    "data_stream.dataset",
    "device.vendor",
    "device.type",
    "device.model",
    "host.name",
    "host.hostname",
    "agent.name",
    "agent.type",
)

_SOFT_HINT_FIELDS: tuple[str, ...] = (
    "message",
    "msg",
    "event.original",
)


def infer_rule_vendor(tags: list[str]) -> str | None:
    """Return canonical vendor key inferred from rule tags."""
    for raw_tag in tags:
        tag = str(raw_tag).strip().lower()
        if not tag:
            continue
        vendor = _RULE_TAG_TO_VENDOR.get(tag)
        if vendor is not None:
            return vendor
    return None


@dataclass(slots=True)
class VendorAnchorSnapshot:
    """Normalized vendor-hint cache for one source event."""

    strict_values: tuple[str, ...]
    soft_values: tuple[str, ...]

    @property
    def has_strict_hints(self) -> bool:
        """Return True when event includes explicit vendor metadata."""
        return bool(self.strict_values)

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "VendorAnchorSnapshot":
        """Build snapshot by extracting and normalizing vendor hint fields."""
        strict_values = tuple(_collect_field_values(event, _STRICT_HINT_FIELDS))
        soft_values = tuple(_collect_field_values(event, _SOFT_HINT_FIELDS))
        return cls(strict_values=strict_values, soft_values=soft_values)

    def matches_vendor(self, vendor: str) -> bool:
        """Return True when event hints align with the provided vendor key."""
        tokens = _VENDOR_TOKENS.get(vendor)
        if not tokens:
            return False
        # When strict metadata exists (observer/device/agent fields), treat it as source
        # of truth and ignore soft text hints to avoid cross-vendor false positives.
        values = self.strict_values if self.strict_values else self.soft_values
        for value in values:
            for token in tokens:
                if token in value:
                    return True
        return False


def _collect_field_values(event: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    """Collect lowercase string values for selected event fields."""
    values: list[str] = []
    for field in fields:
        raw = get_nested(event, field)
        if raw is None and "." not in field:
            raw = event.get(field)
        values.extend(_normalize_value(raw))
    return values


def _normalize_value(raw: Any) -> list[str]:
    """Convert scalar/list values to lowercase strings for token matching."""
    if raw is None:
        return []
    if isinstance(raw, (str, int, float, bool)):
        text = str(raw).strip().lower()
        return [text] if text else []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            out.extend(_normalize_value(item))
        return out
    return []
