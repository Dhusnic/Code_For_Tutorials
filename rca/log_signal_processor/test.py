from collections import Counter, defaultdict
from datetime import datetime, timezone


signal_logs = [{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"MD4w-5wBZ8e6K2BPdM5F","time_stamp":"2026-03-17T09:46:10.61Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"Mj4w-5wBZ8e6K2BPdM5J","time_stamp":"2026-03-17T09:46:10.611Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"YD4x-5wBZ8e6K2BPZtMR","time_stamp":"2026-03-17T09:47:07.629Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"Zj4x-5wBZ8e6K2BPZtMR","time_stamp":"2026-03-17T09:47:07.629Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"hT4x-5wBZ8e6K2BPo9SV","time_stamp":"2026-03-17T09:47:25.88Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"hz4x-5wBZ8e6K2BPo9SV","time_stamp":"2026-03-17T09:47:25.88Z"},{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"5j40-5wBZ8e6K2BP-eZc","time_stamp":"2026-03-17T09:51:10.611Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"6D40-5wBZ8e6K2BP-eZc","time_stamp":"2026-03-17T09:51:10.612Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"Cz42-5wBZ8e6K2BPCe21","time_stamp":"2026-03-17T09:52:07.667Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"bT41-5wBZ8e6K2BP4-wG","time_stamp":"2026-03-17T09:52:07.667Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"9z42-5wBZ8e6K2BPOO2e","time_stamp":"2026-03-17T09:52:25.902Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"8T42-5wBZ8e6K2BPOO2d","time_stamp":"2026-03-17T09:52:25.912Z"},{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"fD85-5wBZ8e6K2BPnACH","time_stamp":"2026-03-17T09:56:10.612Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"ez85-5wBZ8e6K2BPnACH","time_stamp":"2026-03-17T09:56:10.613Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"kj86-5wBZ8e6K2BPhgWk","time_stamp":"2026-03-17T09:57:07.706Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"kz86-5wBZ8e6K2BPhgWk","time_stamp":"2026-03-17T09:57:07.706Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"lz86-5wBZ8e6K2BP1AbU","time_stamp":"2026-03-17T09:57:25.908Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"mz86-5wBZ8e6K2BP1AbZ","time_stamp":"2026-03-17T09:57:25.916Z"},{"signal":"kafka_rebalance_storm","log_level":"info","doc_id":"Cz89-5wBZ8e6K2BPXBQ5","time_stamp":"2026-03-17T10:00:16.37Z"},{"signal":"kafka_rebalance_storm","log_level":"info","doc_id":"Dz89-5wBZ8e6K2BPXBQ7","time_stamp":"2026-03-17T10:00:16.798Z"},{"signal":"postgres_hba_blocked","log_level":"critical","doc_id":"CT89-5wBZ8e6K2BPXBQ5","time_stamp":"2026-03-17T10:00:17.014Z"},{"signal":"postgres_hba_blocked","log_level":"critical","doc_id":"DD89-5wBZ8e6K2BPXBQ5","time_stamp":"2026-03-17T10:00:17.014Z"},{"signal":"postgres_hba_blocked","log_level":"critical","doc_id":"Dj89-5wBZ8e6K2BPXBQ6","time_stamp":"2026-03-17T10:00:17.014Z"},{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"Lj8--5wBZ8e6K2BPLho3","time_stamp":"2026-03-17T10:01:10.613Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"LT8--5wBZ8e6K2BPLho3","time_stamp":"2026-03-17T10:01:10.614Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"tD8_-5wBZ8e6K2BPGiD0","time_stamp":"2026-03-17T10:02:07.744Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"tT8_-5wBZ8e6K2BPGiD0","time_stamp":"2026-03-17T10:02:07.744Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"jj8_-5wBZ8e6K2BPSCGN","time_stamp":"2026-03-17T10:02:25.853Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"kD8_-5wBZ8e6K2BPSCGN","time_stamp":"2026-03-17T10:02:25.853Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"2D9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:28.412Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"3D9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:30.337Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"zD9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:30.338Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"yz9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:30.553Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"0j9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:30.795Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"0z9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:31.401Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"2T9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:31.974Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"3z9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:35.566Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"0T9B-5wBZ8e6K2BPNilU","time_stamp":"2026-03-17T10:04:36.389Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"WT9C-5wBZ8e6K2BPtDN0","time_stamp":"2026-03-17T10:06:10.615Z"},{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"XD9C-5wBZ8e6K2BPtDN5","time_stamp":"2026-03-17T10:06:10.615Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"UD9D-5wBZ8e6K2BPpzp_","time_stamp":"2026-03-17T10:07:07.783Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"Vj9D-5wBZ8e6K2BPpzqA","time_stamp":"2026-03-17T10:07:07.783Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"8j9D-5wBZ8e6K2BPzjqW","time_stamp":"2026-03-17T10:07:25.863Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"-j9D-5wBZ8e6K2BPzjqd","time_stamp":"2026-03-17T10:07:25.864Z"},{"signal":"kafka_unclassified_failure","log_level":"debug","doc_id":"yz9H-5wBZ8e6K2BPXU2D","time_stamp":"2026-03-17T10:11:10.616Z"},{"signal":"kafka_unclassified_failure","log_level":"info","doc_id":"zj9H-5wBZ8e6K2BPXU2H","time_stamp":"2026-03-17T10:11:10.616Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"5z9I-5wBZ8e6K2BPNlMK","time_stamp":"2026-03-17T10:12:07.832Z"},{"signal":"rabbitmq_heartbeat_missed","log_level":"error","doc_id":"kz9I-5wBZ8e6K2BPXVRm","time_stamp":"2026-03-17T10:12:07.832Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"nD9I-5wBZ8e6K2BPXVRs","time_stamp":"2026-03-17T10:12:25.879Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"oj9I-5wBZ8e6K2BPXVRs","time_stamp":"2026-03-17T10:12:25.88Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"dT9K-5wBZ8e6K2BPAVsh","time_stamp":"2026-03-17T10:14:05.352Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"dD9K-5wBZ8e6K2BPAVsh","time_stamp":"2026-03-17T10:14:05.828Z"}]


def parse_time_stamp(time_stamp_text):
    supported_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]

    for time_format in supported_formats:
        try:
            parsed_time = datetime.strptime(time_stamp_text, time_format)
            return parsed_time.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Unsupported time format: {time_stamp_text}")


def format_duration(duration):
    total_seconds = int(duration.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours} hour(s), {minutes} minute(s), {seconds} second(s)"
    if minutes > 0:
        return f"{minutes} minute(s), {seconds} second(s)"
    return f"{seconds} second(s)"


def main():
    if not signal_logs:
        print("No logs found.")
        return

    time_stamp_texts = [entry["time_stamp"] for entry in signal_logs]
    parsed_time_stamps = [parse_time_stamp(value) for value in time_stamp_texts]

    earliest_time = min(parsed_time_stamps)
    latest_time = max(parsed_time_stamps)
    duration_in_list = latest_time - earliest_time

    doc_id_texts = [entry["doc_id"] for entry in signal_logs]
    doc_id_counts = Counter(doc_id_texts)
    duplicate_doc_ids = {
        doc_id: count
        for doc_id, count in doc_id_counts.items()
        if count > 1
    }
    signal_summary = defaultdict(Counter)
    for entry in signal_logs:
        signal_name = entry["signal"]
        log_level = entry["log_level"]
        signal_summary[signal_name]["total"] += 1
        signal_summary[signal_name][log_level] += 1

    print("Signal Log Summary")
    print("-" * 50)
    print(f"Total logs           : {len(signal_logs)}")
    print(f"Earliest time_stamp  : {earliest_time.isoformat()}")
    print(f"Latest time_stamp    : {latest_time.isoformat()}")
    print(f"Time range covered   : {format_duration(duration_in_list)}")

    print("\nSignal frequency with log levels")
    print("-" * 50)
    sorted_signals = sorted(
        signal_summary.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    )
    for signal_name, details in sorted_signals:
        log_level_parts = []
        for log_level, count in details.items():
            if log_level == "total":
                continue
            log_level_parts.append(f"{log_level}={count}")
        print(
            f"{signal_name:<32} | {details['total']:<3} | "
            f"{', '.join(log_level_parts)}"
        )

    print("\nDuplicate doc_id values")
    print("-" * 50)
    if not duplicate_doc_ids:
        print("No duplicate doc_id values found.")
    else:
        for doc_id, count in sorted(duplicate_doc_ids.items()):
            print(f"{doc_id} -> appears {count} times")


if __name__ == "__main__":
    main()
