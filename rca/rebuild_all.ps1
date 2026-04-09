Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

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

function Remove-ExistingBinary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $backupPath = "$Path~"
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
}

function Build-GoTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ProjectDir,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [string]$BuildTarget,
        [Parameter(Mandatory = $true)]
        [string]$GoExe
    )

    $binDir = Split-Path -Parent $OutputPath
    if (-not (Test-Path $binDir)) {
        New-Item -ItemType Directory -Path $binDir | Out-Null
    }

    Write-Host ""
    Write-Host "[$Name] Removing existing binary if present..."
    Remove-ExistingBinary -Path $OutputPath

    Write-Host "[$Name] Building $OutputPath..."
    Push-Location $ProjectDir
    try {
        & $GoExe build -o $OutputPath $BuildTarget
        if ($LASTEXITCODE -ne 0) {
            throw "[$Name] go build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path $OutputPath)) {
        throw "[$Name] Build completed without producing $OutputPath"
    }

    Write-Host "[$Name] Build complete."
}

$goExe = Resolve-GoExe
$env:GOCACHE = Join-Path $repoRoot ".gocache"

New-Item -ItemType Directory -Path $env:GOCACHE -Force | Out-Null

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"
if ($env:GOMODCACHE) {
    Write-Host "Using GOMODCACHE from environment: $env:GOMODCACHE"
}
else {
    Write-Host "Using default Go module cache."
}

$targets = @(
    @{
        Name       = "log_signal_processor"
        ProjectDir = Join-Path $repoRoot "log_signal_processor"
        OutputPath = Join-Path $repoRoot "log_signal_processor\bin\signaled-logs-collector.exe"
        BuildTarget = ".\cmd\signaled_logs_collector"
    },
    @{
        Name       = "log_correlation_engine"
        ProjectDir = Join-Path $repoRoot "log_correlation_engine"
        OutputPath = Join-Path $repoRoot "log_correlation_engine\bin\correlation-engine.exe"
        BuildTarget = ".\cmd"
    },
    @{
        Name       = "log_signalizing/rca-engine"
        ProjectDir = Join-Path $repoRoot "log_signalizing\signalizing_go"
        OutputPath = Join-Path $repoRoot "log_signalizing\signalizing_go\bin\rca-engine.exe"
        BuildTarget = ".\cmd\rca-engine"
    },
    @{
        Name       = "log_signalizing/validate-rules"
        ProjectDir = Join-Path $repoRoot "log_signalizing\signalizing_go"
        OutputPath = Join-Path $repoRoot "log_signalizing\signalizing_go\bin\validate-rules.exe"
        BuildTarget = ".\cmd\validate-rules"
    }
)

foreach ($target in $targets) {
    Build-GoTarget `
        -Name $target.Name `
        -ProjectDir $target.ProjectDir `
        -OutputPath $target.OutputPath `
        -BuildTarget $target.BuildTarget `
        -GoExe $goExe
}

Write-Host ""
Write-Host "Full Go rebuild completed."
Write-Host "Created binaries:"
foreach ($target in $targets) {
    Write-Host "  $($target.OutputPath)"
}
