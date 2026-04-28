// Seed RCA rules, topology, and RCA results from local JSON files into MongoDB.
//
// Rules and topology are replace-synced because MongoDB is their source of truth.
// RCA results are durable history: imports are upsert-only and never delete
// existing result documents from MongoDB.
//
// Usage:
//   mongosh "$MONGO_URI" scripts/import_rca_files_to_mongo.js
//
// Optional environment:
//   RCA_MONGO_DB=dhusnic_test_db
//   RCA_RULES_COLLECTION=correlation_rules
//   RCA_TOPOLOGY_COLLECTION=topology_data
//   RCA_RESULTS_COLLECTION=rca_results

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
const TARGET_DB = process.env.RCA_MONGO_DB || "dhusnic_test_db";
const RULES_COLLECTION = process.env.RCA_RULES_COLLECTION || "correlation_rules";
const TOPOLOGY_COLLECTION = process.env.RCA_TOPOLOGY_COLLECTION || "topology_data";
const RESULTS_COLLECTION = process.env.RCA_RESULTS_COLLECTION || "rca_results";
const MANAGED_BY = "scripts/import_rca_files_to_mongo.js";

function relPath(...parts) {
  return path.join(...parts).replace(/\\/g, "/");
}

function absPath(relativePath) {
  return path.join(REPO_ROOT, relativePath);
}

function listJsonFiles(relativeDir, currentFileName, backupPrefix) {
  const directory = absPath(relativeDir);
  const entries = fs.readdirSync(directory)
    .filter((entry) => entry.toLowerCase().endsWith(".json"))
    .filter((entry) => entry === currentFileName || entry.startsWith(backupPrefix))
    .sort();

  return entries.map((entry) => ({
    relativePath: relPath(relativeDir, entry),
    absolutePath: path.join(directory, entry),
    sourceKind: entry === currentFileName ? "current" : "backup",
  }));
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file.absolutePath, "utf8"));
}

function fileBase(relativePath) {
  return path.basename(relativePath);
}

function sourceIdPrefix(file) {
  return `${file.sourceKind}::${fileBase(file.relativePath)}`;
}

function managedEnvelope(file, importedAt) {
  return {
    managed_by: MANAGED_BY,
    imported_at: importedAt,
    source_kind: file.sourceKind,
    source_file: file.relativePath,
    source_file_name: fileBase(file.relativePath),
  };
}

function collectRules(importedAt) {
  const files = listJsonFiles(
    "log_correlation_engine/rules",
    "rules.json",
    "rules.backup-",
  );
  const docs = [];

  for (const file of files) {
    const rules = readJson(file);
    if (!Array.isArray(rules)) {
      throw new Error(`${file.relativePath} must contain a JSON array`);
    }

    rules.forEach((rule, index) => {
      const ruleID = String(rule.id || `rule_${index + 1}`).trim();
      const isBackup = file.sourceKind !== "current";
      docs.push({
        _id: `${sourceIdPrefix(file)}::${ruleID}`,
        ...managedEnvelope(file, importedAt),
        document_kind: "correlation_rule",
        rule_id: ruleID,
        original_is_enabled: rule.is_enabled !== false,
        is_enabled: isBackup ? false : rule.is_enabled !== false,
        ...rule,
        is_enabled: isBackup ? false : rule.is_enabled !== false,
      });
    });
  }

  return docs;
}

function isTopologyPayload(value) {
  return value && typeof value === "object" && (
    Array.isArray(value.services) ||
    Array.isArray(value.dependencies) ||
    Array.isArray(value.devices) ||
    Array.isArray(value.service_relations)
  );
}

function collectTopologies(importedAt) {
  const files = listJsonFiles(
    "log_rca_engine/data",
    "topology.json",
    "topology.",
  ).concat([
    {
      relativePath: "log_rca_engine/data/topology_bck.json",
      absolutePath: absPath("log_rca_engine/data/topology_bck.json"),
      sourceKind: "backup",
    },
  ]).filter((file, index, all) => (
    fs.existsSync(file.absolutePath) &&
    all.findIndex((candidate) => candidate.relativePath === file.relativePath) === index
  ));

  const docs = [];

  for (const file of files) {
    const payload = readJson(file);
    const organizations = payload.organizations || {};
    const schemaVersion = payload.schema_version || null;

    for (const [organizationID, orgPayload] of Object.entries(organizations)) {
      if (isTopologyPayload(orgPayload)) {
        const topologyID = file.sourceKind === "current" ? "default_topology" : `backup_${fileBase(file.relativePath).replace(/[^A-Za-z0-9]+/g, "_")}`;
        docs.push(topologyDoc(file, importedAt, organizationID, topologyID, schemaVersion, orgPayload));
        continue;
      }

      for (const [topologyID, topologyPayload] of Object.entries(orgPayload || {})) {
        docs.push(topologyDoc(file, importedAt, organizationID, topologyID, schemaVersion, topologyPayload));
      }
    }
  }

  return docs;
}

function topologyDoc(file, importedAt, organizationID, topologyID, schemaVersion, topologyPayload) {
  const isBackup = file.sourceKind !== "current";
  return {
    _id: `${sourceIdPrefix(file)}::${organizationID}::${topologyID}`,
    ...managedEnvelope(file, importedAt),
    document_kind: "topology",
    organization_id: organizationID,
    topology_id: topologyID,
    schema_version: schemaVersion,
    is_enabled: !isBackup,
    topology: topologyPayload,
    services: topologyPayload.services || [],
    dependencies: topologyPayload.dependencies || [],
    devices: topologyPayload.devices || [],
    service_relations: topologyPayload.service_relations || [],
  };
}

function collectRCAResults(importedAt) {
  const file = {
    relativePath: "log_rca_engine/data/results/rca_results.json",
    absolutePath: absPath("log_rca_engine/data/results/rca_results.json"),
    sourceKind: "current",
  };
  if (!fs.existsSync(file.absolutePath)) {
    return [];
  }

  const payload = readJson(file);
  const items = Array.isArray(payload.items) ? payload.items : [];
  return items.map((item, index) => {
    const incidentID = String(item.incident_id || `result_${index + 1}`).trim();
    const resultSignature = String(item.result_signature || item.last_processed_result_signature || "").trim();
    return {
      _id: resultDocumentID(file, incidentID, resultSignature),
      ...managedEnvelope(file, importedAt),
      document_kind: "rca_result",
      ...item,
      incident_id: incidentID,
      result_signature: resultSignature || item.result_signature || null,
      output_updated_at: payload.updated_at || null,
    };
  });
}

function resultDocumentID(file, incidentID, resultSignature) {
  if (resultSignature) {
    return `${sourceIdPrefix(file)}::${incidentID}::${resultSignature}`;
  }
  return `${sourceIdPrefix(file)}::${incidentID}`;
}

function replaceManagedDocuments(collection, docs) {
  collection.deleteMany({ managed_by: MANAGED_BY });
  if (docs.length > 0) {
    collection.insertMany(docs, { ordered: false });
  }
}

function upsertDocuments(collection, docs) {
  if (docs.length === 0) {
    return;
  }

  const operations = docs.map((doc) => {
    const { _id, ...mutableDoc } = doc;
    return {
      updateOne: {
        filter: { _id },
        update: {
          $set: {
            ...mutableDoc,
            last_import_seen_at: doc.imported_at,
          },
          $setOnInsert: {
            first_imported_at: doc.imported_at,
          },
        },
        upsert: true,
      },
    };
  });

  collection.bulkWrite(operations, { ordered: false });
}

function ensureIndexes(database) {
  database.getCollection(RULES_COLLECTION).createIndex({ rule_id: 1, source_kind: 1 });
  database.getCollection(RULES_COLLECTION).createIndex({ is_enabled: 1, priority: 1 });
  database.getCollection(TOPOLOGY_COLLECTION).createIndex({ organization_id: 1, topology_id: 1, source_kind: 1 });
  database.getCollection(TOPOLOGY_COLLECTION).createIndex({ is_enabled: 1 });
  database.getCollection(RESULTS_COLLECTION).createIndex({ incident_id: 1 });
  database.getCollection(RESULTS_COLLECTION).createIndex({ result_signature: 1 });
  database.getCollection(RESULTS_COLLECTION).createIndex({ organization_id: 1, topology_id: 1, rule_id: 1 });
}

function printSummary(database, counts) {
  print("");
  print(`Mongo database: ${database.getName()}`);
  print(`Rules collection: ${RULES_COLLECTION}`);
  print(`Topology collection: ${TOPOLOGY_COLLECTION}`);
  print(`RCA results collection: ${RESULTS_COLLECTION}`);
  print("");
  print(`Imported rules: ${counts.rules}`);
  print(`Imported topologies: ${counts.topologies}`);
  print(`Imported RCA results: ${counts.results}`);
  print("");
  print(`Enabled current rules: ${database.getCollection(RULES_COLLECTION).countDocuments({ source_kind: "current", is_enabled: true })}`);
  print(`Disabled backup rules: ${database.getCollection(RULES_COLLECTION).countDocuments({ source_kind: "backup", is_enabled: false })}`);
  print(`Enabled current topologies: ${database.getCollection(TOPOLOGY_COLLECTION).countDocuments({ source_kind: "current", is_enabled: true })}`);
  print(`Disabled backup topologies: ${database.getCollection(TOPOLOGY_COLLECTION).countDocuments({ source_kind: "backup", is_enabled: false })}`);
}

const importedAt = new Date();
const targetDB = db.getSiblingDB(TARGET_DB);
const rulesDocs = collectRules(importedAt);
const topologyDocs = collectTopologies(importedAt);
const resultDocs = collectRCAResults(importedAt);

replaceManagedDocuments(targetDB.getCollection(RULES_COLLECTION), rulesDocs);
replaceManagedDocuments(targetDB.getCollection(TOPOLOGY_COLLECTION), topologyDocs);
upsertDocuments(targetDB.getCollection(RESULTS_COLLECTION), resultDocs);
ensureIndexes(targetDB);

printSummary(targetDB, {
  rules: rulesDocs.length,
  topologies: topologyDocs.length,
  results: resultDocs.length,
});
