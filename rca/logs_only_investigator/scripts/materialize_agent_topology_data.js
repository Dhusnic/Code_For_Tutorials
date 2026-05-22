const databaseName = "dhusnic_test_db";
const sourceCollectionName = "topology_data";
const targetCollectionName = "agent_topology_data";

const database = db.getSiblingDB(databaseName);
const source = database.getCollection(sourceCollectionName);
const target = database.getCollection(targetCollectionName);

function inferDomain(serviceName, role) {
  const service = String(serviceName || "").trim().toLowerCase();
  const roleValue = String(role || "").trim().toLowerCase();
  const roleDomainMap = {
    upstream: "gateway",
    gateway: "gateway",
    proxy: "gateway",
    application: "application",
    database: "database",
    cache: "database",
    messaging: "messaging",
    streaming: "messaging",
    system: "system",
    network: "network",
  };
  if (roleDomainMap[roleValue]) return roleDomainMap[roleValue];
  if (["nginx", "haproxy", "envoy"].includes(service)) return "gateway";
  if (["mongodb", "postgres", "postgresql", "mysql", "mariadb", "oracle", "redis"].includes(service)) return "database";
  if (["rabbitmq", "kafka", "activemq"].includes(service)) return "messaging";
  if (["system", "linux", "os"].includes(service)) return "system";
  if (["network", "router", "switch", "firewall"].includes(service)) return "network";
  return "application";
}

function inferTier(domain) {
  const map = {
    gateway: "edge",
    application: "app",
    database: "data",
    messaging: "data",
    system: "infra",
    network: "infra",
  };
  return map[String(domain || "").trim().toLowerCase()] || "app";
}

function defaultTags(domain) {
  const map = {
    gateway: ["gateway", "entrypoint"],
    application: ["application"],
    database: ["database", "stateful"],
    messaging: ["messaging"],
    system: ["system", "infra"],
    network: ["network", "infra"],
  };
  return new Set(map[String(domain || "").trim().toLowerCase()] || [String(domain || "").trim().toLowerCase()]);
}

function ensureNode(nodes, service, ip, host, domain) {
  if (!service || !ip) return null;
  const nodeId = `${ip}::${service}`;
  if (!nodes[nodeId]) {
    const normalizedDomain = domain || "application";
    nodes[nodeId] = {
      node_id: nodeId,
      node_type: "service",
      service_name: service,
      service_aliases: new Set([service]),
      device_ip: ip,
      ip_aliases: new Set([ip]),
      host_name: host || "",
      host_aliases: new Set(host ? [host] : []),
      domain: normalizedDomain,
      vendor: null,
      platform: service,
      tier: inferTier(normalizedDomain),
      role: null,
      cluster_id: null,
      replica_set: null,
      is_entrypoint: normalizedDomain === "gateway",
      criticality: "medium",
      match_fields: new Set(["event.module", "host.name", "host.ip", "service.name"]),
      tags: defaultTags(normalizedDomain),
    };
  } else {
    if (host && !nodes[nodeId].host_name) nodes[nodeId].host_name = host;
    if (domain && (!nodes[nodeId].domain || nodes[nodeId].domain === "application")) {
      nodes[nodeId].domain = domain;
      nodes[nodeId].tier = inferTier(domain);
    }
    if (host) nodes[nodeId].host_aliases.add(host);
  }
  return nodes[nodeId];
}

function ensureNodeFromReference(nodes, reference, hostByIp) {
  if (!reference || reference.indexOf("::") === -1) return null;
  const [ipRaw, serviceRaw] = reference.split("::", 2);
  const ip = String(ipRaw || "").trim();
  const service = String(serviceRaw || "").trim();
  if (!ip || !service) return null;
  return ensureNode(nodes, service, ip, hostByIp[ip] || "", inferDomain(service, ""));
}

function normalizeRelationType(relation) {
  const normalized = String(relation || "").trim().toLowerCase();
  if (["underlay", "infra", "infrastructure", "depends_on_host", "depends_on_network", "hosted_on", "routes_through"].includes(normalized)) {
    return "underlay";
  }
  return "depends_on";
}

function addEdge(edges, fromNode, toNode, relationType, relationLabel, sourceRef) {
  if (!fromNode || !toNode || fromNode.node_id === toNode.node_id) return;
  const key = `${fromNode.node_id}|${relationType}|${toNode.node_id}`;
  if (!edges[key]) {
    edges[key] = {
      edge_id: `${fromNode.node_id}->${toNode.node_id}::${relationType}`,
      from_node_id: fromNode.node_id,
      to_node_id: toNode.node_id,
      relation_type: relationType,
      relation_label: relationLabel || relationType,
      weight: 1.0,
      criticality: "medium",
      source_refs: new Set(),
    };
  }
  edges[key].source_refs.add(sourceRef);
}

function serializeNode(node) {
  return {
    node_id: node.node_id,
    node_type: node.node_type,
    service_name: node.service_name,
    service_aliases: Array.from(node.service_aliases).sort(),
    device_ip: node.device_ip,
    ip_aliases: Array.from(node.ip_aliases).sort(),
    host_name: node.host_name,
    host_aliases: Array.from(node.host_aliases).sort(),
    domain: node.domain || "application",
    vendor: node.vendor,
    platform: node.platform || node.service_name,
    tier: node.tier || inferTier(node.domain || "application"),
    role: node.role,
    cluster_id: node.cluster_id,
    replica_set: node.replica_set,
    is_entrypoint: Boolean(node.is_entrypoint),
    criticality: node.criticality || "medium",
    match_fields: Array.from(node.match_fields).sort(),
    tags: Array.from(node.tags).sort(),
  };
}

function serializeEdge(edge) {
  return {
    edge_id: edge.edge_id,
    from_node_id: edge.from_node_id,
    to_node_id: edge.to_node_id,
    relation_type: edge.relation_type,
    relation_label: edge.relation_label || edge.relation_type,
    weight: edge.weight,
    criticality: edge.criticality,
    source_refs: Array.from(edge.source_refs).sort(),
  };
}

function sanitizeIdentifier(value) {
  return String(value || "")
    .split("")
    .map((char) => (/^[a-zA-Z0-9_-]$/.test(char) ? char : "_"))
    .join("")
    .replace(/^_+|_+$/g, "") || "version";
}

function normalizeTime(value) {
  if (!value) return null;
  try {
    return new Date(value).toISOString();
  } catch {
    return null;
  }
}

function inferEnvironment(sourceKind, topologyId) {
  const values = `${sourceKind || ""} ${topologyId || ""}`.toLowerCase();
  if (values.includes("prod") || values.includes("production")) return "prod";
  if (values.includes("stage") || values.includes("staging")) return "staging";
  if (values.includes("dev")) return "dev";
  if (values.includes("lab") || values.includes("test")) return "lab";
  return "unknown";
}

function buildVersionId(document, topologyId, validFrom) {
  const sourceId = String(document._id || "").trim();
  if (sourceId) return sanitizeIdentifier(sourceId);
  if (validFrom) return sanitizeIdentifier(`${topologyId}-${validFrom}`);
  return sanitizeIdentifier(topologyId || "topology");
}

function buildPayload(document) {
  const organizationId = String(document.organization_id || "").trim();
  const topologyId = String(document.topology_id || document._id || "").trim();
  const topology = (document.topology && typeof document.topology === "object") ? document.topology : document;
  const devices = Array.isArray(topology.devices) ? topology.devices : [];
  const services = Array.isArray(topology.services) ? topology.services : [];
  const dependencies = Array.isArray(topology.dependencies) ? topology.dependencies : [];
  const serviceRelations = Array.isArray(topology.service_relations) ? topology.service_relations : [];
  const nodes = {};
  const edges = {};

  const hostByIp = {};
  devices.forEach((device) => {
    const ip = String(device.device_ip || "").trim();
    const host = String(device.host_name || "").trim();
    if (ip) hostByIp[ip] = host;
  });
  const roleByNode = {};

  services.forEach((service) => {
    const serviceName = String(service.service_name || "").trim();
    const deviceIp = String(service.device_ip || "").trim();
    if (!serviceName || !deviceIp) return;
    ensureNode(nodes, serviceName, deviceIp, hostByIp[deviceIp] || "", inferDomain(serviceName, ""));
  });

  devices.forEach((device) => {
    const deviceIp = String(device.device_ip || "").trim();
    const hostName = String(device.host_name || "").trim();
    const deviceServices = Array.isArray(device.services) ? device.services : [];
    deviceServices.forEach((service) => {
      const serviceName = String(service.service_name || "").trim();
      const role = String(service.role || "").trim();
      if (!serviceName || !deviceIp) return;
      const node = ensureNode(nodes, serviceName, deviceIp, hostName, inferDomain(serviceName, role));
      if (role) {
        roleByNode[node.node_id] = role;
        node.role = role;
      }
      if (hostName) {
        node.host_aliases.add(hostName);
        node.host_aliases.add(`${hostName}::${serviceName}`);
      }
      node.service_aliases.add(serviceName);
      node.ip_aliases.add(deviceIp);
      node.tags = defaultTags(node.domain);

      (Array.isArray(service.depends_on) ? service.depends_on : []).forEach((targetServiceRaw) => {
        const targetService = String(targetServiceRaw || "").trim();
        if (!targetService) return;
        const target = ensureNode(nodes, targetService, deviceIp, hostName, inferDomain(targetService, ""));
        addEdge(edges, node, target, "depends_on", "service.depends_on", `device.services[${serviceName}].depends_on[${targetService}]`);
      });

      (Array.isArray(service.upstream_for) ? service.upstream_for : []).forEach((targetServiceRaw) => {
        const targetService = String(targetServiceRaw || "").trim();
        if (!targetService) return;
        const target = ensureNode(nodes, targetService, deviceIp, hostName, inferDomain(targetService, ""));
        addEdge(edges, target, node, "depends_on", "service.upstream_for", `device.services[${serviceName}].upstream_for[${targetService}]`);
      });
    });
  });

  dependencies.forEach((dependency) => {
    const fromNode = ensureNodeFromReference(nodes, dependency.from, hostByIp);
    const toNode = ensureNodeFromReference(nodes, dependency.to, hostByIp);
    if (!fromNode || !toNode) return;
    const relationType = normalizeRelationType(dependency.relation);
    addEdge(edges, fromNode, toNode, relationType, String(dependency.relation || relationType).trim(), `dependencies[${fromNode.node_id}->${toNode.node_id}]`);
  });

  serviceRelations.forEach((relation) => {
    const fromService = String(relation.from_service || "").trim();
    const toService = String(relation.to_service || "").trim();
    const fromIp = String(relation.from_ip || "").trim();
    const toIp = String(relation.to_ip || "").trim();
    if (!fromService || !toService || !fromIp || !toIp) return;
    const fromNode = ensureNode(nodes, fromService, fromIp, hostByIp[fromIp] || "", inferDomain(fromService, roleByNode[`${fromIp}::${fromService}`] || ""));
    const toNode = ensureNode(nodes, toService, toIp, hostByIp[toIp] || "", inferDomain(toService, roleByNode[`${toIp}::${toService}`] || ""));
    const relationType = normalizeRelationType(relation.relation);
    addEdge(edges, fromNode, toNode, relationType, String(relation.relation || relationType).trim(), `service_relations[${fromService}->${toService}]`);
  });

  const serializedNodes = Object.values(nodes).sort((left, right) => left.node_id.localeCompare(right.node_id)).map(serializeNode);
  const serializedEdges = Object.values(edges)
    .sort((left, right) => `${left.from_node_id}|${left.relation_type}|${left.to_node_id}`.localeCompare(`${right.from_node_id}|${right.relation_type}|${right.to_node_id}`))
    .map(serializeEdge);

  const generatedAt = new Date().toISOString();
  const validFrom = normalizeTime(document.generated_at || document.updated_at || document.created_at || document.valid_from) || generatedAt;
  const validTo = normalizeTime(document.valid_to);
  const sourceKind = String(document.source_kind || "").trim();
  const versionId = buildVersionId(document, topologyId, validFrom);
  const isCurrent = Boolean(document.is_enabled) || sourceKind.toLowerCase() === "current";

  return {
    _id: `${organizationId}::${topologyId}::${versionId}`,
    organization_id: organizationId,
    topology_id: topologyId,
    topology_name: String(document.topology_name || topologyId).trim(),
    environment: String(document.environment || inferEnvironment(sourceKind, topologyId)).trim(),
    is_enabled: Boolean(document.is_enabled),
    source_kind: sourceKind,
    source_file_name: String(document.source_file_name || "").trim(),
    schema_version: 2,
    generated_at: generatedAt,
    source_collection: sourceCollectionName,
    version: {
      version_id: versionId,
      generated_at: generatedAt,
      valid_from: validFrom,
      valid_to: validTo,
      is_current: isCurrent,
      source_document_id: String(document._id || "").trim() || null,
      source_schema_version: document.schema_version || null,
    },
    sources: [
      {
        kind: sourceKind || "unknown",
        collection: sourceCollectionName,
        document_id: String(document._id || "").trim() || null,
        file_name: String(document.source_file_name || "").trim() || null,
        ingested_at: generatedAt,
      },
    ],
    incident_time_lookup: {
      valid_from: validFrom,
      valid_to: validTo,
      is_current: isCurrent,
      selection_mode: "version_window",
    },
    nodes: serializedNodes,
    edges: serializedEdges,
  };
}

target.drop();
let upserts = 0;
source.find({}).forEach((document) => {
  const organizationId = String(document.organization_id || "").trim();
  const topologyId = String(document.topology_id || document._id || "").trim();
  if (!organizationId || !topologyId) return;
  const payload = buildPayload(document);
  if (!payload.nodes.length) return;
  target.replaceOne({ _id: payload._id }, payload, { upsert: true });
  upserts += 1;
});

print(`Materialized ${upserts} versioned topology documents into ${databaseName}.${targetCollectionName}`);
