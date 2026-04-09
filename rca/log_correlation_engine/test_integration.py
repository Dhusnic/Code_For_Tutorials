#!/usr/bin/env python3
"""
Integration test for the log correlation engine.
Tests the Redis hash input contract and Redis list output contract.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import redis
except ImportError:
    print("Error: redis-py not installed. Install with: pip install redis")
    sys.exit(1)


class CorrelationTester:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True
        )
        self.org_id = "135098068173316952064"
        self.input_key = f"Rca:{self.org_id}"
        self.input_field = "signaled_logs"
        self.result_key = f"Rca:{self.org_id}:correlated_events"

    def connect(self):
        try:
            self.redis_client.ping()
            print("[OK] Connected to Redis")
            return True
        except Exception as exc:
            print(f"[FAIL] Failed to connect to Redis: {exc}")
            return False

    def clear_data(self):
        self.redis_client.delete(self.input_key)
        self.redis_client.delete(self.result_key)
        print("[OK] Cleared previous data")

    def push_test_logs(self):
        base_time = datetime.now(timezone.utc)
        logs = [
            {
                "signal": "mongodb_auth_failed",
                "log_level": "warning",
                "doc_id": "doc_001",
                "time_stamp": (base_time - timedelta(minutes=5)).isoformat(),
            },
            {
                "signal": "mongodb_auth_failed",
                "log_level": "warning",
                "doc_id": "doc_002",
                "time_stamp": (base_time - timedelta(minutes=4, seconds=30)).isoformat(),
            },
            {
                "signal": "mongodb_interrupted_client_disconnected",
                "log_level": "warning",
                "doc_id": "doc_003",
                "time_stamp": (base_time - timedelta(minutes=4)).isoformat(),
            },
            {
                "signal": "mongodb_host_unreachable",
                "log_level": "error",
                "doc_id": "doc_004",
                "time_stamp": (base_time - timedelta(minutes=3)).isoformat(),
            },
        ]

        self.redis_client.hset(self.input_key, self.input_field, json.dumps(logs))

        print(f"[OK] Wrote {len(logs)} test logs to Redis hash")
        for log in logs:
            print(f"  - {log['signal']} (doc_id: {log['doc_id']})")

    def monitor_results(self, timeout=30):
        start_time = time.time()

        print(f"\nMonitoring for results (timeout: {timeout}s)...")

        while time.time() - start_time < timeout:
            results_count = self.redis_client.llen(self.result_key)
            if results_count > 0:
                print(f"\n[OK] Found {results_count} correlation result(s)")
                for _ in range(results_count):
                    result_data = self.redis_client.lpop(self.result_key)
                    if result_data:
                        self.print_result(json.loads(result_data))
                return True

            payload = self.redis_client.hget(self.input_key, self.input_field)
            input_count = len(json.loads(payload)) if payload else 0
            elapsed = int(time.time() - start_time)
            print(f"  Input logs available: {input_count}, elapsed: {elapsed}s")
            time.sleep(1)

        print(f"[FAIL] No results found within {timeout}s")
        return False

    def print_result(self, result):
        compact_logs = result.get("log_id", [])
        print(
            f"""
  Rule: {result.get('rule_id', 'N/A')}
  Completion: {result.get('rule_completion', 0):.2%}
  Sequence Match: {result.get('sequence_match', 0):.2%}
  Matched Logs: {compact_logs}
"""
        )

    def run(self):
        print("=" * 60)
        print("Log Correlation Engine Integration Test")
        print("=" * 60)

        if not self.connect():
            return False

        self.clear_data()
        self.push_test_logs()

        success = self.monitor_results()

        print("\n" + "=" * 60)
        print("[OK] Test PASSED" if success else "[FAIL] Test FAILED")
        print("=" * 60)
        return success


if __name__ == "__main__":
    tester = CorrelationTester()
    success = tester.run()
    sys.exit(0 if success else 1)
