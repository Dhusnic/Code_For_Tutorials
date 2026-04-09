# Log Correlation Engine

This folder contains a production-oriented Go background service that reads retained signal logs from Redis, enriches them with full-log context, applies rule-based correlation, writes matches to Elasticsearch, and can optionally publish the matched results back to Redis for downstream consumers.

## What It Does

On each cycle the service:

1. Scans Redis for organization keys under the configured prefix, `Rca` by default.
2. Loads the raw `signaled_logs` hash field payload for each organization.
3. Loads the persisted correlation checkpoint from a JSON file and the active incident state from Redis for each organization.
4. Skips unchanged organizations cheaply when there are no active incidents to sweep.
5. Uses only `new signals + bounded lookback` for correlation instead of reprocessing the whole retained payload every cycle.
6. Enriches changed signal logs through the configured fetcher.
7. Compiles and filters correlation rules for that organization.
8. Reuses grouped, time-sorted log views by the rule `group_by` fields.
9. Deduplicates repeated signals within the rule deduplication window.
10. Matches ordered signal sequences using signal indexes instead of rescanning the full log slice for every candidate, and lets recovery close an incident without erasing a sequence that already completed.
11. Suppresses weaker overlapping RCA matches when a stronger incident already explains the same evidence.
12. Maintains an active incident per `organization + rule + group_by values`, updates the same Elasticsearch document for new evidence, closes incidents on recovery signals or inactivity timeout, and optionally publishes lifecycle events into a capped Redis list.

## Redis Contract

Input key:

```text
Rca:{organization}
```

Input type:

```text
HASH
```

Input field:

```text
signaled_logs
```

Input value example:

```json
[
  {
    "signal": "mongodb_auth_failed",
    "log_level": "warning",
    "doc_id": "doc_001",
    "time_stamp": "2026-04-08T12:30:00Z"
  },
  {
    "signal": "mongodb_host_unreachable",
    "log_level": "error",
    "doc_id": "doc_002",
    "time_stamp": "2026-04-08T12:31:00Z"
  }
]
```

Output key:

```text
Rca:{organization}:correlated_events
```

Output type:

```text
LIST
```

Output retention:

```text
LPUSH + LTRIM
```

The Redis result list is only used when `redis.publish_results` is enabled. When enabled, it is capped by `redis.result_list_max_len`.

Checkpoint file example:

The logical checkpoint key is still:

```text
Rca:135098068173316952064:correlation_checkpoint
```

On Windows the actual filename is sanitized because `:` is not allowed in file names, so the stored file looks like:

```text
data/checkpoints/Rca_135098068173316952064_correlation_checkpoint.json
```

Example file content:

```json
{
  "key": "Rca:135098068173316952064:correlation_checkpoint",
  "organization_id": "135098068173316952064",
  "checkpoint": "2026-04-08T12:31:00Z",
  "updated_at": "2026-04-08T12:31:05Z"
}
```

Output entry example:

`rule_completion` and `sequence_match` are both normalized to a `0..1` scale.

```json
{
  "incident_id": "a6d99f4c0d2e5b5a0f4a3f59e7e4f34c9d7f50f5d5c4a0a79d3e4c8a11f41234",
  "log_id": [
    {
      "id": "doc_001",
      "severity": "warning"
    },
    {
      "id": "doc_002",
      "severity": "warning"
    },
    {
      "id": "doc_003",
      "severity": "error"
    }
  ],
  "rule_completion": 0.75,
  "rule_id": "CORR_9XK2_MONGO_AUTH_CHAIN",
  "sequence_match": 0.6666666667
}
```

Elasticsearch document example:

The Elasticsearch writer stores the marshalled `CorrelationResult` as-is, so the indexed document shape matches the JSON below:

```json
{
  "incident_id": "f1d6f83a31e7bf0e69f24b28042fca19665ef8c5f73f8927303e99d6ff441234",
  "log_id": [
    {
      "id": "doc_101",
      "severity": "warning"
    },
    {
      "id": "doc_102",
      "severity": "warning"
    },
    {
      "id": "doc_103",
      "severity": "warning"
    },
    {
      "id": "doc_104",
      "severity": "error"
    }
  ],
  "rule_completion": 1,
  "rule_id": "CORR_P3Z9_QUEUE_BACKPRESSURE",
  "sequence_match": 1
}
```

## Configuration

Primary config file: [config/config.yml](./config/config.yml)

Key settings:

- `scheduler.interval`: how often one correlation cycle runs. Default `1m`.
- `scheduler.run_timeout`: maximum time allowed for one cycle. Default `50s`.
- `scheduler.organization_workers`: maximum number of organizations processed concurrently in one cycle. Default `4`.
- `redis.address`: Redis host and port.
- `redis.key_prefix`: Redis namespace prefix. Default `Rca`.
- `redis.hash_field`: Redis hash field that contains the signal log array. Default `signaled_logs`.
- `redis.result_list`: Redis list used for published correlation results. Default `correlated_events`.
- `redis.result_list_max_len`: maximum Redis correlation results kept per organization. Default `1000`.
- `redis.publish_results`: when `true`, publish correlation events to `redis.result_list`. Default `false`.
- `elasticsearch.addresses`: list of Elasticsearch hosts.
- `elasticsearch.index`: destination index for correlation results.
- `elasticsearch.request_timeout`: per-request timeout for Elasticsearch writes and health checks.
- `elasticsearch.bulk_batch_size`: number of correlation results sent per Bulk API request. Default `250`.
- `engine.rules_file`: JSON file that contains the correlation rules.
- `engine.hot_reload_interval`: how often the rules file is re-checked. Default `30s`.
- `engine.default_window`: fallback rule window when the rule omits one. Default `30m`.
- `engine.default_max_gap`: default max gap between sequence steps when a rule provides a non-empty gap value that resolves through fallback behavior. If a rule leaves `max_gap_between_steps` empty, the engine does not enforce a per-step gap limit for that rule.
- `engine.incremental_lookback`: additional minimum lookback added to the rule-derived incremental window. Default `0s`.
- `engine.incident_inactivity_ttl`: how long an active incident can stay unmatched before it is auto-closed. Default `30m`.
- `engine.checkpoint_directory`: directory that stores per-organization checkpoint JSON files. Default `data/checkpoints`.
- `fetcher.mode`: full-log fetcher implementation. Supported values are `mock` and `elasticsearch`.
- `fetcher.index`: source Elasticsearch index or pattern used to look up full documents by `doc_id`.
- `fetcher.timestamp_field`: source timestamp field used when the fetcher reads original documents. Default `@timestamp`.
- `fetcher.log_level_field`: source log level field used when the fetcher reads original documents. Default `log.level`.
- `logging.format`: `json` or `text`. Default `json`.

Phase 2 incident lifecycle behavior:

- The engine keeps a persistent checkpoint per organization and only correlates `new logs + bounded lookback`.
- That checkpoint is now stored as a local JSON file instead of a Redis string key.
- The active incident identity is built from `organization_id + rule_id + group_by values`.
- If a rule leaves `max_gap_between_steps` empty, that rule is evaluated against the full retained Redis payload for the organization instead of the incremental lookback slice.
- Elasticsearch stores correlation result events by deterministic document ID. A new matched signal set creates a new result document, while an exactly identical matched set reuses the same document ID instead of creating a duplicate entry.
- Lifecycle fields like `status`, `first_seen`, and `last_seen` are kept only in internal incident state and are not written into the final correlation result document.
- Incidents still move through `open`, `updated`, and `closed` states.
- Recovery signals in `not_sequence` close active incidents for the same group.
- Unmatched active incidents are auto-closed after `engine.incident_inactivity_ttl`.
- Redis publication is optional and append-only: when enabled, `open`, `updated`, and `closed` events are pushed as individual result entries.

Phase 1 optimization behavior:

- Raw Redis payloads are fingerprinted before JSON decode, so unchanged organizations are skipped cheaply.
- Organizations are processed with a bounded worker pool instead of a single serial loop.
- Rules are compiled and cached inside the engine, so durations and normalized sequence settings are not reparsed on every match.
- The engine caches grouped log views per distinct `group_by` set and uses signal indexes for sequence starts.
- Elasticsearch writes use the Bulk API instead of one request per result.

## Rule Shape

The engine expects a JSON rule array in [rules/rules.json](./rules/rules.json).

Example rule:

```json
{
  "id": "CORR_9XK2_MONGO_AUTH_CHAIN",
  "organization_id": "135098068173316952064",
  "rule_type": "ordered_signal_sequence",
  "window": "15m",
  "max_gap_between_steps": "3m",
  "group_by": ["event.organization", "host.name", "service.name"],
  "priority": 1,
  "sequence": [
    {
      "signal_key": "mongodb_auth_failed",
      "min_count": 1,
      "within": "5m"
    },
    {
      "signal_key": "mongodb_interrupted_client_disconnected",
      "min_count": 1,
      "within": "3m"
    },
    {
      "signal_key": "mongodb_host_unreachable",
      "min_count": 1,
      "within": "3m"
    }
  ],
  "not_sequence": [
    { "signal_key": "mongodb_auth_success" }
  ],
  "deduplication": {
    "key": ["signal_key", "host.name"],
    "window": "2m"
  }
}
```

## Build And Run

Build the Windows binary:

```powershell
cd "D:\Code for tutorials\rca\log_correlation_engine"
go build -o .\bin\correlation-engine.exe .\cmd
```

Quick build script:

```powershell
.\build.ps1
```

Run one cycle:

```powershell
.\bin\correlation-engine.exe --config .\config\config.yml --run-once
```

Run continuously:

```powershell
.\bin\correlation-engine.exe --config .\config\config.yml
```

Run tests:

```powershell
$env:GOCACHE="D:\Code for tutorials\rca\.gocache"
go test ./...
```

Run the Python smoke test:

```powershell
python .\test_integration.py
```

## Simulation Scripts

Create source signal documents in Elasticsearch for one correlation rule:

```powershell
python .\scripts\simulate_rule_logs.py --rule-id CORR_P3Z9_QUEUE_BACKPRESSURE
```

Run just one batch and exit:

```powershell
python .\scripts\simulate_rule_logs.py --rule-id CORR_P3Z9_QUEUE_BACKPRESSURE --once
```

Print the raw simulated Elasticsearch documents instead of the friendly summary:

```powershell
python .\scripts\simulate_rule_logs.py --rule-id CORR_P3Z9_QUEUE_BACKPRESSURE --once --user-readable false
```

Each simulation batch stamps a reusable KQL field:

```text
simulation.query_key : "sim-<run-id>"
```

Run the signaled logs collector once so the simulated Elasticsearch documents are copied into Redis:

```powershell
cd ..\log_signal_processor
go run .\cmd\signaled_logs_collector --config .\config.yml --run-once
```

Run the correlation engine once so Redis signals are converted into final correlation events:

```powershell
cd ..\log_correlation_engine
.\bin\correlation-engine.exe --config .\config\config.yml --run-once
```

Display correlation results from Elasticsearch in a readable format:

```powershell
python .\scripts\show_correlation_results.py
```

Print the raw Elasticsearch result documents instead of the friendly summary:

```powershell
python .\scripts\show_correlation_results.py --user-readable false
```

Each displayed correlation result also includes a direct KQL filter using the Elasticsearch result document key:

```text
_id : "<result-doc-id>"
```

Current note:
- The project config now uses the Elasticsearch fetcher, so correlation groups use the real nested source fields from the original documents.
- The simulator stamps a per-document `event.module` based on the signal prefix, such as `mongodb`, `nginx`, or `rabbitmq`.
- The simulator stamps `simulation.query_key` on every document in the same batch so you can query that exact run in Kibana.
- By default the simulator runs continuously with a configurable `--interval` between batches.

## Fetcher Modes

The default compiled fallback is still `mock`. It synthesizes full logs for each `doc_id` and keeps them in an in-memory cache so the engine can be exercised locally without wiring a real upstream log source yet.

The checked-in project config uses `fetcher.mode: elasticsearch`, which looks up the original source document by `doc_id`, preserves the full nested `_source` payload in `metadata`, and lets `group_by` rules operate on the real `event.*`, `host.*`, and `service.*` fields.

## Package Layout

- [cmd/main.go](./cmd/main.go): application bootstrap, dependency wiring, and graceful shutdown.
- [internal/config/config.go](./internal/config/config.go): config loading, defaults, normalization, and validation.
- [internal/logger/logger.go](./internal/logger/logger.go): slog logger factory with configurable level and format.
- [internal/scheduler/runner.go](./internal/scheduler/runner.go): panic-safe interval runner.
- [internal/service/processor.go](./internal/service/processor.go): organization discovery, enrichment, correlation, write, and publish flow.
- [internal/redis/client.go](./internal/redis/client.go): Redis client wrapper.
- [internal/redis/store.go](./internal/redis/store.go): Redis hash input and Redis list output contract.
- [internal/loader/logfetcher.go](./internal/loader/logfetcher.go): mock and Elasticsearch-backed full-log fetchers.
- [internal/rules/loader.go](./internal/rules/loader.go): JSON rule loading and hot reload support.
- [internal/engine/engine.go](./internal/engine/engine.go): grouping, deduplication, and ordered sequence matching.
- [internal/elastic/writer.go](./internal/elastic/writer.go): Elasticsearch writer for correlation results.
- [internal/models/models.go](./internal/models/models.go): signal log, rule, and result models.
- [internal/utils/duration.go](./internal/utils/duration.go): duration parsing helpers.
- [internal/utils/groupby.go](./internal/utils/groupby.go): metadata extraction and group-key helpers.
