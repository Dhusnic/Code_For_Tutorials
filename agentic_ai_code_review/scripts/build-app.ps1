param(
  [string]$Go = "go",
  [switch]$UseWails,
  [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

$repoRoot = Join-Path $PSScriptRoot ".."
$appRoot = Join-Path $repoRoot "app"
$resolvedOutputDir = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null

function Resolve-WailsCommand {
  $fromPath = Get-Command "wails" -ErrorAction SilentlyContinue
  if ($fromPath) {
    return $fromPath.Source
  }
  $goPath = if ($env:GOPATH) { $env:GOPATH } else { Join-Path $env:USERPROFILE "go" }
  $candidate = Join-Path $goPath "bin\\wails.exe"
  if (Test-Path $candidate) {
    return $candidate
  }
  return $null
}

Set-Location $appRoot

if ($UseWails) {
  $wailsCmd = Resolve-WailsCommand
  if (-not $wailsCmd) {
    throw "Wails CLI not found. Install: go install github.com/wailsapp/wails/v2/cmd/wails@latest"
  }
  if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    throw "npm not found. Install Node.js 20+."
  }

  Set-Location (Join-Path $appRoot "frontend")
  if (-not (Test-Path ".\node_modules")) {
    Write-Host "Installing frontend dependencies..."
    npm install
    if ($LASTEXITCODE -ne 0) {
      throw "npm install failed."
    }
  }

  Write-Host "Building frontend bundle..."
  npm run build
  if ($LASTEXITCODE -ne 0) {
    throw "npm run build failed."
  }

  Set-Location $appRoot
  Write-Host "Building Wails desktop EXE..."
  & $wailsCmd build -platform windows/amd64 -clean
  if ($LASTEXITCODE -ne 0) {
    throw "wails build failed."
  }

  $wailsExe = Join-Path $appRoot "build\bin\agentic-ai-code-review-desktop.exe"
  if (-not (Test-Path $wailsExe)) {
    throw "Expected Wails EXE not found at $wailsExe"
  }
  $target = Join-Path $resolvedOutputDir "AgenticAICodeReviewDesktop.exe"
  try {
    Copy-Item -Path $wailsExe -Destination $target -Force
    Write-Host "Wails EXE ready: $target"
  } catch {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $fallbackTarget = Join-Path $resolvedOutputDir ("AgenticAICodeReviewDesktop_" + $timestamp + ".exe")
    Copy-Item -Path $wailsExe -Destination $fallbackTarget -Force
    Write-Warning "Default EXE is locked by another process. Wrote updated EXE to: $fallbackTarget"
  }
  exit 0
}

Write-Host "Building Go desktop scaffold EXE..."
$targetCli = Join-Path $resolvedOutputDir "AgenticAICodeReviewDesktopCLI.exe"
& $Go build -o $targetCli .\cmd\desktop
if ($LASTEXITCODE -ne 0) {
  throw "go build failed."
}

Write-Host "CLI EXE ready: $targetCli"
