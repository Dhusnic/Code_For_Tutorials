param(
    [ValidateSet("direct-stream", "compatibility", "all")]
    [string]$Profile = "direct-stream",
    [switch]$RunTests,
    [switch]$SkipClean
)

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

function Build-GoTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ProjectDir,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [string]$Package,
        [Parameter(Mandatory = $true)]
        [string]$GoExe,
        [switch]$SkipClean
    )

    Ensure-Directory -Path (Split-Path -Parent $OutputPath)
    Remove-BinaryIfRequested -Path $OutputPath -Skip:$SkipClean

    Write-Host ""
    Write-Host "[$Name] Building $Package"
    Write-Host "[$Name] Output: $OutputPath"

    Push-Location $ProjectDir
    try {
        & $GoExe build -trimpath -o $OutputPath $Package
        if ($LASTEXITCODE -ne 0) {
            throw "[$Name] go build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path $OutputPath)) {
        throw "[$Name] Build completed without producing '$OutputPath'."
    }
}

function Invoke-GoTests {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectDir,
        [Parameter(Mandatory = $true)]
        [string]$GoExe
    )

    Write-Host ""
    Write-Host "[test] Running go test ./... in $ProjectDir"

    Push-Location $ProjectDir
    try {
        & $GoExe test ./...
        if ($LASTEXITCODE -ne 0) {
            throw "[test] go test failed in '$ProjectDir' with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

$goExe = Resolve-GoExe
$env:GOCACHE = Join-Path $repoRoot ".gocache"
Ensure-Directory -Path $env:GOCACHE

Write-Host "Using Go executable: $goExe"
Write-Host "Using GOCACHE: $env:GOCACHE"
Write-Host "Rebuild profile: $Profile"
if ($SkipClean) {
    Write-Host "Binary cleanup: skipped"
}
else {
    Write-Host "Binary cleanup: enabled"
}

$allTargets = @(
    @{
        Name       = "correlation-engine"
        ProjectDir = Join-Path $repoRoot "log_correlation_engine"
        OutputPath = Join-Path $repoRoot "log_correlation_engine\bin\correlation-engine.exe"
        Package    = ".\cmd"
    },
    @{
        Name       = "log-rca-engine"
        ProjectDir = Join-Path $repoRoot "log_rca_engine"
        OutputPath = Join-Path $repoRoot "log_rca_engine\bin\log-rca-engine.exe"
        Package    = ".\cmd"
    },
    @{
        Name       = "log-config-syncer"
        ProjectDir = Join-Path $repoRoot "log_rca_engine"
        OutputPath = Join-Path $repoRoot "log_rca_engine\bin\log-config-syncer.exe"
        Package    = ".\cmd\log-config-syncer"
    },
    @{
        Name       = "signalizing-engine"
        ProjectDir = Join-Path $repoRoot "log_signalizing\signalizing_go"
        OutputPath = Join-Path $repoRoot "log_signalizing\signalizing_go\bin\signalizing-engine.exe"
        Package    = ".\cmd\signalizing-engine"
    },
    @{
        Name       = "validate-rules"
        ProjectDir = Join-Path $repoRoot "log_signalizing\signalizing_go"
        OutputPath = Join-Path $repoRoot "log_signalizing\signalizing_go\bin\validate-rules.exe"
        Package    = ".\cmd\validate-rules"
    },
    @{
        Name       = "signaled-logs-collector"
        ProjectDir = Join-Path $repoRoot "log_signal_processor"
        OutputPath = Join-Path $repoRoot "log_signal_processor\bin\signaled-logs-collector.exe"
        Package    = ".\cmd\signaled_logs_collector"
    }
)

switch ($Profile) {
    "direct-stream" {
        $targets = $allTargets | Where-Object { $_.Name -in @("correlation-engine", "log-rca-engine", "log-config-syncer", "signalizing-engine", "validate-rules") }
    }
    "compatibility" {
        $targets = $allTargets | Where-Object { $_.Name -eq "signaled-logs-collector" }
    }
    "all" {
        $targets = $allTargets
    }
    default {
        throw "Unsupported profile '$Profile'."
    }
}

foreach ($target in $targets) {
    Build-GoTarget `
        -Name $target.Name `
        -ProjectDir $target.ProjectDir `
        -OutputPath $target.OutputPath `
        -Package $target.Package `
        -GoExe $goExe `
        -SkipClean:$SkipClean
}

if ($RunTests) {
    $testProjects = $targets.ProjectDir | Sort-Object -Unique
    foreach ($projectDir in $testProjects) {
        Invoke-GoTests -ProjectDir $projectDir -GoExe $goExe
    }
}

Write-Host ""
Write-Host "Rebuild completed successfully."
Write-Host "Built targets:"
foreach ($target in $targets) {
    Write-Host "  - $($target.Name): $($target.OutputPath)"
}

Write-Host ""
Write-Host "Recommended usage:"
switch ($Profile) {
    "direct-stream" {
        Write-Host "  pm2 start .\ecosystem.config.js"
    }
    "compatibility" {
        Write-Host "  Start the collector separately from .\log_signal_processor"
    }
    "all" {
        Write-Host "  pm2 start .\ecosystem.config.js"
        Write-Host "  Start signaled-logs-collector separately only if you still want the compatibility flow."
    }
}
