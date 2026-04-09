$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$binDir = Join-Path $projectRoot "bin"
$binaryPath = Join-Path $binDir "correlation-engine.exe"
$goCacheDir = Join-Path $projectRoot ".gocache"

Write-Host "Building log correlation engine..."

if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    throw "Go is not installed or not available in PATH."
}

New-Item -ItemType Directory -Path $binDir -Force | Out-Null
New-Item -ItemType Directory -Path $goCacheDir -Force | Out-Null

if (-not $env:GOCACHE) {
    $env:GOCACHE = $goCacheDir
}

Push-Location $projectRoot
try {
    go build -o $binaryPath .\cmd
    if (-not (Test-Path $binaryPath)) {
        throw "Build completed without producing $binaryPath"
    }
    Write-Host "Build complete!"
    Write-Host "Binary: $binaryPath"
    Write-Host "Run with: .\bin\correlation-engine.exe --config .\config\config.yml"
}
finally {
    Pop-Location
}
