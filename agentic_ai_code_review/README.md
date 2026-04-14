# Agentic AI Code Review Workspace

This repository is now split into two product tracks:

- `web/`: legacy Python + FastAPI + static web UI (current behavior baseline)
- `app/`: new Windows desktop app track (Go + Wails + React) for parity migration

## Workspace Layout

- [`web/`](./web): existing production-like workflow and API surface
- [`app/`](./app): desktop architecture, contracts, service bindings, and frontend shell
- [`docs/migration/`](./docs/migration): parity matrix and contract freeze artifacts
- [`docs/runbooks/`](./docs/runbooks): runbooks for web, app, and rollback
- [`scripts/`](./scripts): convenience scripts for local run and parity checks

## Quick Start

### Run Legacy Web Baseline

```powershell
.\scripts\run-web.ps1
```

### Run Desktop Track (Scaffold)

```powershell
.\scripts\run-app.ps1
```

By default the desktop app auto-starts legacy backend (`web/main.py`) when needed.
If Python dependencies are missing, desktop attempts to install them automatically on first run.

### Build EXE

Quick CLI desktop executable:

```powershell
.\scripts\build-app.ps1
.\scripts\run-app-exe.ps1 -Cli
```

Full Wails desktop executable:

```powershell
go install github.com/wailsapp/wails/v2/cmd/wails@latest
.\scripts\build-app.ps1 -UseWails
.\scripts\run-app-exe.ps1
```

## Migration Strategy

The desktop track currently uses a **strangler bridge** by default:

- UI calls typed desktop bindings.
- Desktop service forwards to `web` API contracts where native Go parity is not complete.
- Contract parity is validated before each native module cutover.

See:

- [`docs/migration/parity-matrix.md`](./docs/migration/parity-matrix.md)
- [`docs/migration/contracts-freeze.md`](./docs/migration/contracts-freeze.md)
