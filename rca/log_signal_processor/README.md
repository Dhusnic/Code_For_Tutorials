# Signaled Logs Collector

This folder contains a production-oriented Go background service that polls Elasticsearch every minute, extracts documents that contain a configured `signal` field, groups them by `event.organization` by default, and stores the retained signal history in Redis.

It now sits alongside an optional direct handoff path:

```text
log_signalizing -> Redis stream -> log_correlation_engine
```

When that stream path is enabled, the correlation engine can hydrate the same Redis hot state directly from compact signal events without waiting for this collector to reread Elasticsearch. That means this service becomes a compatibility or fallback path instead of a hard requirement, while the Redis hash contract and final RCA output shape stay the same.

## What It Does

On each cycle the service:

1. Computes the sliding query window from `now - 10m` to `now` by default.
2. Acquires either a single Redis cycle lock or shard-specific Redis locks, depending on `lock.shard_count`.
3. Queries Elasticsearch for documents that both fall in the window and contain the configured signal field.
4. Normalizes each matching document into:

```json
{
  "signal": "disk_failure",
  "log_level": "critical",
  "doc_id": "abc123",
  "time_stamp": "2026-03-17T10:21:00Z"
}
```

5. Groups records by organization.
6. Merges the new records with the existing Redis payload for each organization.
7. Dedupes by `doc_id`.
8. Trims anything older than the configured retention window, 30 minutes by default.
9. Skips the Redis write completely if the merged organization payload is byte-for-byte unchanged.
10. Persists organizations in parallel with a bounded worker pool.
11. Writes the sorted JSON array back to the Redis hash field `signaled_logs` without creating a separate Redis organization index key.

## When To Run This Service

Use this collector when:

- you want the original Elasticsearch -> Redis retained-signal path
- you want a fallback path while migrating to direct stream ingest
- `log_signalizing` is not publishing compact signal events into Redis stream yet

You can treat it as optional when both of these are enabled:

- `log_signalizing/config.yml` -> `signal_stream.enabled: true`
- `log_correlation_engine/config/config.yml` -> `redis.signal_stream_enabled: true`

In that direct-stream mode, `log_correlation_engine` ingests compact signal events first, refreshes the same `Rca:{organization}` `signaled_logs` hot state itself, and then runs the normal correlation flow. The existing Redis key structure and downstream RCA outputs do not change.

## Redis Storage Contract

Default Redis key:

```text
Rca:{organization}
```

Redis type:

```text
HASH
```

Field name:

```text
signaled_logs
```

Field value example:

```json
[
  {
    "signal": "disk_failure",
    "log_level": "critical",
    "doc_id": "abc123",
    "time_stamp": "2026-03-17T10:21:00Z"
  },
  {
    "signal": "cpu_high",
    "log_level": "warning",
    "doc_id": "abc124",
    "time_stamp": "2026-03-17T10:22:00Z"
  }
]
```

The service removes only the `signaled_logs` field when that retained list becomes empty. If the same organization hash also carries correlation incident state, the hash itself is preserved.

## Configuration

Primary config file: [config.yml](./config.yml)

Key settings:

- `scheduler.interval`: job frequency. Default `1m`.
- `scheduler.run_timeout`: maximum time allowed for one cycle. Default `50s`.
- `scheduler.organization_workers`: number of parallel organization merge/save workers inside one cycle. Default `4`.
- `elasticsearch.addresses`: list of Elasticsearch hosts.
- `elasticsearch.index`: source index or index pattern.
- `elasticsearch.page_size`: page size for `search_after` pagination.
- `elasticsearch.max_pages`: optional hard cap for pages per cycle. `0` means unlimited.
- `elasticsearch.window`: sliding query window. Default `10m`.
- `elasticsearch.use_point_in_time`: enables PIT-backed pagination so the collector does not need to sort on `_id`. Default `true`.
- `elasticsearch.pit_keep_alive`: PIT keep-alive for paginated reads. Default `2m`.
- `elasticsearch.extra_filters`: optional additional Elasticsearch filter clauses.
- `redis.address`: Redis host and port.
- `redis.key_prefix`: Redis namespace prefix. Default `Rca`.
- `redis.hash_field`: Redis hash field name. Default `signaled_logs`.
- `redis.retention_window`: retention cutoff. Default `30m`.
- `lock.enabled`: enables the Redis leader lock. Default `true`.
- `lock.key`: lock key. Default `Rca:collector_lock`.
- `lock.shard_count`: number of shard locks used to split organizations across PM2 instances. Default `1`. The checked-in config uses `8`.
- `lock.ttl`: lock TTL. Default `90s`.
- `mappings.organization_field`: source organization field. Default `event.organization`.
- `mappings.signal_field`: source signal field. Default `signal`.
- `mappings.log_level_field`: source log level field. Default `log_level`.
- `mappings.timestamp_field`: source timestamp field. Default `@timestamp`.
- `mappings.doc_id_source`: `_id` or `field`.
- `mappings.doc_id_field`: source field used when `doc_id_source` is `field`.

Common environment overrides are also supported with `SLP_` prefixes, for example `SLP_REDIS_ADDRESS`, `SLP_ELASTICSEARCH_INDEX`, `SLP_SCHEDULER_INTERVAL`, and `SLP_LOCK_TTL`.

## Build And Run

Build the Windows binary:

```powershell
cd "D:\Code for tutorials\rca\log_signal_processor"
go build -o .\bin\signaled-logs-collector.exe .\cmd\signaled_logs_collector
```

Quick rebuild scripts:

```powershell
.\rebuild.ps1
```

```sh
./rebuild.sh
```

Run one cycle:

```powershell
.\bin\signaled-logs-collector.exe --config .\config.yml --run-once
```

Run continuously:

```powershell
.\bin\signaled-logs-collector.exe --config .\config.yml
```

Run tests:

```powershell
go test ./...
```

## PM2 Multi-Instance Behavior

PM2 configuration lives in [app.json](./app.json). It runs the compiled Go binary directly with `exec_interpreter: "none"` and supports multiple instances.

Recommended flow:

```powershell
cd "D:\Code for tutorials\rca\log_signal_processor"
go build -o .\bin\signaled-logs-collector.exe .\cmd\signaled_logs_collector
pm2 start .\app.json
pm2 logs signaled-logs-collector
```

PM2 does not coordinate scheduled jobs for Go processes. Duplicate Elasticsearch reads are prevented by the Redis lock:

- when `lock.shard_count=1`, every worker wakes up on the same schedule and only one worker acquires `lock.key` for the whole cycle
- when `lock.shard_count>1`, PM2 instances deterministically own a subset of shard locks based on the PM2 instance id and `SLP_PM2_INSTANCES`
- each shard lock maps to a stable subset of organizations, so different instances can merge and persist disjoint organizations in parallel
- release still uses a compare-and-delete Lua script so a worker only removes shard locks it actually owns
- standalone or `--run-once` execution without PM2 falls back to owning all shards, so the full dataset is still processed

Current limitation:

- Elasticsearch fetches are still performed per process before shard filtering. Shard locking removes duplicate Redis writes and unlocks parallel persistence, but it does not yet eliminate duplicate Elasticsearch reads across PM2 instances.

You can also start the whole RCA stack from the repo root with:

```powershell
cd "D:\Code for tutorials\rca"
pm2 start .\ecosystem.config.js
```

That root PM2 stack no longer starts this collector by default. It boots the direct stream path instead:

```text
log_signalizing/signalizing_go -> Redis stream -> log_correlation_engine
```

Run this collector separately only when you want the legacy Elasticsearch -> Redis compatibility flow.

## Package Layout

- [cmd/signaled_logs_collector/main.go](./cmd/signaled_logs_collector/main.go): application bootstrap and graceful shutdown.
- [internal/config/config.go](./internal/config/config.go): config loading, defaults, env overrides, validation.
- [internal/elasticsearch/client.go](./internal/elasticsearch/client.go): Elasticsearch client wrapper.
- [internal/elasticsearch/repository.go](./internal/elasticsearch/repository.go): paginated signal log query.
- [internal/redisstore/store.go](./internal/redisstore/store.go): Redis hash storage.
- [internal/redisstore/lock.go](./internal/redisstore/lock.go): distributed lock helper.
- [internal/service/collector.go](./internal/service/collector.go): core fetch/normalize/merge/store flow.
- [internal/scheduler/runner.go](./internal/scheduler/runner.go): panic-safe ticker loop.
- [internal/util/mapextract.go](./internal/util/mapextract.go): nested field extraction and timestamp parsing.
