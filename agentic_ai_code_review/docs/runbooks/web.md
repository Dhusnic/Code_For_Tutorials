# Web Runbook

This runbook starts the legacy FastAPI + static UI from `web/`.

## Prerequisites

- Python 3.10+
- project dependencies installed in your environment
- `web/config/.env` configured (OpenAI/Azure secrets as needed)

## Start

```powershell
Set-Location web
python main.py
```

App default:

- API/UI host: `http://localhost:8000`

## Health Check

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/health"
```

Expected:

```json
{"status":"healthy","service":"agentic-ai-code-review"}
```
