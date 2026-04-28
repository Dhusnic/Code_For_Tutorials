// Load generated load-test correlation rules into MongoDB, refresh the active
// snapshot, and bump the correlation config revision.
//
// Usage:
//   mongosh "$MONGO_URI" scripts/import_load_test_rules_to_mongo.js
//
// Optional environment:
//   RCA_MONGO_DB=dhusnic_test_db
//   RCA_RULES_COLLECTION=correlation_rules
//   RCA_STATE_COLLECTION=rca_config_state
//   RCA_STATE_NAME=prod_rules_topology
//   RCA_SNAPSHOT_COLLECTION=rca_config_snapshots
//   RCA_SNAPSHOT_NAME=prod_rules_topology
//   RCA_RULES_FILE=dist/load_test_rules/correlation_rules.load-test.json

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
const TARGET_DB = process.env.RCA_MONGO_DB || "dhusnic_test_db";
const RULES_COLLECTION = process.env.RCA_RULES_COLLECTION || "correlation_rules";
const STATE_COLLECTION = process.env.RCA_STATE_COLLECTION || "rca_config_state";
const STATE_NAME = process.env.RCA_STATE_NAME || "prod_rules_topology";
const SNAPSHOT_COLLECTION = process.env.RCA_SNAPSHOT_COLLECTION || "rca_config_snapshots";
const SNAPSHOT_NAME = process.env.RCA_SNAPSHOT_NAME || "prod_rules_topology";
const RULES_FILE = path.resolve(
  process.env.RCA_RULES_FILE || path.join(REPO_ROOT, "dist", "load_test_rules", "correlation_rules.load-test.json"),
);
const MANAGED_BY = "scripts/import_load_test_rules_to_mongo.js";

function readLoadTestRules(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`load-test rules file not found: ${filePath}`);
  }

  const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!Array.isArray(payload)) {
    throw new Error(`load-test rules file must contain a JSON array: ${filePath}`);
  }
  if (payload.length === 0) {
    throw new Error(`load-test rules file is empty: ${filePath}`);
  }

  for (const [index, rule] of payload.entries()) {
    if (!rule || typeof rule !== "object") {
      throw new Error(`rule at index ${index} is not an object`);
    }
    if (!String(rule.id || "").trim()) {
      throw new Error(`rule at index ${index} is missing id`);
    }
    if (rule.load_test !== true) {
      throw new Error(`rule ${rule.id} must include load_test: true`);
    }
  }

  return payload;
}

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
  const importedAt = new Date();
  const loadTestRules = readLoadTestRules(RULES_FILE);

  let upserted = 0;
  for (const rule of loadTestRules) {
    const filter = { id: rule.id };
    const update = {
      $set: {
        ...rule,
        is_enabled: true,
        managed_by: MANAGED_BY,
        managed_at: importedAt,
      },
      $setOnInsert: {
        created_at: importedAt,
      },
    };
    const result = rulesCollection.updateOne(filter, update, { upsert: true });
    upserted += result.upsertedCount + result.matchedCount;
  }

  const enabledRules = rebuildSnapshot(database);
  const state = stateCollection.findOneAndUpdate(
    { name: STATE_NAME },
    {
      $inc: { revision: 1 },
      $set: {
        name: STATE_NAME,
        updated_at: importedAt,
      },
      $setOnInsert: {
        created_at: importedAt,
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
        updated_at: importedAt,
        rules: enabledRules,
        managed_by: MANAGED_BY,
      },
      $setOnInsert: {
        created_at: importedAt,
      },
    },
    { upsert: true },
  );

  print(JSON.stringify({
    database: TARGET_DB,
    rules_file: path.relative(REPO_ROOT, RULES_FILE).replace(/\\/g, "/"),
    load_test_rules_processed: loadTestRules.length,
    upsert_operations: upserted,
    enabled_rules_in_snapshot: enabledRules.length,
    revision: state.revision,
    snapshot_name: SNAPSHOT_NAME,
  }, null, 2));
}

main();
