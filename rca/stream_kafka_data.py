#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
from datetime import datetime, timezone

import yaml

try:
    from confluent_kafka import Consumer, KafkaException
except Exception as exc:  # pragma: no cover - runtime dependency hint only
    Consumer = None
    KafkaException = RuntimeError
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


DEFAULT_CONFIG = Path(__file__).resolve().parent / "log_signalizing" / "config.yml"
RUNNING = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="View Kafka log messages using the same config block as log_signalizing/config.yml."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to RCA config.yml")
    parser.add_argument("--topic", default=None, help="Override kafka.topic")
    parser.add_argument("--group-id", default=None, help="Override kafka.group_id")
    parser.add_argument(
        "--offset",
        default=None,
        choices=("earliest", "latest"),
        help="Override kafka.start_offset",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after this many messages. 0 means run continuously.",
    )
    return parser.parse_args()


def load_runtime_config(path: str) -> dict[str, object]:
    config_path = Path(path).resolve()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Configuration root must be a mapping")

    kafka_raw = payload.get("kafka") or {}
    if not isinstance(kafka_raw, dict):
        raise ValueError("kafka must be a mapping when provided")

    brokers = kafka_raw.get("brokers") or []
    if isinstance(brokers, str):
        brokers = [part.strip() for part in brokers.replace(";", ",").split(",") if part.strip()]
    if not isinstance(brokers, list):
        raise ValueError("kafka.brokers must be a list or string")

    def optional_text(key: str) -> str | None:
        value = kafka_raw.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    ca_file = optional_text("ca_file")
    if ca_file:
        ca_file = str((config_path.parent / ca_file).resolve())

    return {
        "brokers": [str(item).strip() for item in brokers if str(item).strip()],
        "topic": optional_text("topic"),
        "group_id": optional_text("group_id"),
        "start_offset": optional_text("start_offset") or "latest",
        "security_protocol": optional_text("security_protocol") or "PLAINTEXT",
        "sasl_mechanism": optional_text("sasl_mechanism"),
        "username": optional_text("username"),
        "password": optional_text("password"),
        "tls_enabled": bool(kafka_raw.get("tls_enabled", False)),
        "insecure_skip_verify": bool(kafka_raw.get("insecure_skip_verify", False)),
        "ca_file": ca_file,
        "batch_size": int(kafka_raw.get("batch_size", 500)),
    }


def build_consumer_config(runtime_config: dict[str, object]) -> dict[str, object]:
    config = {
        "bootstrap.servers": ",".join(runtime_config["brokers"]),
        "group.id": runtime_config["group_id"],
        "auto.offset.reset": runtime_config["start_offset"],
        "enable.auto.commit": True,
        "fetch.min.bytes": 1,
        "fetch.wait.max.ms": 1000,
        "queued.min.messages": max(1000, int(runtime_config["batch_size"]) * 2),
    }

    security_protocol = str(runtime_config["security_protocol"]).strip().upper()
    if security_protocol:
        config["security.protocol"] = security_protocol
    sasl_mechanism = runtime_config.get("sasl_mechanism")
    if sasl_mechanism:
        config["sasl.mechanisms"] = sasl_mechanism
    if runtime_config.get("username"):
        config["sasl.username"] = runtime_config["username"]
    if runtime_config.get("password"):
        config["sasl.password"] = runtime_config["password"]

    if runtime_config.get("tls_enabled"):
        ca_file = runtime_config.get("ca_file")
        if ca_file:
            config["ssl.ca.location"] = ca_file
        if runtime_config.get("insecure_skip_verify"):
            config["ssl.endpoint.identification.algorithm"] = "none"

    return config


def stop_handler(signum, frame):  # noqa: ANN001,ARG001
    global RUNNING
    RUNNING = False


def print_log(message) -> None:  # noqa: ANN001
    raw = message.value()
    if raw is None:
        return

    text = raw.decode("utf-8", errors="replace")
    try:
        output = json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
    except Exception:
        output = text

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(
        f"{now} topic={message.topic()} partition={message.partition()} offset={message.offset()} {output}",
        flush=True,
    )


def main() -> int:
    args = parse_args()

    if Consumer is None:
        print(
            "confluent_kafka is required to run this viewer. "
            f"Import error: {IMPORT_ERROR!r}",
            file=sys.stderr,
        )
        return 1

    runtime_config = load_runtime_config(args.config)
    if args.topic:
        runtime_config["topic"] = args.topic
    if args.group_id:
        runtime_config["group_id"] = args.group_id
    if args.offset:
        runtime_config["start_offset"] = args.offset

    if not runtime_config["brokers"]:
        print("kafka.brokers must not be empty", file=sys.stderr)
        return 1
    if not runtime_config["topic"]:
        print("kafka.topic must not be empty", file=sys.stderr)
        return 1
    if not runtime_config["group_id"]:
        print("kafka.group_id must not be empty", file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    consumer = Consumer(build_consumer_config(runtime_config))
    consumer.subscribe([str(runtime_config["topic"])])

    seen = 0
    try:
        while RUNNING:
            messages = consumer.consume(num_messages=int(runtime_config["batch_size"]), timeout=1.0)
            for message in messages:
                if message is None:
                    continue
                if message.error():
                    raise KafkaException(message.error())

                print_log(message)
                seen += 1
                if args.limit > 0 and seen >= args.limit:
                    return 0
    finally:
        consumer.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
