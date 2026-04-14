# Agentic Desktop App (Go + Wails + React)

This folder contains the Windows desktop track for Agentic AI Code Review.

## Architecture

- `internal/contracts`: frozen request/response models aligned with `web` API
- `internal/services`: service interfaces and implementations
  - `legacy`: HTTP bridge to baseline web API (default mode)
  - `native`: parity target modules (incremental cutover)
- `internal/core`: shared app infrastructure (config, jobs, events, logging, secrets, errors)
- `internal/git`: hardened git command adapter for native workflows
- `internal/desktop`: binding layer exposed to Wails frontend
- `frontend`: React + TypeScript UI shell for desktop experience

## UI Parity Mode

Desktop frontend now runs in **full parity mode** by default:

- boots integrated backend startup from desktop runtime
- then loads the existing `web` UI flow inside the desktop window
- this preserves complete web feature behavior/sequence while running as Windows app

## Modes

- `legacy`: desktop calls `web` API for all operations
- `hybrid`: selected operations native, remaining operations legacy
- `native`: all operations served by Go desktop backend modules

## Legacy API Auto-Start

Desktop app can auto-start legacy backend (`web/main.py`) internally.
Defaults:

- `auto_start_legacy_api=true`
- `legacy_api_python_bin=python`
- `legacy_api_script_path=web/main.py`

## Run

```powershell
go run .\cmd\desktop
```

For Wails dev/build, use Wails CLI after dependencies are installed.

## Build Executables

From repository root:

```powershell
.\scripts\build-app.ps1
```

for quick CLI desktop binary, and:

```powershell
.\scripts\build-app.ps1 -UseWails
```

for full UI desktop EXE.
