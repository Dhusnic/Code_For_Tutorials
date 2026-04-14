param(
  [string]$ExePath = "dist\\AgenticAICodeReviewDesktop.exe",
  [switch]$Cli
)

$ErrorActionPreference = "Stop"

$repoRoot = Join-Path $PSScriptRoot ".."
$resolved = if ($Cli) {
  Join-Path $repoRoot "dist\\AgenticAICodeReviewDesktopCLI.exe"
} else {
  Join-Path $repoRoot $ExePath
}

if (-not (Test-Path $resolved)) {
  throw "EXE not found: $resolved. Build first with .\\scripts\\build-app.ps1"
}

Write-Host "Launching $resolved"
& $resolved
