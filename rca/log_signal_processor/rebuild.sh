#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
export GOCACHE="$REPO_ROOT/.gocache"
export GOMODCACHE="$REPO_ROOT/.gomodcache"

if command -v go >/dev/null 2>&1; then
  GO_EXE=go
elif [ -x "/c/Program Files/Go/bin/go.exe" ]; then
  GO_EXE="/c/Program Files/Go/bin/go.exe"
elif [ -x "/mnt/c/Program Files/Go/bin/go.exe" ]; then
  GO_EXE="/mnt/c/Program Files/Go/bin/go.exe"
else
  echo "Go executable not found. Install Go or add 'go' to PATH." >&2
  exit 1
fi

BIN_DIR="$SCRIPT_DIR/bin"
COLLECTOR_EXE="$BIN_DIR/signaled-logs-collector.exe"
COLLECTOR_EXE_BACKUP="$BIN_DIR/signaled-logs-collector.exe~"

mkdir -p "$BIN_DIR"

echo "Using Go executable: $GO_EXE"
echo "Using GOCACHE: $GOCACHE"
echo "Using GOMODCACHE: $GOMODCACHE"
echo "Removing previous collector binary if it exists..."
rm -f "$COLLECTOR_EXE" "$COLLECTOR_EXE_BACKUP"

echo "Building signaled-logs-collector.exe..."
"$GO_EXE" build -o "$COLLECTOR_EXE" ./cmd/signaled_logs_collector

echo "Rebuild completed."
echo "Created:"
echo "  $COLLECTOR_EXE"

if [ -e "$COLLECTOR_EXE_BACKUP" ]; then
  echo "Warning: a .exe~ backup file is still present. This usually means the old binary was in use. Restart or stop PM2 and rerun this script for a fully clean replacement." >&2
fi
