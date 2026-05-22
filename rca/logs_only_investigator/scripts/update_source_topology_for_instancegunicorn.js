const databaseName = "dhusnic_test_db";
const collectionName = "topology_data";
const sourceId = "current::topology.json::135098068173316952064::infraon_onprem_prod";

const dbx = db.getSiblingDB(databaseName);
const collection = dbx.getCollection(collectionName);
const doc = collection.findOne({ _id: sourceId });
if (!doc) {
  throw new Error(`source topology document not found: ${sourceId}`);
}

const topology = doc.topology || {};
topology.dependencies = [
  { from: "10.0.4.72::nginx", to: "10.0.4.72::instancegunicorn", relation: "upstream" },
  { from: "10.0.4.72::instancegunicorn", to: "10.0.4.72::mongodb", relation: "depends_on" },
  { from: "10.0.4.72::instancegunicorn", to: "10.0.4.72::rabbitmq", relation: "depends_on" },
  { from: "10.0.4.72::instancegunicorn", to: "10.0.4.72::redis", relation: "depends_on" },
  { from: "10.0.4.72::instancegunicorn", to: "10.0.4.72::kafka", relation: "depends_on" },
  { from: "10.0.4.72::instancegunicorn", to: "10.0.4.72::postgresql", relation: "depends_on" },
];

topology.services = Array.isArray(topology.services) ? topology.services : [];
if (!topology.services.some((item) => item && item.service_name === "network" && item.device_ip === "10.0.4.72")) {
  topology.services.push({ service_name: "network", device_ip: "10.0.4.72" });
}

topology.devices = Array.isArray(topology.devices) ? topology.devices : [];
if (!topology.devices.length) {
  topology.devices.push({
    device_ip: "10.0.4.72",
    host_name: "localhost.localdomain",
    services: [],
  });
}

const device =
  topology.devices.find((item) => item && String(item.device_ip || "").trim() === "10.0.4.72") ||
  topology.devices[0];
device.services = Array.isArray(device.services) ? device.services : [];

function ensureService(name, role) {
  let service = device.services.find((item) => item && item.service_name === name);
  if (!service) {
    service = { service_name: name };
    device.services.push(service);
  }
  if (role && !service.role) {
    service.role = role;
  }
  return service;
}

ensureService("network", "network");

const dependencyMap = new Map([
  ["nginx", ["instancegunicorn"]],
  ["mongodb", []],
  ["rabbitmq", []],
  ["redis", []],
  ["kafka", []],
  ["postgresql", []],
  ["instancegunicorn", ["mongodb", "rabbitmq", "redis", "kafka", "postgresql"]],
  ["auth", []],
  ["system", []],
  ["network", []],
]);

for (const service of device.services) {
  const name = String(service.service_name || "").trim();
  if (!name) {
    continue;
  }
  if (dependencyMap.has(name)) {
    service.depends_on = dependencyMap.get(name);
  }
  delete service.upstream_for;
}

collection.updateOne(
  { _id: sourceId },
  {
    $set: {
      topology,
    },
  }
);

printjson({
  updated: sourceId,
  dependency_count: topology.dependencies.length,
  services: device.services.map((service) => ({
    service_name: service.service_name,
    role: service.role,
    depends_on: service.depends_on || [],
  })),
});
