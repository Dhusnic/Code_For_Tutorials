from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import TopologyEdge, TopologyNode


UNDERLAY_RELATIONS = {"underlay", "depends_on_host", "depends_on_network", "hosted_on", "routes_through"}


class TopologyGraph:
    def __init__(self, nodes: dict[str, TopologyNode], edges: tuple[TopologyEdge, ...] = ()) -> None:
        self._nodes = nodes
        self._edges = edges
        self._alias_index: dict[str, str] = {}
        self._upstream_by_node: dict[str, tuple[str, ...]] = {}
        self._downstream_by_node: dict[str, tuple[str, ...]] = {}
        self._underlay_by_node: dict[str, tuple[str, ...]] = {}

        dependency_outgoing: dict[str, list[str]] = defaultdict(list)
        dependency_incoming: dict[str, list[str]] = defaultdict(list)
        underlay_outgoing: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                continue
            if _is_underlay_relation(edge.relation_type):
                underlay_outgoing[edge.from_node_id].append(edge.to_node_id)
            else:
                dependency_outgoing[edge.from_node_id].append(edge.to_node_id)
                dependency_incoming[edge.to_node_id].append(edge.from_node_id)

        for node in nodes.values():
            aliases = {
                node.node_id,
                node.service,
                node.host,
                node.ip,
                f"{node.ip}::{node.service}" if node.ip and node.service else "",
                *node.aliases,
                *node.service_aliases,
                *node.host_aliases,
                *node.ip_aliases,
            }
            for alias in aliases:
                normalized = alias.strip().lower()
                if normalized:
                    self._alias_index[normalized] = node.node_id

            self._upstream_by_node[node.node_id] = tuple(_unique_preserve_order(dependency_outgoing.get(node.node_id, [])))
            self._downstream_by_node[node.node_id] = tuple(_unique_preserve_order(dependency_incoming.get(node.node_id, [])))
            self._underlay_by_node[node.node_id] = tuple(_unique_preserve_order(underlay_outgoing.get(node.node_id, [])))

        for node_id, node in list(nodes.items()):
            nodes[node_id] = TopologyNode(
                node_id=node.node_id,
                service=node.service,
                host=node.host,
                ip=node.ip,
                domain=node.domain,
                aliases=node.aliases,
                node_type=node.node_type,
                service_aliases=node.service_aliases,
                ip_aliases=node.ip_aliases,
                host_aliases=node.host_aliases,
                vendor=node.vendor,
                platform=node.platform,
                tier=node.tier,
                role=node.role,
                cluster_id=node.cluster_id,
                replica_set=node.replica_set,
                is_entrypoint=node.is_entrypoint,
                criticality=node.criticality,
                match_fields=node.match_fields,
                tags=node.tags,
                upstream=self._upstream_by_node[node_id],
                downstream=self._downstream_by_node[node_id],
                underlay=self._underlay_by_node[node_id],
            )
        self._nodes = nodes

    @classmethod
    def from_json(cls, path: Path) -> "TopologyGraph":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "TopologyGraph":
        raw_nodes = payload.get("nodes", [])
        raw_edges = payload.get("edges", [])
        nodes = {
            str(item["node_id"]): _node_from_payload_item(item)
            for item in raw_nodes
            if isinstance(item, dict) and item.get("node_id")
        }
        edges = tuple(
            _edge_from_payload_item(item)
            for item in raw_edges
            if isinstance(item, dict) and item.get("from_node_id") and item.get("to_node_id")
        )

        if not edges:
            edges = _derive_edges_from_legacy_nodes(nodes)

        return cls(nodes, edges)

    def known_hosts(self) -> set[str]:
        values: set[str] = set()
        for node in self._nodes.values():
            if node.host:
                values.add(node.host.lower())
            values.update(value.lower() for value in node.host_aliases if value)
        return values

    def known_services(self) -> set[str]:
        values: set[str] = set()
        for node in self._nodes.values():
            if node.service:
                values.add(node.service.lower())
            values.update(value.lower() for value in node.service_aliases if value)
        return values

    def nodes(self) -> tuple[TopologyNode, ...]:
        return tuple(self._nodes.values())

    def edges(self) -> tuple[TopologyEdge, ...]:
        return self._edges

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def nodes_for_ip(self, ip: str | None) -> tuple[TopologyNode, ...]:
        if not ip:
            return ()
        target = ip.lower()
        return tuple(
            node
            for node in self._nodes.values()
            if node.ip.lower() == target or any(alias.lower() == target for alias in node.ip_aliases)
        )

    def nodes_for_host(self, host: str | None) -> tuple[TopologyNode, ...]:
        if not host:
            return ()
        target = host.lower()
        return tuple(
            node
            for node in self._nodes.values()
            if node.host.lower() == target or any(alias.lower() == target for alias in node.host_aliases)
        )

    def nodes_for_service(self, service: str | None) -> tuple[TopologyNode, ...]:
        if not service:
            return ()
        target = service.lower()
        return tuple(
            node
            for node in self._nodes.values()
            if node.service.lower() == target or any(alias.lower() == target for alias in node.service_aliases)
        )

    def nodes_for_domain(self, domain: str | None) -> tuple[TopologyNode, ...]:
        if not domain:
            return ()
        target = domain.lower()
        return tuple(node for node in self._nodes.values() if node.domain.lower() == target)

    def resolve_node(
        self,
        node_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
    ) -> TopologyNode | None:
        candidates = [node_id, f"{ip}::{service}" if ip and service else None, ip, host]
        for candidate in candidates:
            if not candidate:
                continue
            resolved = self._alias_index.get(candidate.lower())
            if resolved and resolved in self._nodes:
                return self._nodes[resolved]

        if service:
            for node in self._nodes.values():
                service_match = node.service.lower() == service.lower() or any(
                    alias.lower() == service.lower() for alias in node.service_aliases
                )
                if not service_match:
                    continue
                if ip and not (
                    node.ip.lower() == ip.lower() or any(alias.lower() == ip.lower() for alias in node.ip_aliases)
                ):
                    continue
                if host and not (
                    node.host.lower() == host.lower() or any(alias.lower() == host.lower() for alias in node.host_aliases)
                ):
                    continue
                return node
        return None

    def get(self, node_id: str) -> TopologyNode | None:
        return self._nodes.get(node_id)

    def prioritized_neighbors(self, node_id: str) -> list[tuple[str, str]]:
        node = self._nodes.get(node_id)
        if not node:
            return []

        ordered: list[tuple[str, str]] = []
        seen: set[str] = set()
        for hop_type, neighbors in (
            ("upstream", self._upstream_by_node.get(node_id, ())),
            ("underlay", self._underlay_by_node.get(node_id, ())),
            ("downstream", self._downstream_by_node.get(node_id, ())),
        ):
            for neighbor in neighbors:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                ordered.append((hop_type, neighbor))
        return ordered


def _node_from_payload_item(item: dict[str, object]) -> TopologyNode:
    service = _first_text(item.get("service"), item.get("service_name"))
    host = _first_text(item.get("host"), item.get("host_name"))
    ip = _first_text(item.get("ip"), item.get("device_ip"))
    service_aliases = tuple(str(value) for value in item.get("service_aliases", []) if value)
    host_aliases = tuple(str(value) for value in item.get("host_aliases", []) if value)
    ip_aliases = tuple(str(value) for value in item.get("ip_aliases", []) if value)
    legacy_aliases = tuple(str(value) for value in item.get("aliases", []) if value)
    aliases = tuple(
        _unique_preserve_order(
            [
                *legacy_aliases,
                *service_aliases,
                *host_aliases,
                *ip_aliases,
                service,
                host,
                ip,
            ]
        )
    )
    return TopologyNode(
        node_id=str(item["node_id"]),
        service=service,
        host=host,
        ip=ip,
        domain=_first_text(item.get("domain"), item.get("tier"), default="application"),
        aliases=aliases,
        node_type=_first_text(item.get("node_type"), default="service"),
        service_aliases=service_aliases,
        ip_aliases=ip_aliases,
        host_aliases=host_aliases,
        vendor=_optional_text(item.get("vendor")),
        platform=_optional_text(item.get("platform")) or service,
        tier=_optional_text(item.get("tier")),
        role=_optional_text(item.get("role")),
        cluster_id=_optional_text(item.get("cluster_id")),
        replica_set=_optional_text(item.get("replica_set")),
        is_entrypoint=bool(item.get("is_entrypoint", False)),
        criticality=_first_text(item.get("criticality"), default="medium"),
        match_fields=tuple(str(value) for value in item.get("match_fields", []) if value),
        tags=tuple(str(value) for value in item.get("tags", []) if value),
        upstream=tuple(str(value) for value in item.get("upstream", []) if value),
        downstream=tuple(str(value) for value in item.get("downstream", []) if value),
        underlay=tuple(str(value) for value in item.get("underlay", []) if value),
    )


def _edge_from_payload_item(item: dict[str, object]) -> TopologyEdge:
    from_node_id = str(item["from_node_id"])
    to_node_id = str(item["to_node_id"])
    relation_type = _first_text(item.get("relation_type"), item.get("relation"), default="depends_on")
    edge_id = _first_text(item.get("edge_id"), default=f"{from_node_id}->{to_node_id}::{relation_type}")
    return TopologyEdge(
        edge_id=edge_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        relation_type=relation_type,
        relation_label=_first_text(item.get("relation_label"), item.get("label"), item.get("relation"), default=relation_type),
        weight=_float_value(item.get("weight"), default=1.0),
        criticality=_first_text(item.get("criticality"), default="medium"),
        source_refs=tuple(str(value) for value in item.get("source_refs", []) if value),
        valid_from=_optional_text(item.get("valid_from")),
        valid_to=_optional_text(item.get("valid_to")),
    )


def _derive_edges_from_legacy_nodes(nodes: dict[str, TopologyNode]) -> tuple[TopologyEdge, ...]:
    edges: list[TopologyEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes.values():
        for upstream_id in node.upstream:
            key = (node.node_id, upstream_id, "depends_on")
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                TopologyEdge(
                    edge_id=f"{node.node_id}->{upstream_id}::depends_on",
                    from_node_id=node.node_id,
                    to_node_id=upstream_id,
                    relation_type="depends_on",
                    relation_label="legacy_upstream",
                )
            )
        for underlay_id in node.underlay:
            key = (node.node_id, underlay_id, "underlay")
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                TopologyEdge(
                    edge_id=f"{node.node_id}->{underlay_id}::underlay",
                    from_node_id=node.node_id,
                    to_node_id=underlay_id,
                    relation_type="underlay",
                    relation_label="legacy_underlay",
                )
            )
    return tuple(sorted(edges, key=lambda item: (item.from_node_id, item.relation_type, item.to_node_id)))


def _first_text(*values: object, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_value(value: object, *, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _is_underlay_relation(relation_type: str) -> bool:
    return relation_type.strip().lower() in UNDERLAY_RELATIONS
