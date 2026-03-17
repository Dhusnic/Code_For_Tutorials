# Signaled Logs Collector

This folder contains a production-oriented Go background service that polls Elasticsearch every minute, extracts documents that contain a configured `signal` field, groups them by `event.organization` by default, and stores the retained signal history in Redis.

## What It Does

On each cycle the service:

1. Computes the sliding query window from `now - 10m` to `now` by default.
2. Acquires a Redis distributed lock so only one PM2 worker performs the cycle.
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
9. Writes the sorted JSON array back to the Redis hash field `signaled_logs`.

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

The service removes an organization key when its retained list becomes empty.

## Configuration

Primary config file: [config.yml](./config.yml)

Key settings:

- `scheduler.interval`: job frequency. Default `1m`.
- `scheduler.run_timeout`: maximum time allowed for one cycle. Default `50s`.
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

- every worker wakes up on the same schedule
- each cycle tries `SET NX EX` on the lock key
- only the worker that acquires the key performs the fetch/store cycle
- other workers stay idle for that cycle
- release uses a compare-and-delete Lua script so a worker only removes its own lock
- if the active worker crashes, the TTL expires and another worker can take the next cycle

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
