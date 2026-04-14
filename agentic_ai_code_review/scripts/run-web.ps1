param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\web")
Write-Host "Starting legacy web service from $(Get-Location)..."
& $Python "main.py"
