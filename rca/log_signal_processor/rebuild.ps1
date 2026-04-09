Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

function Resolve-GoExe {
    $goCommand = Get-Command go -ErrorAction SilentlyContinue
    if ($goCommand) {
        return $goCommand.Source
    }

    $defaultGoExe = "C:\Program Files\Go\bin\go.exe"
    if (Test-Path $defaultGoExe) {
        return $defaultGoExe
    }

    throw "Go executable not found. Install Go or add 'go' to PATH."
}

$goExe = Resolve-GoExe
$repoRoot = Split-Path -Parent $scriptDir
$binDir = Join-Path $scriptDir "bin"
$collectorExe = Join-Path $binDir "signaled-logs-collector.exe"
$collectorExeBackup = Join-Path $binDir "signaled-logs-collector.exe~"
$env:GOCACHE = Join-Path $repoRoot ".gocache"

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir | Out-Null
}

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"
if ($env:GOMODCACHE) {
    Write-Host "Using GOMODCACHE from environment: $env:GOMODCACHE"
}
else {
    Write-Host "Using default Go module cache."
}
Write-Host "Removing previous collector binary if it exists..."
Remove-Item $collectorExe -Force -ErrorAction SilentlyContinue
Remove-Item $collectorExeBackup -Force -ErrorAction SilentlyContinue

Write-Host "Building signaled-logs-collector.exe..."
& $goExe build -o $collectorExe .\cmd\signaled_logs_collector
if ($LASTEXITCODE -ne 0) {
    throw "go build failed with exit code $LASTEXITCODE"
}

Write-Host "Rebuild completed."
Write-Host "Created:"
Write-Host "  $collectorExe"

if (Test-Path $collectorExeBackup) {
    Write-Warning "A .exe~ backup file is still present. This usually means the old binary was in use. Restart or stop PM2 and rerun this script for a fully clean replacement."
}
