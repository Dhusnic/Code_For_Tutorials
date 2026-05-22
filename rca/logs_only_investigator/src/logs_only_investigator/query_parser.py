from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .models import InvestigationScope, QueryIntent, TimeWindow, to_utc_string


STOP_WORDS = {
    "a",
    "an",
    "and",
    "around",
    "at",
    "because",
    "cause",
    "caused",
    "did",
    "for",
    "go",
    "happen",
    "happened",
    "how",
    "incident",
    "is",
    "it",
    "of",
    "the",
    "this",
    "to",
    "what",
    "when",
    "why",
    "was",
    "were",
}

DOMAIN_KEYWORDS = {
    "network": ("network", "router", "switch", "packet", "latency", "dns"),
    "database": ("database", "mongodb", "mongo", "postgres", "redis", "cache", "query"),
    "gateway": ("gateway", "nginx", "proxy", "502", "503", "504", "upstream"),
    "application": ("application", "app", "api", "service", "slow", "down", "error", "timeout"),
    "system": ("system", "disk", "cpu", "memory", "host", "node"),
}

TERM_EXPANSIONS = {
    "down": ("unavailable", "failed", "timeout", "gateway", "502", "503", "504"),
    "outage": ("unavailable", "failed", "timeout", "gateway"),
    "slow": ("latency", "timeout", "degraded"),
    "latency": ("slow", "timeout", "degraded"),
    "network": ("link", "bgp", "dns", "packet", "latency"),
    "application": ("gateway", "upstream", "timeout", "unavailable", "502"),
    "api": ("gateway", "upstream", "timeout", "unavailable"),
    "database": ("mongodb", "query", "disk", "timeout"),
    "mongo": ("mongodb", "query", "disk", "timeout"),
}


@dataclass(frozen=True)
class ParsedTimeHint:
    label: str
    start: str
    end: str


def parse_query(query: str, known_services: set[str], known_vendors: set[str], known_hosts: set[str]) -> QueryIntent:
    normalized = " ".join(query.lower().strip().split())
    tokens = [token.strip(" ,.?!:;()[]{}\"'") for token in normalized.split()]
    search_terms = [token for token in tokens if token and token not in STOP_WORDS]
    expanded_terms: list[str] = []
    for term in search_terms:
        expanded_terms.extend(TERM_EXPANSIONS.get(term, ()))
    search_terms = list(dict.fromkeys(search_terms + expanded_terms))

    service_hint = _match_known_phrase(normalized, known_services)
    vendor_hint = _match_known_phrase(normalized, known_vendors)
    host_hint = _match_known_phrase(normalized, known_hosts)
    ip_hint = _extract_ip(normalized)
    domain_hint = _infer_domain(normalized)

    time_phrase = _extract_time_phrase(normalized)
    vague = not any([service_hint, vendor_hint, host_hint, ip_hint, time_phrase])

    return QueryIntent(
        raw_query=query,
        normalized_query=normalized,
        search_terms=search_terms[:12],
        symptom=normalized,
        service_hint=service_hint,
        vendor_hint=vendor_hint,
        host_hint=host_hint,
        ip_hint=ip_hint,
        domain_hint=domain_hint,
        time_phrase=time_phrase,
        vague=vague,
    )


def resolve_scope(
    intent: QueryIntent,
    organization_id: str,
    dataset_start: str,
    dataset_end: str,
    explicit_start: str | None = None,
    explicit_end: str | None = None,
    service: str | None = None,
    host: str | None = None,
    ip: str | None = None,
    selected_node_id: str | None = None,
) -> InvestigationScope:
    assumptions: list[str] = []
    time_window = _resolve_time_window(
        intent=intent,
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        explicit_start=explicit_start,
        explicit_end=explicit_end,
        assumptions=assumptions,
    )

    resolved_service = service or intent.service_hint
    resolved_host = host or intent.host_hint
    resolved_ip = ip or intent.ip_hint

    if not intent.time_phrase and not explicit_start and not explicit_end:
        assumptions.append("No explicit incident time was provided, so the scope defaulted to the latest one-hour window in the available logs.")

    return InvestigationScope(
        organization_id=organization_id,
        time_window=time_window,
        service=resolved_service,
        vendor=intent.vendor_hint,
        host=resolved_host,
        ip=resolved_ip,
        selected_node_id=selected_node_id,
        domain_hint=intent.domain_hint,
        assumptions=tuple(assumptions),
    )


def _resolve_time_window(
    intent: QueryIntent,
    dataset_start: str,
    dataset_end: str,
    explicit_start: str | None,
    explicit_end: str | None,
    assumptions: list[str],
) -> TimeWindow:
    if explicit_start or explicit_end:
        start = explicit_start or dataset_start
        end = explicit_end or dataset_end
        assumptions.append("The investigation window used the explicit CLI time bounds.")
        return TimeWindow(start=start, end=end, label="explicit_range")

    if intent.time_phrase:
        parsed = _parse_time_phrase(intent.time_phrase, dataset_end)
        if parsed:
            assumptions.append(f"The query time hint '{intent.time_phrase}' was converted into the active incident window.")
            return TimeWindow(start=parsed.start, end=parsed.end, label=parsed.label)

    dataset_end_dt = _parse_iso(dataset_end)
    start_dt = dataset_end_dt - timedelta(hours=1)
    return TimeWindow(
        start=to_utc_string(start_dt),
        end=dataset_end,
        label="latest_1h",
    )


def _parse_time_phrase(time_phrase: str, dataset_end: str) -> ParsedTimeHint | None:
    end_dt = _parse_iso(dataset_end)

    if match := re.search(r"last\s+(\d+)\s*(minute|minutes|min|hour|hours|hr|hrs)", time_phrase):
        amount = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(minutes=amount) if unit.startswith(("minute", "min")) else timedelta(hours=amount)
        return ParsedTimeHint(
            label=f"last_{amount}_{'minutes' if delta < timedelta(hours=1) else 'hours'}",
            start=to_utc_string(end_dt - delta),
            end=to_utc_string(end_dt),
        )

    if "now" in time_phrase:
        return ParsedTimeHint(
            label="now_window",
            start=to_utc_string(end_dt - timedelta(minutes=10)),
            end=to_utc_string(end_dt + timedelta(minutes=10)),
        )

    if match := re.search(r"\b(\d{1,2}):(\d{2})\b", time_phrase):
        hour = int(match.group(1))
        minute = int(match.group(2))
        base_day = _parse_iso(dataset_end).date()
        centered = datetime.combine(base_day, time(hour=hour, minute=minute), tzinfo=end_dt.tzinfo)
        return ParsedTimeHint(
            label=f"around_{hour:02d}{minute:02d}",
            start=to_utc_string(centered - timedelta(minutes=10)),
            end=to_utc_string(centered + timedelta(minutes=10)),
        )

    return None


def _infer_domain(normalized_query: str) -> str | None:
    best_domain = None
    best_score = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in normalized_query)
        if score > best_score:
            best_domain = domain
            best_score = score
    return best_domain


def _match_known_phrase(normalized_query: str, values: set[str]) -> str | None:
    matches = [value for value in values if value and value in normalized_query]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return matches[0]


def _extract_ip(normalized_query: str) -> str | None:
    match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", normalized_query)
    if not match:
        return None
    return match.group(0)


def _extract_time_phrase(normalized_query: str) -> str | None:
    if "last " in normalized_query:
        return normalized_query
    if "now" in normalized_query:
        return "now"
    if re.search(r"\b\d{1,2}:\d{2}\b", normalized_query):
        return normalized_query
    return None


def _parse_iso(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)
