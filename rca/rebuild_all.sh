#!/usr/bin/env bash
set -Eeuo pipefail

PROFILE="direct-stream"
RUN_TESTS=0
SKIP_CLEAN=0
AUTO_INSTALL_GO=1
RESTART_PM2=0

GO_MIN_VERSION="${GO_MIN_VERSION:-1.23.0}"
GO_VERSION="${GO_VERSION:-auto}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

usage() {
  cat <<'EOF'
Usage: ./rebuild_all.sh [options]

Options:
  --profile direct-stream|compatibility|all
      Build profile. Default: direct-stream

  --run-tests
      Run go test ./... for every built Go module.

  --skip-clean
      Do not remove existing binaries before build.

  --no-install-go
      Fail if Go is missing or older than the required version.

  --restart-pm2
      Restart PM2 apps after a successful build.

  -h, --help
      Show this help.

Environment:
  GO_VERSION=auto          Go tarball version used when Go must be installed.
                           Use auto for latest stable from go.dev, or set a
                           version like GO_VERSION=1.23.12.
  GO_MIN_VERSION=1.23.0    Minimum accepted Go version.
  CGO_ENABLED=0            Build setting. Defaults to 0.

Examples:
  ./rebuild_all.sh
  ./rebuild_all.sh --profile all --run-tests
  GO_VERSION=1.23.12 ./rebuild_all.sh --profile direct-stream
  ./rebuild_all.sh --restart-pm2
EOF
}

log() {
  printf '[rebuild] %s\n' "$*"
}

fail() {
  printf '[rebuild] ERROR: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      [ "$#" -ge 2 ] || fail "--profile requires a value"
      PROFILE="$2"
      shift 2
      ;;
    --profile=*)
      PROFILE="${1#*=}"
      shift
      ;;
    --run-tests)
      RUN_TESTS=1
      shift
      ;;
    --skip-clean)
      SKIP_CLEAN=1
      shift
      ;;
    --no-install-go)
      AUTO_INSTALL_GO=0
      shift
      ;;
    --restart-pm2)
      RESTART_PM2=1
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

case "$PROFILE" in
  direct-stream|compatibility|all) ;;
  *) fail "unsupported profile '$PROFILE'" ;;
esac

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  fail "root privileges are required for: $*"
}

version_ge() {
  local left="${1#go}"
  local right="${2#go}"
  local left_major left_minor left_patch right_major right_minor right_patch

  IFS=. read -r left_major left_minor left_patch <<<"$left"
  IFS=. read -r right_major right_minor right_patch <<<"$right"

  left_major="${left_major:-0}"
  left_minor="${left_minor:-0}"
  left_patch="${left_patch:-0}"
  right_major="${right_major:-0}"
  right_minor="${right_minor:-0}"
  right_patch="${right_patch:-0}"

  if [ "$left_major" -gt "$right_major" ]; then return 0; fi
  if [ "$left_major" -lt "$right_major" ]; then return 1; fi
  if [ "$left_minor" -gt "$right_minor" ]; then return 0; fi
  if [ "$left_minor" -lt "$right_minor" ]; then return 1; fi
  [ "$left_patch" -ge "$right_patch" ]
}

current_go_version() {
  if ! command -v go >/dev/null 2>&1; then
    return 1
  fi

  go version | awk '{print $3}' | sed -E 's/^go([0-9]+(\.[0-9]+){1,2}).*$/\1/'
}

install_packages() {
  local packages=(ca-certificates curl gzip tar)

  if command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y "${packages[@]}"
    return
  fi

  if command -v yum >/dev/null 2>&1; then
    run_as_root yum install -y "${packages[@]}"
    return
  fi

  fail "neither dnf nor yum was found; install curl, gzip, and tar manually"
}

go_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'amd64' ;;
    aarch64|arm64) printf 'arm64' ;;
    *) fail "unsupported CPU architecture: $(uname -m)" ;;
  esac
}

resolve_go_download_version() {
  local version_json
  local resolved

  if [ "$GO_VERSION" != "auto" ]; then
    printf '%s' "$GO_VERSION"
    return
  fi

  log "Resolving latest stable Go version from go.dev"
  version_json="$(curl -fsSL 'https://go.dev/dl/?mode=json')"
  resolved="$(printf '%s\n' "$version_json" | sed -nE 's/.*"version"[[:space:]]*:[[:space:]]*"go([0-9]+(\.[0-9]+){1,2})".*/\1/p' | head -n 1)"

  if [ -z "$resolved" ]; then
    fail "unable to resolve latest Go version from go.dev; rerun with GO_VERSION=1.23.12 or newer"
  fi

  if ! version_ge "$resolved" "$GO_MIN_VERSION"; then
    fail "resolved Go $resolved is older than required $GO_MIN_VERSION"
  fi

  printf '%s' "$resolved"
}

install_go_tarball() {
  local arch
  local version
  local url
  local tmpdir

  arch="$(go_arch)"
  install_packages
  version="$(resolve_go_download_version)"
  url="https://go.dev/dl/go${version}.linux-${arch}.tar.gz"
  tmpdir="$(mktemp -d)"

  cleanup_go_tmp() {
    rm -rf "$tmpdir"
  }
  trap cleanup_go_tmp RETURN

  log "Installing Go ${version} for linux-${arch}"

  log "Downloading $url"
  curl -fL "$url" -o "$tmpdir/go.tar.gz"

  log "Installing into /usr/local/go"
  run_as_root rm -rf /usr/local/go
  run_as_root tar -C /usr/local -xzf "$tmpdir/go.tar.gz"

  if [ -d /etc/profile.d ]; then
    printf '%s\n' 'export PATH=/usr/local/go/bin:$PATH' | run_as_root tee /etc/profile.d/go.sh >/dev/null
  fi

  export PATH="/usr/local/go/bin:$PATH"
}

ensure_go() {
  local detected=""

  if detected="$(current_go_version)"; then
    if version_ge "$detected" "$GO_MIN_VERSION"; then
      log "Using Go $(go version)"
      return
    fi

    log "Installed Go $detected is older than required $GO_MIN_VERSION"
  else
    log "Go is not installed or not in PATH"
  fi

  if [ "$AUTO_INSTALL_GO" -ne 1 ]; then
    fail "Go $GO_MIN_VERSION+ is required. Install Go or rerun without --no-install-go."
  fi

  install_go_tarball

  if ! detected="$(current_go_version)"; then
    fail "Go install completed, but go is still not available in PATH"
  fi
  if ! version_ge "$detected" "$GO_MIN_VERSION"; then
    fail "Go $detected is still older than required $GO_MIN_VERSION"
  fi

  log "Using Go $(go version)"
}

ensure_dir() {
  mkdir -p "$1"
}

remove_binary_if_requested() {
  local path="$1"

  if [ "$SKIP_CLEAN" -eq 1 ]; then
    return
  fi

  if [ -e "$path" ]; then
    rm -f "$path" || fail "unable to remove '$path'; stop the running process and rerun, or use --skip-clean"
  fi

  if [ -e "${path}~" ]; then
    rm -f "${path}~" || fail "unable to remove '${path}~'"
  fi
}

build_go_target() {
  local name="$1"
  local project_dir="$2"
  local output_path="$3"
  local package_path="$4"

  ensure_dir "$(dirname "$output_path")"
  remove_binary_if_requested "$output_path"

  log ""
  log "[$name] Building $package_path"
  log "[$name] Output: $output_path"

  (
    cd "$project_dir"
    CGO_ENABLED="${CGO_ENABLED:-0}" GOOS=linux go build -trimpath -o "$output_path" "$package_path"
  )

  [ -f "$output_path" ] || fail "[$name] build completed without producing '$output_path'"
  chmod +x "$output_path"
}

run_go_tests() {
  local project_dir="$1"

  log ""
  log "[test] Running go test ./... in $project_dir"
  (
    cd "$project_dir"
    CGO_ENABLED="${CGO_ENABLED:-0}" go test ./...
  )
}

restart_pm2_apps() {
  if ! command -v pm2 >/dev/null 2>&1; then
    fail "--restart-pm2 requested, but pm2 is not installed or not in PATH"
  fi

  restart_pm2_app() {
    local app="$1"
    if pm2 describe "$app" >/dev/null 2>&1; then
      log "Restarting PM2 app: $app"
      pm2 restart "$app"
    else
      log "PM2 app not found, skipping: $app"
    fi
  }

  case "$PROFILE" in
    direct-stream)
      restart_pm2_app signalizing-engine
      restart_pm2_app correlation-engine
      restart_pm2_app log-rca-engine
      ;;
    compatibility)
      restart_pm2_app signaled-logs-collector
      ;;
    all)
      restart_pm2_app signalizing-engine
      restart_pm2_app correlation-engine
      restart_pm2_app log-rca-engine
      restart_pm2_app signaled-logs-collector
      ;;
  esac
}

TARGET_NAMES=(
  "correlation-engine"
  "log-rca-engine"
  "signalizing-engine"
  "validate-rules"
  "signaled-logs-collector"
)
TARGET_PROJECTS=(
  "$REPO_ROOT/log_correlation_engine"
  "$REPO_ROOT/log_rca_engine"
  "$REPO_ROOT/log_signalizing/signalizing_go"
  "$REPO_ROOT/log_signalizing/signalizing_go"
  "$REPO_ROOT/log_signal_processor"
)
TARGET_OUTPUTS=(
  "$REPO_ROOT/log_correlation_engine/bin/correlation-engine.exe"
  "$REPO_ROOT/log_rca_engine/bin/log-rca-engine.exe"
  "$REPO_ROOT/log_signalizing/signalizing_go/bin/signalizing-engine.exe"
  "$REPO_ROOT/log_signalizing/signalizing_go/bin/validate-rules.exe"
  "$REPO_ROOT/log_signal_processor/bin/signaled-logs-collector.exe"
)
TARGET_PACKAGES=(
  "./cmd"
  "./cmd"
  "./cmd/signalizing-engine"
  "./cmd/validate-rules"
  "./cmd/signaled_logs_collector"
)

selected_indices() {
  case "$PROFILE" in
    direct-stream) printf '%s\n' 0 1 2 3 ;;
    compatibility) printf '%s\n' 4 ;;
    all) printf '%s\n' 0 1 2 3 4 ;;
  esac
}

unique_test_projects() {
  local seen=""
  local idx project

  while read -r idx; do
    project="${TARGET_PROJECTS[$idx]}"
    case " $seen " in
      *" $project "*) ;;
      *)
        seen="$seen $project"
        printf '%s\n' "$project"
        ;;
    esac
  done < <(selected_indices)
}

main() {
  cd "$REPO_ROOT"
  ensure_go

  export GOCACHE="$REPO_ROOT/.gocache"
  ensure_dir "$GOCACHE"

  log "Repository: $REPO_ROOT"
  log "Using GOCACHE: $GOCACHE"
  log "Rebuild profile: $PROFILE"
  if [ "$SKIP_CLEAN" -eq 1 ]; then
    log "Binary cleanup: skipped"
  else
    log "Binary cleanup: enabled"
  fi

  local idx
  while read -r idx; do
    build_go_target \
      "${TARGET_NAMES[$idx]}" \
      "${TARGET_PROJECTS[$idx]}" \
      "${TARGET_OUTPUTS[$idx]}" \
      "${TARGET_PACKAGES[$idx]}"
  done < <(selected_indices)

  if [ "$RUN_TESTS" -eq 1 ]; then
    while read -r project; do
      run_go_tests "$project"
    done < <(unique_test_projects)
  fi

  if [ "$RESTART_PM2" -eq 1 ]; then
    restart_pm2_apps
  fi

  log ""
  log "Rebuild completed successfully."
  log "Built targets:"
  while read -r idx; do
    printf '  - %s: %s\n' "${TARGET_NAMES[$idx]}" "${TARGET_OUTPUTS[$idx]}"
  done < <(selected_indices)

  log ""
  log "Recommended usage:"
  case "$PROFILE" in
    direct-stream)
      printf '  pm2 start ./ecosystem.config.js\n'
      ;;
    compatibility)
      printf '  cd ./log_signal_processor && ./bin/signaled-logs-collector.exe --config ./config.yml\n'
      ;;
    all)
      printf '  pm2 start ./ecosystem.config.js\n'
      printf '  Start signaled-logs-collector only if you still want the compatibility flow.\n'
      ;;
  esac
}

main "$@"
