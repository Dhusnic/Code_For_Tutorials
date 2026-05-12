#!/usr/bin/env python3

import os
import json
import signal
from datetime import datetime, timezone
from confluent_kafka import Consumer, KafkaException


BOOTSTRAP_SERVERS = "10.0.4.203:9092"
TOPIC = "linux-logs"
GROUP_ID = "linux-log-viewer"

CA_CERT = "./ca-cert"
KAFKA_USERNAME = "dnsadmin"
KAFKA_PASSWORD = "dnsadmin@123"

running = True


def stop_handler(signum, frame):
    global running
    running = False


def create_consumer():
    return Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,

        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "SCRAM-SHA-512",
        "sasl.username": KAFKA_USERNAME,
        "sasl.password": KAFKA_PASSWORD,

        "ssl.ca.location": CA_CERT,
        "ssl.endpoint.identification.algorithm": "none",

        "fetch.min.bytes": 1,
        "fetch.wait.max.ms": 100,
        "queued.min.messages": 10000,
    })


def print_log(msg):
    raw = msg.value()
    if raw is None:
        return

    text = raw.decode("utf-8", errors="replace")

    try:
        data = json.loads(text)
        output = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        output = text

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} topic={msg.topic()} partition={msg.partition()} offset={msg.offset()} {output}", flush=True)


def main():
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    consumer = create_consumer()
    consumer.subscribe([TOPIC])

    try:
        while running:
            messages = consumer.consume(num_messages=500, timeout=1.0)

            for msg in messages:
                if msg is None:
                    continue

                if msg.error():
                    raise KafkaException(msg.error())

                print_log(msg)

    finally:
        consumer.close()


if __name__ == "__main__":
    main()