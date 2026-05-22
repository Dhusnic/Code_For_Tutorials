from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


UTC = timezone.utc


@dataclass
class MutableNode:
    node_id: str
    service_name: str
    device_ip: str
    host_name: str
    domain: str
    node_type: str = "service"
    vendor: str | None = None
    platform: str | None = None
    tier: str | None = None
    role: str | None = None
    cluster_id: str | None = None
    replica_set: str | None = None
    is_entrypoint: bool = False
    criticality: str = "medium"
    service_aliases: set[str] = field(default_factory=set)
    ip_aliases: set[str] = field(default_factory=set)
    host_aliases: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    match_fields: set[str] = field(default_factory=lambda: {"event.module", "host.name", "host.ip", "service.name"})


@dataclass
class MutableEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation_type: str
    relation_label: str
    weight: float = 1.0
    criticality: str = "medium"
    source_refs: set[str] = field(default_factory=set)


def build_agent_topology_documents(source_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for source_document in source_documents:
        payload = _build_agent_topology_document(source_document)
        if payload["nodes"]:
            payloads.append(payload)
    return payloads


def _build_agent_topology_document(source_document: dict[str, Any]) -> dict[str, Any]:
    organization_id = str(source_document.get("organization_id", "")).strip()
    topology_id = str(source_document.get("topology_id") or source_document.get("_id") or "").strip()
    topology = _extract_topology_section(source_document)
    devices = topology.get("devices", []) if isinstance(topology.get("devices"), list) else []
    services = topology.get("services", []) if isinstance(topology.get("services"), list) else []
    dependencies = topology.get("dependencies", []) if isinstance(topology.get("dependencies"), list) else []
    service_relations = topology.get("service_relations", []) if isinstance(topology.get("service_relations"), list) else []

    nodes: dict[str, MutableNode] = {}
    edges: dict[tuple[str, str, str], MutableEdge] = {}
    host_by_ip = {
        str(device.get("device_ip", "")).strip(): str(device.get("host_name", "")).strip()
        for device in devices
        if isinstance(device, dict) and str(device.get("device_ip", "")).strip()
    }
    role_by_node: dict[str, str] = {}

    for service in services:
        if not isinstance(service, dict):
            continue
        service_name = str(service.get("service_name", "")).strip()
        device_ip = str(service.get("device_ip", "")).strip()
        if not service_name or not device_ip:
            continue
        node = _ensure_node(
            nodes,
            service=service_name,
            ip=device_ip,
            host=host_by_ip.get(device_ip, ""),
            domain=_infer_domain(service_name=service_name),
        )
        node.service_aliases.update({service_name})
        node.ip_aliases.add(device_ip)

    for device in devices:
        if not isinstance(device, dict):
            continue
        device_ip = str(device.get("device_ip", "")).strip()
        host_name = str(device.get("host_name", "")).strip()
        for service in device.get("services", []) or []:
            if not isinstance(service, dict):
                continue
            service_name = str(service.get("service_name", "")).strip()
            role = str(service.get("role", "")).strip()
            if not service_name or not device_ip:
                continue
            node = _ensure_node(
                nodes,
                service=service_name,
                ip=device_ip,
                host=host_name,
                domain=_infer_domain(service_name=service_name, role=role),
            )
            if role:
                role_by_node[node.node_id] = role
                node.role = role
            if host_name:
                node.host_aliases.add(host_name)
                node.host_aliases.add(f"{host_name}::{service_name}")
            node.service_aliases.add(service_name)
            node.ip_aliases.add(device_ip)
            node.platform = node.platform or service_name
            node.tier = node.tier or _infer_tier(node.domain)
            node.is_entrypoint = node.is_entrypoint or node.domain == "gateway"
            node.tags.update(_default_tags(node.domain))

            for target_service in service.get("depends_on", []) or []:
                target_name = str(target_service).strip()
                if not target_name:
                    continue
                target = _ensure_node(
                    nodes,
                    service=target_name,
                    ip=device_ip,
                    host=host_name,
                    domain=_infer_domain(service_name=target_name),
                )
                _add_edge(
                    edges,
                    from_node=node,
                    to_node=target,
                    relation_type="depends_on",
                    relation_label="service.depends_on",
                    source_ref=f"device.services[{service_name}].depends_on[{target_name}]",
                )

            for target_service in service.get("upstream_for", []) or []:
                target_name = str(target_service).strip()
                if not target_name:
                    continue
                target = _ensure_node(
                    nodes,
                    service=target_name,
                    ip=device_ip,
                    host=host_name,
                    domain=_infer_domain(service_name=target_name),
                )
                _add_edge(
                    edges,
                    from_node=target,
                    to_node=node,
                    relation_type="depends_on",
                    relation_label="service.upstream_for",
                    source_ref=f"device.services[{service_name}].upstream_for[{target_name}]",
                )

    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        from_node = _ensure_node_from_reference(nodes, str(dependency.get("from", "")).strip(), host_by_ip)
        to_node = _ensure_node_from_reference(nodes, str(dependency.get("to", "")).strip(), host_by_ip)
        if not from_node or not to_node:
            continue
        relation_type = _normalize_relation_type(str(dependency.get("relation", "")).strip())
        _add_edge(
            edges,
            from_node=from_node,
            to_node=to_node,
            relation_type=relation_type,
            relation_label=str(dependency.get("relation", "")).strip() or relation_type,
            source_ref=f"dependencies[{from_node.node_id}->{to_node.node_id}]",
        )

    for relation in service_relations:
        if not isinstance(relation, dict):
            continue
        from_service = str(relation.get("from_service", "")).strip()
        to_service = str(relation.get("to_service", "")).strip()
        from_ip = str(relation.get("from_ip", "")).strip()
        to_ip = str(relation.get("to_ip", "")).strip()
        if not from_service or not to_service or not from_ip or not to_ip:
            continue
        from_node = _ensure_node(
            nodes,
            service=from_service,
            ip=from_ip,
            host=host_by_ip.get(from_ip, ""),
            domain=_infer_domain(service_name=from_service, role=role_by_node.get(f"{from_ip}::{from_service}")),
        )
        to_node = _ensure_node(
            nodes,
            service=to_service,
            ip=to_ip,
            host=host_by_ip.get(to_ip, ""),
            domain=_infer_domain(service_name=to_service, role=role_by_node.get(f"{to_ip}::{to_service}")),
        )
        relation_type = _normalize_relation_type(str(relation.get("relation", "")).strip())
        _add_edge(
            edges,
            from_node=from_node,
            to_node=to_node,
            relation_type=relation_type,
            relation_label=str(relation.get("relation", "")).strip() or relation_type,
            source_ref=f"service_relations[{from_service}->{to_service}]",
        )

    serialized_nodes = [_serialize_node(node) for node in sorted(nodes.values(), key=lambda item: item.node_id)]
    serialized_edges = [_serialize_edge(edge) for edge in sorted(edges.values(), key=lambda item: (item.from_node_id, item.relation_type, item.to_node_id))]

    generated_at = _utc_now()
    valid_from = _document_effective_time(source_document) or generated_at
    source_kind = str(source_document.get("source_kind", "")).strip()
    version_id = _build_version_id(source_document, topology_id, valid_from)

    return {
        "_id": f"{organization_id}::{topology_id}::{version_id}" if organization_id and topology_id else "",
        "organization_id": organization_id,
        "topology_id": topology_id,
        "topology_name": str(source_document.get("topology_name") or topology_id).strip(),
        "environment": str(source_document.get("environment") or _infer_environment(source_kind, topology_id)).strip(),
        "is_enabled": bool(source_document.get("is_enabled", False)),
        "source_kind": source_kind,
        "source_file_name": str(source_document.get("source_file_name", "")).strip(),
        "schema_version": 2,
        "generated_at": generated_at,
        "source_collection": "topology_data",
        "version": {
            "version_id": version_id,
            "generated_at": generated_at,
            "valid_from": valid_from,
            "valid_to": _optional_time(source_document.get("valid_to")),
            "is_current": bool(source_document.get("is_enabled", False) or source_kind.lower() == "current"),
            "source_document_id": str(source_document.get("_id", "")).strip() or None,
            "source_schema_version": source_document.get("schema_version"),
        },
        "sources": [
            {
                "kind": source_kind or "unknown",
                "collection": "topology_data",
                "document_id": str(source_document.get("_id", "")).strip() or None,
                "file_name": str(source_document.get("source_file_name", "")).strip() or None,
                "ingested_at": generated_at,
            }
        ],
        "incident_time_lookup": {
            "valid_from": valid_from,
            "valid_to": _optional_time(source_document.get("valid_to")),
            "is_current": bool(source_document.get("is_enabled", False) or source_kind.lower() == "current"),
            "selection_mode": "version_window",
        },
        "nodes": serialized_nodes,
        "edges": serialized_edges,
    }


def _extract_topology_section(document: dict[str, Any]) -> dict[str, Any]:
    topology = document.get("topology")
    if isinstance(topology, dict):
        return topology
    return document


def _ensure_node(
    nodes: dict[str, MutableNode],
    *,
    service: str,
    ip: str,
    host: str,
    domain: str,
) -> MutableNode:
    node_id = f"{ip}::{service}"
    existing = nodes.get(node_id)
    if existing:
        if host and not existing.host_name:
            existing.host_name = host
        if domain and (not existing.domain or existing.domain == "application"):
            existing.domain = domain
        existing.platform = existing.platform or service
        existing.tier = existing.tier or _infer_tier(existing.domain)
        existing.tags.update(_default_tags(existing.domain))
        return existing

    node = MutableNode(
        node_id=node_id,
        service_name=service,
        device_ip=ip,
        host_name=host,
        domain=domain or "application",
        platform=service,
        tier=_infer_tier(domain or "application"),
        is_entrypoint=(domain == "gateway"),
    )
    node.service_aliases.add(service)
    node.ip_aliases.add(ip)
    if host:
        node.host_aliases.add(host)
    node.tags.update(_default_tags(node.domain))
    nodes[node_id] = node
    return node


def _ensure_node_from_reference(
    nodes: dict[str, MutableNode],
    reference: str,
    host_by_ip: dict[str, str],
) -> MutableNode | None:
    if "::" not in reference:
        return None
    ip, service = reference.split("::", 1)
    ip = ip.strip()
    service = service.strip()
    if not ip or not service:
        return None
    return _ensure_node(
        nodes,
        service=service,
        ip=ip,
        host=host_by_ip.get(ip, ""),
        domain=_infer_domain(service_name=service),
    )


def _add_edge(
    edges: dict[tuple[str, str, str], MutableEdge],
    *,
    from_node: MutableNode,
    to_node: MutableNode,
    relation_type: str,
    relation_label: str,
    source_ref: str,
) -> None:
    if from_node.node_id == to_node.node_id:
        return
    key = (from_node.node_id, to_node.node_id, relation_type)
    edge = edges.get(key)
    if edge is None:
        edge = MutableEdge(
            edge_id=f"{from_node.node_id}->{to_node.node_id}::{relation_type}",
            from_node_id=from_node.node_id,
            to_node_id=to_node.node_id,
            relation_type=relation_type,
            relation_label=relation_label or relation_type,
        )
        edges[key] = edge
    edge.source_refs.add(source_ref)


def _serialize_node(node: MutableNode) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "service_name": node.service_name,
        "service_aliases": sorted(node.service_aliases),
        "device_ip": node.device_ip,
        "ip_aliases": sorted(node.ip_aliases),
        "host_name": node.host_name,
        "host_aliases": sorted(node.host_aliases),
        "domain": node.domain or "application",
        "vendor": node.vendor,
        "platform": node.platform or node.service_name,
        "tier": node.tier or _infer_tier(node.domain or "application"),
        "role": node.role,
        "cluster_id": node.cluster_id,
        "replica_set": node.replica_set,
        "is_entrypoint": node.is_entrypoint,
        "criticality": node.criticality,
        "match_fields": sorted(node.match_fields),
        "tags": sorted(node.tags),
    }


def _serialize_edge(edge: MutableEdge) -> dict[str, Any]:
    return {
        "edge_id": edge.edge_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "relation_type": edge.relation_type,
        "relation_label": edge.relation_label or edge.relation_type,
        "weight": edge.weight,
        "criticality": edge.criticality,
        "source_refs": sorted(edge.source_refs),
    }


def _normalize_relation_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"underlay", "infra", "infrastructure", "depends_on_host", "depends_on_network", "hosted_on", "routes_through"}:
        return "underlay"
    return "depends_on"


def _infer_domain(*, service_name: str, role: str | None = None) -> str:
    service = service_name.strip().lower()
    role_value = (role or "").strip().lower()
    role_domain_map = {
        "upstream": "gateway",
        "gateway": "gateway",
        "proxy": "gateway",
        "application": "application",
        "database": "database",
        "cache": "database",
        "messaging": "messaging",
        "streaming": "messaging",
        "system": "system",
        "network": "network",
    }
    if role_value in role_domain_map:
        return role_domain_map[role_value]
    if service in {"nginx", "haproxy", "envoy"}:
        return "gateway"
    if service in {"mongodb", "postgres", "postgresql", "mysql", "mariadb", "oracle", "redis"}:
        return "database"
    if service in {"rabbitmq", "kafka", "activemq"}:
        return "messaging"
    if service in {"system", "linux", "os"}:
        return "system"
    if service in {"network", "router", "switch", "firewall"}:
        return "network"
    return "application"


def _infer_tier(domain: str) -> str:
    mapping = {
        "gateway": "edge",
        "application": "app",
        "database": "data",
        "messaging": "data",
        "system": "infra",
        "network": "infra",
    }
    return mapping.get(domain.strip().lower(), "app")


def _default_tags(domain: str) -> set[str]:
    mapping = {
        "gateway": {"gateway", "entrypoint"},
        "application": {"application"},
        "database": {"database", "stateful"},
        "messaging": {"messaging"},
        "system": {"system", "infra"},
        "network": {"network", "infra"},
    }
    return set(mapping.get(domain.strip().lower(), {domain.strip().lower()}))


def _infer_environment(source_kind: str, topology_id: str) -> str:
    values = f"{source_kind} {topology_id}".lower()
    if "prod" in values or "production" in values:
        return "prod"
    if "stage" in values or "staging" in values:
        return "staging"
    if "dev" in values:
        return "dev"
    if "lab" in values or "test" in values:
        return "lab"
    return "unknown"


def _document_effective_time(source_document: dict[str, Any]) -> str | None:
    for key in ("generated_at", "updated_at", "created_at", "valid_from"):
        value = source_document.get(key)
        normalized = _optional_time(value)
        if normalized:
            return normalized
    return None


def _build_version_id(source_document: dict[str, Any], topology_id: str, valid_from: str) -> str:
    source_id = str(source_document.get("_id", "")).strip()
    if source_id:
        return _sanitize_identifier(source_id)
    if valid_from:
        return _sanitize_identifier(f"{topology_id}-{valid_from}")
    return _sanitize_identifier(topology_id or "topology")


def _sanitize_identifier(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_") or "version"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if hasattr(value, "isoformat"):
        try:
            iso_value = value.isoformat()
            return str(iso_value).replace("+00:00", "Z")
        except Exception:
            return None
    text = str(value).strip()
    return text or None
