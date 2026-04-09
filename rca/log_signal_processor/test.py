from collections import Counter, defaultdict
from datetime import datetime, timezone


signal_logs = [{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"BTZdbJ0BFK2GVfCYdAZW","time_stamp":"2026-04-08T09:12:25.87Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"_TZdbJ0BFK2GVfCYdAVW","time_stamp":"2026-04-08T09:12:25.87Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"ETZibJ0BFK2GVfCYHAox","time_stamp":"2026-04-08T09:17:26.165Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"_DZibJ0BFK2GVfCYHAkt","time_stamp":"2026-04-08T09:17:26.476Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"ZDZmbJ0BFK2GVfCYtA1L","time_stamp":"2026-04-08T09:22:25.914Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"bjZmbJ0BFK2GVfCYtA1X","time_stamp":"2026-04-08T09:22:25.914Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"wDZobJ0BFK2GVfCYFw7r","time_stamp":"2026-04-08T09:24:10.026Z"},{"signal":"nginx_access_5xx_any","log_level":"warning","doc_id":"8zZobJ0BFK2GVfCYSw7G","time_stamp":"2026-04-08T09:24:19Z"},{"signal":"nginx_access_5xx_any","log_level":"warning","doc_id":"9DZobJ0BFK2GVfCYSw7G","time_stamp":"2026-04-08T09:24:19Z"}]


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
