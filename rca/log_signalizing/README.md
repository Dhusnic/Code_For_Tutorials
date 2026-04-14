# RCA Overview

This repository contains the RCA engine in two implementations:

- [signalizing_python](./signalizing_python) is the original Python implementation.
- [signalizing_go](./signalizing_go) is the Go migration/build target.

Both implementations share the same operational assets in this `signalizing` folder:

- [config.yml](./config.yml)
- [rules](./rules)
- [state](./state)
- [log_simulations](../log_simulations)
- [Flow charts](./Flow%20charts)

## How RCA Works

At a high level, RCA does this in a loop:

1. Loads [config.yml](./config.yml).
2. Loads YAML rules from [rules](./rules).
3. Reads source events from Elasticsearch.
4. Matches each event against service rules.
5. Enriches matched events with RCA fields like `signal`, `source_index`, `source_id`, `signal_present`, and normalized `log.level`.
6. Writes enriched results back to Elasticsearch.
7. Stores checkpoints in [state](./state) or the configured external checkpoint backend.
8. Learns repeated unmatched critical patterns into [rules/suggestions](./rules/suggestions) when rule learning is enabled.

Optional compact signal stream path:

```text
raw logs -> signalizing -> Redis stream -> log_correlation_engine
```

When `signal_stream.enabled` is turned on in [config.yml](./config.yml), the Go signalizing runtime publishes one compact signal event per matched log into Redis stream `Rca:signalized_log_events` by default. That stream does not replace the existing Elasticsearch write path by itself; it adds a lower-latency handoff that the correlation engine can ingest directly.

The checked-in config now enables this direct signal stream path by default.

## Main Runtime Flow

The main service behavior is:

1. Start one or more workers.
2. Each worker owns a deterministic partition of services/indexes based on `worker_id` and `worker_count`.
3. For each enabled service, RCA:
   - loads the correct rule file
   - builds the Elasticsearch query
   - reads events in batches
   - evaluates rules
   - creates bulk index/update actions
   - retries failures with backoff
   - dead-letters exhausted failures
4. At the end of each cycle it logs throughput and autoscaling metrics, then sleeps for `poll_interval_seconds`.

## Shared Files And What They Mean

- [config.yml](./config.yml): shared default runtime config for both Python and Go.
- [rules](./rules): all live YAML rules and suggestion output.
- [state](./state): shared local runtime state like file checkpoints and spool directories.
- [log_simulations](../log_simulations): raw syslog simulation inputs and the current simulator script.
- [Flow charts](./Flow%20charts): project flow/reference diagrams.

Relevant `signal_stream` settings in [config.yml](./config.yml):

- `signal_stream.enabled`: turn compact signal publication on or off.
- `signal_stream.address`: Redis server used for the stream.
- `signal_stream.stream_key`: Redis stream key. Default `Rca:signalized_log_events`.
- `signal_stream.max_len`: approximate stream trim length for storage control.
- `signal_stream.organization_field`: source event field used to extract organization id. Default `event.organization`.

## Which Folder To Use

Use [signalizing_python](./signalizing_python) when you want the original Python runtime, tests, and legacy adapter flow.

Use [signalizing_go](./signalizing_go) when you want to build or run the Go implementation and PM2-managed Go executable.

## Common Run Commands

Python:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_python"
..\..\.venv\Scripts\python .\main.py --config ..\config.yml --run-once
```

Go:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
.\bin\signalizing-engine.exe --config ..\config.yml --run-once
```

PM2 with Go:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
pm2 start .\app.json
```

Or start the full RCA stack from the repo root:

```powershell
cd "D:\Code for tutorials\rca"
pm2 start .\ecosystem.config.js
```

That root PM2 flow starts the direct path by default:

```text
raw logs -> signalizing_go -> Redis stream -> log_correlation_engine
```

## Related Docs

- [Go README](./signalizing_go/README.md)
- [Python README](./signalizing_python/README.md)
