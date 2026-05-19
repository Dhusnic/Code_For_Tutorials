param(
    [string]$BundleName = "rca_three_engines_bundle",
    [switch]$Rebuild,
    [ValidateSet("direct-stream", "compatibility", "all")]
    [string]$RebuildProfile = "direct-stream"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Reset-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Warning "Skipping missing path: $Source"
        return
    }

    $destinationParent = Split-Path -Parent $Destination
    if ($destinationParent) {
        Ensure-Directory -Path $destinationParent
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $source = Join-Path $repoRoot $RelativePath
    $destination = Join-Path $bundleRoot $RelativePath
    Copy-IfExists -Source $source -Destination $destination
}

$distRoot = Join-Path $repoRoot "dist"
$bundleRoot = Join-Path $distRoot $BundleName
$zipPath = Join-Path $distRoot ($BundleName + ".zip")

Ensure-Directory -Path $distRoot
Reset-Path -Path $bundleRoot
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

if ($Rebuild) {
    $rebuildScript = Join-Path $repoRoot "rebuild_all.ps1"
    if (-not (Test-Path -LiteralPath $rebuildScript)) {
        throw "Missing rebuild script: $rebuildScript"
    }

    Write-Host "Rebuilding binaries with profile '$RebuildProfile'..."
    & $rebuildScript -Profile $RebuildProfile
    if ($LASTEXITCODE -ne 0) {
        throw "Rebuild failed with exit code $LASTEXITCODE"
    }
}

$pathsToCopy = @(
    "ca-cert",
    "ecosystem.config.js",
    "rebuild_all.ps1",
    "rebuild_all.sh",
    "log_signalizing\config.yml",
    "log_signalizing\rules",
    "log_signalizing\state",
    "log_signalizing\signalizing_go\app.json",
    "log_signalizing\signalizing_go\rebuild.ps1",
    "log_signalizing\signalizing_go\rebuild.sh",
    "log_signalizing\signalizing_go\go.mod",
    "log_signalizing\signalizing_go\go.sum",
    "log_signalizing\signalizing_go\cmd",
    "log_signalizing\signalizing_go\internal",
    "log_signalizing\signalizing_go\bin",
    "log_correlation_engine\build.ps1",
    "log_correlation_engine\build.sh",
    "log_correlation_engine\go.mod",
    "log_correlation_engine\go.sum",
    "log_correlation_engine\cmd",
    "log_correlation_engine\internal",
    "log_correlation_engine\config",
    "log_correlation_engine\rules",
    "log_correlation_engine\bin",
    "log_rca_engine\app.json",
    "log_rca_engine\rebuild.ps1",
    "log_rca_engine\rebuild.sh",
    "log_rca_engine\go.mod",
    "log_rca_engine\go.sum",
    "log_rca_engine\cmd",
    "log_rca_engine\internal",
    "log_rca_engine\config",
    "log_rca_engine\data",
    "log_rca_engine\bin"
)

foreach ($relativePath in $pathsToCopy) {
    Copy-Tree -RelativePath $relativePath
}

Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $zipPath -Force

$fileCount = (Get-ChildItem -Path $bundleRoot -Recurse -File | Measure-Object).Count
$zipItem = Get-Item -LiteralPath $zipPath

Write-Host ""
Write-Host "Bundle created successfully."
Write-Host "Folder: $bundleRoot"
Write-Host "Zip:    $($zipItem.FullName)"
Write-Host "Files:  $fileCount"
Write-Host "Size:   $([Math]::Round($zipItem.Length / 1MB, 2)) MB"
