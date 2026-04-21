# Log Correlation Engine

This folder contains a production-oriented Go background service that reads retained signal logs from Redis, enriches them with full-log context, applies rule-based correlation, writes matches to Elasticsearch, and can optionally publish the matched results back to Redis for downstream consumers.

It now also supports an optional direct compact-signal stream ingest path:

```text
log_signalizing -> Redis stream -> log_correlation_engine -> same Redis hot state + same final RCA output
```

When that stream path is enabled, the correlation engine hydrates its existing `Rca:{organization}` `signaled_logs` state from the Redis stream before it runs the normal rule pipeline. That means the external hot-state contract and final Elasticsearch result shape stay the same, but the extra Elasticsearch reread hop can be skipped.

## What It Does

On each cycle the service:

1. Scans Redis for organization hashes that contain either retained `signaled_logs` or embedded `active_incidents`.
2. Loads the raw `signaled_logs` hash field payload for each organization.
3. Loads the persisted correlation checkpoint from a JSON file and the active incident state from Redis for each organization.
4. Skips unchanged organizations cheaply when there are no active incidents to sweep.
5. Uses only `new signals + bounded lookback` for correlation instead of reprocessing the whole retained payload every cycle.
6. Enriches changed signal logs through the configured fetcher, batching full-document lookups whenever the fetcher supports it.
7. Compiles and filters correlation rules for that organization.
8. Reuses grouped, time-sorted log views by the rule `group_by` fields.
9. Deduplicates repeated signals within the rule deduplication window.
10. Matches ordered signal sequences using signal indexes instead of rescanning the full log slice for every candidate, and lets recovery close an incident without erasing a sequence that already completed.
11. Suppresses weaker overlapping RCA matches when a stronger incident already explains the same evidence.
12. Maintains incident episodes: derives a stable incident key from `organization + rule + group_by values`, reuses the same incident when a match recurs within `engine.incident_inactivity_ttl`, and creates a new `incident_id` when it recurs after that window; closes on recovery signals or inactivity timeout (closed state is retained briefly so fast reopens do not fork new incidents).
13. Emits structured match-audit logs for every live or shadow rule match so you can see exactly which rule, group, steps, metadata filters, and matched document IDs produced the RCA result.
14. When `redis.signal_stream_enabled` is true, ingests new compact signal events from the Redis stream, merges them into the existing per-organization `signaled_logs` payload with retention/deduplication, checkpoints the stream id, trims the stream by consumer-aware retention, and then runs the normal correlation cycle on that refreshed state.

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

Additional incident field in the same organization hash:

```text
active_incidents
```

Incident field type:

```text
JSON array stored inside the same HASH
```

The engine no longer stores active incidents as separate Redis keys. Each organization now keeps only the mandatory Redis structures:

- one `HASH` at `Rca:{organization}` with:
  - `signaled_logs`
  - `active_incidents`
- one shared `STREAM` at `Rca:signalized_log_events`

Stream retention behavior:

- entries that are already past the saved correlation stream checkpoint are trimmed after `redis.signal_stream_consumed_retention`
- entries that are still not consumed are allowed to stay longer, up to `redis.signal_stream_unconsumed_retention`
- this is done with consumer-side stream trimming, not with a plain `EXPIRE` on the whole stream key

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
  "signal_payload_signature": "4d2f0c9eb3c0d5cde7d5a5d1fbec7e8f21c8fd24636cf0c57d4e4f01192c3c8d",
  "signal_count": 42,
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
- `redis.signal_stream_enabled`: when `true`, ingest compact signal events from Redis stream before each cycle. The checked-in config enables this path by default.
- `redis.signal_stream_key`: Redis stream that carries compact signal events from signalizing. Default `Rca:signalized_log_events`.
- `redis.signal_stream_batch_size`: maximum stream entries fetched per Redis round trip while catching up. Default `1000`.
- `redis.signal_stream_consumed_retention`: how long already-consumed stream entries are kept before they are trimmed. Default `30m`.
- `redis.signal_stream_unconsumed_retention`: how long not-yet-consumed backlog can stay in the stream before it is trimmed. Default `2h`.
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
- That checkpoint is now stored as a local JSON file instead of a Redis string key, and it also persists the last payload signature and signal count so unchanged organizations can still be skipped after a process restart.
- The engine derives a stable incident key from `organization_id + rule_id + group_by values`, then builds an episode `incident_id` from that key plus the episode start time.
- If a rule leaves `max_gap_between_steps` empty, only that rule is evaluated against the full retained Redis payload for the organization. Other rules keep using the cheaper incremental lookback slice in the same cycle.
- Elasticsearch stores correlation result events by deterministic document ID. A new matched signal set creates a new result document, while an exactly identical matched set reuses the same document ID instead of creating a duplicate entry.
- Lifecycle fields like `status`, `first_seen`, and `last_seen` are written into correlation result documents and mirrored in Redis incident state.
- Incidents still move through `open`, `updated`, and `closed` states.
- Recovery signals in `not_sequence` close active incidents for the same group key (and are kept for the reopen window).
- Unmatched active incidents are auto-closed after `engine.incident_inactivity_ttl` and then purged after the same reopen window if no new evidence arrives.
- Redis publication is optional and append-only: when enabled, `open`, `updated`, and `closed` events are pushed as individual result entries.

Phase 3 accuracy and control behavior:

- Rules can now declare `required_metadata` so correlation only considers logs whose enriched metadata matches the exact field/value anchors you want, such as `event.module`, `service.name`, `kubernetes.namespace`, or environment tags.
- Rules can now run in `shadow_mode`. Shadow rules are evaluated and logged, but they do not create incidents, do not write Elasticsearch result documents, and do not publish Redis result events.
- When full-payload rules and incremental rules exist together, the processor enriches the full-payload set once and reuses that cache for the incremental pass instead of refetching the same document context twice.
- Every emitted or shadowed match now carries a structured `audit` log payload in the service logs with rule shape, group-by values, required metadata, negative signals, dedup settings, per-step matched counts, and matched document IDs. This audit payload is for debugging and is not written into the final Elasticsearch result document.
- Sequence steps can now use `any_of` and `all_of` blocks so one ordered step can express a clean OR group or AND group without flattening everything into one large `signal_keys` list.

Phase 1 optimization behavior:

- Raw Redis payloads are fingerprinted before JSON decode, so unchanged organizations are skipped cheaply.
- Redis storage is reduced to the mandatory keys only: the shared signal stream plus one organization hash that contains both `signaled_logs` and `active_incidents`.
- Organizations are processed with a bounded worker pool instead of a single serial loop.
- Rules are compiled and cached inside the engine, so durations and normalized sequence settings are not reparsed on every match.
- The engine caches grouped log views per distinct `group_by` set and uses signal indexes for sequence starts.
- Full-log enrichment batches repeated `doc_id` lookups, so the Elasticsearch fetcher avoids one request per signal when multiple documents need context in the same cycle.
- Elasticsearch writes use the Bulk API instead of one request per result.

Optional direct stream ingest behavior:

- `log_signalizing` can publish compact signal events into Redis stream `redis.signal_stream_key`.
- `log_correlation_engine` can ingest that stream directly and refresh the same `Rca:{organization}` hot state it already uses.
- The correlation consumer trims that stream with two windows: a shorter retention for already-consumed entries and a longer safety buffer for backlog that has not been consumed yet.
- This keeps the current correlation input and final output contracts stable.
- The legacy `log_signal_processor` path can remain enabled as a fallback during migration, but it is no longer required for the stream-enabled path.

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
  "required_metadata": {
    "event.module": "mongodb"
  },
  "shadow_mode": false,
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

Sequence step alternatives:

- Use `signal_key` for a single required signal.
- Use `signal_keys` for an OR group where any one signal can satisfy the step.
- Use `any_of` for a block where any one selector satisfies the step.
- Use `all_of` for a block where every selector must match within the same step window.

Example step:

```json
{
  "signal_keys": ["kafka_broker_not_available", "mongodb_host_unreachable", "postgres_conn_failed"],
  "min_count": 1,
  "within": "5m"
}
```

`any_of` example:

```json
{
  "any_of": [
    { "signal_key": "kafka_broker_not_available" },
    { "signal_key": "mongodb_host_unreachable" },
    { "signal_key": "postgres_conn_failed" }
  ],
  "within": "10m"
}
```

`all_of` example:

```json
{
  "all_of": [
    { "signal_key": "data_collector_service_down" },
    { "signal_keys": ["systemd_unit_failed", "systemd_watchdog_timeout"] }
  ],
  "within": "6m"
}
```

Grouped step behavior:

- `any_of` is still one ordered step. The step is complete when any one selector in the block matches.
- `all_of` is still one ordered step. The step is complete only when every selector in the block matches before the step deadline.
- Inside one selector object, `signal_key` and `signal_keys` behave the same as today, so you can still use a small OR group inside an `all_of` block.
- For clarity, use only one selector style per step: either legacy `signal_key` / `signal_keys`, or `any_of`, or `all_of`.
- `grouped` steps currently assume one match per selector. If you need repeated counts like `min_count: 3`, keep using the legacy `signal_key` / `signal_keys` step style.

Cross-service join behavior:

- `group_by` already supports arbitrary nested metadata fields from the enriched log document.
- That means you can group by the usual `event.organization` and `host.identity`, and optionally add join keys such as `attr.run_id`, `trace.id`, `transaction.id`, or parsed labels when those fields exist in your logs.
- This is the clean way to improve accuracy when multiple services on the same host emit related failure signals for the same request or run.

## Match Scoring

The engine emits both `rule_completion` and `sequence_match` on a `0..1` scale.

For each sequence step `i`:

- `required_i = max(1, min_count_i)`
- `matched_i = min(actual_ordered_matches_i, required_i)`

Then the final scores are:

```text
rule_completion = (sum of matched_i) / (sum of required_i)
sequence_match = (completed_prefix_steps + partial_progress_of_next_step) / number_of_steps
```

Meaning:

- `rule_completion` is occurrence-weighted, so a step with `min_count: 3` contributes more than a step with `min_count: 1`
- `sequence_match` is ordered-prefix progress, so only the fully completed steps from the start of the sequence plus any partial progress on the next step contribute
- extra matches above `min_count` do not increase the score beyond `1` for that step
- if a step has `min_count <= 0`, the engine treats it as `1`
- later steps contribute `0` until all earlier steps are fully complete
- both scores are based on the ordered sequence matcher, not on unordered signal presence

Example:

If a rule has `min_count` values `[3, 1, 1]` and the engine matched `[2, 1, 0]`, then:

```text
rule_completion = (2 + 1 + 0) / (3 + 1 + 1) = 3/5 = 0.6
sequence_match = (0 + 2/3) / 3 = 0.2222
```

If a rule has `min_count` values `[3, 1, 1]` and the engine matched `[3, 1, 0]`, then:

```text
rule_completion = (3 + 1 + 0) / (3 + 1 + 1) = 4/5 = 0.8
sequence_match = (2 + 0) / 3 = 0.6667
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

Start the whole RCA stack from the repo root with PM2:

```powershell
cd "D:\Code for tutorials\rca"
pm2 start .\ecosystem.config.js
```

That root PM2 stack now starts the direct-stream path by default:

```text
log_signalizing/signalizing_go -> Redis stream -> log_correlation_engine
```

The collector is no longer part of the default root PM2 boot path. Run [log_signal_processor](../log_signal_processor/README.md) separately only when you want the legacy compatibility path.

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
