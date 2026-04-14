from collections import Counter, defaultdict
from datetime import datetime, timezone


signal_logs = [{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"AnMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:00.973Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"6nMXhp0BFK2GVfCYR9Yt","time_stamp":"2026-04-13T09:06:01.002Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"DnMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:01.142Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"BXMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:01.175Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"63MXhp0BFK2GVfCYR9Yt","time_stamp":"2026-04-13T09:06:01.221Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"8nMXhp0BFK2GVfCYR9Yt","time_stamp":"2026-04-13T09:06:01.221Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"BHMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:01.237Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"CHMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:01.237Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"-HMXhp0BFK2GVfCYR9ZC","time_stamp":"2026-04-13T09:06:01.331Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"EXMXhp0BFK2GVfCYR9dC","time_stamp":"2026-04-13T09:06:01.331Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"7XMXhp0BFK2GVfCYR9Yt","time_stamp":"2026-04-13T09:06:01.345Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"2nMYhp0BFK2GVfCYk9iv","time_stamp":"2026-04-13T09:07:25.897Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"4HMYhp0BFK2GVfCYk9iv","time_stamp":"2026-04-13T09:07:25.897Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"onMchp0BFK2GVfCYhOIa","time_stamp":"2026-04-13T09:11:41.824Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"p3Mchp0BFK2GVfCYhOIa","time_stamp":"2026-04-13T09:11:42.206Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"k3Mchp0BFK2GVfCYhOIJ","time_stamp":"2026-04-13T09:11:43.41Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"rnMchp0BFK2GVfCYhOIa","time_stamp":"2026-04-13T09:11:44.034Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"33Mdhp0BFK2GVfCYAeI1","time_stamp":"2026-04-13T09:12:04.073Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"4HMdhp0BFK2GVfCYAeI1","time_stamp":"2026-04-13T09:12:04.562Z"},{"signal":"mongodb_slow_command","log_level":"warning","doc_id":"8HMdhp0BFK2GVfCYAeI4","time_stamp":"2026-04-13T09:12:05.834Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"33Mdhp0BFK2GVfCYVuX5","time_stamp":"2026-04-13T09:12:25.927Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"7XMdhp0BFK2GVfCYVuX5","time_stamp":"2026-04-13T09:12:25.927Z"},{"signal":"nginx_unclassified_failure","log_level":"critical","doc_id":"JXMfhp0BFK2GVfCYMOsv","time_stamp":"2026-04-13T09:14:33Z"},{"signal":"nginx_access_5xx_any","log_level":"warning","doc_id":"b3Mfhp0BFK2GVfCYMOuL","time_stamp":"2026-04-13T09:14:33Z"},{"signal":"nginx_access_5xx_any","log_level":"warning","doc_id":"bXMfhp0BFK2GVfCYMOuK","time_stamp":"2026-04-13T09:14:33Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"UHMhhp0BFK2GVfCY2_Gg","time_stamp":"2026-04-13T09:17:25.894Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"UXMhhp0BFK2GVfCY2_Gg","time_stamp":"2026-04-13T09:17:25.894Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"nXQmhp0BFK2GVfCYdAFS","time_stamp":"2026-04-13T09:22:25.894Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"4HQmhp0BFK2GVfCYdAF0","time_stamp":"2026-04-13T09:22:25.895Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"-3Qrhp0BFK2GVfCYDw5r","time_stamp":"2026-04-13T09:27:25.955Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"xHQrhp0BFK2GVfCYDw5d","time_stamp":"2026-04-13T09:27:25.955Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"qnQrhp0BFK2GVfCYDw5O","time_stamp":"2026-04-13T09:27:27.101Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"nnQrhp0BFK2GVfCYDw5I","time_stamp":"2026-04-13T09:27:27.102Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"zXQrhp0BFK2GVfCYDw5d","time_stamp":"2026-04-13T09:27:27.271Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"03Qrhp0BFK2GVfCYDw5d","time_stamp":"2026-04-13T09:27:27.272Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"1XQrhp0BFK2GVfCYZRBO","time_stamp":"2026-04-13T09:27:48.173Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"sXQrhp0BFK2GVfCYZRAx","time_stamp":"2026-04-13T09:27:48.173Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"5XQrhp0BFK2GVfCYZRBR","time_stamp":"2026-04-13T09:27:53.447Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"0HQrhp0BFK2GVfCYZRBB","time_stamp":"2026-04-13T09:27:53.448Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"tHQrhp0BFK2GVfCYZRAx","time_stamp":"2026-04-13T09:27:53.448Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"x3Qrhp0BFK2GVfCYZRA4","time_stamp":"2026-04-13T09:27:53.448Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"2HQrhp0BFK2GVfCYZRBO","time_stamp":"2026-04-13T09:27:57.769Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"tnQrhp0BFK2GVfCYZRAx","time_stamp":"2026-04-13T09:27:57.769Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"YXQshp0BFK2GVfCYHBP2","time_stamp":"2026-04-13T09:28:44.514Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"YnQshp0BFK2GVfCYHBP2","time_stamp":"2026-04-13T09:28:44.515Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"V3Qshp0BFK2GVfCYHBP2","time_stamp":"2026-04-13T09:28:44.7Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"WHQshp0BFK2GVfCYHBP2","time_stamp":"2026-04-13T09:28:44.701Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"PXQuhp0BFK2GVfCYPxjd","time_stamp":"2026-04-13T09:31:04.758Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"TnQuhp0BFK2GVfCYPxjd","time_stamp":"2026-04-13T09:31:04.759Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"c3Qvhp0BFK2GVfCYKhpE","time_stamp":"2026-04-13T09:31:55.082Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"dnQvhp0BFK2GVfCYKhpW","time_stamp":"2026-04-13T09:31:55.082Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"l3Qvhp0BFK2GVfCYaxsD","time_stamp":"2026-04-13T09:32:25.899Z"},{"signal":"mongodb_auth_failed","log_level":"warning","doc_id":"lnQvhp0BFK2GVfCYaxsD","time_stamp":"2026-04-13T09:32:25.899Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"Q3Qwhp0BFK2GVfCYnSJs","time_stamp":"2026-04-13T09:33:26.23Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"RHQwhp0BFK2GVfCYnSJs","time_stamp":"2026-04-13T09:33:26.23Z"},{"signal":"mongodb_interrupted_client_disconnected","log_level":"warning","doc_id":"THQwhp0BFK2GVfCYnSJ2","time_stamp":"2026-04-13T09:33:26.231Z"},{"signal":"mongodb_host_unreachable","log_level":"critical","doc_id":"TXQwhp0BFK2GVfCYnSJ2","time_stamp":"2026-04-13T09:33:26.231Z"}]


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
