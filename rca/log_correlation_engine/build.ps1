$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$binDir = Join-Path $projectRoot "bin"
$binaryPath = Join-Path $binDir "correlation-engine.exe"
$binaryBackupPath = Join-Path $binDir "correlation-engine.exe~"
$goCacheDir = Join-Path $projectRoot ".gocache"

Write-Host "Building log correlation engine..."

if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    throw "Go is not installed or not available in PATH."
}

New-Item -ItemType Directory -Path $binDir -Force | Out-Null
New-Item -ItemType Directory -Path $goCacheDir -Force | Out-Null

$env:GOCACHE = $goCacheDir

Write-Host "Removing previous correlation-engine binary if it exists..."
Remove-Item -LiteralPath $binaryPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $binaryBackupPath -Force -ErrorAction SilentlyContinue

Push-Location $projectRoot
try {
    go build -o $binaryPath .\cmd
    if ($LASTEXITCODE -ne 0) {
        throw "go build failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path $binaryPath)) {
        throw "Build completed without producing $binaryPath"
    }
    Write-Host "Build complete!"
    Write-Host "Binary: $binaryPath"
    Write-Host "Run with: .\bin\correlation-engine.exe --config .\config\config.yml"
    if (Test-Path $binaryBackupPath) {
        Write-Warning "A .exe~ backup file is still present. This usually means the old binary was in use. Stop the running process and rebuild again for a fully clean replacement."
    }
}
finally {
    Pop-Location
}
