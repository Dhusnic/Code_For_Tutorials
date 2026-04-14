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

function Build-Target {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [string]$Package,
        [Parameter(Mandatory = $true)]
        [string]$GoExe,
        [switch]$SkipClean
    )

    Remove-BinaryIfRequested -Path $OutputPath -Skip:$SkipClean

    Write-Host "Building $Name..."
    & $GoExe build -trimpath -o $OutputPath $Package
    if ($LASTEXITCODE -ne 0) {
        throw "go build failed for '$Name' with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path $OutputPath)) {
        throw "Build completed without producing '$OutputPath'."
    }
}

$goExe = Resolve-GoExe
$binaryDir = Join-Path $projectRoot "bin"
$engineBinary = Join-Path $binaryDir "signalizing-engine.exe"
$validatorBinary = Join-Path $binaryDir "validate-rules.exe"
$env:GOCACHE = Join-Path $projectRoot ".gocache"

Ensure-Directory -Path $binaryDir
Ensure-Directory -Path $env:GOCACHE

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"

Build-Target -Name "signalizing-engine" -OutputPath $engineBinary -Package ".\cmd\signalizing-engine" -GoExe $goExe -SkipClean:$SkipClean
Build-Target -Name "validate-rules" -OutputPath $validatorBinary -Package ".\cmd\validate-rules" -GoExe $goExe -SkipClean:$SkipClean

if ($RunTests) {
    Write-Host "Running go test ./..."
    & $goExe test ./...
    if ($LASTEXITCODE -ne 0) {
        throw "go test failed with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Rebuild completed successfully."
Write-Host "Binaries:"
Write-Host "  - $engineBinary"
Write-Host "  - $validatorBinary"
Write-Host "Run with: .\bin\signalizing-engine.exe --config ..\config.yml"
