#!/usr/bin/env bash
set -Eeuo pipefail

# Realtime RCA trigger for:
#   CORR_REALTIME_MONGO_USER_NOT_FOUND_TO_NGINX_502
#
# Normal VM usage:
#   1. Edit ONLY the config block below.
#   2. Run:
#        sudo bash log_simulations/trigger_realtime_mongo_nginx_502.sh
#
# The script creates real activity:
#   - 3 real MongoDB auth attempts with a missing user
#   - stops your real upstream backend
#   - 3 real requests through NGINX that should return 502
#   - starts your backend again

###############################################################################
# EDIT THIS CONFIG BLOCK FOR YOUR VM
###############################################################################

# MongoDB endpoint on the VM.
MONGO_HOST="10.0.4.72"
MONGO_PORT="27017"
MONGO_AUTH_DB="infraon_default_db"
MONGO_AUTH_MECHANISM="SCRAM-SHA-1"

# NGINX URL that proxies to your backend app.
# It must be an endpoint that returns 502 when the backend is stopped.
NGINX_URL="https://10.0.4.72/"
CURL_INSECURE_TLS=true

# Pick ONE backend control style.
#
# Option A: systemd service backend
# Example: BACKEND_SYSTEMD_SERVICE="my-api"
BACKEND_SYSTEMD_SERVICE=""

# Option B: PM2 app backend
# Example: BACKEND_PM2_APP="api-service"
BACKEND_PM2_APP=""

# If you need a custom backend stop/start command, set these.
# These override BACKEND_SYSTEMD_SERVICE and BACKEND_PM2_APP.
BACKEND_STOP_CMD=""
BACKEND_START_CMD=""

###############################################################################
# Usually no need to edit below this line.
###############################################################################

RULE_ID="CORR_REALTIME_MONGO_USER_NOT_FOUND_TO_NGINX_502"

MONGO_FAKE_USER="rca_missing_user_$(date +%s)"
MONGO_FAKE_PASSWORD="WrongPassword123"
MONGO_ATTEMPTS=3
NGINX_REQUESTS=3
RESTORE_BACKEND=true
SLEEP_BETWEEN=1
WAIT_AFTER_BACKEND_STOP=3

backend_stopped=false

usage() {
  cat <<'USAGE'
Trigger real logs for:
  CORR_REALTIME_MONGO_USER_NOT_FOUND_TO_NGINX_502

Normal usage:
  Edit the config block at the top of this file, then run:

    sudo bash log_simulations/trigger_realtime_mongo_nginx_502.sh

Examples:
  sudo bash log_simulations/trigger_realtime_mongo_nginx_502.sh \
    --nginx-url http://127.0.0.1/api/users \
    --systemd-service my-api

  bash log_simulations/trigger_realtime_mongo_nginx_502.sh \
    --nginx-url http://127.0.0.1/api/users \
    --pm2-app api-service

Flags:
  --mongo-host HOST
  --mongo-port PORT
  --mongo-auth-db DB
  --mongo-auth-mechanism MECH
  --nginx-url URL
  --systemd-service NAME
  --pm2-app NAME
  --strict-tls
  --no-restore
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

restore_backend() {
  if [[ "$backend_stopped" == "true" && "$RESTORE_BACKEND" == "true" && -n "$BACKEND_START_CMD" ]]; then
    log "Restoring backend: $BACKEND_START_CMD"
    bash -lc "$BACKEND_START_CMD" || {
      log "WARNING: backend restore command failed"
      return 1
    }
  fi
}

trap restore_backend EXIT

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mongo-host)
      MONGO_HOST="${2:?missing value for --mongo-host}"
      shift 2
      ;;
    --mongo-port)
      MONGO_PORT="${2:?missing value for --mongo-port}"
      shift 2
      ;;
    --mongo-auth-db)
      MONGO_AUTH_DB="${2:?missing value for --mongo-auth-db}"
      shift 2
      ;;
    --mongo-auth-mechanism)
      MONGO_AUTH_MECHANISM="${2:?missing value for --mongo-auth-mechanism}"
      shift 2
      ;;
    --nginx-url)
      NGINX_URL="${2:?missing value for --nginx-url}"
      shift 2
      ;;
    --systemd-service)
      BACKEND_SYSTEMD_SERVICE="${2:?missing value for --systemd-service}"
      shift 2
      ;;
    --pm2-app)
      BACKEND_PM2_APP="${2:?missing value for --pm2-app}"
      shift 2
      ;;
    --strict-tls)
      CURL_INSECURE_TLS=false
      shift
      ;;
    --no-restore)
      RESTORE_BACKEND=false
      shift
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd mongosh
require_cmd curl

if [[ -z "$BACKEND_STOP_CMD" || -z "$BACKEND_START_CMD" ]]; then
  if [[ -n "$BACKEND_SYSTEMD_SERVICE" ]]; then
    BACKEND_STOP_CMD="systemctl stop ${BACKEND_SYSTEMD_SERVICE}"
    BACKEND_START_CMD="systemctl start ${BACKEND_SYSTEMD_SERVICE}"
  elif [[ -n "$BACKEND_PM2_APP" ]]; then
    BACKEND_STOP_CMD="pm2 stop ${BACKEND_PM2_APP}"
    BACKEND_START_CMD="pm2 start ${BACKEND_PM2_APP}"
  fi
fi

log "Rule target: $RULE_ID"
log "MongoDB target: ${MONGO_HOST}:${MONGO_PORT}/${MONGO_AUTH_DB} authMechanism=${MONGO_AUTH_MECHANISM}"
log "NGINX URL: $NGINX_URL"

if [[ -z "$BACKEND_STOP_CMD" ]]; then
  cat >&2 <<'EOF'
ERROR: No backend stop command configured.

Edit the script config block and set one of:
  BACKEND_SYSTEMD_SERVICE="your-service"
  BACKEND_PM2_APP="your-pm2-app"
  BACKEND_STOP_CMD="custom stop command"
  BACKEND_START_CMD="custom start command"

Or run with:
  --systemd-service your-service
  --pm2-app your-pm2-app
EOF
  exit 1
fi

log "Generating ${MONGO_ATTEMPTS} MongoDB user-not-found attempts"
for attempt in $(seq 1 "$MONGO_ATTEMPTS"); do
  uri="mongodb://${MONGO_FAKE_USER}:${MONGO_FAKE_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}/${MONGO_AUTH_DB}?retryWrites=false&authSource=${MONGO_AUTH_DB}&authMechanism=${MONGO_AUTH_MECHANISM}&serverSelectionTimeoutMS=2000"
  if mongosh "$uri" --quiet --eval 'db.runCommand({ ping: 1 })' >/dev/null 2>&1; then
    log "WARNING: MongoDB auth attempt ${attempt}/${MONGO_ATTEMPTS} unexpectedly succeeded"
  else
    log "MongoDB auth attempt ${attempt}/${MONGO_ATTEMPTS} failed as expected"
  fi
  sleep "$SLEEP_BETWEEN"
done

if [[ -n "$BACKEND_STOP_CMD" ]]; then
  log "Stopping upstream backend to make NGINX return 502: $BACKEND_STOP_CMD"
  bash -lc "$BACKEND_STOP_CMD"
  backend_stopped=true
  sleep "$WAIT_AFTER_BACKEND_STOP"
else
  log "BACKEND_STOP_CMD not set; assuming NGINX URL already returns 502 from a broken upstream"
fi

log "Sending ${NGINX_REQUESTS} requests through NGINX"
for request in $(seq 1 "$NGINX_REQUESTS"); do
  curl_tls_args=()
  if [[ "$CURL_INSECURE_TLS" == "true" ]]; then
    curl_tls_args=(-k)
  fi
  status="$(curl "${curl_tls_args[@]}" -sS -o /tmp/rca_nginx_502_body.$$ -w '%{http_code}' "$NGINX_URL" || true)"
  rm -f /tmp/rca_nginx_502_body.$$
  if [[ "$status" == "502" ]]; then
    log "NGINX request ${request}/${NGINX_REQUESTS} returned 502 as expected"
  else
    log "WARNING: NGINX request ${request}/${NGINX_REQUESTS} returned HTTP ${status}, expected 502"
  fi
  sleep "$SLEEP_BETWEEN"
done

log "Trigger sequence completed. Wait for signalizing, correlation, and RCA cycles to process it."
log "Expected signals: mongodb_user_not_found x3, nginx_access_502_bad_gateway x3"
