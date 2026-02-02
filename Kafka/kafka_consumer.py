import signal, sys, json
from kafka import KafkaConsumer, TopicPartition
from config import BOOTSTRAP_SERVERS, TOPIC, GROUP_ID

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP_SERVERS,
    group_id=GROUP_ID,
    auto_offset_reset="earliest",  # start at beginning if no commit
    enable_auto_commit=False,      # we’ll commit explicitly
    key_deserializer=lambda k: k.decode() if k else None,
    value_deserializer=lambda v: json.loads(v.decode()),
    max_poll_records=10,
)

running = True
def handle_sig(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, handle_sig)

while running:
    records = consumer.poll(timeout_ms=1000)
    for tp, msgs in records.items():
        for m in msgs:
            print(f"partition={tp.partition} offset={m.offset} "
                  f"key={m.key} value={m.value}")
    # commit offsets for all partitions in one go
    consumer.commit()

print("Closing consumer...")
consumer.close()
