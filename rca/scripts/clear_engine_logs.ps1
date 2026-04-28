[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$DeleteEmptyDirectories
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

$logDirectories = @(
    "log_correlation_engine\logs",
    "log_rca_engine\logs",
    "log_signalizing\signalizing_go\logs",
    "log_signal_processor\logs"
)

$filePatterns = @("*.log", "*.out", "*.err")
$deletedFiles = @()

foreach ($relativeDir in $logDirectories) {
    $fullDir = Join-Path $repoRoot $relativeDir
    if (-not (Test-Path -LiteralPath $fullDir)) {
        continue
    }

    $files = Get-ChildItem -LiteralPath $fullDir -File | Where-Object {
        $name = $_.Name
        foreach ($pattern in $filePatterns) {
            if ($name -like $pattern) {
                return $true
            }
        }
        return $false
    }

    foreach ($file in $files) {
        if ($PSCmdlet.ShouldProcess($file.FullName, "Delete log file")) {
            Remove-Item -LiteralPath $file.FullName -Force
            $deletedFiles += $file.FullName
        }
    }

    if ($DeleteEmptyDirectories) {
        $remaining = Get-ChildItem -LiteralPath $fullDir -Force
        if ($remaining.Count -eq 0) {
            if ($PSCmdlet.ShouldProcess($fullDir, "Delete empty log directory")) {
                Remove-Item -LiteralPath $fullDir -Force
            }
        }
    }
}

Write-Host ""
Write-Host "Deleted log files: $($deletedFiles.Count)"
foreach ($path in $deletedFiles) {
    Write-Host "  $path"
}
