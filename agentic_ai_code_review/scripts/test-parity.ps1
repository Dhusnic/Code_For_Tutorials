param(
  [string]$Go = "go"
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\app")
Write-Host "Running desktop contract/parity unit tests..."
& $Go "test" ".\..." "-run" "Test"
