from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _es_utils import (
    ElasticsearchHttpClient,
    default_rules_file,
    default_signal_processor_config,
    load_elasticsearch_settings,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert simulated signal documents into Elasticsearch for correlation-rule testing.")
    parser.add_argument("--config", default=str(default_signal_processor_config()), help="Path to log_signal_processor config.yml")
    parser.add_argument("--rules", default=str(default_rules_file()), help="Path to correlation rules.json")
    parser.add_argument("--rule-id", default="CORR_P3Z9_QUEUE_BACKPRESSURE", help="Rule ID to simulate, or 'all'")
    parser.add_argument("--index", default="", help="Elasticsearch index for simulated source documents")
    parser.add_argument("--organization-id", default="", help="Override organization_id from rules.json")
    parser.add_argument("--host", default="sim-host-1", help="Host name to stamp into simulated documents")
    parser.add_argument("--service", default="sim-service", help="Service name to stamp into simulated documents")
    parser.add_argument("--interval", default="5s", help="Sleep interval between batches in continuous mode")
    parser.add_argument("--once", action="store_true", help="Insert one batch and exit")
    parser.add_argument("--max-batches", type=int, default=0, help="Optional cap for continuous mode (0 means unlimited)")
    parser.add_argument("--list-rules", action="store_true", help="Print available rule IDs and exit")
    return parser.parse_args()


def load_rules(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_duration(value: str) -> timedelta:
    if not value:
        return timedelta(0)
    unit = value[-1].lower()
    amount = int(value[:-1])
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError(f"Unsupported duration value: {value}")


def infer_level(signal_key: str) -> str:
    lowered = signal_key.lower()
    if any(token in lowered for token in ("5xx", "failure", "unreachable", "critical", "down")):
        return "error"
    if any(token in lowered for token in ("recovered", "success", "ok")):
        return "info"
    return "warning"


def infer_module(signal_key: str) -> str:
    prefix = signal_key.split("_", 1)[0].lower()
    aliases = {
        "mongodb": "mongodb",
        "nginx": "nginx",
        "rabbitmq": "rabbitmq",
        "kafka": "kafka",
        "redis": "redis",
        "postgres": "postgresql",
        "system": "system",
    }
    return aliases.get(prefix, prefix)


def build_documents(rule: dict[str, Any], now: datetime, run_id: str, host: str, service: str, organization_id: str) -> list[tuple[str, dict[str, Any]]]:
    sequence = rule.get("sequence", [])
    max_gap = parse_duration(rule.get("max_gap_between_steps", "1m"))
    doc_spacing = timedelta(seconds=20)
    step_gap = min(max_gap / 2 if max_gap else timedelta(seconds=45), timedelta(seconds=45))
    if step_gap <= timedelta(0):
        step_gap = timedelta(seconds=20)

    estimated_docs = sum(max(int(step.get("min_count", 1) or 1), 1) for step in sequence)
    total_span = estimated_docs * doc_spacing + len(sequence) * step_gap + timedelta(minutes=1)
    current_time = now - total_span

    documents: list[tuple[str, dict[str, Any]]] = []
    sequence_counter = 0
    for step in sequence:
        signal_key = str(step["signal_key"])
        min_count = max(int(step.get("min_count", 1) or 1), 1)
        within = parse_duration(step.get("within", "1m"))
        local_spacing = min(doc_spacing, within / max(min_count, 1)) if within else doc_spacing
        if local_spacing <= timedelta(0):
            local_spacing = timedelta(seconds=5)

        module = infer_module(signal_key)
        severity = infer_level(signal_key)
        last_time = current_time
        for occurrence in range(min_count):
            event_time = current_time + occurrence * local_spacing
            doc_id = f"{run_id}-{rule['id'].lower()}-{sequence_counter:02d}"
            sequence_counter += 1
            documents.append(
                (
                    doc_id,
                    {
                        "@timestamp": event_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "signal": signal_key,
                        "message": f"Simulated signal {signal_key} for rule {rule['id']}",
                        "event": {
                            "organization": organization_id,
                            "module": module,
                            "dataset": f"{module}.simulated",
                        },
                        "host": {
                            "name": host,
                        },
                        "service": {
                            "name": service,
                        },
                        "log": {
                            "level": severity,
                        },
                        "simulation": {
                            "tool": "simulate_rule_logs.py",
                            "run_id": run_id,
                            "rule_id": rule["id"],
                            "event_module": module,
                        },
                    },
                )
            )
            last_time = event_time

        current_time = last_time + step_gap
    return documents


def bulk_index(client: ElasticsearchHttpClient, index: str, documents: list[tuple[str, dict[str, Any]]]) -> None:
    lines: list[str] = []
    for doc_id, document in documents:
        lines.append(json.dumps({"index": {"_index": index, "_id": doc_id}}))
        lines.append(json.dumps(document))
    payload = "\n".join(lines) + "\n"

    response = client.request_json(
        "POST",
        "/_bulk",
        payload=payload,
        query={"refresh": "wait_for"},
        content_type="application/x-ndjson",
    )
    if response.get("errors"):
        failed = []
        for item in response.get("items", []):
            details = item.get("index", {})
            if "error" in details:
                failed.append({"id": details.get("_id"), "error": details["error"]})
        raise RuntimeError(f"Bulk index completed with failures: {json.dumps(failed, indent=2)}")


def print_batch_summary(
    *,
    documents: list[tuple[str, dict[str, Any]]],
    selected_rules: list[dict[str, Any]],
    settings: dict[str, Any],
    index: str,
    batch_number: int,
    run_id: str,
) -> None:
    print(f"Batch {batch_number} inserted {len(documents)} simulated signal documents")
    print(f"Elasticsearch: {settings['address']}")
    print(f"Index        : {index}")
    print(f"Run ID       : {run_id}")
    print()
    print("Simulated rules:")
    for rule in selected_rules:
        print(f"  - {rule['id']}")
    print()
    print("Inserted document IDs:")
    for doc_id, document in documents:
        print(
            "  - "
            f"{doc_id} | "
            f"{document['signal']} | "
            f"{document['event']['module']} | "
            f"{document['@timestamp']} | "
            f"{document['log']['level']}"
        )
    print()
    print("Next steps:")
    print("  1. Run the signal collector once:")
    print("     cd ..\\log_signal_processor")
    print("     go run .\\cmd\\signaled_logs_collector --config .\\config.yml --run-once")
    print("  2. Run the correlation engine once:")
    print("     cd ..\\log_correlation_engine")
    print("     .\\bin\\correlation-engine.exe --config .\\config\\config.yml --run-once")
    print("  3. Read the final correlation results:")
    print("     python .\\scripts\\show_correlation_results.py")
    print()


def run_batch(
    *,
    selected_rules: list[dict[str, Any]],
    args: argparse.Namespace,
    settings: dict[str, Any],
    index: str,
    client: ElasticsearchHttpClient,
    batch_number: int,
) -> None:
    run_id = f"{uuid.uuid4().hex[:8]}-b{batch_number:04d}"
    now = datetime.now(timezone.utc)
    all_documents: list[tuple[str, dict[str, Any]]] = []

    for offset, rule in enumerate(selected_rules):
        suffix = rule["id"].split("_", 1)[-1].lower()
        host = args.host if len(selected_rules) == 1 else f"{args.host}-{suffix}"
        service = args.service if len(selected_rules) == 1 else f"{args.service}-{suffix}"
        organization_id = args.organization_id.strip() or str(rule["organization_id"])
        rule_now = now + timedelta(seconds=offset * 5)
        all_documents.extend(build_documents(rule, rule_now, run_id, host, service, organization_id))

    bulk_index(client, index, all_documents)
    print_batch_summary(
        documents=all_documents,
        selected_rules=selected_rules,
        settings=settings,
        index=index,
        batch_number=batch_number,
        run_id=run_id,
    )


def main() -> None:
    args = parse_args()
    rules = load_rules(Path(args.rules))

    if args.list_rules:
        for rule in rules:
            print(rule["id"])
        return

    requested_rule_id = args.rule_id.strip()
    if requested_rule_id.lower() == "all":
        selected_rules = rules
    else:
        selected_rules = [rule for rule in rules if rule["id"] == requested_rule_id]
    if not selected_rules:
        raise SystemExit(f"No rule found for {requested_rule_id!r}")

    settings = load_elasticsearch_settings(Path(args.config))
    index = args.index.strip() or f"simulated-signal-logs-{datetime.now(timezone.utc):%Y.%m.%d}"
    client = ElasticsearchHttpClient(
        settings["address"],
        username=settings["username"],
        password=settings["password"],
        api_key=settings["api_key"],
    )
    interval = parse_duration(args.interval)
    if interval <= timedelta(0):
        raise SystemExit("--interval must be greater than zero")

    if len(selected_rules) > 1:
        print("Note: the correlation engine is still using a mock full-log fetcher.")
        print("For the cleanest validation, simulate one rule at a time.")
        print()

    batch_number = 1
    try:
        while True:
            run_batch(
                selected_rules=selected_rules,
                args=args,
                settings=settings,
                index=index,
                client=client,
                batch_number=batch_number,
            )
            if args.once:
                return
            if args.max_batches > 0 and batch_number >= args.max_batches:
                return
            print(f"Sleeping for {args.interval} before the next simulation batch...")
            print("-" * 80)
            time.sleep(interval.total_seconds())
            batch_number += 1
    except KeyboardInterrupt:
        print()
        print("Continuous simulation stopped by user.")


if __name__ == "__main__":
    main()
