#!/usr/bin/env sh
set -eu

DELETE_EMPTY_DIRECTORIES=0
DRY_RUN=0

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

usage() {
  cat <<'EOF'
Usage: ./scripts/clear_engine_logs.sh [options]

Options:
  --dry-run
      Show which log files would be deleted without deleting them.

  --delete-empty-directories
      Remove engine log directories too, but only if they become empty.

  -h, --help
      Show this help.
EOF
}

log() {
  printf '[clear-logs] %s\n' "$*"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --delete-empty-directories)
      DELETE_EMPTY_DIRECTORIES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '[clear-logs] ERROR: unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

LOG_DIRECTORIES="
log_correlation_engine/logs
log_rca_engine/logs
log_signalizing/signalizing_go/logs
log_signal_processor/logs
"

deleted_count=0
list_file="${TMPDIR:-/tmp}/clear_engine_logs.$$"
trap 'rm -f "$list_file"' EXIT HUP INT TERM

delete_file() {
  file_path="$1"

  if [ "$DRY_RUN" -eq 1 ]; then
    log "Would delete: $file_path"
    return
  fi

  rm -f -- "$file_path"
  deleted_count=$((deleted_count + 1))
  log "Deleted: $file_path"
}

for relative_dir in $LOG_DIRECTORIES; do
  full_dir="$REPO_ROOT/$relative_dir"

  if [ ! -d "$full_dir" ]; then
    continue
  fi

  : > "$list_file"
  find "$full_dir" -maxdepth 1 -type f \( -name '*.log' -o -name '*.out' -o -name '*.err' \) -print > "$list_file"

  while IFS= read -r file_path; do
    delete_file "$file_path"
  done < "$list_file"

  if [ "$DELETE_EMPTY_DIRECTORIES" -eq 1 ] && [ "$DRY_RUN" -eq 0 ] && [ -d "$full_dir" ]; then
    if [ -z "$(find "$full_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
      rmdir "$full_dir"
      log "Removed empty directory: $full_dir"
    fi
  fi
done

if [ "$DRY_RUN" -eq 1 ]; then
  log "Dry run completed."
else
  log "Deleted log files: $deleted_count"
fi
