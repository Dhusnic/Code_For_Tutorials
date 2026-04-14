# Rollback Runbook

Use this when desktop rollout causes regressions.

## Trigger Conditions

- Contract mismatch on critical flows (review/apply/pr-workflow)
- Job approval flow failures
- Data integrity risk during patch apply or Git operations

## Immediate Actions

1. Switch operators back to web baseline:

```powershell
.\scripts\run-web.ps1
```

2. Disable desktop default launch in your deployment channel.
3. Capture failing desktop request/response payload and attach to parity bug.

## Runtime Rollback Toggle (Desktop)

Set desktop config:

- `service_mode = "legacy"`

This forces all calls through baseline `web` APIs while preserving desktop shell.

## Validation After Rollback

- `api/health` is reachable on web baseline
- `run-full-review` succeeds
- `apply-changes` dry run succeeds on test repo
- PR workflow steps return expected payloads
