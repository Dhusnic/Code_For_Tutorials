#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def candidate_config_paths() -> list[Path]:
    return [
        repo_root() / "log_correlation_engine" / "config" / "config.yml",
        repo_root() / "log_rca_engine" / "config" / "config.yml",
        repo_root() / "log_signalizing" / "config.yml",
    ]


def default_rules_path() -> Path:
    return repo_root() / "log_correlation_engine" / "rules" / "rules.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect correlation-engine Elasticsearch output and print a human-readable "
            "health summary plus the most recent incident activity."
        )
    )
    parser.add_argument(
        "--config",
        default=str(candidate_config_paths()[0]),
        help="Config file used to auto-discover Elasticsearch and RCA index settings.",
    )
    parser.add_argument(
        "--rules",
        default="",
        help="Optional rules.json path for friendlier rule descriptions.",
    )
    parser.add_argument(
        "--es-url",
        default=os.getenv("RCA_ES_URL") or "",
        help="Elasticsearch base URL, for example http://10.0.4.132:9200",
    )
    parser.add_argument(
        "--es-username",
        default=os.getenv("RCA_ES_USERNAME") or "",
        help="Elasticsearch username.",
    )
    parser.add_argument(
        "--es-password",
        default=os.getenv("RCA_ES_PASSWORD") or "",
        help="Elasticsearch password.",
    )
    parser.add_argument(
        "--es-api-key",
        default=os.getenv("RCA_ES_API_KEY") or "",
        help="Elasticsearch API key.",
    )
    parser.add_argument(
        "--events-index",
        default="",
        help="Override the correlation history index. Defaults to elasticsearch.index from config.",
    )
    parser.add_argument(
        "--incidents-index",
        default="",
        help="Override the current incident index. Defaults to elasticsearch.current_index from config.",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="How far back to inspect recent correlation activity. Default: 60 minutes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="How many incident rows and detail cards to print. Default: 8.",
    )
    parser.add_argument(
        "--organization",
        default="",
        help="Optional exact organization_id filter.",
    )
    parser.add_argument(
        "--rule-id",
        default="",
        help="Optional exact rule_id filter.",
    )
    parser.add_argument(
        "--status",
        default="",
        help="Optional exact status filter, for example open, updated, or closed.",
    )
    parser.add_argument(
        "--show-json",
        action="store_true",
        help="Print compact raw JSON for the displayed incident documents.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for HTTPS endpoints.",
    )
    return parser.parse_args()


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_sectioned_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            data[current_section] = {}
            current_list_key = None
            continue

        if current_section is None:
            continue

        section = data[current_section]
        if indent == 2 and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value == "":
                section[key] = []
                current_list_key = key
            else:
                section[key] = parse_scalar(raw_value)
                current_list_key = None
            continue

        if indent >= 4 and stripped.startswith("- ") and current_list_key:
            section[current_list_key].append(parse_scalar(stripped[2:]))

    return data


def detect_config_path(explicit_path: str) -> Path | None:
    checked: list[Path] = []
    if explicit_path:
        checked.append(Path(explicit_path).expanduser().resolve())
    checked.extend(candidate_config_paths())

    seen: set[Path] = set()
    for path in checked:
        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        try:
            config = load_sectioned_yaml(path)
        except OSError:
            continue
        elasticsearch = config.get("elasticsearch", {})
        addresses = elasticsearch.get("addresses", [])
        if isinstance(addresses, list) and any(str(item).strip() for item in addresses):
            return path

    for path in checked:
        if path.exists() and path.is_file():
            return path
    return None


def resolve_related_path(raw_path: str, config_path: Path | None) -> Path | None:
    text = str(raw_path).strip()
    if not text:
        return None

    candidate = Path(text).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve()

    bases: list[Path] = []
    if config_path is not None:
        bases.append(config_path.parent)
        if config_path.parent.parent.exists():
            bases.append(config_path.parent.parent)
    bases.append(repo_root())

    for base in bases:
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    return candidate.resolve()


def resolve_settings(args: argparse.Namespace) -> dict[str, Any]:
    config_path = detect_config_path(args.config)
    yaml_config = load_sectioned_yaml(config_path) if config_path else {}
    elasticsearch = yaml_config.get("elasticsearch", {})
    engine = yaml_config.get("engine", {})

    addresses = [
        str(item).strip()
        for item in (elasticsearch.get("addresses") or [])
        if str(item).strip()
    ]
    address = str(args.es_url or (addresses[0] if addresses else "")).strip()
    if not address:
        raise ValueError(
            "Could not determine Elasticsearch URL. Pass --es-url or use a config.yml with elasticsearch.addresses."
        )

    rules_path = args.rules.strip()
    if not rules_path:
        rules_path = str(engine.get("rules_file") or "").strip()
    resolved_rules = resolve_related_path(rules_path, config_path) if rules_path else default_rules_path()

    events_index = str(args.events_index or elasticsearch.get("index") or "rca_correlated_events").strip()
    incidents_index = str(
        args.incidents_index or elasticsearch.get("current_index") or "rca_correlated_incidents_current"
    ).strip()

    return {
        "address": address.rstrip("/"),
        "username": str(args.es_username or elasticsearch.get("username") or "").strip(),
        "password": str(args.es_password or elasticsearch.get("password") or "").strip(),
        "api_key": str(args.es_api_key or elasticsearch.get("api_key") or "").strip(),
        "events_index": events_index,
        "incidents_index": incidents_index,
        "write_history_index": bool(elasticsearch.get("write_history_index")),
        "config_path": str(config_path) if config_path else "(none)",
        "rules_path": str(resolved_rules) if resolved_rules else "(none)",
    }


class ElasticsearchHttpClient:
    def __init__(
        self,
        address: str,
        username: str = "",
        password: str = "",
        api_key: str = "",
        insecure: bool = False,
    ) -> None:
        self.address = address.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.ssl_context = ssl._create_unverified_context() if insecure else None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username or self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self.address + path
        if query:
            url += "?" + parse.urlencode(query)

        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = request.Request(url, data=data, method=method.upper(), headers=self._headers())
        try:
            with request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Elasticsearch request failed ({exc.code} {exc.reason}): {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Elasticsearch at {self.address}: {exc}") from exc

        return json.loads(body) if body else {}


def load_rules(path: str) -> dict[str, dict[str, Any]]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, list):
        return {}
    rules: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("id") or "").strip()
        if rule_id:
            rules[rule_id] = item
    return rules


def exact_match_clause(field: str, value: str) -> dict[str, Any]:
    return {
        "bool": {
            "should": [
                {"term": {field: value}},
                {"term": {f"{field}.keyword": value}},
            ],
            "minimum_should_match": 1,
        }
    }


def build_common_filters(args: argparse.Namespace, time_field: str) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"range": {time_field: {"gte": f"now-{max(args.minutes, 1)}m"}}},
    ]
    if args.organization.strip():
        filters.append(exact_match_clause("organization_id", args.organization.strip()))
    if args.rule_id.strip():
        filters.append(exact_match_clause("rule_id", args.rule_id.strip()))
    if args.status.strip():
        filters.append(exact_match_clause("status", args.status.strip().lower()))
    return filters


def build_event_overview_query(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "size": 0,
        "query": {
            "bool": {
                "filter": build_common_filters(args, "correlated_at"),
            }
        },
        "aggs": {
            "distinct_incidents": {"cardinality": {"field": "incident_id.keyword"}},
            "by_status": {"terms": {"field": "status.keyword", "size": 10}},
            "by_rule": {"terms": {"field": "rule_id.keyword", "size": 5}},
            "by_org": {"terms": {"field": "organization_id.keyword", "size": 5}},
            "latest_event": {"max": {"field": "correlated_at"}},
        },
    }


def build_recent_events_query(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "size": max(args.limit, 1),
        "query": {
            "bool": {
                "filter": build_common_filters(args, "correlated_at"),
            }
        },
        "sort": [
            {"correlated_at": {"order": "desc", "unmapped_type": "date"}},
            {"matched_at": {"order": "desc", "unmapped_type": "date"}},
        ],
        "_source": True,
    }


def build_current_incidents_query(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "size": max(args.limit, 1),
        "query": {
            "bool": {
                "filter": build_common_filters(args, "last_seen"),
            }
        },
        "sort": [
            {"last_seen": {"order": "desc", "unmapped_type": "date"}},
            {"first_seen": {"order": "desc", "unmapped_type": "date"}},
            {"correlated_at": {"order": "desc", "unmapped_type": "date"}},
        ],
        "_source": True,
    }


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, tail = text.split(".", 1)
        tz_index = max(tail.find("+"), tail.find("-"))
        if tz_index >= 0:
            fraction = tail[:tz_index]
            suffix = tail[tz_index:]
        else:
            fraction = tail
            suffix = ""
        digits = "".join(ch for ch in fraction if ch.isdigit())
        if digits:
            digits = digits[:6].ljust(6, "0")
            text = f"{head}.{digits}{suffix}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: Any) -> str:
    parsed = parse_timestamp(value)
    if parsed is None:
        return "-"
    return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")


def humanize_age(value: Any, now: datetime) -> str:
    parsed = parse_timestamp(value)
    if parsed is None:
        return "-"
    delta = now - parsed
    if delta < timedelta(seconds=0):
        delta = timedelta(seconds=0)

    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h ago"
    if hours:
        return f"{hours}h {minutes}m ago"
    if minutes:
        return f"{minutes}m ago"
    return f"{seconds}s ago"


def shorten(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render_row(values: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    separator = "  ".join("-" * width for width in widths)
    lines = [render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def status_counts(overview: dict[str, Any]) -> dict[str, int]:
    buckets = overview.get("aggregations", {}).get("by_status", {}).get("buckets", [])
    result: dict[str, int] = {}
    for bucket in buckets:
        key = str(bucket.get("key", "")).strip() or "unknown"
        result[key] = int(bucket.get("doc_count", 0))
    return result


def format_percent(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{numeric * 100:.1f}%"


def get_nested(source: dict[str, Any], dotted_path: str) -> Any:
    current: Any = source
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def rule_label(rule_id: str, rules: dict[str, dict[str, Any]]) -> str:
    rule = rules.get(rule_id)
    if not rule:
        return rule_id or "-"
    description = str(rule.get("description") or "").strip()
    if description:
        return shorten(description, 70)
    return rule_id or "-"


def format_group_values(values: Any) -> str:
    if not isinstance(values, dict) or not values:
        return "-"
    parts = [f"{key}={value}" for key, value in sorted(values.items()) if str(value).strip()]
    return shorten(", ".join(parts), 80) if parts else "-"


def format_signals(source: dict[str, Any]) -> str:
    audit = source.get("audit") or {}
    if isinstance(audit, dict):
        matched_signals = audit.get("matched_signals") or []
        if isinstance(matched_signals, list):
            cleaned = [str(item).strip() for item in matched_signals if str(item).strip()]
            if cleaned:
                return shorten(" -> ".join(cleaned), 80)

    log_entries = source.get("log_id") or []
    if isinstance(log_entries, list) and log_entries:
        log_ids = []
        for entry in log_entries:
            if isinstance(entry, dict):
                log_id = str(entry.get("id") or "").strip()
                if log_id:
                    log_ids.append(log_id)
        if log_ids:
            return shorten(", ".join(log_ids), 80)
    return "-"


def format_bucket_list(
    buckets: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    *,
    rule_mode: bool,
) -> str:
    if not buckets:
        return "-"
    parts: list[str] = []
    for bucket in buckets:
        key = str(bucket.get("key", "")).strip() or "unknown"
        count = int(bucket.get("doc_count", 0))
        if rule_mode:
            key = shorten(rule_label(key, rules), 60)
        parts.append(f"{key} ({count})")
    return "; ".join(parts)


def build_incident_rows(
    hits: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    now: datetime,
    window_minutes: int,
) -> list[list[str]]:
    rows: list[list[str]] = []
    new_window = timedelta(minutes=max(window_minutes, 1))
    for index, hit in enumerate(hits, start=1):
        source = hit.get("_source") or {}
        first_seen = source.get("first_seen")
        first_seen_time = parse_timestamp(first_seen)
        rows.append(
            [
                str(index),
                humanize_age(source.get("last_seen") or source.get("correlated_at"), now),
                str(source.get("status") or "-"),
                str(source.get("organization_id") or "-"),
                shorten(str(source.get("rule_id") or "-"), 38),
                format_percent(source.get("rule_completion")),
                str(len(source.get("log_id") or [])),
                "yes" if first_seen_time and now - first_seen_time <= new_window else "no",
                shorten(format_signals(source), 55),
            ]
        )
    return rows


def print_incident_details(hits: list[dict[str, Any]], rules: dict[str, dict[str, Any]], now: datetime) -> None:
    print()
    print("Incident detail cards")
    print("---------------------")
    for index, hit in enumerate(hits, start=1):
        source = hit.get("_source") or {}
        rule_id = str(source.get("rule_id") or "-")
        rule = rules.get(rule_id, {})
        print(f"{index}. {rule_id}")
        print(f"   Summary        : {rule_label(rule_id, rules)}")
        print(f"   Incident ID    : {source.get('incident_id') or hit.get('_id') or '-'}")
        print(f"   Status         : {source.get('status') or '-'}")
        print(f"   Organization   : {source.get('organization_id') or '-'}")
        print(f"   First seen     : {format_timestamp(source.get('first_seen'))} ({humanize_age(source.get('first_seen'), now)})")
        print(f"   Last seen      : {format_timestamp(source.get('last_seen'))} ({humanize_age(source.get('last_seen'), now)})")
        print(f"   Matched at     : {format_timestamp(source.get('matched_at'))}")
        print(f"   Correlated at  : {format_timestamp(source.get('correlated_at'))}")
        print(f"   Rule completion: {format_percent(source.get('rule_completion'))}")
        print(f"   Sequence match : {format_percent(source.get('sequence_match'))}")
        print(f"   Matched logs   : {len(source.get('log_id') or [])}")
        print(f"   Group values   : {format_group_values(source.get('group_by_values'))}")
        print(f"   Signals        : {format_signals(source)}")
        if rule:
            print(f"   Priority       : {rule.get('priority', '-')}")
            print(f"   Window         : {rule.get('window', '-')}")
            print(f"   Max gap        : {rule.get('max_gap_between_steps', '-')}")
        print()


def verdict_text(overview: dict[str, Any], current_hits: list[dict[str, Any]], write_history_index: bool) -> str:
    total_events = int(overview.get("hits", {}).get("total", {}).get("value", 0))
    distinct_incidents = int(
        overview.get("aggregations", {}).get("distinct_incidents", {}).get("value", 0)
    )
    counts = status_counts(overview)
    open_count = counts.get("open", 0)
    closed_count = counts.get("closed", 0)

    if not write_history_index:
        if current_hits:
            return (
                "Correlation appears active via the current incident index; "
                "history-index writes are disabled in config, so zero history documents is expected."
            )
        return (
            "History-index writes are disabled in config, and no current incident documents "
            "matched the selected window."
        )

    if total_events == 0 and not current_hits:
        return "No recent correlation activity was found in the selected window."
    if total_events > 0 and distinct_incidents > 0:
        return (
            f"Correlation is active: {total_events} recent event documents across "
            f"{distinct_incidents} incident(s); open={open_count}, closed={closed_count}."
        )
    if current_hits:
        return "Current incident documents exist, but no recent history events matched the selected window."
    return "Recent history documents exist, but no current incident documents matched the selected filters."


def print_json_hits(hits: list[dict[str, Any]]) -> None:
    print()
    print("Raw incident documents")
    print("----------------------")
    payload = []
    for hit in hits:
        payload.append(
            {
                "_index": hit.get("_index"),
                "_id": hit.get("_id"),
                "_source": hit.get("_source"),
            }
        )
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def print_report(
    args: argparse.Namespace,
    settings: dict[str, Any],
    overview: dict[str, Any],
    recent_events: dict[str, Any],
    current_incidents: dict[str, Any],
    rules: dict[str, dict[str, Any]],
) -> None:
    now = datetime.now(timezone.utc)
    recent_event_hits = recent_events.get("hits", {}).get("hits", [])
    current_hits = current_incidents.get("hits", {}).get("hits", [])
    total_events = int(overview.get("hits", {}).get("total", {}).get("value", 0))
    distinct_incidents = int(
        overview.get("aggregations", {}).get("distinct_incidents", {}).get("value", 0)
    )
    latest_event_hit = recent_event_hits[0] if recent_event_hits else {}
    latest_event_source = latest_event_hit.get("_source") or {}
    latest_event_time = latest_event_source.get("correlated_at") or latest_event_source.get("matched_at")
    by_status = status_counts(overview)
    by_rule = overview.get("aggregations", {}).get("by_rule", {}).get("buckets", [])
    by_org = overview.get("aggregations", {}).get("by_org", {}).get("buckets", [])

    print("Correlation Elasticsearch Check")
    print("===============================")
    print(f"Elasticsearch URL : {settings['address']}")
    print(f"Config source     : {settings['config_path']}")
    print(f"Rules source      : {settings['rules_path']}")
    print(f"Events index      : {settings['events_index']}")
    print(f"Incidents index   : {settings['incidents_index']}")
    print(f"History writes    : {'enabled' if settings['write_history_index'] else 'disabled'}")
    print(f"Window            : last {max(args.minutes, 1)} minute(s)")
    print(f"Organization      : {args.organization.strip() or '(all)'}")
    print(f"Rule ID           : {args.rule_id.strip() or '(all)'}")
    print(f"Status            : {args.status.strip() or '(all)'}")
    print()
    print("Health verdict")
    print("--------------")
    print(verdict_text(overview, current_hits, settings["write_history_index"]))
    print()
    print("Recent activity summary")
    print("-----------------------")
    print(f"History documents  : {total_events}")
    print(f"Distinct incidents : {distinct_incidents}")
    print(f"Latest event time  : {format_timestamp(latest_event_time)}")
    print(f"Latest event age   : {humanize_age(latest_event_time, now)}")
    print(f"Open events        : {by_status.get('open', 0)}")
    print(f"Updated events     : {by_status.get('updated', 0)}")
    print(f"Closed events      : {by_status.get('closed', 0)}")
    print(f"Current docs shown : {len(current_hits)}")
    print()
    print("Top organizations")
    print("-----------------")
    print(format_bucket_list(by_org, rules, rule_mode=False))
    print()
    print("Top rules")
    print("---------")
    print(format_bucket_list(by_rule, rules, rule_mode=True))
    print()
    print("Current/latest incidents")
    print("------------------------")
    if not current_hits:
        print("No current incident documents matched the selected filters.")
    else:
        print(
            render_table(
                [
                    "S/N",
                    "last_seen",
                    "status",
                    "organization",
                    "rule_id",
                    "completion",
                    "logs",
                    "new?",
                    "signals",
                ],
                build_incident_rows(current_hits, rules, now, args.minutes),
            )
        )
        print_incident_details(current_hits, rules, now)

    if args.show_json and current_hits:
        print_json_hits(current_hits)


def main() -> int:
    args = parse_args()
    try:
        settings = resolve_settings(args)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    client = ElasticsearchHttpClient(
        settings["address"],
        username=settings["username"],
        password=settings["password"],
        api_key=settings["api_key"],
        insecure=args.insecure,
    )
    rules = load_rules(settings["rules_path"])

    try:
        overview = client.request_json(
            "POST",
            f"/{settings['events_index']}/_search",
            build_event_overview_query(args),
            query={"ignore_unavailable": "true", "allow_no_indices": "true"},
        )
        recent_events = client.request_json(
            "POST",
            f"/{settings['events_index']}/_search",
            build_recent_events_query(args),
            query={"ignore_unavailable": "true", "allow_no_indices": "true"},
        )
        current_incidents = client.request_json(
            "POST",
            f"/{settings['incidents_index']}/_search",
            build_current_incidents_query(args),
            query={"ignore_unavailable": "true", "allow_no_indices": "true"},
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    print_report(args, settings, overview, recent_events, current_incidents, rules)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
