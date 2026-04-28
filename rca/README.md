# RCA Production Runtime Notes

This repo runs the log signalizing, correlation, RCA, and config-sync services for the RCA pipeline.

## Runtime Services

The default PM2 stack is defined in `ecosystem.config.js`:

- `signalizing-engine`: converts raw logs into signalized events.
- `log-config-syncer`: syncs rules/topology config from MongoDB to local JSON.
- `correlation-engine`: matches signalized logs against enabled correlation rules.
- `log-rca-engine`: scores correlated incidents and writes RCA lifecycle results.

Build all direct-stream services:

```bash
./rebuild_all.sh --profile direct-stream
```

Start the stack:

```bash
pm2 start ./ecosystem.config.js
```

If the old config syncer name exists in PM2, remove it once:

```bash
pm2 delete rca-config-syncer
```

## Mongo-Backed Config Sync

MongoDB is the source of truth for rules and topology.

Configured database:

```text
dhusnic_test_db
```

Collections:

- `correlation_rules`: all rules, enabled and disabled.
- `topology_data`: topology documents.
- `rca_config_state`: one lightweight revision document.
- `rca_config_snapshots`: prepared rules/topology snapshots.
- `rca_results`: optional Mongo copy of RCA result history/imports.

The engines still consume local JSON at runtime:

```text
log_correlation_engine/rules/rules.json
log_rca_engine/data/topology.json
log_rca_engine/data/results/rca_results.json
```

Only enabled rules are written to `rules.json`. Only enabled topologies referenced by enabled rules are written to `topology.json`.

## Revision Flow

The sync decision is controlled by this Mongo document:

```js
db.rca_config_state.findOne({ name: "prod_rules_topology" })
```

Example:

```json
{
  "name": "prod_rules_topology",
  "revision": 18,
  "updated_at": "2026-04-22T00:00:00Z"
}
```

The number `18` is only a config version. It does not affect scoring, confidence, priority, or topology weights.

Every engine cycle checks this small revision document first:

- If the revision is unchanged, full Mongo sync is skipped.
- If the revision changed, config is refreshed from snapshot or source collections.
- After refresh, local JSON is updated atomically only when content changed.

Any rule/topology add, update, disable, or delete must bump the revision:

```bash
./scripts/bump_rca_config_revision.sh
```

## Snapshot Flow

`log-config-syncer` can build a prepared snapshot in `rca_config_snapshots`:

```json
{
  "name": "prod_rules_topology",
  "revision": 18,
  "rules": [],
  "topology": {}
}
```

When a snapshot exists for the current revision, engines can load that single snapshot instead of querying and assembling all rule/topology documents.

Current config keys:

```yaml
mongo_sync:
  enabled: true
  database: dhusnic_test_db
  rules_collection: correlation_rules
  topology_collection: topology_data
  state_collection: rca_config_state
  state_name: prod_rules_topology
  snapshot_collection: rca_config_snapshots
  snapshot_name: prod_rules_topology
  use_snapshot: true
  write_snapshot: true
```

For the lowest production load, let `log-config-syncer` own Mongo-to-JSON/snapshot writes. The engines can then run from JSON and reload when files change.

## Redis Notifications

Redis pub/sub config-change notifications are supported but disabled by default.

When enabled, publish to:

```text
rca_config_changed
```

After a config change:

```bash
PUBLISH_REDIS=1 ./scripts/bump_rca_config_revision.sh
```

Without Redis notification, the next scheduled cycle still detects the revision change by polling Mongo.

## Mongo Indexes

Create production indexes before load testing:

```bash
./scripts/create_rca_config_indexes.sh
```

Indexes created:

```js
db.correlation_rules.createIndex({ is_enabled: 1, priority: 1, id: 1 })
db.correlation_rules.createIndex({ id: 1 }, { unique: true, sparse: true })
db.topology_data.createIndex({ is_enabled: 1, topology_id: 1, organization_id: 1 })
db.topology_data.createIndex({ organization_id: 1, topology_id: 1 }, { unique: true, sparse: true })
db.rca_config_state.createIndex({ name: 1 }, { unique: true })
db.rca_config_snapshots.createIndex({ name: 1, revision: -1 })
```

## RCA Results

`rca_results.json` is a lifecycle result store.

It keeps every RCA record once created:

- `open`
- `updated`
- `closed`

When a close event arrives for an existing incident, the RCA engine updates that same record to `status: "closed"` instead of deleting it.

MongoDB `rca_results` is also durable history. The import script upserts RCA result documents and never deletes existing MongoDB result documents.

Import local RCA files into MongoDB:

```bash
mongosh "$MONGO_URI" scripts/import_rca_files_to_mongo.js
```

Rules/topology are replace-synced by this import script. RCA results are append/upsert-only.

## Production Change Procedure

1. Edit or import rules/topology in MongoDB.
2. Keep disabled rules with `is_enabled: false`.
3. Run:

```bash
./scripts/bump_rca_config_revision.sh
```

4. `log-config-syncer` sees the revision change.
5. It writes updated `rules.json` and `topology.json`.
6. Correlation/RCA engines reload changed JSON and continue processing.

## Validation Commands

Run Go tests:

```bash
cd log_correlation_engine && go test ./...
cd ../log_rca_engine && go test ./...
```

Build the RCA engine and config syncer:

```bash
cd log_rca_engine
go build ./cmd ./cmd/log-config-syncer
```

Build all direct-stream services on Oracle Linux:

```bash
./rebuild_all.sh --profile direct-stream --run-tests
```
