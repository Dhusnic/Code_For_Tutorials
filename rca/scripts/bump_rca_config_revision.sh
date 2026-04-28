#!/usr/bin/env bash
set -Eeuo pipefail

MONGO_URI="${MONGO_URI:-mongodb://infraondns:InfraonMongodb321@10.0.4.72:27017/infraon_default_db?retryWrites=false&authSource=infraon_default_db&authMechanism=SCRAM-SHA-1}"
MONGO_DB="${MONGO_DB:-dhusnic_test_db}"
STATE_COLLECTION="${STATE_COLLECTION:-rca_config_state}"
STATE_NAME="${STATE_NAME:-prod_rules_topology}"
REDIS_CHANNEL="${REDIS_CHANNEL:-rca_config_changed}"
PUBLISH_REDIS="${PUBLISH_REDIS:-0}"
REDIS_HOST="${REDIS_HOST:-10.0.5.97}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

if ! command -v mongosh >/dev/null 2>&1; then
  echo "ERROR: mongosh is required to bump the RCA config revision." >&2
  exit 1
fi

revision="$(
  mongosh "$MONGO_URI" --quiet --eval "
    const result = db.getSiblingDB('$MONGO_DB').getCollection('$STATE_COLLECTION').findOneAndUpdate(
      { name: '$STATE_NAME' },
      { \$inc: { revision: 1 }, \$set: { updated_at: new Date() }, \$setOnInsert: { name: '$STATE_NAME' } },
      { upsert: true, returnDocument: 'after' }
    );
    print(result.revision);
  "
)"

payload="{\"name\":\"$STATE_NAME\",\"revision\":$revision}"
echo "Bumped RCA config revision: $payload"

if [ "$PUBLISH_REDIS" = "1" ]; then
  if ! command -v redis-cli >/dev/null 2>&1; then
    echo "ERROR: redis-cli is required when PUBLISH_REDIS=1." >&2
    exit 1
  fi
  redis_args=(-h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB")
  if [ -n "$REDIS_PASSWORD" ]; then
    redis_args+=(-a "$REDIS_PASSWORD")
  fi
  redis-cli "${redis_args[@]}" PUBLISH "$REDIS_CHANNEL" "$payload" >/dev/null
  echo "Published config change on Redis channel: $REDIS_CHANNEL"
fi
