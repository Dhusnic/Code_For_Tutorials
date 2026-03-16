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
$binDir = Join-Path $scriptDir "bin"
$repoRoot = Split-Path -Parent $scriptDir
$engineExe = Join-Path $binDir "rca-engine.exe"
$engineExeBackup = Join-Path $binDir "rca-engine.exe~"
$validatorExe = Join-Path $binDir "validate-rules.exe"
$validatorExeBackup = Join-Path $binDir "validate-rules.exe~"
$env:GOCACHE = Join-Path $repoRoot ".gocache"
$env:GOMODCACHE = Join-Path $repoRoot ".gomodcache"

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir | Out-Null
}

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"
Write-Host "Using GOMODCACHE: $env:GOMODCACHE"
Write-Host "Removing previous binaries if they exist..."
Remove-Item $engineExe -Force -ErrorAction SilentlyContinue
Remove-Item $engineExeBackup -Force -ErrorAction SilentlyContinue
Remove-Item $validatorExe -Force -ErrorAction SilentlyContinue
Remove-Item $validatorExeBackup -Force -ErrorAction SilentlyContinue

Write-Host "Building rca-engine.exe..."
& $goExe build -o $engineExe .\cmd\rca-engine

Write-Host "Building validate-rules.exe..."
& $goExe build -o $validatorExe .\cmd\validate-rules

Write-Host "Rebuild completed."
Write-Host "Created:"
Write-Host "  $engineExe"
Write-Host "  $validatorExe"

if ((Test-Path $engineExeBackup) -or (Test-Path $validatorExeBackup)) {
    Write-Warning "A .exe~ backup file is still present. This usually means the old binary was in use. Restart or stop PM2 and rerun this script for a fully clean replacement."
}
