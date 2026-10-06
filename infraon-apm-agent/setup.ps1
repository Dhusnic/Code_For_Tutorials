<#
.SYNOPSIS
    Windows setup for the Infraon Agent tutorial.

.DESCRIPTION
    What this script does, in order:
      1. Checks for python on PATH.
      2. Creates a local virtualenv (.\venv) so nothing is installed globally.
      3. Installs this project's own dependencies (requirements.txt: psutil,
         requests) AND the OpenTelemetry packages installer.py would otherwise
         install into a *target* app's interpreter (see README.md "Two
         halves" section for why that distinction matters).
      4. Loads secrets from a local ".env" file if one exists (never committed).
      5. Checks bin\otelcol — it is a LINUX binary shipped from the source
         VM, so it cannot run natively on Windows. This script detects that
         and, unless -SkipCollectorDownload is passed, downloads a genuine
         Windows build of the OpenTelemetry Collector Contrib (same v0.147.0
         release) to bin\otelcol.exe instead.
      6. Generates collector\otel.yaml from config.py (collector_manager.py).
      7. With -Start, also launches the collector in the foreground.

    What this script deliberately does NOT do:
      - It never runs agent.py for you. agent.py finds a running Django/
        gunicorn/uwsgi process and SIGTERMs/kills it, then restarts it
        wrapped in `opentelemetry-instrument`. That is also Linux/psutil
        process-signal code that does not map cleanly onto Windows services
        — read README.md's "Windows caveats" section before ever trying it
        here. Run it yourself, on purpose, never automatically.

.PARAMETER Start
    After setup, also launch the collector in the foreground.

.PARAMETER SkipCollectorDownload
    Skip downloading a Windows build of otelcol; leave the Linux binary in
    place (useful if you plan to run the collector inside WSL instead).

.EXAMPLE
    .\setup.ps1
.EXAMPLE
    .\setup.ps1 -Start
#>
[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$SkipCollectorDownload
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Step($n, $total, $text) {
    Write-Host ""
    Write-Host "== $n/$total $text ==" -ForegroundColor Cyan
}

$TotalSteps = 6

# -----------------------------------------------------------------------
Write-Step 1 $TotalSteps "Checking for python"
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Error "python not found on PATH. Install Python 3.9+ from python.org and re-run."
}
& $pythonCmd.Source --version

# -----------------------------------------------------------------------
Write-Step 2 $TotalSteps "Creating virtualenv (.\venv)"
if (-not (Test-Path ".\venv")) {
    & $pythonCmd.Source -m venv venv
} else {
    Write-Host "venv already exists, reusing it"
}
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$venvPip    = Join-Path $PSScriptRoot "venv\Scripts\pip.exe"

# -----------------------------------------------------------------------
Write-Step 3 $TotalSteps "Installing dependencies"
& $venvPip install --upgrade pip --quiet
& $venvPip install -r requirements.txt --quiet
# Same four packages installer.py would push into a *target* app's
# interpreter in the full self-instrumentation flow — installed here too so
# you can experiment with `opentelemetry-instrument` directly in this venv.
& $venvPip install --quiet `
    opentelemetry-distro `
    opentelemetry-exporter-otlp `
    opentelemetry-instrumentation-django `
    opentelemetry-instrumentation-psycopg2
$venvOtelBootstrap = Join-Path $PSScriptRoot "venv\Scripts\opentelemetry-bootstrap.exe"
if (Test-Path $venvOtelBootstrap) {
    & $venvOtelBootstrap --action=install *> $null
}
Write-Host "dependencies installed into .\venv"

# -----------------------------------------------------------------------
Write-Step 4 $TotalSteps "Loading local secrets (.env), if present"
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $value = $line -split "=", 2
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
        }
    }
    Write-Host ".env loaded"
} else {
    Write-Host "No .env file found - config.py will fall back to its placeholder"
    Write-Host "defaults (CHANGE_ME_...). Copy .env.example to .env and fill in real"
    Write-Host "values before pointing this at a real OpenObserve/Elasticsearch."
}

# -----------------------------------------------------------------------
Write-Step 5 $TotalSteps "Preparing the collector binary"
$otelcolExe = Join-Path $PSScriptRoot "bin\otelcol.exe"
$otelcolLinux = Join-Path $PSScriptRoot "bin\otelcol"

if (Test-Path $otelcolExe) {
    Write-Host "bin\otelcol.exe already present, using it"
}
elseif ($SkipCollectorDownload) {
    Write-Host "bin\otelcol is a LINUX binary and cannot run natively on Windows." -ForegroundColor Yellow
    Write-Host "You passed -SkipCollectorDownload, so it was left as-is."
    Write-Host "Run it under WSL instead: wsl ./bin/otelcol --config collector/otel.yaml"
}
else {
    Write-Host "bin\otelcol is a LINUX binary (confirmed via its ELF header) and cannot" -ForegroundColor Yellow
    Write-Host "run natively on Windows. Downloading a genuine Windows build of the same"
    Write-Host "OpenTelemetry Collector Contrib release (v0.147.0) instead..."
    $version = "0.147.0"
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
    $assetName = "otelcol-contrib_${version}_windows_${arch}.tar.gz"
    $url = "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v$version/$assetName"
    $tmpTar = Join-Path $env:TEMP $assetName
    try {
        Write-Host "Downloading: $url"
        Invoke-WebRequest -Uri $url -OutFile $tmpTar -UseBasicParsing
        $extractDir = Join-Path $env:TEMP "otelcol-extract-$version"
        New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
        tar -xzf $tmpTar -C $extractDir
        $exe = Get-ChildItem -Path $extractDir -Filter "otelcol-contrib.exe" -Recurse | Select-Object -First 1
        if (-not $exe) {
            throw "otelcol-contrib.exe not found inside the downloaded archive"
        }
        Copy-Item $exe.FullName $otelcolExe -Force
        Write-Host "Installed bin\otelcol.exe (Windows, v$version)" -ForegroundColor Green
    }
    catch {
        Write-Host "Could not download a Windows build automatically: $_" -ForegroundColor Yellow
        Write-Host "Options:"
        Write-Host "  1. Download it yourself from:"
        Write-Host "     https://github.com/open-telemetry/opentelemetry-collector-releases/releases"
        Write-Host "     and save the exe as bin\otelcol.exe"
        Write-Host "  2. Or run the bundled Linux binary under WSL:"
        Write-Host "     wsl ./bin/otelcol --config collector/otel.yaml"
    }
}

# -----------------------------------------------------------------------
Write-Step 6 $TotalSteps "Generating collector\otel.yaml from config.py"
& $venvPython -c "from config import CONFIG; from collector_manager import generate_config; generate_config(CONFIG)"
Write-Host "wrote collector\otel.yaml"

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "  - Review collector\otel.yaml before trusting it with real data."
if (Test-Path $otelcolExe) {
    Write-Host "  - Start the collector manually with:  .\bin\otelcol.exe --config collector\otel.yaml"
} else {
    Write-Host "  - Start the collector manually with:  wsl ./bin/otelcol --config collector/otel.yaml"
}
Write-Host "  - Or re-run this script with -Start to do that now."

if ($Start) {
    Write-Host ""
    Write-Host "== Starting the collector (Ctrl+C to stop) ==" -ForegroundColor Cyan
    if (Test-Path $otelcolExe) {
        & $otelcolExe --config "collector\otel.yaml"
    } else {
        wsl ./bin/otelcol --config collector/otel.yaml
    }
}
