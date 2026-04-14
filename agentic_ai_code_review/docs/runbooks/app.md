# App Runbook

This runbook covers the Go desktop track in `app/`.

## Current State

- Wails-ready project structure is in place.
- Default runtime mode is `legacy` bridge (desktop calls `web` APIs).
- Desktop now auto-starts legacy backend process by default (`auto_start_legacy_api=true`).
- If Python deps are missing, desktop can auto-install backend deps on first run (`auto_install_legacy_deps=true`).
- Native Go domain modules are scaffolded for parity cutover.

## Prerequisites

- Go 1.23+
- Node.js 20+ (for frontend tooling)
- Wails CLI (for full desktop build workflow)
- Legacy web service running locally (for bridge mode)

Install Wails CLI:

```powershell
go install github.com/wailsapp/wails/v2/cmd/wails@latest
```

If `wails` is not available in PATH, scripts auto-detect:

- `%USERPROFILE%\\go\\bin\\wails.exe`
- `%GOPATH%\\bin\\wails.exe`

## Dev Flow (Bridge Mode)

1. Start desktop app directly (backend auto-start handles `web/main.py`):

```powershell
.\scripts\run-app.ps1 -UseWails
```

2. If auto-start is disabled, run web baseline manually:

```powershell
.\scripts\run-web.ps1
```

3. For full Wails desktop runtime (when Wails CLI + frontend deps are installed):

```powershell
.\scripts\run-app.ps1 -UseWails
```

## Configuration

Config file:

- `%APPDATA%\\AgenticAICodeReview\\config.json`

Important keys:

- `service_mode`: `legacy`, `hybrid`, `native`
- `legacy_api_base_url`: default `http://localhost:8000`
- `request_timeout_seconds`

## Target Build

### Quick Desktop EXE (Go scaffold, no embedded UI window)

```powershell
.\scripts\build-app.ps1
.\scripts\run-app-exe.ps1 -Cli
```

### Full Windows Desktop EXE (Wails + React UI)

Once Node.js + Wails are installed:

```powershell
.\scripts\build-app.ps1 -UseWails
.\scripts\run-app-exe.ps1
```

Equivalent manual commands:

```powershell
Set-Location app\frontend
npm install
npm run build
Set-Location ..
wails build -platform windows/amd64 -clean
```

Output:

- `dist\AgenticAICodeReviewDesktop.exe`

## If EXE Does Not Open

1. Rebuild with embedded assets:

```powershell
.\scripts\build-app.ps1 -UseWails
```

2. Run from terminal to capture startup errors:

```powershell
.\scripts\run-app-exe.ps1
```

3. Ensure WebView2 Runtime is installed (required by Wails on Windows):
   - Install Microsoft Edge WebView2 Evergreen Runtime.

4. If Windows blocks the file, right-click EXE -> Properties -> Unblock.
5. If build cannot overwrite `dist\AgenticAICodeReviewDesktop.exe` (file in use), close running app and rebuild, or use the timestamped fallback EXE emitted by build script.

Note:

- First startup can take ~1-3 minutes if dependency install is required.
