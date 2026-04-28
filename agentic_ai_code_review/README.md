# Agentic AI Code Review Workspace

This repository contains two runtimes:

- `app/`: Windows desktop app built with Go, Wails, and React. This is the primary runtime.
- `web/`: legacy Python + FastAPI + static UI kept for reference and rollback work.

## Workspace Layout

- [`app/`](./app): native desktop bindings, Go services, contracts, and React UI
- [`web/`](./web): previous web service implementation
- [`docs/migration/`](./docs/migration): contract and parity notes
- [`docs/runbooks/`](./docs/runbooks): runbooks for desktop, web, and rollback
- [`scripts/`](./scripts): local build and run scripts

## Quick Start

### Run Desktop App

```powershell
.\scripts\run-app.ps1 -UseWails
```

The desktop app now runs native Go services in-process through Wails bindings. It does not iframe the web UI and does not auto-start `web/main.py`.

### Build Desktop EXE

```powershell
go install github.com/wailsapp/wails/v2/cmd/wails@latest
.\scripts\build-app.ps1 -UseWails
.\scripts\run-app-exe.ps1
```

Output:

- `app\build\bin\agentic-ai-code-review-desktop.exe`
- `dist\AgenticAICodeReviewDesktop.exe`

### Optional Legacy Web Runtime

```powershell
.\scripts\run-web.ps1
```

Use this only when comparing behavior against the old FastAPI baseline.

## Desktop Architecture

- React renders directly inside the Wails window.
- Frontend calls Go methods through generated Wails bindings.
- Native Go services handle local review, static checks, patch application, usage metrics, jobs, and PR planning.
- No localhost backend process is required for the desktop app.
