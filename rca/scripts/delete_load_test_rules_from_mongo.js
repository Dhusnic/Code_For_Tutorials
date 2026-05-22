// Delete correlation rules tagged with load_test: true from MongoDB, refresh
// the active snapshot, bump the correlation config revision, and mark the config as pending sync.
//
// Usage:
//   mongosh "$MONGO_URI" scripts/delete_load_test_rules_from_mongo.js
//
// Optional environment:
//   RCA_MONGO_DB=dhusnic_test_db
//   RCA_RULES_COLLECTION=correlation_rules
//   RCA_STATE_COLLECTION=rca_config_state
//   RCA_STATE_NAME=prod_rules_topology
//   RCA_SNAPSHOT_COLLECTION=rca_config_snapshots
//   RCA_SNAPSHOT_NAME=prod_rules_topology
//   RCA_LOAD_TEST_BATCH=<batch label>

const TARGET_DB = process.env.RCA_MONGO_DB || "dhusnic_test_db";
const RULES_COLLECTION = process.env.RCA_RULES_COLLECTION || "correlation_rules";
const STATE_COLLECTION = process.env.RCA_STATE_COLLECTION || "rca_config_state";
const STATE_NAME = process.env.RCA_STATE_NAME || "prod_rules_topology";
const SNAPSHOT_COLLECTION = process.env.RCA_SNAPSHOT_COLLECTION || "rca_config_snapshots";
const SNAPSHOT_NAME = process.env.RCA_SNAPSHOT_NAME || "prod_rules_topology";
const LOAD_TEST_BATCH = String(process.env.RCA_LOAD_TEST_BATCH || "").trim();
const MANAGED_BY = "scripts/delete_load_test_rules_from_mongo.js";

function rebuildSnapshot(database) {
  const enabledRules = database.getCollection(RULES_COLLECTION)
    .find({ is_enabled: true })
    .sort({ priority: 1, id: 1 })
    .toArray();

  return enabledRules.map((doc) => {
    const clone = { ...doc };
    delete clone._id;
    return clone;
  });
}

function main() {
  const database = db.getSiblingDB(TARGET_DB);
  const rulesCollection = database.getCollection(RULES_COLLECTION);
  const stateCollection = database.getCollection(STATE_COLLECTION);
  const snapshotCollection = database.getCollection(SNAPSHOT_COLLECTION);
  const updatedAt = new Date();
  const filter = { load_test: true };

  if (LOAD_TEST_BATCH) {
    filter.load_test_batch = LOAD_TEST_BATCH;
  }

  const deletion = rulesCollection.deleteMany(filter);
  const enabledRules = rebuildSnapshot(database);
  const state = stateCollection.findOneAndUpdate(
    { name: STATE_NAME },
    {
      $inc: { revision: 1 },
      $set: {
        name: STATE_NAME,
        is_synced: false,
        updated_at: updatedAt,
      },
      $setOnInsert: {
        created_at: updatedAt,
      },
    },
    { upsert: true, returnDocument: "after" },
  );

  snapshotCollection.updateOne(
    { name: SNAPSHOT_NAME },
    {
      $set: {
        name: SNAPSHOT_NAME,
        revision: state.revision,
        updated_at: updatedAt,
        rules: enabledRules,
        managed_by: MANAGED_BY,
      },
      $setOnInsert: {
        created_at: updatedAt,
      },
    },
    { upsert: true },
  );

  print(JSON.stringify({
    database: TARGET_DB,
    deleted_rules: deletion.deletedCount,
    load_test_batch: LOAD_TEST_BATCH || null,
    enabled_rules_in_snapshot: enabledRules.length,
    revision: state.revision,
    is_synced: state.is_synced,
    snapshot_name: SNAPSHOT_NAME,
  }, null, 2));
}

main();
