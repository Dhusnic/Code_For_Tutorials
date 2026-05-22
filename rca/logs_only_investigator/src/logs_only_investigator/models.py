from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


UTC = timezone.utc


def parse_utc(timestamp: str) -> datetime:
    normalized = timestamp.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def to_utc_string(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TimeWindow:
    start: str
    end: str
    label: str

    def start_dt(self) -> datetime:
        return parse_utc(self.start)

    def end_dt(self) -> datetime:
        return parse_utc(self.end)

    def widen(self, before: timedelta, after: timedelta, label: str | None = None) -> "TimeWindow":
        return TimeWindow(
            start=to_utc_string(self.start_dt() - before),
            end=to_utc_string(self.end_dt() + after),
            label=label or self.label,
        )

    def shift(self, before: timedelta, after: timedelta, label: str | None = None) -> "TimeWindow":
        return TimeWindow(
            start=to_utc_string(self.start_dt() + before),
            end=to_utc_string(self.end_dt() + after),
            label=label or self.label,
        )

    def contains(self, timestamp: str) -> bool:
        point = parse_utc(timestamp)
        return self.start_dt() <= point <= self.end_dt()


@dataclass(frozen=True)
class LogRecord:
    doc_id: str
    timestamp: str
    service: str
    host: str
    severity: str
    signal: str
    message: str
    ip: str = ""
    vendor: str = ""
    domain: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def searchable_text(self) -> str:
        fields = [
            self.service,
            self.host,
            self.ip,
            self.vendor,
            self.domain,
            self.severity,
            self.signal,
            self.message,
        ]
        metadata_text = " ".join(f"{key} {value}" for key, value in self.metadata.items())
        fields.append(metadata_text)
        return " ".join(part for part in fields if part).lower()

    def node_id(self) -> str | None:
        if self.ip and self.service:
            return f"{self.ip}::{self.service}"
        return None


@dataclass(frozen=True)
class QueryIntent:
    raw_query: str
    normalized_query: str
    search_terms: list[str]
    symptom: str
    service_hint: str | None = None
    vendor_hint: str | None = None
    host_hint: str | None = None
    ip_hint: str | None = None
    domain_hint: str | None = None
    time_phrase: str | None = None
    vague: bool = False


@dataclass(frozen=True)
class InvestigationScope:
    organization_id: str
    time_window: TimeWindow
    service: str | None = None
    vendor: str | None = None
    host: str | None = None
    ip: str | None = None
    selected_node_id: str | None = None
    domain_hint: str | None = None
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SignalRecord:
    id: str
    service: str | None
    vendor: str | None
    domain: str | None
    rule_file: str
    signal: str
    title: str
    summary: str
    symptom_keywords: list[str]
    related_signals: list[str]
    query_hints: dict[str, Any]

    def searchable_text(self) -> str:
        return " ".join(
            [
                self.signal,
                self.title,
                self.summary,
                self.service or "",
                self.vendor or "",
                self.domain or "",
                " ".join(self.symptom_keywords),
                " ".join(self.related_signals),
            ]
        ).lower()


@dataclass(frozen=True)
class RankedSignal:
    record: SignalRecord
    score: float
    matched_terms: tuple[str, ...]
    retrieval_mode: str = "lexical"
    semantic_score: float | None = None


@dataclass(frozen=True)
class RAGScope:
    scope_type: str
    scope_key: str
    domain_bias: str | None
    records: tuple[SignalRecord, ...]


@dataclass(frozen=True)
class Anchor:
    service: str | None
    host: str | None
    ip: str | None
    signal_set: tuple[str, ...]
    time_window: TimeWindow
    node_id: str | None
    reason: str


@dataclass(frozen=True)
class TopologyNode:
    node_id: str
    service: str
    host: str
    ip: str
    domain: str
    aliases: tuple[str, ...] = ()
    node_type: str = "service"
    service_aliases: tuple[str, ...] = ()
    ip_aliases: tuple[str, ...] = ()
    host_aliases: tuple[str, ...] = ()
    vendor: str | None = None
    platform: str | None = None
    tier: str | None = None
    role: str | None = None
    cluster_id: str | None = None
    replica_set: str | None = None
    is_entrypoint: bool = False
    criticality: str = "medium"
    match_fields: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    upstream: tuple[str, ...] = ()
    downstream: tuple[str, ...] = ()
    underlay: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopologyEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation_type: str
    relation_label: str = ""
    weight: float = 1.0
    criticality: str = "medium"
    source_refs: tuple[str, ...] = ()
    valid_from: str | None = None
    valid_to: str | None = None


@dataclass(frozen=True)
class HopSearchResult:
    source_node_id: str
    target_node_id: str
    hop_type: str
    service: str
    ip: str
    time_window: TimeWindow
    signals: tuple[str, ...]
    event_ids: tuple[str, ...]
    first_seen: str | None
    last_seen: str | None
    matched_signal_count: int
    summary: str
    chronology_ok: bool


@dataclass(frozen=True)
class DiscoveryBucket:
    start: str
    end: str
    count: int


@dataclass(frozen=True)
class DiscoveryCount:
    key: str
    count: int


@dataclass(frozen=True)
class SearchSummary:
    events: tuple[LogRecord, ...]
    signal_counts: dict[str, int]
    first_seen: str | None
    last_seen: str | None
    entities: tuple[dict[str, str], ...]

    @property
    def matched_signal_count(self) -> int:
        return sum(self.signal_counts.values())
