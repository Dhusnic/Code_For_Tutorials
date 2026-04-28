# App Runbook

This runbook covers the Go + Wails desktop runtime in `app/`.

## Current State

- Default runtime mode is `native`.
- React renders directly in the Wails window.
- Go services run in-process through Wails bindings.
- The desktop app does not auto-start FastAPI or `web/main.py`.

## Prerequisites

- Go 1.23+
- Node.js 20+
- Wails CLI
- Microsoft Edge WebView2 Runtime

Install Wails CLI:

```powershell
go install github.com/wailsapp/wails/v2/cmd/wails@latest
```

If `wails` is not available in PATH, scripts auto-detect:

- `%USERPROFILE%\\go\\bin\\wails.exe`
- `%GOPATH%\\bin\\wails.exe`

## Dev Flow

```powershell
.\scripts\run-app.ps1 -UseWails
```

## Configuration

Config file:

- `%APPDATA%\\AgenticAICodeReview\\config.json`

Important keys:

- `service_mode`: normalized to `native`
- `request_timeout_seconds`
- `log_level`

Existing legacy keys may remain in older config files, but the desktop runtime ignores backend auto-start settings.

## Build

### CLI Scaffold

```powershell
.\scripts\build-app.ps1
.\scripts\run-app-exe.ps1 -Cli
```

### Full Windows Desktop EXE

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

- `app\build\bin\agentic-ai-code-review-desktop.exe`
- `dist\AgenticAICodeReviewDesktop.exe`

## If EXE Does Not Open

1. Rebuild with embedded assets:

```powershell
.\scripts\build-app.ps1 -UseWails
```

2. Run from terminal to capture errors:

```powershell
.\scripts\run-app-exe.ps1
```

3. Ensure WebView2 Runtime is installed.
4. If Windows blocks the file, right-click EXE -> Properties -> Unblock.
5. If the build cannot overwrite the EXE, close the running desktop process and rebuild.
