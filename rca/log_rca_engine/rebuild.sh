#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

mkdir -p "$SCRIPT_DIR/bin"
export GOCACHE="${REPO_ROOT}/.gocache"
go build -trimpath -o "$SCRIPT_DIR/bin/log-rca-engine.exe" ./cmd
