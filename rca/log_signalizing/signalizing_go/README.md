# RCA Engine Go

This folder contains only the Go implementation of RCA.

Shared runtime assets are outside this folder in the parent `signalizing` folder:

- [../config.yml](../config.yml)
- [../rules](../rules)
- [../state](../state)

## What Is In This Folder

- [cmd](./cmd): Go entrypoints.
- [internal](./internal): internal Go packages for config, rules, checkpoints, enrichment, logging, writer, and Elasticsearch.
- [bin](./bin): built executables.
- [app.json](./app.json): PM2 config for the Go executable.
- [go.mod](./go.mod) and [go.sum](./go.sum): Go module definitions.

## Install Go

Install the Go toolchain version required by [go.mod](./go.mod).

Windows steps:

1. Download and install Go from the official installer.
2. Reopen PowerShell.
3. Verify:

```powershell
go version
```

If `go` is not on `PATH`, use the full executable path:

```powershell
& "C:\Program Files\Go\bin\go.exe" version
```

## Download Dependencies

From this folder:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
go mod tidy
```

If you want to prefetch everything explicitly:

```powershell
go mod download
```

## Build The EXE After Changes

Quick rebuild scripts:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
.\rebuild.ps1
```

```sh
cd /d/Code\ for\ tutorials/rca/signalizing/signalizing_go
./rebuild.sh
```

Both scripts:

- remove the previous `bin/signalizing-engine.exe`
- remove the previous `bin/validate-rules.exe`
- remove leftover `*.exe~` backup files when possible
- rebuild both executables using the current folder structure
- use the repo-local `.gocache` and `.gomodcache`

If PM2 is still running the old binary, Windows may keep a `bin\signalizing-engine.exe~` file until you restart or stop PM2 and rebuild again.

Build the main RCA executable:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
go build -o .\bin\signalizing-engine.exe .\cmd\signalizing-engine
```

Build the rule validator:

```powershell
go build -o .\bin\validate-rules.exe .\cmd\validate-rules
```

Build all packages to catch compile issues:

```powershell
go build ./...
```

## Run After Building

Run the shared default config:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
.\bin\signalizing-engine.exe --config ..\config.yml --run-once
```

Run continuously:

```powershell
.\bin\signalizing-engine.exe --config ..\config.yml
```

Validate rules:

```powershell
.\bin\validate-rules.exe --rules-dir ..\rules
```

## Run Without Building

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
go run .\cmd\signalizing-engine --config ..\config.yml --run-once
```

## PM2 Usage

The PM2 file for the Go binary is [app.json](./app.json). It already points to the shared root [../config.yml](../config.yml).

Start it with:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
pm2 start .\app.json
pm2 logs signalizing-engine
```

The Go runtime also reads `instances` from [app.json](./app.json) to infer `RCA_WORKER_COUNT` when PM2 sets `RCA_WORKER_ID`.

## Go Libraries Used

Direct dependencies from [go.mod](./go.mod):

- `github.com/elastic/go-elasticsearch/v8`
  - Official Elasticsearch client.
  - Used for search, count, bulk, index, get, and index metadata calls.
- `github.com/jackc/pgx/v5`
  - PostgreSQL client.
  - Used by the Postgres checkpoint store.
- `github.com/redis/go-redis/v9`
  - Redis client.
  - Used by the Redis checkpoint store.
- `github.com/shirou/gopsutil/v4`
  - Host CPU and memory metrics.
  - Used by bulk writer autoscaling guardrails.
- `gopkg.in/yaml.v3`
  - YAML parsing.
  - Used for app config, rule files, and rule validation.

Transitive dependencies are recorded in [go.sum](./go.sum) and are pulled automatically by `go mod tidy` or `go mod download`.

## Test Commands

Run all Go tests:

```powershell
cd "D:\Code for tutorials\rca\signalizing\signalizing_go"
go test ./...
```

Rebuild and rerun after a code change:

```powershell
go test ./...
go build -o .\bin\signalizing-engine.exe .\cmd\signalizing-engine
.\bin\signalizing-engine.exe --config ..\config.yml --run-once
```

## Notes

- Shared config, rules, and state now live outside this folder on purpose.
- If Elasticsearch is unreachable, the executable will still start but fail when it tries to read checkpoints or source events.
- The syslog simulator is still currently in [../../log_simulations](../../log_simulations).
