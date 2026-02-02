# create_topic.py
from kafka.admin import KafkaAdminClient, NewTopic
from config import BOOTSTRAP_SERVERS, TOPIC

admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
topic = NewTopic(name=TOPIC, num_partitions=3, replication_factor=1)
try:
    admin.create_topics([topic])
    print("Topic created")
except Exception as e:
    print("Topic may already exist:", e)
admin.close()
