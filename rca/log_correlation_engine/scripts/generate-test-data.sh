#!/bin/bash
# Generate test data for log correlation engine

set -e

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
ORG_ID="135098068173316952064"

# Generate sample signalized logs and push to Redis
generate_test_data() {
    echo "Generating test data..."
    
    # Using redis-cli, add test logs
    redis-cli -h $REDIS_HOST -p $REDIS_PORT <<EOF
DEL RCA:$ORG_ID:signaled_logs

LPUSH RCA:$ORG_ID:signaled_logs '{
  "signal": "mongodb_auth_failed",
  "log_level": "warning",
  "doc_id": "doc_001",
  "time_stamp": "2026-04-07T10:25:00.000Z"
}'

LPUSH RCA:$ORG_ID:signaled_logs '{
  "signal": "mongodb_interrupted_client_disconnected",
  "log_level": "warning",
  "doc_id": "doc_002",
  "time_stamp": "2026-04-07T10:26:00.000Z"
}'

LPUSH RCA:$ORG_ID:signaled_logs '{
  "signal": "mongodb_host_unreachable",
  "log_level": "error",
  "doc_id": "doc_003",
  "time_stamp": "2026-04-07T10:27:00.000Z"
}'

LPUSH RCA:$ORG_ID:signaled_logs '{
  "signal": "nginx_access_5xx_any",
  "log_level": "error",
  "doc_id": "doc_004",
  "time_stamp": "2026-04-07T10:27:30.000Z"
}'

LPUSH RCA:$ORG_ID:signaled_logs '{
  "signal": "nginx_unclassified_failure",
  "log_level": "error",
  "doc_id": "doc_005",
  "time_stamp": "2026-04-07T10:28:00.000Z"
}'

EOF

    echo "Test data generated in Redis"
    echo "Organization ID: $ORG_ID"
    echo ""
    echo "List test data:"
    redis-cli -h $REDIS_HOST -p $REDIS_PORT LRANGE RCA:$ORG_ID:signaled_logs 0 -1
}

# Check connection
check_connection() {
    if ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1; then
        echo "Error: Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
        echo "Make sure Redis is running:"
        echo "  docker-compose up -d"
        exit 1
    fi
}

check_connection
generate_test_data
