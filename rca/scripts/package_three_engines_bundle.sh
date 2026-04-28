#!/usr/bin/env bash
set -Eeuo pipefail

BUNDLE_NAME="rca_three_engines_bundle"
REBUILD=0
REBUILD_PROFILE="direct-stream"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_ROOT="$REPO_ROOT/dist"

usage() {
  cat <<'EOF'
Usage: ./scripts/package_three_engines_bundle.sh [options]

Options:
  --bundle-name NAME
      Output folder and zip base name. Default: rca_three_engines_bundle

  --rebuild
      Rebuild binaries first using ./rebuild_all.sh

  --rebuild-profile direct-stream|compatibility|all
      Build profile used with --rebuild. Default: direct-stream

  -h, --help
      Show this help.

Examples:
  ./scripts/package_three_engines_bundle.sh
  ./scripts/package_three_engines_bundle.sh --bundle-name my_bundle
  ./scripts/package_three_engines_bundle.sh --rebuild --rebuild-profile direct-stream
EOF
}

log() {
  printf '[package] %s\n' "$*"
}

fail() {
  printf '[package] ERROR: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --bundle-name)
      [ "$#" -ge 2 ] || fail "--bundle-name requires a value"
      BUNDLE_NAME="$2"
      shift 2
      ;;
    --bundle-name=*)
      BUNDLE_NAME="${1#*=}"
      shift
      ;;
    --rebuild)
      REBUILD=1
      shift
      ;;
    --rebuild-profile)
      [ "$#" -ge 2 ] || fail "--rebuild-profile requires a value"
      REBUILD_PROFILE="$2"
      shift 2
      ;;
    --rebuild-profile=*)
      REBUILD_PROFILE="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

case "$REBUILD_PROFILE" in
  direct-stream|compatibility|all) ;;
  *) fail "unsupported rebuild profile '$REBUILD_PROFILE'" ;;
esac

ensure_dir() {
  mkdir -p "$1"
}

reset_path() {
  local path="$1"
  if [ -e "$path" ]; then
    rm -rf "$path"
  fi
}

copy_if_exists() {
  local source="$1"
  local destination="$2"
  local destination_parent

  if [ ! -e "$source" ]; then
    printf '[package] WARNING: skipping missing path: %s\n' "$source" >&2
    return
  fi

  destination_parent="$(dirname "$destination")"
  ensure_dir "$destination_parent"
  cp -R "$source" "$destination"
}

copy_tree() {
  local relative_path="$1"
  copy_if_exists "$REPO_ROOT/$relative_path" "$BUNDLE_ROOT/$relative_path"
}

create_zip() {
  local source_dir="$1"
  local zip_path="$2"

  if command -v zip >/dev/null 2>&1; then
    (
      cd "$source_dir"
      zip -qr "$zip_path" .
    )
    return
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command \
      "\$ErrorActionPreference = 'Stop'; Compress-Archive -Path '$source_dir\\*' -DestinationPath '$zip_path' -Force" >/dev/null
    return
  fi

  if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -Command \
      "\$ErrorActionPreference = 'Stop'; Compress-Archive -Path '$source_dir/*' -DestinationPath '$zip_path' -Force" >/dev/null
    return
  fi

  fail "neither 'zip' nor PowerShell is available to create the zip archive"
}

file_count() {
  find "$1" -type f | wc -l | awk '{print $1}'
}

bundle_size_mb() {
  local zip_path="$1"

  if command -v stat >/dev/null 2>&1; then
    if stat -c %s "$zip_path" >/dev/null 2>&1; then
      awk -v bytes="$(stat -c %s "$zip_path")" 'BEGIN { printf "%.2f", bytes / 1048576 }'
      return
    fi
    if stat -f %z "$zip_path" >/dev/null 2>&1; then
      awk -v bytes="$(stat -f %z "$zip_path")" 'BEGIN { printf "%.2f", bytes / 1048576 }'
      return
    fi
  fi

  printf 'unknown'
}

BUNDLE_ROOT="$DIST_ROOT/$BUNDLE_NAME"
ZIP_PATH="$DIST_ROOT/$BUNDLE_NAME.zip"

ensure_dir "$DIST_ROOT"
reset_path "$BUNDLE_ROOT"
if [ -f "$ZIP_PATH" ]; then
  rm -f "$ZIP_PATH"
fi

if [ "$REBUILD" -eq 1 ]; then
  [ -f "$REPO_ROOT/rebuild_all.sh" ] || fail "missing rebuild script: $REPO_ROOT/rebuild_all.sh"
  log "Rebuilding binaries with profile '$REBUILD_PROFILE'..."
  (
    cd "$REPO_ROOT"
    ./rebuild_all.sh --profile "$REBUILD_PROFILE"
  )
fi

PATHS_TO_COPY=(
  "ecosystem.config.js"
  "rebuild_all.ps1"
  "rebuild_all.sh"
  "log_signalizing/config.yml"
  "log_signalizing/rules"
  "log_signalizing/state"
  "log_signalizing/signalizing_go/app.json"
  "log_signalizing/signalizing_go/rebuild.ps1"
  "log_signalizing/signalizing_go/rebuild.sh"
  "log_signalizing/signalizing_go/go.mod"
  "log_signalizing/signalizing_go/go.sum"
  "log_signalizing/signalizing_go/cmd"
  "log_signalizing/signalizing_go/internal"
  "log_signalizing/signalizing_go/bin"
  "log_correlation_engine/build.ps1"
  "log_correlation_engine/build.sh"
  "log_correlation_engine/go.mod"
  "log_correlation_engine/go.sum"
  "log_correlation_engine/cmd"
  "log_correlation_engine/internal"
  "log_correlation_engine/config"
  "log_correlation_engine/rules"
  "log_correlation_engine/bin"
  "log_rca_engine/app.json"
  "log_rca_engine/rebuild.ps1"
  "log_rca_engine/rebuild.sh"
  "log_rca_engine/go.mod"
  "log_rca_engine/go.sum"
  "log_rca_engine/cmd"
  "log_rca_engine/internal"
  "log_rca_engine/config"
  "log_rca_engine/data"
  "log_rca_engine/bin"
)

for relative_path in "${PATHS_TO_COPY[@]}"; do
  copy_tree "$relative_path"
done

create_zip "$BUNDLE_ROOT" "$ZIP_PATH"

log ""
log "Bundle created successfully."
log "Folder: $BUNDLE_ROOT"
log "Zip:    $ZIP_PATH"
log "Files:  $(file_count "$BUNDLE_ROOT")"
log "Size:   $(bundle_size_mb "$ZIP_PATH") MB"
