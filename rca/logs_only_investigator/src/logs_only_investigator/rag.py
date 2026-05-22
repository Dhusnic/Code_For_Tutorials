from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import RAGScope, RankedSignal, SignalRecord


os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "chromadb.telemetry.product.noop.Noop")

LOGGER = logging.getLogger("logs_only_investigator")


@dataclass(frozen=True)
class VectorScopeTarget:
    scope_type: str
    scope_key: str
    db_dir: Path
    collection_name: str
    embedding_model: str
    domain: str | None


class _LocalSentenceTransformerEmbeddingFunction:
    def __init__(self, *, sentence_transformer_cls: Any, model_name: str) -> None:
        self._model = sentence_transformer_cls(model_name, local_files_only=True)

    def __call__(self, input: Any) -> list[list[float]]:
        texts = [str(item) for item in input]
        vectors = self._model.encode(texts, show_progress_bar=False)
        return vectors.tolist()


class CatalogRepository:
    def __init__(
        self,
        root: Path,
        *,
        vector_root: Path | None = None,
        vector_enabled: bool = True,
        semantic_top_k: int = 8,
        global_scope_fanout: int = 6,
    ) -> None:
        self._root = root
        self._services = self._load_catalog_group(root / "services")
        self._vendors = self._load_catalog_group(root / "network")
        self._global_records = tuple(
            record
            for records in list(self._services.values()) + list(self._vendors.values())
            for record in records
        )
        self._record_by_id = {record.id: record for record in self._global_records}
        self._vector_runtime = VectorRuntime(
            vector_root=vector_root,
            enabled=vector_enabled,
            semantic_top_k=semantic_top_k,
            global_scope_fanout=global_scope_fanout,
        )

    def known_services(self) -> set[str]:
        return set(self._services.keys())

    def known_vendors(self) -> set[str]:
        return set(self._vendors.keys())

    def route_scope(self, service: str | None, vendor: str | None, domain_bias: str | None) -> RAGScope:
        if service and service in self._services and self._services[service]:
            records = self._services[service]
            return RAGScope(scope_type="service", scope_key=service, domain_bias=domain_bias, records=records)

        if vendor and vendor in self._vendors:
            records = self._vendors[vendor]
            return RAGScope(scope_type="vendor", scope_key=vendor, domain_bias=domain_bias, records=records)

        if domain_bias:
            domain_records = tuple(record for record in self._global_records if record.domain == domain_bias)
            if domain_records:
                return RAGScope(scope_type="global", scope_key="global", domain_bias=domain_bias, records=domain_records)

        return RAGScope(scope_type="global", scope_key="global", domain_bias=domain_bias, records=self._global_records)

    def rank_signals(self, query: str, terms: list[str], scope: RAGScope, limit: int = 8) -> list[RankedSignal]:
        normalized_terms = tuple(dict.fromkeys(term.lower() for term in terms if term))
        vector_ranked = self._vector_runtime.rank_signals(
            query=query,
            terms=normalized_terms,
            scope=scope,
            record_by_id=self._record_by_id,
            limit=limit,
        )
        if vector_ranked:
            return _filter_ranked(vector_ranked, scope=scope, limit=limit)

        ranked: list[RankedSignal] = []
        for record in scope.records:
            score, matched_terms = _score_record(record, query=query.lower(), terms=normalized_terms, domain_bias=scope.domain_bias)
            if score <= 0:
                continue
            ranked.append(
                RankedSignal(
                    record=record,
                    score=score,
                    matched_terms=matched_terms,
                    retrieval_mode="lexical_fallback",
                    semantic_score=None,
                )
            )

        if not ranked and scope.domain_bias:
            fallback_records = [record for record in scope.records if record.domain == scope.domain_bias][:limit]
            return [
                RankedSignal(
                    record=record,
                    score=0.18,
                    matched_terms=(scope.domain_bias,),
                    retrieval_mode="domain_fallback",
                    semantic_score=None,
                )
                for record in fallback_records
            ]

        return _filter_ranked(ranked, scope=scope, limit=limit)

    def signal_records_for_service(self, service: str) -> tuple[SignalRecord, ...]:
        return self._services.get(service, ())

    def expand_with_related(self, ranked: list[RankedSignal], service: str | None = None, limit: int = 8) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        candidate_pool = self._services.get(service, ()) if service and service in self._services else self._global_records
        by_signal = {record.signal: record for record in candidate_pool}

        for item in ranked[:4]:
            _append_unique(ordered, seen, item.record.signal)
            for related in item.record.related_signals:
                if related in by_signal:
                    _append_unique(ordered, seen, related)

        return ordered[:limit]

    def _load_catalog_group(self, directory: Path) -> dict[str, tuple[SignalRecord, ...]]:
        records: dict[str, tuple[SignalRecord, ...]] = {}
        if not directory.exists():
            return records

        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = tuple(
                SignalRecord(
                    id=str(item["id"]),
                    service=item.get("service"),
                    vendor=item.get("vendor"),
                    domain=item.get("domain"),
                    rule_file=str(item.get("rule_file", path.name)),
                    signal=str(item["signal"]),
                    title=str(item.get("title", item["signal"])),
                    summary=str(item.get("summary", "")),
                    symptom_keywords=[str(value) for value in item.get("symptom_keywords", [])],
                    related_signals=[str(value) for value in item.get("related_signals", [])],
                    query_hints=dict(item.get("query_hints", {})),
                )
                for item in payload
            )
            records[path.stem.lower()] = items
        return records


class VectorRuntime:
    def __init__(
        self,
        *,
        vector_root: Path | None,
        enabled: bool,
        semantic_top_k: int,
        global_scope_fanout: int,
    ) -> None:
        self._vector_root = vector_root
        self._enabled = enabled and vector_root is not None and vector_root.exists()
        self._semantic_top_k = max(1, semantic_top_k)
        self._global_scope_fanout = max(1, global_scope_fanout)
        self._targets_by_service: dict[str, VectorScopeTarget] = {}
        self._targets_by_vendor: dict[str, VectorScopeTarget] = {}
        self._targets_by_domain: dict[str, list[VectorScopeTarget]] = {}
        self._all_targets: list[VectorScopeTarget] = []
        self._clients: dict[str, Any] = {}
        self._embedding_functions: dict[str, Any] = {}
        self._chromadb_module: Any | None = None
        self._embedding_function_cls: Any | None = None
        self._dependency_error: str | None = None

        if self._enabled:
            self._discover_targets()

    def rank_signals(
        self,
        *,
        query: str,
        terms: tuple[str, ...],
        scope: RAGScope,
        record_by_id: dict[str, SignalRecord],
        limit: int,
    ) -> list[RankedSignal]:
        if not self._enabled:
            return []

        targets = self._targets_for_scope(scope)
        if not targets:
            return []

        self._ensure_dependencies()
        if self._dependency_error:
            return []

        query_text = _build_vector_query(query=query, terms=terms, scope=scope)
        semantic_scores: dict[str, float] = {}
        for target in targets:
            collection = self._get_collection(target)
            if collection is None:
                continue
            try:
                response = collection.query(
                    query_texts=[query_text],
                    n_results=max(limit, self._semantic_top_k),
                    include=["distances", "metadatas"],
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Vector query failed for %s:%s: %s", target.scope_type, target.scope_key, exc)
                continue

            ids = (response.get("ids") or [[]])[0]
            distances = (response.get("distances") or [[]])[0]
            for record_id, distance in zip(ids, distances, strict=False):
                if not record_id:
                    continue
                score = _distance_to_semantic_score(distance)
                current = semantic_scores.get(record_id)
                if current is None or score > current:
                    semantic_scores[record_id] = score

        if not semantic_scores:
            return []

        ranked: list[RankedSignal] = []
        for record_id, semantic_score in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True):
            record = record_by_id.get(record_id)
            if record is None:
                continue
            lexical_score, matched_terms = _score_record(record, query=query.lower(), terms=terms, domain_bias=scope.domain_bias)
            combined = round(max(lexical_score, 0.05) + semantic_score * 4.0, 4)
            if scope.domain_bias and record.domain == scope.domain_bias:
                combined = round(combined + 0.6, 4)
            ranked.append(
                RankedSignal(
                    record=record,
                    score=combined,
                    matched_terms=matched_terms or _semantic_matched_terms(scope, record),
                    retrieval_mode="hybrid_vector",
                    semantic_score=round(semantic_score, 4),
                )
            )

        return ranked

    def _targets_for_scope(self, scope: RAGScope) -> list[VectorScopeTarget]:
        if scope.scope_type == "service":
            target = self._targets_by_service.get(scope.scope_key.lower())
            return [target] if target else []
        if scope.scope_type == "vendor":
            target = self._targets_by_vendor.get(scope.scope_key.lower())
            return [target] if target else []
        if scope.domain_bias:
            return self._targets_by_domain.get(scope.domain_bias.lower(), [])[: self._global_scope_fanout]
        return self._all_targets[: self._global_scope_fanout]

    def _discover_targets(self) -> None:
        assert self._vector_root is not None
        for manifest_path in sorted(self._vector_root.glob("*/*/manifest.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Skipping invalid vector manifest %s: %s", manifest_path, exc)
                continue

            relative = manifest_path.relative_to(self._vector_root)
            category = relative.parts[0].lower()
            scope_key = relative.parts[1].lower()
            scope_type = "service" if category == "services" else "vendor"
            target = VectorScopeTarget(
                scope_type=scope_type,
                scope_key=scope_key,
                db_dir=manifest_path.parent,
                collection_name=str(payload.get("collection_name", "signals")),
                embedding_model=str(payload.get("embedding_model", "all-MiniLM-L6-v2")),
                domain=str(payload.get("domain") or "").lower() or None,
            )
            if scope_type == "service":
                self._targets_by_service[scope_key] = target
            else:
                self._targets_by_vendor[scope_key] = target
            if target.domain:
                self._targets_by_domain.setdefault(target.domain, []).append(target)
            self._all_targets.append(target)

    def _ensure_dependencies(self) -> None:
        if self._dependency_error is not None or self._chromadb_module is not None:
            return
        try:
            import chromadb  # type: ignore[import-not-found]
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - runtime dependency check
            self._dependency_error = (
                "Vector retrieval dependencies are not installed. "
                "Install them with `uv sync --extra rag-build` or `pip install chromadb sentence-transformers`."
            )
            LOGGER.warning(self._dependency_error)
            LOGGER.debug("Vector dependency import error: %s", exc)
            return

        self._chromadb_module = chromadb
        self._embedding_function_cls = SentenceTransformer

    def _get_collection(self, target: VectorScopeTarget) -> Any | None:
        if self._chromadb_module is None or self._embedding_function_cls is None:
            return None
        cache_key = str(target.db_dir.resolve())
        if cache_key in self._clients:
            return self._clients[cache_key]

        try:
            client = self._chromadb_module.PersistentClient(path=str(target.db_dir))
            embedding_function = self._embedding_functions.get(target.embedding_model)
            if embedding_function is None:
                embedding_function = _LocalSentenceTransformerEmbeddingFunction(
                    sentence_transformer_cls=self._embedding_function_cls,
                    model_name=target.embedding_model,
                )
                self._embedding_functions[target.embedding_model] = embedding_function
            collection = client.get_collection(name=target.collection_name, embedding_function=embedding_function)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Unable to open vector collection at %s: %s", target.db_dir, exc)
            return None

        self._clients[cache_key] = collection
        return collection


def _filter_ranked(ranked: list[RankedSignal], *, scope: RAGScope, limit: int) -> list[RankedSignal]:
    ranked.sort(key=lambda item: item.score, reverse=True)
    if not ranked:
        return []
    top_score = ranked[0].score
    threshold = max(top_score * 0.45, 0.12)
    filtered = [item for item in ranked if item.score >= threshold]
    if not filtered and scope.domain_bias:
        filtered = ranked[:limit]
    return filtered[:limit]


def _score_record(record: SignalRecord, query: str, terms: tuple[str, ...], domain_bias: str | None) -> tuple[float, tuple[str, ...]]:
    searchable = record.searchable_text()
    matched_terms = [term for term in terms if term in searchable]
    if not matched_terms and record.signal not in query and record.title.lower() not in query:
        return 0.0, ()

    score = 0.0
    for term in matched_terms:
        score += 1.1
        if term == record.service:
            score += 1.4
        if term == record.domain:
            score += 1.2
        if term in record.signal:
            score += 1.0
        if any(term == keyword.lower() for keyword in record.symptom_keywords):
            score += 0.8

    if record.signal in query:
        score += 1.5
    if record.title.lower() in query:
        score += 1.0
    if domain_bias and record.domain == domain_bias:
        score += 1.0

    diversity_bonus = math.log(len(set(matched_terms)) + 1, 2)
    return round(score + diversity_bonus, 4), tuple(matched_terms)


def _append_unique(items: list[str], seen: set[str], value: str) -> None:
    if value in seen:
        return
    seen.add(value)
    items.append(value)


def _build_vector_query(*, query: str, terms: tuple[str, ...], scope: RAGScope) -> str:
    parts = [
        f"query: {query.strip()}",
        f"terms: {', '.join(terms)}" if terms else "",
        f"scope type: {scope.scope_type}",
        f"scope key: {scope.scope_key}" if scope.scope_key else "",
        f"domain bias: {scope.domain_bias}" if scope.domain_bias else "",
    ]
    return "\n".join(part for part in parts if part)


def _distance_to_semantic_score(distance: Any) -> float:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    return round(1.0 / (1.0 + max(value, 0.0)), 4)


def _semantic_matched_terms(scope: RAGScope, record: SignalRecord) -> tuple[str, ...]:
    terms: list[str] = []
    if scope.scope_key and scope.scope_key != "global":
        terms.append(scope.scope_key)
    if scope.domain_bias and scope.domain_bias != scope.scope_key:
        terms.append(scope.domain_bias)
    if record.signal not in terms:
        terms.append(record.signal)
    return tuple(terms[:3])
