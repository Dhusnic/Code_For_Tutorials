#!/usr/bin/env bash
set -Eeuo pipefail

MONGO_URI="${MONGO_URI:-mongodb://infraondns:InfraonMongodb321@10.0.4.72:27017/infraon_default_db?retryWrites=false&authSource=infraon_default_db&authMechanism=SCRAM-SHA-1}"
MONGO_DB="${MONGO_DB:-dhusnic_test_db}"

if ! command -v mongosh >/dev/null 2>&1; then
  echo "ERROR: mongosh is required to create RCA config indexes." >&2
  exit 1
fi

mongosh "$MONGO_URI" --quiet --eval "
  const dbx = db.getSiblingDB('$MONGO_DB');
  dbx.correlation_rules.createIndex({ is_enabled: 1, priority: 1, id: 1 });
  dbx.correlation_rules.createIndex({ id: 1 }, { unique: true, sparse: true });
  dbx.topology_data.createIndex({ is_enabled: 1, topology_id: 1, organization_id: 1 });
  dbx.topology_data.createIndex({ organization_id: 1, topology_id: 1 }, { unique: true, sparse: true });
  dbx.rca_config_state.createIndex({ name: 1 }, { unique: true });
  dbx.rca_config_snapshots.createIndex({ name: 1, revision: -1 });
  dbx.rca_results.createIndex({ incident_id: 1 });
  dbx.rca_results.createIndex({ result_signature: 1 });
  dbx.rca_results.createIndex({ organization_id: 1, topology_id: 1, rule_id: 1 });
  print('RCA config indexes are ready.');
"
