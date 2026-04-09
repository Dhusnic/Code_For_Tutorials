from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _es_utils import (
    ElasticsearchHttpClient,
    default_correlation_engine_config,
    default_rules_file,
    load_elasticsearch_settings,
)


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected true/false value, got {value!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read correlation results from Elasticsearch and print them in a human-readable format.")
    parser.add_argument("--config", default=str(default_correlation_engine_config()), help="Path to log_correlation_engine config/config.yml")
    parser.add_argument("--rules", default=str(default_rules_file()), help="Path to correlation rules.json")
    parser.add_argument("--index", default="rca_correlated_events*", help="Override Elasticsearch result index")
    parser.add_argument("--rule-id", default="", help="Only display one rule_id")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to display")
    parser.add_argument("--fetch-size", type=int, default=100, help="How many Elasticsearch documents to fetch before local filtering/sorting")
    parser.add_argument(
        "--user-readable",
        type=parse_bool,
        default=True,
        help="If true, show the friendly summary. If false, print neat raw JSON results.",
    )
    return parser.parse_args()


def load_rules(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in payload}


def fetch_results(client: ElasticsearchHttpClient, index: str, fetch_size: int) -> list[dict[str, Any]]:
    response = client.request_json(
        "POST",
        f"/{index}/_search",
        payload={
            "size": fetch_size,
            "query": {"match_all": {}},
        },
    )
    return response.get("hits", {}).get("hits", [])


def format_percentage(value: float) -> str:
    return f"{value:.4f} ({value * 100:.2f}%)"


def format_sequence(rule: dict[str, Any] | None) -> str:
    if not rule:
        return "unknown"
    parts = []
    for step in rule.get("sequence", []):
        count = max(int(step.get("min_count", 1) or 1), 1)
        parts.append(f"{step['signal_key']} x{count}")
    return " -> ".join(parts) if parts else "unknown"


def sort_key(hit: dict[str, Any]) -> tuple[Any, ...]:
    source = hit.get("_source", {})
    return (
        -float(source.get("rule_completion", 0)),
        -float(source.get("sequence_match", 0)),
        str(source.get("rule_id", "")),
        str(source.get("incident_id", "")),
        str(hit.get("_id", "")),
    )


def build_raw_result(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit.get("_source", {})
    if isinstance(source, dict):
        return source
    return {"_source": source}


def print_user_readable(filtered: list[dict[str, Any]], rule_lookup: dict[str, dict[str, Any]], index: str) -> None:
    print(f"Correlation results from index: {index}")
    print("=" * 80)
    for position, hit in enumerate(filtered, start=1):
        source = hit.get("_source", {})
        rule_id = str(source.get("rule_id", "unknown"))
        rule = rule_lookup.get(rule_id)
        compact_logs = source.get("log_id", [])
        doc_id = str(hit.get("_id", ""))
        incident_id = str(source.get("incident_id", "")) or doc_id

        print(f"{position}. {rule_id}")
        print(f"   Result doc ID   : {doc_id or 'n/a'}")
        print(f"   Incident ID     : {incident_id or 'n/a'}")
        # print(f"   KQL key         : _id")
        # print(f"   KQL filter      : _id : \"{doc_id}\"" if doc_id else "   KQL filter      : n/a")
        print(f"   Rule completion : {format_percentage(float(source.get('rule_completion', 0)))}")
        print(f"   Sequence match  : {format_percentage(float(source.get('sequence_match', 0)))}")
        if rule:
            print(f"   Priority        : {rule.get('priority', 'n/a')}")
            print(f"   Window          : {rule.get('window', 'n/a')}")
            print(f"   Max gap         : {rule.get('max_gap_between_steps', 'n/a')}")
            print(f"   Expected seq    : {format_sequence(rule)}")
        else:
            print("   Rule metadata   : not found in rules.json")
        print("   Matched logs    :")
        if not compact_logs:
            print("     - none")
        else:
            for entry in compact_logs:
                print(f"     - {entry.get('id', 'n/a')} [{entry.get('severity', 'n/a')}]")
        print("-" * 80)


def print_raw_results(filtered: list[dict[str, Any]], index: str) -> None:
    print(f"Correlation results from index: {index}")
    print("=" * 80)
    raw_results = [build_raw_result(hit) for hit in filtered]
    print(json.dumps(raw_results, indent=2))


def main() -> None:
    args = parse_args()
    settings = load_elasticsearch_settings(Path(args.config))
    index = args.index.strip() or settings["index"]
    if not index:
        raise SystemExit("No Elasticsearch result index found in config and no --index override was provided.")

    client = ElasticsearchHttpClient(
        settings["address"],
        username=settings["username"],
        password=settings["password"],
        api_key=settings["api_key"],
    )
    rule_lookup: dict[str, dict[str, Any]] = {}
    if args.user_readable:
        rule_lookup = load_rules(Path(args.rules))
    hits = fetch_results(client, index, max(args.limit, args.fetch_size))

    filtered = []
    for hit in hits:
        source = hit.get("_source", {})
        if args.rule_id and source.get("rule_id") != args.rule_id:
            continue
        filtered.append(hit)

    filtered.sort(key=sort_key, reverse=True)
    filtered = filtered[: args.limit]

    if not filtered:
        print("No correlation results found.")
        return

    if args.user_readable:
        print_user_readable(filtered, rule_lookup, index)
    else:
        print_raw_results(filtered, index)


if __name__ == "__main__":
    main()
