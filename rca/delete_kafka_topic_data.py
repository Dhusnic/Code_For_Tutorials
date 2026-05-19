#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys

try:
    from confluent_kafka import OFFSET_END, KafkaException, TopicPartition
    from confluent_kafka.admin import AdminClient
except Exception as exc:  # pragma: no cover - runtime dependency hint only
    AdminClient = None
    OFFSET_END = -1
    KafkaException = RuntimeError
    TopicPartition = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

from stream_kafka_data import DEFAULT_CONFIG, load_runtime_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete all retained Kafka records from the topic used by stream_kafka_data.py "
            "while keeping the topic itself."
        )
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to RCA config.yml")
    parser.add_argument("--topic", default=None, help="Override kafka.topic")
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=30.0,
        help="Kafka admin request timeout in seconds.",
    )
    parser.add_argument(
        "--operation-timeout",
        type=float,
        default=30.0,
        help="Broker-side delete operation timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which partitions would be truncated without changing Kafka.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    return parser.parse_args()


def build_admin_config(runtime_config: dict[str, object]) -> dict[str, object]:
    config: dict[str, object] = {
        "bootstrap.servers": ",".join(str(item) for item in runtime_config["brokers"]),
        "client.id": "delete-kafka-topic-data",
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


def fetch_partition_ids(admin: AdminClient, topic: str, request_timeout: float) -> list[int]:
    metadata = admin.list_topics(topic=topic, timeout=request_timeout)
    topic_metadata = metadata.topics.get(topic)
    if topic_metadata is None:
        raise RuntimeError(f"topic {topic!r} was not returned by Kafka metadata")

    if topic_metadata.error is not None:
        raise KafkaException(topic_metadata.error)

    return sorted(int(partition_id) for partition_id in topic_metadata.partitions)


def confirm(topic: str, brokers: list[str]) -> bool:
    print(f"About to delete all retained records from Kafka topic: {topic}")
    print(f"Brokers: {', '.join(brokers)}")
    answer = input("Type DELETE to continue: ").strip()
    return answer == "DELETE"


def main() -> int:
    args = parse_args()

    if AdminClient is None or TopicPartition is None:
        print(
            "confluent_kafka is required to run this script. "
            f"Import error: {IMPORT_ERROR!r}",
            file=sys.stderr,
        )
        return 1

    runtime_config = load_runtime_config(args.config)
    if args.topic:
        runtime_config["topic"] = args.topic

    brokers = [str(item).strip() for item in runtime_config.get("brokers", []) if str(item).strip()]
    topic = str(runtime_config.get("topic") or "").strip()
    if not brokers:
        print("kafka.brokers must not be empty", file=sys.stderr)
        return 1
    if not topic:
        print("kafka.topic must not be empty", file=sys.stderr)
        return 1

    admin = AdminClient(build_admin_config(runtime_config))
    partition_ids = fetch_partition_ids(admin, topic, args.request_timeout)
    if not partition_ids:
        print(f"Topic {topic!r} has no partitions; nothing to delete.")
        return 0

    partitions = [TopicPartition(topic, partition_id, OFFSET_END) for partition_id in partition_ids]

    print(f"Topic: {topic}")
    print(f"Partitions: {', '.join(str(partition_id) for partition_id in partition_ids)}")

    if args.dry_run:
        print("Dry run only; no Kafka records were deleted.")
        return 0

    if not args.yes and not confirm(topic, brokers):
        print("Cancelled.")
        return 1

    futures = admin.delete_records(
        partitions,
        request_timeout=args.request_timeout,
        operation_timeout=args.operation_timeout,
    )

    for partition, future in sorted(futures.items(), key=lambda item: int(item[0].partition)):
        result = future.result()
        print(
            f"Deleted records for {partition.topic}[{partition.partition}] "
            f"new_low_watermark={result.low_watermark}"
        )

    print("Kafka topic data deletion completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
