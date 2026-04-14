param(
  [string]$Go = "go",
  [switch]$UseWails
)

$ErrorActionPreference = "Stop"

function Resolve-WailsCommand {
  $fromPath = Get-Command "wails" -ErrorAction SilentlyContinue
  if ($fromPath) {
    return $fromPath.Source
  }
  $goPath = if ($env:GOPATH) { $env:GOPATH } else { Join-Path $env:USERPROFILE "go" }
  $candidate = Join-Path $goPath "bin\\wails.exe"
  if (Test-Path $candidate) {
    return $candidate
  }
  return $null
}

Set-Location (Join-Path $PSScriptRoot "..\app")
if ($UseWails) {
  $wailsCmd = Resolve-WailsCommand
  if (-not $wailsCmd) {
    throw "Wails CLI was not found in PATH. Install Wails or run without -UseWails."
  }
  Write-Host "Starting Wails desktop dev runtime from $(Get-Location)..."
  & $wailsCmd dev
  exit $LASTEXITCODE
}

Write-Host "Running desktop backend scaffold from $(Get-Location)..."
& $Go "run" ".\cmd\desktop"
