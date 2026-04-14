Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".\bin")) {
    New-Item -ItemType Directory -Path ".\bin" | Out-Null
}

$env:GOCACHE = Join-Path (Split-Path -Parent $projectRoot) ".gocache"
go build -trimpath -o .\bin\log-rca-engine.exe .\cmd
