import json, time, random, string
from kafka import KafkaProducer
from config import BOOTSTRAP_SERVERS, TOPIC

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    acks="all",                    # safest delivery
    compression_type="gzip",       # shrink network traffic
    linger_ms=500,                 # wait up to 0.5 s to fill a batch
    batch_size=64_000,             # 64 kB batches
    key_serializer=lambda k: k.encode(),
    value_serializer=lambda v: json.dumps(v).encode(),
)

def rand_key():
    return random.choice(["red", "green", "blue"])     # three partitions

def rand_value():
    letters = string.ascii_lowercase
    return {"msg": "".join(random.choices(letters, k=8)),
            "ts": time.time()}

for i in range(20):
    key   = rand_key()
    value = rand_value()
    # partitioning: same key ⇒ same partition
    producer.send(TOPIC, key=key, value=value)
    print(f"sent {i:02} key={key} value={value}")
    time.sleep(0.2)

producer.flush()
producer.close()
