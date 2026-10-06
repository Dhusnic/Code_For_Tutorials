#!/usr/bin/env bash
# =============================================================================
# setup.sh — Linux / macOS / WSL setup for the Infraon Agent tutorial.
#
# What this script does, in order:
#   1. Checks for python3 and pip.
#   2. Creates a local virtualenv (./venv) so nothing is installed globally.
#   3. Installs this project's own dependencies (requirements.txt: psutil,
#      requests) AND the OpenTelemetry packages installer.py would otherwise
#      install into a *target* app's interpreter (see README.md "Two halves"
#      section for why that distinction matters).
#   4. Loads secrets from a local ".env" file if one exists (never committed).
#   5. Makes bin/otelcol executable and prints its detected platform.
#   6. Generates collector/otel.yaml from config.py (collector_manager.py).
#   7. With --start, also launches the collector in the foreground.
#
# What this script deliberately does NOT do:
#   - It never runs agent.py for you. agent.py finds a running Django/
#     gunicorn/uwsgi process on THIS machine and SIGTERMs/kills it, then
#     restarts it wrapped in `opentelemetry-instrument`. That is a real,
#     disruptive action against a real process — run it yourself, on
#     purpose, when you're ready (see README.md "Running the full
#     self-instrumentation flow").
#
# Usage:
#   ./setup.sh            # install deps + generate collector/otel.yaml only
#   ./setup.sh --start    # also start the collector in the foreground
# =============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

START_COLLECTOR=0
for arg in "$@"; do
  case "$arg" in
    --start) START_COLLECTOR=1 ;;
    -h|--help)
      echo "Usage: $0 [--start]"
      echo "  --start   also launch the collector in the foreground after setup"
      exit 0
      ;;
  esac
done

echo "== 1/6 Checking for python3 =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH. Install Python 3.9+ and re-run." >&2
  exit 1
fi
python3 --version

echo "== 2/6 Creating virtualenv (./venv) =="
if [ ! -d venv ]; then
  python3 -m venv venv
else
  echo "venv already exists, reusing it"
fi
# shellcheck source=/dev/null
source venv/bin/activate

echo "== 3/6 Installing dependencies =="
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
# These four packages are what installer.py pip-installs into a *target*
# app's interpreter during the full self-instrumentation flow. We install
# them here too so you can experiment with `opentelemetry-instrument` and
# the Django/psycopg2 instrumentors directly in this tutorial's own venv.
pip install --quiet \
  opentelemetry-distro \
  opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-django \
  opentelemetry-instrumentation-psycopg2
# opentelemetry-distro doesn't pull in instrumentation auto-detection data
# by itself — this populates it (safe to re-run, it's idempotent).
opentelemetry-bootstrap --action=install >/dev/null 2>&1 || true
echo "dependencies installed into ./venv"

echo "== 4/6 Loading local secrets (.env), if present =="
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  echo ".env loaded"
else
  echo "No .env file found — config.py will fall back to its placeholder"
  echo "defaults (CHANGE_ME_...). Copy .env.example to .env and fill in real"
  echo "values before pointing this at a real OpenObserve/Elasticsearch."
fi

echo "== 5/6 Preparing the collector binary =="
chmod +x bin/otelcol
BIN_TYPE="$(file bin/otelcol 2>/dev/null || echo 'unknown (the "file" command is not installed)')"
echo "bin/otelcol: $BIN_TYPE"
case "$BIN_TYPE" in
  *ELF*)
    if [ "$(uname -s)" != "Linux" ]; then
      echo "WARNING: bin/otelcol is a Linux binary but this host is not Linux."
      echo "         On macOS, run the collector under Docker or download a"
      echo "         native build from https://github.com/open-telemetry/opentelemetry-collector-releases/releases"
    fi
    ;;
esac

echo "== 6/6 Generating collector/otel.yaml from config.py =="
python3 -c "from config import CONFIG; from collector_manager import generate_config; generate_config(CONFIG)"
echo "wrote collector/otel.yaml"
echo
echo "Setup complete."
echo "  - Review collector/otel.yaml before trusting it with real data."
echo "  - Start the collector manually with:  ./bin/otelcol --config collector/otel.yaml"
echo "  - Or re-run this script with --start to do that now."

if [ "$START_COLLECTOR" -eq 1 ]; then
  echo
  echo "== Starting the collector (Ctrl+C to stop) =="
  exec ./bin/otelcol --config collector/otel.yaml
fi
