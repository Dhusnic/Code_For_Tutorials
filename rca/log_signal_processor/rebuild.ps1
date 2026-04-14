param(
    [switch]$RunTests,
    [switch]$SkipClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

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

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Remove-BinaryIfRequested {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$Skip
    )

    if ($Skip) {
        return
    }

    foreach ($candidate in @($Path, "$Path~")) {
        if (-not (Test-Path $candidate)) {
            continue
        }

        try {
            Remove-Item -LiteralPath $candidate -Force -ErrorAction Stop
        }
        catch {
            throw "Unable to remove '$candidate'. Stop the running binary or PM2 process and rerun the rebuild."
        }
    }
}

$goExe = Resolve-GoExe
$binaryDir = Join-Path $projectRoot "bin"
$binaryPath = Join-Path $binaryDir "signaled-logs-collector.exe"
$env:GOCACHE = Join-Path $projectRoot ".gocache"

Ensure-Directory -Path $binaryDir
Ensure-Directory -Path $env:GOCACHE
Remove-BinaryIfRequested -Path $binaryPath -Skip:$SkipClean

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"
Write-Host "Building signaled logs collector..."

& $goExe build -trimpath -o $binaryPath .\cmd\signaled_logs_collector
if ($LASTEXITCODE -ne 0) {
    throw "go build failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $binaryPath)) {
    throw "Build completed without producing '$binaryPath'."
}

if ($RunTests) {
    Write-Host "Running go test ./..."
    & $goExe test ./...
    if ($LASTEXITCODE -ne 0) {
        throw "go test failed with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Rebuild completed successfully."
Write-Host "Binary: $binaryPath"
Write-Host "Run with: .\bin\signaled-logs-collector.exe --config .\config.yml"
