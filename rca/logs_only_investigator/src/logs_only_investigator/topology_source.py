from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from pymongo.collection import Collection
from pymongo.database import Database

from .config import MongoConfig
from .observability import log_step
from .topology import TopologyGraph


LOGGER = logging.getLogger("logs_only_investigator")


class TopologySource(Protocol):
    def get_topology(self, organization_id: str, as_of: str | None = None) -> TopologyGraph:
        ...

    def known_hosts(self, organization_id: str, as_of: str | None = None) -> set[str]:
        ...

    def clear_cache(self, organization_id: str | None = None) -> None:
        ...

    def describe_topology(self, organization_id: str, as_of: str | None = None) -> dict[str, object]:
        ...


@dataclass
class StaticTopologySource:
    topology: TopologyGraph

    def get_topology(self, organization_id: str, as_of: str | None = None) -> TopologyGraph:
        return self.topology

    def known_hosts(self, organization_id: str, as_of: str | None = None) -> set[str]:
        return self.topology.known_hosts()

    def clear_cache(self, organization_id: str | None = None) -> None:
        return None

    def describe_topology(self, organization_id: str, as_of: str | None = None) -> dict[str, object]:
        return {
            "organization_id": organization_id,
            "topology_id": "static",
            "node_count": self.topology.node_count(),
            "edge_count": self.topology.edge_count(),
        }


class MongoTopologySource:
    def __init__(self, database: Database, config: MongoConfig) -> None:
        self._collection: Collection = database[config.collection]
        self._config = config
        self._cache: dict[tuple[str, str | None], TopologyGraph] = {}
        self._selected_metadata: dict[tuple[str, str | None], dict[str, object]] = {}

    def get_topology(self, organization_id: str, as_of: str | None = None) -> TopologyGraph:
        cache_key = (organization_id, as_of)
        if cache_key in self._cache:
            log_step(LOGGER, logging.DEBUG, "Topology cache hit", organization_id=organization_id, as_of=as_of)
            return self._cache[cache_key]

        log_step(LOGGER, logging.INFO, "Topology cache miss, loading from MongoDB", organization_id=organization_id, as_of=as_of)
        document = self._select_document(organization_id, as_of=as_of)
        if document is None:
            raise ValueError(
                f"No topology document was found for organization_id={organization_id!r} in MongoDB collection {self._config.collection!r}."
            )

        topology_payload = self._normalize_payload(document)
        topology = TopologyGraph.from_payload(topology_payload)
        self._cache[cache_key] = topology
        version = document.get("version") if isinstance(document.get("version"), dict) else {}
        lookup = document.get("incident_time_lookup") if isinstance(document.get("incident_time_lookup"), dict) else {}
        self._selected_metadata[cache_key] = {
            "organization_id": organization_id,
            "topology_id": document.get("topology_id"),
            "topology_name": document.get("topology_name"),
            "environment": document.get("environment"),
            "is_enabled": document.get("is_enabled"),
            "source_kind": document.get("source_kind"),
            "collection": self._config.collection,
            "schema_version": topology_payload.get(self._config.schema_version_field, self._config.default_schema_version),
            "version_id": version.get("version_id"),
            "version_valid_from": version.get("valid_from") or lookup.get("valid_from"),
            "version_valid_to": version.get("valid_to") or lookup.get("valid_to"),
            "version_is_current": version.get("is_current") if version else lookup.get("is_current"),
            "node_count": len(topology_payload.get("nodes", [])),
            "edge_count": len(topology_payload.get("edges", [])),
            "as_of": as_of,
        }
        log_step(
            LOGGER,
            logging.INFO,
            "Topology loaded from MongoDB",
            organization_id=organization_id,
            as_of=as_of,
            topology_id=document.get("topology_id"),
            version_id=version.get("version_id"),
            is_enabled=document.get("is_enabled"),
            node_count=len(topology_payload.get("nodes", [])),
            edge_count=len(topology_payload.get("edges", [])),
            schema_version=topology_payload.get(self._config.schema_version_field, self._config.default_schema_version),
        )
        return topology

    def known_hosts(self, organization_id: str, as_of: str | None = None) -> set[str]:
        return self.get_topology(organization_id, as_of=as_of).known_hosts()

    def clear_cache(self, organization_id: str | None = None) -> None:
        if organization_id is None:
            self._cache.clear()
            self._selected_metadata.clear()
            return
        for key in list(self._cache):
            if key[0] == organization_id:
                self._cache.pop(key, None)
        for key in list(self._selected_metadata):
            if key[0] == organization_id:
                self._selected_metadata.pop(key, None)

    def describe_topology(self, organization_id: str, as_of: str | None = None) -> dict[str, object]:
        cache_key = (organization_id, as_of)
        if cache_key not in self._selected_metadata:
            self.get_topology(organization_id, as_of=as_of)
        return dict(self._selected_metadata.get(cache_key, {"organization_id": organization_id, "as_of": as_of}))

    def _select_document(self, organization_id: str, *, as_of: str | None = None) -> dict[str, object] | None:
        documents = list(self._collection.find({self._config.organization_field: organization_id}))
        if not documents:
            return None
        if as_of:
            matching = [document for document in documents if _document_matches_as_of(document, as_of)]
            if matching:
                documents = matching
        documents.sort(key=lambda item: _topology_priority(item, as_of=as_of), reverse=True)
        selected = documents[0]
        log_step(
            LOGGER,
            logging.INFO,
            "Selected topology document",
            organization_id=organization_id,
            as_of=as_of,
            topology_id=selected.get("topology_id"),
            version_id=_version_metadata(selected).get("version_id"),
            is_enabled=selected.get("is_enabled"),
            candidate_count=len(documents),
        )
        return selected

    def _normalize_payload(self, document: dict[str, object]) -> dict[str, object]:
        topology_payload = document.get(self._config.topology_field)
        if "nodes" in document:
            payload = {"nodes": document["nodes"]}
            if "edges" in document:
                payload["edges"] = document["edges"]
        elif isinstance(topology_payload, dict) and "nodes" in topology_payload:
            payload = dict(topology_payload)
        else:
            raise ValueError(
                f"MongoDB topology document is missing a nodes payload in either {self._config.topology_field!r} or the root document."
            )

        if self._config.schema_version_field in document:
            payload.setdefault(self._config.schema_version_field, document[self._config.schema_version_field])
        payload.setdefault(self._config.schema_version_field, self._config.default_schema_version)
        return payload


def _topology_priority(document: dict[str, object], *, as_of: str | None = None) -> tuple[int, int, int, str, str]:
    topology_id = str(document.get("topology_id", "")).strip().lower()
    source_kind = str(document.get("source_kind", "")).strip().lower()
    version = _version_metadata(document)
    valid_from = str(version.get("valid_from") or "")
    return (
        1 if _document_matches_as_of(document, as_of) else 0,
        1 if bool(document.get("is_enabled", False)) else 0,
        1 if source_kind == "current" else 0,
        1 if topology_id in {"topology_current", "infraon_onprem_prod"} else 0,
        valid_from,
        topology_id,
    )


def _version_metadata(document: dict[str, object]) -> dict[str, object]:
    version = document.get("version")
    if isinstance(version, dict):
        return version
    lookup = document.get("incident_time_lookup")
    if isinstance(lookup, dict):
        return lookup
    return {}


def _document_matches_as_of(document: dict[str, object], as_of: str | None) -> bool:
    if not as_of:
        return True
    try:
        from .models import parse_utc

        point = parse_utc(as_of)
    except Exception:
        return True

    version = _version_metadata(document)
    valid_from_raw = version.get("valid_from")
    valid_to_raw = version.get("valid_to")

    try:
        from .models import parse_utc

        if valid_from_raw and point < parse_utc(str(valid_from_raw)):
            return False
        if valid_to_raw and point >= parse_utc(str(valid_to_raw)):
            return False
    except Exception:
        return True
    return True
