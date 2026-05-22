from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import difflib
import re
from typing import Any

from .config import OpenAIConfig
from .llm import CriticGenerator, DisabledCriticGenerator, ExplanationGenerator, ScopeResolutionGenerator
from .models import Anchor, HopSearchResult, InvestigationScope, LogRecord, QueryIntent, SearchSummary, TimeWindow, TopologyEdge, TopologyNode, parse_utc, to_utc_string
from .query_parser import parse_query, resolve_scope
from .rag import CatalogRepository
from .tools.log_store import LogStore
from .topology_source import TopologySource


class InvestigationService:
    def __init__(
        self,
        log_store: LogStore,
        catalogs: CatalogRepository,
        topology_source: TopologySource,
        explanation_generator: ExplanationGenerator,
        scope_resolution_generator: ScopeResolutionGenerator,
        max_hops: int,
        openai_config: OpenAIConfig | None = None,
        critic_generator: CriticGenerator | None = None,
    ) -> None:
        self.log_store = log_store
        self.catalogs = catalogs
        self.topology_source = topology_source
        self.explanation_generator = explanation_generator
        self.scope_resolution_generator = scope_resolution_generator
        self.critic_generator = critic_generator or DisabledCriticGenerator()
        self.openai_config = openai_config
        self.max_hops = max_hops

    def resolve_scope(
        self,
        *,
        query: str,
        organization_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        session_memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        memory = session_memory or {}
        topology = self.topology_source.get_topology(organization_id)
        _clear_debug_queries(self.log_store)
        parsed = parse_query(
            query=query,
            known_services={item.lower() for item in self.catalogs.known_services()},
            known_vendors={item.lower() for item in self.catalogs.known_vendors()},
            known_hosts=topology.known_hosts(),
        )

        llm_scope_resolution = None
        scope_candidates = _build_scope_resolution_candidates(
            query=query,
            parsed=parsed,
            memory=memory,
            topology=topology,
            explicit_service=service,
            explicit_host=host,
            explicit_ip=ip,
        )
        if _should_invoke_scope_resolution(
            parsed=parsed,
            memory=memory,
            topology=topology,
            explicit_service=service,
            explicit_host=host,
            explicit_ip=ip,
            candidates=scope_candidates,
        ):
            llm_scope_resolution = self.scope_resolution_generator.resolve_scope(scope_candidates)

        validated_resolution = _validate_scope_resolution(
            llm_scope_resolution,
            candidates=scope_candidates,
            topology=topology,
            confidence_threshold=self.openai_config.scope_resolution_confidence_threshold if self.openai_config else 0.6,
        )
        resolved_service = service or parsed.service_hint or validated_resolution.get("service") or memory.get("service")
        resolved_host = host or parsed.host_hint or validated_resolution.get("host") or memory.get("host")
        resolved_ip = ip or parsed.ip_hint or validated_resolution.get("ip") or memory.get("ip")
        dataset_start, dataset_end, dataset_bounds_source = self._resolve_scope_time_bounds(
            organization_id=organization_id,
            service=resolved_service,
            host=resolved_host,
            ip=resolved_ip,
        )
        selected_node = topology.resolve_node(
            node_id=_optional_text(validated_resolution.get("selected_node_id")),
            service=resolved_service,
            host=resolved_host,
            ip=resolved_ip,
        )
        scope = resolve_scope(
            intent=parsed,
            organization_id=organization_id,
            dataset_start=dataset_start,
            dataset_end=dataset_end,
            explicit_start=start_time,
            explicit_end=end_time,
            service=resolved_service,
            host=resolved_host,
            ip=resolved_ip,
            selected_node_id=selected_node.node_id if selected_node else None,
        )

        trace = [
            f"Parsed query into service={parsed.service_hint}, host={parsed.host_hint}, ip={parsed.ip_hint}, domain={parsed.domain_hint}."
        ]
        if llm_scope_resolution is None:
            trace.append("Skipped LLM scope resolution because the deterministic hints and thread memory were already specific enough.")
        elif validated_resolution.get("accepted"):
            trace.append(
                f"LLM scope resolution selected node={validated_resolution.get('selected_node_id')} "
                f"service={validated_resolution.get('service')} host={validated_resolution.get('host')} ip={validated_resolution.get('ip')} "
                f"with confidence={validated_resolution.get('confidence')}."
            )
        else:
            rejection_reason = validated_resolution.get("rejection_reason") or llm_scope_resolution.get("error") or "the suggestion was not reliable."
            trace.append(f"Ignored the LLM scope suggestion and fell back to deterministic resolution because {rejection_reason}")
        if memory and any(memory.get(key) for key in ("service", "host", "ip")) and not any(
            [service, host, ip, parsed.service_hint, parsed.host_hint, parsed.ip_hint]
        ):
            trace.append("Reused prior thread scope memory because the current turn did not specify a new service, host, or IP.")
        if parsed.time_phrase and dataset_bounds_source == "scoped_entity":
            trace.append(
                f"Resolved the relative time hint against the latest matching logs for service={resolved_service}, host={resolved_host}, ip={resolved_ip}."
            )
        elif parsed.time_phrase:
            trace.append("Resolved the relative time hint against the latest available logs in the organization because no scoped entity-specific timestamps were available.")
        trace.append(
            f"Resolved incident scope to time={scope.time_window.start}..{scope.time_window.end}, service={scope.service}, host={scope.host}, ip={scope.ip}."
        )
        return {
            "parsed_query": _query_intent_to_dict(parsed),
            "scope": _scope_to_dict(scope),
            "scope_resolution": {
                "llm_invoked": llm_scope_resolution is not None,
                "deterministic_hints": scope_candidates["deterministic_hints"],
                "thread_memory": scope_candidates["thread_memory"],
                "candidate_services": scope_candidates["candidate_services"],
                "candidate_hosts": scope_candidates["candidate_hosts"],
                "candidate_ips": scope_candidates["candidate_ips"],
                "candidate_nodes": scope_candidates["candidate_nodes"],
                "llm_request": llm_scope_resolution.get("request") if isinstance(llm_scope_resolution, dict) else None,
                "llm_response": {
                    "selected_node_id": llm_scope_resolution.get("selected_node_id"),
                    "service": llm_scope_resolution.get("service"),
                    "host": llm_scope_resolution.get("host"),
                    "ip": llm_scope_resolution.get("ip"),
                    "confidence": llm_scope_resolution.get("confidence"),
                    "reason": llm_scope_resolution.get("reason"),
                    "requested_model": llm_scope_resolution.get("requested_model"),
                    "llm_model": llm_scope_resolution.get("llm_model"),
                    "usage": llm_scope_resolution.get("usage"),
                    "raw_output_text": llm_scope_resolution.get("raw_output_text"),
                    "error": llm_scope_resolution.get("error"),
                }
                if isinstance(llm_scope_resolution, dict)
                else None,
                "validated_resolution": validated_resolution,
            },
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "trace": trace,
        }

    def _resolve_scope_time_bounds(
        self,
        *,
        organization_id: str,
        service: str | None,
        host: str | None,
        ip: str | None,
    ) -> tuple[str, str, str]:
        if any([service, host, ip]):
            try:
                dataset_start, dataset_end = self.log_store.time_bounds(
                    organization_id=organization_id,
                    service=service,
                    host=host,
                    ip=ip,
                )
                return dataset_start, dataset_end, "scoped_entity"
            except ValueError:
                pass
        dataset_start, dataset_end = self.log_store.time_bounds(organization_id=organization_id)
        return dataset_start, dataset_end, "organization"

    def retrieve_signal_candidates(self, *, query: str, parsed_query: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
        parsed = _query_intent_from_dict(parsed_query)
        scope_obj = _scope_from_dict(scope)
        rag_scope = self.catalogs.route_scope(service=scope_obj.service, vendor=scope_obj.vendor, domain_bias=scope_obj.domain_hint)
        ranked = self.catalogs.rank_signals(query, parsed.search_terms, rag_scope)
        signal_names = self.catalogs.expand_with_related(ranked, service=scope_obj.service, limit=8)
        if not signal_names and scope_obj.service:
            signal_names = [record.signal for record in self.catalogs.signal_records_for_service(scope_obj.service)[:4]]

        retrieval_modes = _unique_strings([item.retrieval_mode for item in ranked]) if ranked else []
        if ranked:
            trace = [
                f"Routed signal retrieval to {rag_scope.scope_type}:{rag_scope.scope_key} with domain bias {rag_scope.domain_bias}.",
                f"Ran Layer 2 candidate retrieval using mode={','.join(retrieval_modes)}.",
                "Retrieved candidate signals: " + ", ".join(f"{item.record.signal}({item.score:.2f})" for item in ranked[:5]) + ".",
            ]
        else:
            trace = [
                f"Routed signal retrieval to {rag_scope.scope_type}:{rag_scope.scope_key} with domain bias {rag_scope.domain_bias}.",
                "No strong signal matches were ranked from the catalog, so the runtime will rely more on direct query-term matching.",
            ]

        return {
            "rag_scope": _rag_scope_to_dict(rag_scope),
            "retrieval_details": {
                "layer_1_scope": _rag_scope_to_dict(rag_scope),
                "layer_2_modes": retrieval_modes,
                "semantic_candidate_count": sum(1 for item in ranked if item.semantic_score is not None),
                "expanded_signal_count": len(signal_names),
            },
            "candidate_signals": [
                {
                    "signal": item.record.signal,
                    "service": item.record.service,
                    "domain": item.record.domain,
                    "score": item.score,
                    "matched_terms": list(item.matched_terms),
                    "retrieval_mode": item.retrieval_mode,
                    "semantic_score": item.semantic_score,
                }
                for item in ranked
            ],
            "candidate_signal_names": signal_names,
            "needs_discovery": parsed.vague or not any([scope_obj.service, scope_obj.host, scope_obj.ip]),
            "trace": trace,
        }

    def aggregate_discovery(self, *, scope: dict[str, Any], candidate_signal_names: list[str]) -> dict[str, Any]:
        scope_obj = _scope_from_dict(scope)
        _clear_debug_queries(self.log_store)
        summary = self.log_store.aggregate_discovery(
            candidate_signals=candidate_signal_names,
            time_window=scope_obj.time_window,
            organization_id=scope_obj.organization_id,
            service=scope_obj.service,
            host=scope_obj.host,
            ip=scope_obj.ip,
            bucket_minutes=5,
        )
        return {
            "discovery_summary": summary,
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "trace": ["Ran aggregate discovery to identify the hottest time bucket, service, and entity anchors before deep RCA."],
        }

    def build_initial_anchor(
        self,
        *,
        scope: dict[str, Any],
        candidate_signals: list[dict[str, Any]],
        candidate_signal_names: list[str],
        discovery_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope_obj = _scope_from_dict(scope)
        topology = self.topology_source.get_topology(scope_obj.organization_id, as_of=scope_obj.time_window.end)
        discovery = discovery_summary or {}
        service = scope_obj.service
        host = scope_obj.host
        ip = scope_obj.ip
        signal_set = _select_anchor_signal_set(candidate_signals, candidate_signal_names)
        time_window = scope_obj.time_window
        reason = "Scope-derived anchor."

        if discovery:
            service = service or _first_value(discovery.get("top_services", []), "service")
            host = host or _first_value(discovery.get("top_hosts", []), "host")
            ip = ip or _first_value(discovery.get("top_ips", []), "ip")
            top_signals = [str(item["signal"]) for item in discovery.get("top_signals", []) if item.get("signal")]
            signal_set = [signal for signal in top_signals if signal in candidate_signal_names] or top_signals[:4] or signal_set

            if top_bucket := (discovery.get("top_time_buckets") or [None])[0]:
                bucket_window = TimeWindow(
                    start=str(top_bucket["start"]),
                    end=str(top_bucket["end"]),
                    label="discovery_hotspot",
                )
                time_window = bucket_window.widen(timedelta(minutes=5), timedelta(minutes=5), label="first_circle_hotspot")
                reason = "Discovery-derived hotspot anchor."

        node = topology.resolve_node(service=service, host=host, ip=ip)
        if node:
            service = service or node.service
            host = host or node.host
            ip = ip or node.ip

        anchor = Anchor(
            service=service,
            host=host,
            ip=ip,
            signal_set=tuple(signal_set),
            time_window=time_window,
            node_id=node.node_id if node else None,
            reason=reason,
        )
        return {
            "anchor": _anchor_to_dict(anchor),
            "trace": [f"Built initial anchor on service={service}, host={host}, ip={ip}, signals={signal_set}, window={time_window.label}."],
        }

    def first_circle_search(self, *, anchor: dict[str, Any], parsed_query: dict[str, Any], organization_id: str) -> dict[str, Any]:
        anchor_obj = _anchor_from_dict(anchor)
        parsed = _query_intent_from_dict(parsed_query)
        _clear_debug_queries(self.log_store)
        summary = self._run_anchor_search(parsed.search_terms, anchor_obj, organization_id=organization_id)
        active_anchor = anchor_obj

        if summary.matched_signal_count == 0 and parsed.time_phrase and ":" in parsed.time_phrase:
            shifted_anchor = Anchor(
                service=anchor_obj.service,
                host=anchor_obj.host,
                ip=anchor_obj.ip,
                signal_set=anchor_obj.signal_set,
                time_window=anchor_obj.time_window.shift(
                    before=-timedelta(days=1),
                    after=-timedelta(days=1),
                    label=f"{anchor_obj.time_window.label}_previous_day",
                ),
                node_id=anchor_obj.node_id,
                reason=f"{anchor_obj.reason} Shifted to the previous day after the initial clock-only search found no evidence.",
            )
            shifted_summary = self._run_anchor_search(parsed.search_terms, shifted_anchor, organization_id=organization_id)
            if shifted_summary.matched_signal_count:
                active_anchor = shifted_anchor
                summary = shifted_summary

        return {
            "anchor": _anchor_to_dict(active_anchor),
            "first_circle": _search_summary_to_dict(summary),
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "trace": [f"First-circle search found {len(summary.events)} events and {summary.matched_signal_count} matched signals."],
        }

    def topology_walk(
        self,
        *,
        anchor: dict[str, Any],
        first_circle: dict[str, Any],
        parsed_query: dict[str, Any],
        scope: dict[str, Any],
    ) -> dict[str, Any]:
        anchor_obj = _anchor_from_dict(anchor)
        first_circle_obj = _search_summary_from_dict(first_circle)
        parsed = _query_intent_from_dict(parsed_query)
        scope_obj = _scope_from_dict(scope)
        topology = self.topology_source.get_topology(scope_obj.organization_id, as_of=scope_obj.time_window.end)
        topology_metadata = self.topology_source.describe_topology(scope_obj.organization_id, as_of=scope_obj.time_window.end)
        _clear_debug_queries(self.log_store)

        impacted_node = None
        if anchor_obj.node_id:
            impacted_node = topology.get(anchor_obj.node_id)
        if not impacted_node and first_circle_obj.entities:
            entity = first_circle_obj.entities[0]
            impacted_node = topology.resolve_node(
                node_id=entity.get("node_id") or None,
                service=entity.get("service") or None,
                host=entity.get("host") or None,
                ip=entity.get("ip") or None,
            )
        if not impacted_node:
            impacted_node = topology.resolve_node(service=anchor_obj.service, host=anchor_obj.host, ip=anchor_obj.ip)

        trace = [f"Mapped the impact anchor to topology node {impacted_node.node_id if impacted_node else 'none'}."]
        node_inspections: list[dict[str, Any]] = []
        if impacted_node:
            node_inspections.append(
                {
                    "node_id": impacted_node.node_id,
                    "source_node_id": None,
                    "hop_type": "impact",
                    "depth": 0,
                    "status": "validated",
                    "service": impacted_node.service,
                    "host": impacted_node.host,
                    "ip": impacted_node.ip,
                    "candidate_signals": list(anchor_obj.signal_set),
                    "time_window": asdict(anchor_obj.time_window),
                    "matched_signal_count": first_circle_obj.matched_signal_count,
                    "chronology_ok": True,
                    "summary": "First-circle impact evidence anchored the topology walk.",
                    "event_ids": [log.doc_id for log in first_circle_obj.events[:12]],
                    "fetched_logs": [asdict(log) for log in first_circle_obj.events[:25]],
                    "elasticsearch_queries": [],
                }
            )
        if not impacted_node or not first_circle_obj.events:
            trace.append("Skipped topology walk because no mapped impact node or no first-circle evidence was available.")
            return {
                "impacted_node": _topology_node_to_dict(impacted_node),
                "topology_metadata": topology_metadata,
                "topology_hops": [],
                "rejected_paths": [],
                "alternate_paths": [],
                "topology_graph": _topology_graph_to_dict(topology, impacted_node, []),
                "topology_comparison_rounds": [],
                "node_inspections": node_inspections,
                "trace": trace,
            }

        current_node = impacted_node
        current_first_seen = first_circle_obj.first_seen or scope_obj.time_window.end
        visited = {current_node.node_id}
        validated_hops: list[HopSearchResult] = []
        rejected_paths: list[str] = []
        topology_comparison_rounds: list[dict[str, Any]] = []
        alternate_paths: list[dict[str, Any]] = []

        for depth_index in range(1, self.max_hops + 1):
            best: HopSearchResult | None = None
            best_score = -1.0
            round_inspections: list[dict[str, Any]] = []
            round_comparison_candidates: list[dict[str, Any]] = []
            candidate_results: dict[str, HopSearchResult] = {}
            service_policy = _service_rca_policy(current_node.service, current_node.domain)

            for hop_type, neighbor_id in topology.prioritized_neighbors(current_node.node_id):
                if neighbor_id in visited:
                    continue
                neighbor = topology.get(neighbor_id)
                if not neighbor:
                    continue

                neighbor_scope = self.catalogs.route_scope(service=neighbor.service, vendor=None, domain_bias=neighbor.domain)
                ranked = self.catalogs.rank_signals(
                    query=parsed.normalized_query,
                    terms=parsed.search_terms + [neighbor.service, current_node.service],
                    scope=neighbor_scope,
                    limit=5,
                )
                signals = self.catalogs.expand_with_related(ranked, service=neighbor.service, limit=5)
                if not signals:
                    signals = [record.signal for record in self.catalogs.signal_records_for_service(neighbor.service)[:3]]

                hop_window = _build_hop_window(current_first_seen, hop_type)
                _clear_debug_queries(self.log_store)
                summary = self.log_store.summarize(
                    query_terms=parsed.search_terms,
                    signals=signals or None,
                    time_window=hop_window,
                    organization_id=scope_obj.organization_id,
                    service=neighbor.service,
                    host=neighbor.host or None,
                    ip=neighbor.ip or None,
                    limit=200,
                )
                if summary.matched_signal_count == 0:
                    fallback_summary = self.log_store.summarize(
                        query_terms=parsed.search_terms,
                        signals=None,
                        time_window=hop_window,
                        organization_id=scope_obj.organization_id,
                        service=neighbor.service,
                        host=neighbor.host or None,
                        ip=neighbor.ip or None,
                        limit=200,
                    )
                    if fallback_summary.matched_signal_count == 0:
                        fallback_summary = self.log_store.summarize(
                            query_terms=None,
                            signals=None,
                            time_window=hop_window,
                            organization_id=scope_obj.organization_id,
                            service=neighbor.service,
                            host=neighbor.host or None,
                            ip=neighbor.ip or None,
                            limit=200,
                        )
                    if fallback_summary.matched_signal_count:
                        summary = fallback_summary
                        signals = list(summary.signal_counts.keys())[:5]
                    else:
                        generic_events = _generic_supporting_events(
                            events=fallback_summary.events,
                            neighbor=neighbor,
                            current_node=current_node,
                            hop_type=hop_type,
                            parsed_terms=parsed.search_terms,
                            require_neighbor_identity=False,
                        )
                        if not generic_events and (neighbor.host or neighbor.ip):
                            broadened_summary = self.log_store.summarize(
                                query_terms=None,
                                signals=None,
                                time_window=hop_window,
                                organization_id=scope_obj.organization_id,
                                service=None,
                                host=neighbor.host or None,
                                ip=neighbor.ip or None,
                                limit=200,
                            )
                            generic_events = _generic_supporting_events(
                                events=broadened_summary.events,
                                neighbor=neighbor,
                                current_node=current_node,
                                hop_type=hop_type,
                                parsed_terms=parsed.search_terms,
                                require_neighbor_identity=True,
                            )

                        if generic_events:
                            summary = _summary_from_logs(generic_events)
                            signals = [f"generic_{hop_type}_evidence"]
                query_payloads = _consume_debug_queries(self.log_store)

                chronology_ok = bool(summary.first_seen and summary.first_seen <= current_first_seen)
                matched_signal_count = summary.matched_signal_count
                signalized_match_count = sum(summary.signal_counts.values())
                if matched_signal_count == 0 and summary.events:
                    matched_signal_count = min(len(summary.events), 4)
                used_generic = bool(summary.events and not summary.signal_counts)
                score_breakdown = _score_topology_candidate(
                    neighbor=neighbor,
                    current_node=current_node,
                    hop_type=hop_type,
                    matched_signal_count=matched_signal_count,
                    signalized_match_count=signalized_match_count,
                    event_count=len(summary.events),
                    chronology_ok=chronology_ok,
                    first_seen=summary.first_seen,
                    current_first_seen=current_first_seen,
                    used_generic=used_generic,
                    parsed=parsed,
                    policy=service_policy,
                )
                comparison_row = {
                    "node_id": neighbor.node_id,
                    "service": neighbor.service,
                    "domain": neighbor.domain,
                    "hop_type": hop_type,
                    "matched_signal_count": matched_signal_count,
                    "signalized_match_count": signalized_match_count,
                    "event_count": len(summary.events),
                    "chronology_ok": chronology_ok,
                    "first_seen": summary.first_seen,
                    "used_generic": used_generic,
                    "policy_name": service_policy["policy_name"],
                    "score": score_breakdown["total_score"],
                    "score_breakdown": score_breakdown,
                    "status": "candidate",
                    "rejection_reason": None,
                    "critic_adjustment": 0.0,
                }
                if matched_signal_count == 0:
                    rejection_reason = f"{neighbor.node_id} had no supporting {hop_type} evidence inside the incident path window."
                    rejected_paths.append(rejection_reason)
                    comparison_row["status"] = "rejected"
                    comparison_row["rejection_reason"] = rejection_reason
                    round_comparison_candidates.append(comparison_row)
                    round_inspections.append(
                        {
                            "node_id": neighbor.node_id,
                            "source_node_id": current_node.node_id,
                            "hop_type": hop_type,
                            "depth": depth_index,
                            "status": "rejected",
                            "service": neighbor.service,
                            "host": neighbor.host,
                            "ip": neighbor.ip,
                            "candidate_signals": list(signals),
                            "time_window": asdict(hop_window),
                            "matched_signal_count": 0,
                            "chronology_ok": chronology_ok,
                            "score": score_breakdown["total_score"],
                            "policy_name": service_policy["policy_name"],
                            "score_breakdown": score_breakdown,
                            "summary": f"No supporting {hop_type} evidence was found inside the incident path window.",
                            "event_ids": [],
                            "fetched_logs": [asdict(log) for log in summary.events[:25]],
                            "elasticsearch_queries": query_payloads,
                        }
                    )
                    continue

                score = float(score_breakdown["total_score"])

                candidate = HopSearchResult(
                    source_node_id=current_node.node_id,
                    target_node_id=neighbor.node_id,
                    hop_type=hop_type,
                    service=neighbor.service,
                    ip=neighbor.ip,
                    time_window=hop_window,
                    signals=tuple(signals),
                    event_ids=tuple(log.doc_id for log in summary.events[:8]),
                    first_seen=summary.first_seen,
                    last_seen=summary.last_seen,
                    matched_signal_count=matched_signal_count,
                    summary=_hop_summary_text(
                        neighbor=neighbor,
                        hop_type=hop_type,
                        matched_signal_count=matched_signal_count,
                        used_generic=used_generic,
                    ),
                    chronology_ok=chronology_ok,
                )
                candidate_results[neighbor.node_id] = candidate
                if score > best_score:
                    best = candidate
                    best_score = score
                round_comparison_candidates.append(comparison_row)
                round_inspections.append(
                    {
                        "node_id": neighbor.node_id,
                        "source_node_id": current_node.node_id,
                        "hop_type": hop_type,
                        "depth": depth_index,
                        "status": "candidate",
                        "service": neighbor.service,
                        "host": neighbor.host,
                        "ip": neighbor.ip,
                        "candidate_signals": list(signals),
                        "time_window": asdict(hop_window),
                        "matched_signal_count": matched_signal_count,
                        "chronology_ok": chronology_ok,
                        "score": score_breakdown["total_score"],
                        "policy_name": service_policy["policy_name"],
                        "score_breakdown": score_breakdown,
                        "summary": _hop_summary_text(
                            neighbor=neighbor,
                            hop_type=hop_type,
                            matched_signal_count=matched_signal_count,
                            used_generic=used_generic,
                        ),
                        "event_ids": [log.doc_id for log in summary.events[:12]],
                        "fetched_logs": [asdict(log) for log in summary.events[:25]],
                        "elasticsearch_queries": query_payloads,
                    }
                )

            best, critic_review = _choose_topology_round_winner(
                critic_generator=self.critic_generator,
                query=parsed.normalized_query,
                current_node=current_node,
                depth_index=depth_index,
                service_policy=service_policy,
                candidate_results=candidate_results,
                round_candidates=round_comparison_candidates,
                best=best,
            )
            _mark_selected_round_inspections(round_inspections, best)
            _mark_selected_round_comparison(round_comparison_candidates, best)
            round_comparison_candidates.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
            alternate_paths.extend(
                _retain_alternate_paths(
                    round_candidates=round_comparison_candidates,
                    selected_node_id=best.target_node_id if best else None,
                    depth=depth_index,
                    source_node_id=current_node.node_id,
                    limit=int(service_policy.get("max_alternate_paths_per_round", 2) or 2),
                )
            )
            topology_comparison_rounds.append(
                {
                    "depth": depth_index,
                    "source_node_id": current_node.node_id,
                    "selected_node_id": best.target_node_id if best else None,
                    "service_policy": _public_service_policy(service_policy),
                    "critic_review": critic_review,
                    "candidates": round_comparison_candidates,
                }
            )
            node_inspections.extend(round_inspections)
            if not best:
                break

            validated_hops.append(best)
            visited.add(best.target_node_id)
            current_node = topology.get(best.target_node_id) or current_node
            current_first_seen = best.first_seen or current_first_seen

        if validated_hops:
            trace.append(
                "Topology walk validated the path: "
                + " -> ".join([impacted_node.node_id] + [hop.target_node_id for hop in validated_hops])
                + "."
            )
        else:
            trace.append("Topology walk did not find stronger upstream or underlay evidence than the first-circle impact node.")

        return {
            "impacted_node": _topology_node_to_dict(impacted_node),
            "topology_metadata": topology_metadata,
            "topology_hops": [_hop_to_dict(item) for item in validated_hops],
            "rejected_paths": rejected_paths,
            "alternate_paths": alternate_paths,
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "topology_graph": _topology_graph_to_dict(topology, impacted_node, validated_hops),
            "topology_comparison_rounds": topology_comparison_rounds,
            "node_inspections": node_inspections,
            "trace": trace,
        }

    def raw_log_context(
        self,
        *,
        scope: dict[str, Any],
        first_circle: dict[str, Any],
        topology_walk: dict[str, Any],
    ) -> dict[str, Any]:
        scope_obj = _scope_from_dict(scope)
        first_circle_obj = _search_summary_from_dict(first_circle)
        hop_payloads = topology_walk.get("topology_hops", [])

        anchor_ids: list[str] = []
        if hop_payloads:
            for hop in reversed(hop_payloads[-2:]):
                anchor_ids.extend(list(hop.get("event_ids", [])[:2]))
        else:
            anchor_ids.extend([log.doc_id for log in first_circle_obj.events[:3]])

        if not anchor_ids:
            return {"raw_context": [], "trace": []}

        _clear_debug_queries(self.log_store)
        raw_context = self.log_store.raw_context(
            anchor_event_ids=anchor_ids,
            time_window=scope_obj.time_window.widen(timedelta(minutes=5), timedelta(minutes=5), label="raw_context"),
            organization_id=scope_obj.organization_id,
            service=_context_service(scope_obj.service, first_circle_obj),
            host=scope_obj.host,
            ip=scope_obj.ip,
            limit=12,
        )
        return {
            "raw_context": raw_context,
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "trace": [f"Collected {len(raw_context)} raw-context lines around the strongest validated evidence."],
        }

    def healthy_window_comparison(
        self,
        *,
        scope: dict[str, Any],
        anchor: dict[str, Any],
        first_circle: dict[str, Any],
        topology_walk: dict[str, Any],
    ) -> dict[str, Any]:
        scope_obj = _scope_from_dict(scope)
        anchor_obj = _anchor_from_dict(anchor)
        first_circle_obj = _search_summary_from_dict(first_circle)
        hops = [_hop_from_dict(item) for item in topology_walk.get("topology_hops", [])]

        target_node_id = hops[-1].target_node_id if hops else anchor_obj.node_id
        target_service = scope_obj.service or anchor_obj.service
        target_host = scope_obj.host or anchor_obj.host
        target_ip = scope_obj.ip or anchor_obj.ip
        incident_window = anchor_obj.time_window
        incident_minutes = max(
            (parse_utc(incident_window.end) - parse_utc(incident_window.start)).total_seconds() / 60.0,
            1.0,
        )
        healthy_end_dt = parse_utc(incident_window.start) - timedelta(minutes=15)
        healthy_start_dt = healthy_end_dt - timedelta(minutes=incident_minutes)
        healthy_window = TimeWindow(
            start=to_utc_string(healthy_start_dt),
            end=to_utc_string(healthy_end_dt),
            label=f"healthy_baseline_{int(round(incident_minutes))}m",
        )

        _clear_debug_queries(self.log_store)
        baseline_summary = self.log_store.summarize(
            query_terms=None,
            signals=list(anchor_obj.signal_set) or None,
            time_window=healthy_window,
            organization_id=scope_obj.organization_id,
            service=target_service,
            host=target_host,
            ip=target_ip,
            limit=250,
        )
        if not baseline_summary.events and not baseline_summary.signal_counts:
            previous_day_window = TimeWindow(
                start=to_utc_string(healthy_start_dt - timedelta(days=1)),
                end=to_utc_string(healthy_end_dt - timedelta(days=1)),
                label=f"{healthy_window.label}_previous_day",
            )
            baseline_summary = self.log_store.summarize(
                query_terms=None,
                signals=list(anchor_obj.signal_set) or None,
                time_window=previous_day_window,
                organization_id=scope_obj.organization_id,
                service=target_service,
                host=target_host,
                ip=target_ip,
                limit=250,
            )
            healthy_window = previous_day_window

        comparison = _compare_against_healthy_window(
            incident_summary=first_circle_obj,
            baseline_summary=baseline_summary,
            incident_minutes=incident_minutes,
        )
        return {
            "target_node_id": target_node_id,
            "target_service": target_service,
            "target_host": target_host,
            "target_ip": target_ip,
            "incident_window": asdict(incident_window),
            "healthy_window": asdict(healthy_window),
            "incident_summary": _comparison_summary_payload(first_circle_obj),
            "healthy_summary": _comparison_summary_payload(baseline_summary),
            "comparison": comparison,
            "elasticsearch_queries": _consume_debug_queries(self.log_store),
            "trace": [
                f"Compared the incident window against a healthy baseline for service={target_service}, host={target_host}, ip={target_ip}.",
                f"Healthy-window anomaly score was {comparison['anomaly_score']:.2f}.",
            ],
        }

    def critic_pass(
        self,
        *,
        query: str,
        scope: dict[str, Any],
        anchor: dict[str, Any],
        first_circle: dict[str, Any],
        topology_walk: dict[str, Any],
        raw_context: list[str],
        healthy_window: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        anchor_obj = _anchor_from_dict(anchor)
        first_circle_obj = _search_summary_from_dict(first_circle)
        hops = [_hop_from_dict(item) for item in topology_walk.get("topology_hops", [])]
        rejected_paths = list(topology_walk.get("rejected_paths", []))
        alternate_paths = list(topology_walk.get("alternate_paths", []))
        confidence, classification, confidence_breakdown = _score_and_classify(first_circle_obj, hops, rejected_paths, raw_context)
        confidence, classification, confidence_breakdown = _apply_healthy_window_adjustment(
            confidence=confidence,
            classification=classification,
            confidence_breakdown=confidence_breakdown,
            healthy_window=healthy_window if isinstance(healthy_window, dict) else None,
        )

        flattened_candidates: list[dict[str, Any]] = []
        comparison_rounds = topology_walk.get("topology_comparison_rounds")
        if isinstance(comparison_rounds, list):
            for round_item in comparison_rounds[:2]:
                if not isinstance(round_item, dict):
                    continue
                candidates = round_item.get("candidates")
                if not isinstance(candidates, list):
                    continue
                for candidate in candidates[:5]:
                    if isinstance(candidate, dict):
                        flattened_candidates.append(
                            {
                                "node_id": candidate.get("node_id"),
                                "service": candidate.get("service"),
                                "status": candidate.get("status"),
                                "score": candidate.get("score"),
                                "policy_name": candidate.get("policy_name"),
                                "critic_adjustment": candidate.get("critic_adjustment"),
                                "matched_signal_count": candidate.get("matched_signal_count"),
                                "chronology_ok": candidate.get("chronology_ok"),
                                "rejection_reason": candidate.get("rejection_reason"),
                            }
                        )

        critic_payload = self.critic_generator.review_weak_rca(
            {
                "query": query,
                "incident_window": asdict(anchor_obj.time_window),
                "current_assessment": {
                    "classification": classification,
                    "confidence": confidence,
                    "confidence_breakdown": confidence_breakdown,
                    "likely_impacted_node": anchor_obj.node_id,
                    "rejected_paths": rejected_paths[:6],
                    "alternate_paths": alternate_paths[:4],
                },
                "topology_summary": {
                    "hop_count": len(hops),
                    "deepest_supported_node": hops[-1].target_node_id if hops else anchor_obj.node_id,
                    "validated_hops": [_hop_to_dict(item) for item in hops[-3:]],
                },
                "healthy_window_summary": {
                    "comparison": (healthy_window or {}).get("comparison") if isinstance(healthy_window, dict) else None,
                    "healthy_window": (healthy_window or {}).get("healthy_window") if isinstance(healthy_window, dict) else None,
                },
                "candidate_comparison": flattened_candidates,
                "raw_context": raw_context[:8],
            }
        )
        return {
            "critic": critic_payload,
            "trace": [
                f"Ran the weak-RCA critic against classification={classification} confidence={confidence:.2f}.",
                f"Critic verdict was {critic_payload.get('verdict')}.",
            ],
        }

    def compose_report(
        self,
        *,
        scope: dict[str, Any],
        rag_scope: dict[str, Any],
        candidate_signals: list[dict[str, Any]],
        anchor: dict[str, Any],
        first_circle: dict[str, Any],
        topology_walk: dict[str, Any],
        raw_context: list[str],
        investigation_trace: list[str],
        healthy_window: dict[str, Any] | None = None,
        critic_pass: dict[str, Any] | None = None,
        session_memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope_obj = _scope_from_dict(scope)
        anchor_obj = _anchor_from_dict(anchor)
        first_circle_obj = _search_summary_from_dict(first_circle)
        impacted_node = _topology_node_from_dict(topology_walk.get("impacted_node"))
        hops = [_hop_from_dict(item) for item in topology_walk.get("topology_hops", [])]
        rejected_paths = list(topology_walk.get("rejected_paths", []))
        alternate_paths = list(topology_walk.get("alternate_paths", []))

        confidence, classification, confidence_breakdown = _score_and_classify(first_circle_obj, hops, rejected_paths, raw_context)
        confidence, classification, confidence_breakdown = _apply_healthy_window_adjustment(
            confidence=confidence,
            classification=classification,
            confidence_breakdown=confidence_breakdown,
            healthy_window=healthy_window if isinstance(healthy_window, dict) else None,
        )
        confidence, classification, confidence_breakdown = _apply_critic_adjustment(
            confidence=confidence,
            classification=classification,
            confidence_breakdown=confidence_breakdown,
            critic_pass=critic_pass if isinstance(critic_pass, dict) else None,
        )
        impacted_label = impacted_node.node_id if impacted_node else anchor_obj.node_id or _entity_label(anchor_obj.service, anchor_obj.host, anchor_obj.ip)
        root_hop = hops[-1] if hops else None
        likely_root_cause = f"{root_hop.service} at {root_hop.target_node_id}" if root_hop else _fallback_root_cause(first_circle_obj, impacted_label)

        path_nodes = [impacted_label] + [hop.target_node_id for hop in hops]
        unknowns = list(scope_obj.assumptions)
        contradictions = list(rejected_paths)
        if first_circle_obj.events and len(first_circle_obj.signal_counts) > 3:
            contradictions.append("The first-circle evidence contains several competing signal families, so the conclusion is partly dependent on topology ordering.")
        if not hops and first_circle_obj.events:
            contradictions.append("No stronger upstream evidence was found beyond the impacted node, so the result stays closer to symptom-level RCA.")
        if alternate_paths:
            unknowns.append("Alternate supported topology branches remain plausible and should be reviewed before acting on a low-risk fix.")

        fallback_summary = _build_summary(likely_root_cause, impacted_label, hops, classification)
        supporting_evidence = _build_supporting_evidence(impacted_label, first_circle_obj, hops)
        if first_circle_obj.matched_signal_count == 0:
            unknowns.append("No candidate signal matched directly in the first-circle search; the evidence is based on generic log activity near the scoped entity.")
        if not raw_context:
            unknowns.append("No additional raw-log context materially strengthened the validated signal path.")
        if not impacted_node:
            unknowns.append("The impacted service could not be mapped to a topology node, so graph-guided expansion was limited.")
        if isinstance(healthy_window, dict):
            comparison = healthy_window.get("comparison") if isinstance(healthy_window.get("comparison"), dict) else {}
            anomaly_score = float(comparison.get("anomaly_score") or 0.0)
            if anomaly_score < 0.35:
                contradictions.append("The incident window did not differ strongly from the healthy baseline for the scoped entity.")
            else:
                supporting_evidence.append(
                    {
                        "claim": "The incident window showed stronger scoped activity than the healthy baseline comparison window.",
                        "evidence_ids": [],
                    }
                )
        service_rule_hits = _build_service_specific_contradictions(
            impacted_service=anchor_obj.service or scope_obj.service,
            root_service=root_hop.service if root_hop else anchor_obj.service or scope_obj.service,
            root_node_id=root_hop.target_node_id if root_hop else impacted_label,
            first_circle=first_circle_obj,
            hops=hops,
            topology_walk=topology_walk,
            raw_context=raw_context,
            alternate_paths=alternate_paths,
        )
        confidence, classification, confidence_breakdown = _apply_service_contradiction_adjustment(
            confidence=confidence,
            classification=classification,
            confidence_breakdown=confidence_breakdown,
            rule_hits=service_rule_hits,
        )
        contradictions.extend(hit["message"] for hit in service_rule_hits)
        critic_payload = (critic_pass or {}).get("critic") if isinstance(critic_pass, dict) else None
        if isinstance(critic_payload, dict):
            for risk in critic_payload.get("key_risks", []):
                if isinstance(risk, str) and risk and risk not in unknowns:
                    unknowns.append(risk)
            if critic_payload.get("verdict") == "downgrade_confidence":
                contradictions.append(f"Weak-RCA critic warning: {critic_payload.get('reasoning')}")

        llm_payload = self.explanation_generator.generate_summary(
            {
                "incident_window": {
                    "start": anchor_obj.time_window.start,
                    "end": anchor_obj.time_window.end,
                    "label": anchor_obj.time_window.label,
                },
                "likely_root_cause": likely_root_cause,
                "classification": classification,
                "confidence": confidence,
                "primary_entities": _unique_strings(path_nodes),
                "timeline": _build_timeline(impacted_label, first_circle_obj, hops),
                "supporting_evidence": supporting_evidence,
                "contradictions": contradictions,
                "unknowns": unknowns,
                "raw_context": raw_context,
                "fallback_summary": fallback_summary,
            }
        )

        report = {
            "summary": fallback_summary,
            "analyst_summary": llm_payload["analyst_summary"],
            "analyst_summary_source": llm_payload.get("summary_source"),
            "llm_requested_model": llm_payload.get("requested_model"),
            "llm_model": llm_payload.get("llm_model"),
            "llm_usage": llm_payload.get("usage"),
            "total_tokens_used": (llm_payload.get("usage") or {}).get("total_tokens"),
            "llm_error": llm_payload.get("error"),
            "likely_root_cause": likely_root_cause,
            "confidence": confidence,
            "confidence_breakdown": confidence_breakdown,
            "classification": classification,
            "incident_window": {
                "start": anchor_obj.time_window.start,
                "end": anchor_obj.time_window.end,
                "label": anchor_obj.time_window.label,
            },
            "rag_scope": rag_scope,
            "candidate_signals": candidate_signals,
            "primary_entities": _unique_strings(path_nodes),
            "dominant_signals": dict(first_circle_obj.signal_counts),
            "alternate_paths": alternate_paths,
            "service_specific_contradictions": service_rule_hits,
            "timeline": _build_timeline(impacted_label, first_circle_obj, hops),
            "supporting_evidence": supporting_evidence,
            "contradictions": contradictions,
            "unknowns": unknowns,
            "evidence_logs": _build_evidence_logs(first_circle_obj),
            "raw_context": raw_context,
            "healthy_window_comparison": healthy_window,
            "critic_pass": critic_pass,
            "next_log_checks": [
                "Check whether the root-cause node shows the same signal family in a healthy comparison window.",
                "Verify whether alert thresholds should trigger one hop earlier on the validated path.",
                "Inspect neighboring dependencies for repeated low-severity warnings before the confirmed incident window.",
            ],
            "investigation_trace": investigation_trace,
        }
        updated_memory = dict(session_memory or {})
        updated_memory.update(
            {
                "organization_id": scope_obj.organization_id,
                "service": anchor_obj.service or scope_obj.service,
                "host": anchor_obj.host or scope_obj.host,
                "ip": anchor_obj.ip or scope_obj.ip,
                "last_impacted_node": impacted_label,
                "last_root_cause": likely_root_cause,
                "last_incident_window": report["incident_window"],
                "last_classification": classification,
            }
        )
        return {"report": report, "session_memory": updated_memory}

    def _run_anchor_search(self, search_terms: list[str], anchor: Anchor, *, organization_id: str) -> SearchSummary:
        summary = self.log_store.summarize(
            query_terms=search_terms,
            signals=list(anchor.signal_set) or None,
            time_window=anchor.time_window,
            organization_id=organization_id,
            service=anchor.service,
            host=anchor.host,
            ip=anchor.ip,
            limit=250,
        )
        if summary.matched_signal_count:
            return summary

        summary = self.log_store.summarize(
            query_terms=search_terms,
            signals=None,
            time_window=anchor.time_window,
            organization_id=organization_id,
            service=anchor.service,
            host=anchor.host,
            ip=anchor.ip,
            limit=250,
        )
        if summary.matched_signal_count:
            return summary

        return self.log_store.summarize(
            query_terms=None,
            signals=None,
            time_window=anchor.time_window,
            organization_id=organization_id,
            service=anchor.service,
            host=anchor.host,
            ip=anchor.ip,
            limit=250,
        )


def _build_hop_window(reference_time: str, hop_type: str) -> TimeWindow:
    reference_dt = parse_utc(reference_time)
    if hop_type == "upstream":
        start = reference_dt - timedelta(minutes=15)
        end = reference_dt + timedelta(minutes=2)
    elif hop_type == "underlay":
        start = reference_dt - timedelta(minutes=20)
        end = reference_dt + timedelta(minutes=1)
    else:
        start = reference_dt - timedelta(minutes=8)
        end = reference_dt + timedelta(minutes=8)
    return TimeWindow(
        start=to_utc_string(start),
        end=to_utc_string(end),
        label=f"{hop_type}_window",
    )


GENERIC_ERROR_KEYWORDS = (
    "failed",
    "failure",
    "refused",
    "temporarily disabled",
    "timeout",
    "timed out",
    "unavailable",
    "bad gateway",
    "gateway timeout",
    "error",
    "denied",
    "degraded",
    "disconnect",
    "connection refused",
    "slow query",
    "no space",
    "i/o",
    "latency",
)


def _generic_supporting_events(
    *,
    events: tuple[LogRecord, ...],
    neighbor: TopologyNode,
    current_node: TopologyNode,
    hop_type: str,
    parsed_terms: list[str],
    require_neighbor_identity: bool,
) -> list[LogRecord]:
    selected: list[LogRecord] = []
    for event in events:
        text = event.searchable_text()
        if require_neighbor_identity and not _event_matches_neighbor_identity(event, neighbor):
            continue

        score = 0
        severity = (event.severity or "").lower()
        if severity in {"error", "critical", "fatal", "warn", "warning"}:
            score += 1
        if any(keyword in text for keyword in GENERIC_ERROR_KEYWORDS):
            score += 1
        if hop_type == "upstream" and any(
            keyword in text
            for keyword in (
                "upstream",
                "connect() failed",
                "response header",
                "backend",
                "dependency",
                "gunicorn",
                "application",
            )
        ):
            score += 1
        if hop_type == "underlay" and any(
            keyword in text
            for keyword in ("disk", "filesystem", "memory", "cpu", "i/o", "latency", "network")
        ):
            score += 1
        if any(term in text for term in _meaningful_terms(parsed_terms)):
            score += 1
        if _event_matches_neighbor_identity(event, neighbor):
            score += 1
        elif event.service and event.service.lower() != current_node.service.lower() and not require_neighbor_identity:
            score += 1

        if score >= 2:
            selected.append(event)

    return selected[:8]


def _event_matches_neighbor_identity(event: LogRecord, neighbor: TopologyNode) -> bool:
    text = event.searchable_text()
    if event.service and _normalize_service_name(event.service) == _normalize_service_name(neighbor.service):
        return True
    return any(term in text for term in _neighbor_identity_terms(neighbor))


def _neighbor_identity_terms(neighbor: TopologyNode) -> set[str]:
    raw_terms = {neighbor.service, *neighbor.aliases}
    expanded: set[str] = set()
    for term in raw_terms:
        value = str(term).strip().lower()
        if not value or value == neighbor.host.lower() or value == neighbor.ip.lower():
            continue
        expanded.add(value)
        expanded.update(_tokenize_identity_term(value))
        if value.endswith(".service"):
            expanded.add(value[:-8])
        if value.startswith("instance") and len(value) > len("instance"):
            expanded.add(value[len("instance") :])
    return {term for term in expanded if len(term) >= 4}


def _tokenize_identity_term(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value) if len(token) >= 4}


def _normalize_service_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", value.lower())
    if normalized.startswith("instance") and len(normalized) > len("instance"):
        normalized = normalized[len("instance") :]
    if normalized.endswith("service") and len(normalized) > len("service"):
        normalized = normalized[: -len("service")]
    return normalized


def _meaningful_terms(terms: list[str]) -> set[str]:
    ignore = {"my", "why", "the", "is", "in", "for", "last", "min"}
    return {term.lower() for term in terms if len(term) >= 4 and term.lower() not in ignore}


def _summary_from_logs(events: list[LogRecord]) -> SearchSummary:
    ordered = tuple(sorted(events, key=lambda item: item.timestamp))
    entities = tuple(
        {
            "service": log.service,
            "host": log.host,
            "ip": log.ip,
            "node_id": log.node_id() or "",
        }
        for log in _unique_entity_logs(list(ordered))
    )
    signal_counts = {signal: count for signal, count in _count_signals(ordered).items() if signal}
    return SearchSummary(
        events=ordered,
        signal_counts=signal_counts,
        first_seen=ordered[0].timestamp if ordered else None,
        last_seen=ordered[-1].timestamp if ordered else None,
        entities=entities,
    )


def _unique_entity_logs(logs: list[LogRecord]) -> list[LogRecord]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[LogRecord] = []
    for log in logs:
        key = (log.service, log.host, log.ip)
        if key in seen:
            continue
        seen.add(key)
        unique.append(log)
    return unique


def _count_signals(events: tuple[LogRecord, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if not event.signal:
            continue
        counts[event.signal] = counts.get(event.signal, 0) + 1
    return counts


def _hop_summary_text(*, neighbor: TopologyNode, hop_type: str, matched_signal_count: int, used_generic: bool) -> str:
    if used_generic:
        return f"{neighbor.service} produced {matched_signal_count} generic error logs over the {hop_type} path."
    return f"{neighbor.service} produced {matched_signal_count} matched signals over the {hop_type} path."


DEFAULT_RCA_POLICY: dict[str, Any] = {
    "policy_name": "default",
    "signal_evidence_weight": 0.9,
    "generic_evidence_weight": 0.18,
    "chronology_multiplier": 1.0,
    "timing_multiplier": 1.0,
    "domain_alignment_bonus": 0.8,
    "service_alignment_bonus": 0.6,
    "hop_biases": {"upstream": 0.6, "underlay": 0.2, "downstream": -0.15},
    "preferred_dependencies": [],
    "deemphasized_dependencies": [],
    "critic_gap_threshold": 1.15,
    "max_alternate_paths_per_round": 2,
}

DOMAIN_RCA_POLICIES: dict[str, dict[str, Any]] = {
    "gateway": {
        "policy_name": "gateway",
        "generic_evidence_weight": 0.14,
        "chronology_multiplier": 1.1,
        "timing_multiplier": 1.1,
        "hop_biases": {"upstream": 1.0, "underlay": 0.2, "downstream": -0.35},
        "critic_gap_threshold": 1.35,
    },
    "database": {
        "policy_name": "database",
        "signal_evidence_weight": 1.05,
        "generic_evidence_weight": 0.12,
        "chronology_multiplier": 1.15,
        "timing_multiplier": 1.1,
        "hop_biases": {"upstream": 0.75, "underlay": 0.15, "downstream": -0.2},
    },
    "messaging": {
        "policy_name": "messaging",
        "signal_evidence_weight": 1.0,
        "generic_evidence_weight": 0.15,
        "chronology_multiplier": 1.1,
        "timing_multiplier": 1.05,
        "hop_biases": {"upstream": 0.85, "underlay": 0.15, "downstream": -0.2},
    },
}

SERVICE_RCA_POLICIES: dict[str, dict[str, Any]] = {
    "nginx": {
        "policy_name": "nginx_gateway",
        "signal_evidence_weight": 0.95,
        "generic_evidence_weight": 0.12,
        "chronology_multiplier": 1.15,
        "timing_multiplier": 1.15,
        "hop_biases": {"upstream": 1.15, "underlay": 0.2, "downstream": -0.45},
        "preferred_dependencies": ["instancegunicorn"],
        "deemphasized_dependencies": ["network", "system", "auth"],
        "critic_gap_threshold": 1.45,
    },
    "instancegunicorn": {
        "policy_name": "instancegunicorn_backend",
        "signal_evidence_weight": 1.0,
        "generic_evidence_weight": 0.15,
        "chronology_multiplier": 1.2,
        "timing_multiplier": 1.1,
        "hop_biases": {"upstream": 1.0, "underlay": 0.15, "downstream": -0.35},
        "preferred_dependencies": ["mongodb", "postgresql", "redis", "rabbitmq", "kafka"],
        "deemphasized_dependencies": ["network", "system", "auth", "nginx"],
        "critic_gap_threshold": 1.2,
        "max_alternate_paths_per_round": 3,
    },
    "mongodb": {
        "policy_name": "mongodb_database",
        "signal_evidence_weight": 1.1,
        "generic_evidence_weight": 0.1,
        "chronology_multiplier": 1.2,
        "timing_multiplier": 1.15,
    },
    "postgresql": {
        "policy_name": "postgresql_database",
        "signal_evidence_weight": 1.1,
        "generic_evidence_weight": 0.1,
        "chronology_multiplier": 1.2,
        "timing_multiplier": 1.15,
    },
    "redis": {
        "policy_name": "redis_cache",
        "signal_evidence_weight": 1.0,
        "generic_evidence_weight": 0.11,
        "chronology_multiplier": 1.1,
        "timing_multiplier": 1.05,
    },
    "rabbitmq": {
        "policy_name": "rabbitmq_queue",
        "signal_evidence_weight": 1.0,
        "generic_evidence_weight": 0.12,
        "chronology_multiplier": 1.12,
        "timing_multiplier": 1.05,
    },
    "kafka": {
        "policy_name": "kafka_stream",
        "signal_evidence_weight": 1.02,
        "generic_evidence_weight": 0.12,
        "chronology_multiplier": 1.12,
        "timing_multiplier": 1.05,
    },
}

SERVICE_CONTRADICTION_RULES: dict[str, dict[str, Any]] = {
    "nginx": {
        "expected_upstream_services": ["instancegunicorn"],
        "root_keywords": ("upstream", "bad gateway", "gateway timeout", "connection refused", "temporarily disabled", "timeout"),
        "success_patterns": ('" 200 "', '" 201 "', '" 204 "'),
    },
    "instancegunicorn": {
        "root_keywords": ("gunicorn", "worker", "traceback", "timeout", "connection refused", "db", "redis", "rabbitmq", "kafka"),
    },
    "mongodb": {
        "root_keywords": ("slow query", "lock", "maxtime", "replica", "primary stepped down", "stale config", "checkpoint", "connection", "wiredtiger"),
    },
    "postgresql": {
        "root_keywords": ("postgres", "deadlock", "canceling statement", "too many connections", "checkpoint", "relation", "timeout", "database"),
    },
    "rabbitmq": {
        "root_keywords": ("rabbitmq", "queue", "consumer", "channel", "amqp", "connection", "heartbeat", "blocked"),
    },
    "redis": {
        "root_keywords": ("redis", "evicted", "oom", "loading", "replica", "timeout", "connection", "latency"),
    },
    "kafka": {
        "root_keywords": ("kafka", "broker", "partition", "leader", "offset", "replica", "rebalance", "timeout"),
    },
}


def _comparison_summary_payload(summary: SearchSummary) -> dict[str, Any]:
    return {
        "event_count": len(summary.events),
        "matched_signal_count": summary.matched_signal_count,
        "first_seen": summary.first_seen,
        "last_seen": summary.last_seen,
        "top_signals": dict(sorted(summary.signal_counts.items(), key=lambda item: item[1], reverse=True)[:5]),
        "severity_profile": _severity_profile(summary.events),
        "error_keyword_ratio": _error_keyword_ratio(summary.events),
        "message_fingerprint_count": len(_message_fingerprint_set(summary.events)),
        "top_message_fingerprints": _top_message_fingerprints(summary.events),
    }


def _compare_against_healthy_window(
    *,
    incident_summary: SearchSummary,
    baseline_summary: SearchSummary,
    incident_minutes: float,
) -> dict[str, Any]:
    incident_event_count = len(incident_summary.events)
    baseline_event_count = len(baseline_summary.events)
    incident_signal_count = incident_summary.matched_signal_count
    baseline_signal_count = baseline_summary.matched_signal_count
    incident_rate = incident_event_count / max(incident_minutes, 1.0)
    baseline_rate = baseline_event_count / max(incident_minutes, 1.0)
    event_ratio = (incident_event_count + 1.0) / (baseline_event_count + 1.0)
    signal_ratio = (incident_signal_count + 1.0) / (baseline_signal_count + 1.0)
    incident_severity = _severity_weighted_total(incident_summary.events)
    baseline_severity = _severity_weighted_total(baseline_summary.events)
    severity_ratio = (incident_severity + 0.2) / (baseline_severity + 0.2)
    incident_signals = set(incident_summary.signal_counts.keys())
    baseline_signals = set(baseline_summary.signal_counts.keys())
    signal_overlap = len(incident_signals & baseline_signals)
    signal_union = max(len(incident_signals | baseline_signals), 1)
    signal_drift_score = round(1.0 - (signal_overlap / signal_union), 3) if incident_signals or baseline_signals else 0.0
    incident_fingerprints = _message_fingerprint_set(incident_summary.events)
    baseline_fingerprints = _message_fingerprint_set(baseline_summary.events)
    novel_fingerprints = incident_fingerprints - baseline_fingerprints
    message_novelty_score = round(len(novel_fingerprints) / max(len(incident_fingerprints), 1), 3) if incident_fingerprints else 0.0
    incident_error_ratio = _error_keyword_ratio(incident_summary.events)
    baseline_error_ratio = _error_keyword_ratio(baseline_summary.events)
    error_keyword_delta = max(0.0, round(incident_error_ratio - baseline_error_ratio, 3))
    components = {
        "event_component": round(min(max((event_ratio - 1.0) / 5.0, 0.0), 1.0) * 0.28, 3),
        "signal_component": round(min(max((signal_ratio - 1.0) / 4.0, 0.0), 1.0) * 0.24, 3),
        "severity_component": round(min(max((severity_ratio - 1.0) / 3.0, 0.0), 1.0) * 0.18, 3),
        "signal_drift_component": round(signal_drift_score * 0.15, 3),
        "message_novelty_component": round(message_novelty_score * 0.1, 3),
        "error_keyword_component": round(min(error_keyword_delta, 1.0) * 0.05, 3),
    }
    anomaly_score = round(min(max(sum(float(item) for item in components.values()), 0.0), 1.0), 3)
    return {
        "incident_event_rate": round(incident_rate, 3),
        "healthy_event_rate": round(baseline_rate, 3),
        "event_ratio": round(event_ratio, 3),
        "signal_ratio": round(signal_ratio, 3),
        "severity_ratio": round(severity_ratio, 3),
        "signal_drift_score": signal_drift_score,
        "message_novelty_score": message_novelty_score,
        "error_keyword_delta": error_keyword_delta,
        "incident_event_count": incident_event_count,
        "healthy_event_count": baseline_event_count,
        "incident_signal_count": incident_signal_count,
        "healthy_signal_count": baseline_signal_count,
        "components": components,
        "anomaly_score": anomaly_score,
    }


def _severity_weight(severity: str | None) -> float:
    normalized = (severity or "").strip().lower()
    if normalized in {"critical", "fatal", "panic", "emerg"}:
        return 1.0
    if normalized in {"error", "err"}:
        return 0.8
    if normalized in {"warn", "warning"}:
        return 0.5
    if normalized in {"notice", "info"}:
        return 0.2
    if normalized in {"debug", "trace"}:
        return 0.05
    return 0.1


def _severity_weighted_total(events: tuple[LogRecord, ...]) -> float:
    return round(sum(_severity_weight(item.severity) for item in events), 3)


def _severity_profile(events: tuple[LogRecord, ...]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in events:
        key = (item.severity or "unknown").strip().lower() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return {
        "counts": counts,
        "weighted_total": _severity_weighted_total(events),
    }


def _normalize_message_fingerprint(message: str) -> str:
    text = (message or "").strip().lower()
    text = re.sub(r"\b\d+\b", "<num>", text)
    text = re.sub(r"[0-9a-f]{8,}", "<hex>", text)
    text = re.sub(r"\s+", " ", text)
    return text[:160]


def _message_fingerprint_set(events: tuple[LogRecord, ...]) -> set[str]:
    return {
        fingerprint
        for fingerprint in (_normalize_message_fingerprint(item.message) for item in events)
        if fingerprint
    }


def _top_message_fingerprints(events: tuple[LogRecord, ...], limit: int = 5) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in events:
        fingerprint = _normalize_message_fingerprint(item.message)
        if not fingerprint:
            continue
        counts[fingerprint] = counts.get(fingerprint, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [{"fingerprint": fingerprint, "count": count} for fingerprint, count in ordered[:limit]]


def _error_keyword_ratio(events: tuple[LogRecord, ...]) -> float:
    if not events:
        return 0.0
    matched = 0
    for item in events:
        text = (item.message or "").lower()
        if any(keyword in text for keyword in GENERIC_ERROR_KEYWORDS):
            matched += 1
    return round(matched / max(len(events), 1), 3)


def _deep_merge_policy(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _service_rca_policy(service: str | None, domain: str | None) -> dict[str, Any]:
    policy = dict(DEFAULT_RCA_POLICY)
    if domain and domain in DOMAIN_RCA_POLICIES:
        policy = _deep_merge_policy(policy, DOMAIN_RCA_POLICIES[domain])
    service_key = (service or "").strip().lower()
    if service_key and service_key in SERVICE_RCA_POLICIES:
        policy = _deep_merge_policy(policy, SERVICE_RCA_POLICIES[service_key])
    policy["preferred_dependencies"] = list(policy.get("preferred_dependencies", []))
    policy["deemphasized_dependencies"] = list(policy.get("deemphasized_dependencies", []))
    return policy


def _service_contradiction_profile(service: str | None) -> dict[str, Any]:
    return dict(SERVICE_CONTRADICTION_RULES.get((service or "").strip().lower(), {}))


def _public_service_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_name": policy.get("policy_name"),
        "signal_evidence_weight": policy.get("signal_evidence_weight"),
        "generic_evidence_weight": policy.get("generic_evidence_weight"),
        "chronology_multiplier": policy.get("chronology_multiplier"),
        "timing_multiplier": policy.get("timing_multiplier"),
        "hop_biases": dict(policy.get("hop_biases", {})),
        "preferred_dependencies": list(policy.get("preferred_dependencies", [])),
        "deemphasized_dependencies": list(policy.get("deemphasized_dependencies", [])),
        "critic_gap_threshold": policy.get("critic_gap_threshold"),
    }


def _hop_uses_generic(hop: HopSearchResult) -> bool:
    return any(signal.startswith("generic_") for signal in hop.signals) or "generic error logs" in hop.summary.lower()


def _should_run_topology_candidate_critic(round_candidates: list[dict[str, Any]], service_policy: dict[str, Any]) -> bool:
    supported = [item for item in round_candidates if item.get("status") != "rejected"]
    if len(supported) < 2:
        return False
    ordered = sorted(supported, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    gap_threshold = float(service_policy.get("critic_gap_threshold", 1.15) or 1.15)
    top_gap = float(ordered[0].get("score") or 0.0) - float(ordered[1].get("score") or 0.0)
    top_is_generic = bool(ordered[0].get("used_generic"))
    has_mixed_chronology = any(not bool(item.get("chronology_ok")) for item in ordered[:2])
    return top_gap <= gap_threshold or top_is_generic or has_mixed_chronology


def _validate_topology_candidate_critic(
    payload: dict[str, Any] | None,
    *,
    round_candidates: list[dict[str, Any]],
    scored_best_node_id: str | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"accepted": False, "reason": "The topology candidate critic returned no structured payload."}
    verdict = str(payload.get("verdict") or "").strip()
    supported_ids = {
        str(item.get("node_id"))
        for item in round_candidates
        if isinstance(item, dict) and item.get("status") != "rejected" and item.get("node_id")
    }
    selected_node_id = _optional_text(payload.get("selected_node_id"))
    if verdict == "keep_scored_best":
        return {
            "accepted": True,
            "reason": None,
            "selected_node_id": scored_best_node_id,
            "score_adjustment": float(payload.get("score_adjustment") or 0.0),
        }
    if verdict == "select_alternate":
        if not selected_node_id or selected_node_id not in supported_ids:
            return {"accepted": False, "reason": "The topology candidate critic selected a node outside the supported candidate set."}
        return {
            "accepted": True,
            "reason": None,
            "selected_node_id": selected_node_id,
            "score_adjustment": float(payload.get("score_adjustment") or 0.0),
        }
    return {"accepted": False, "reason": "The topology candidate critic was inconclusive."}


def _choose_topology_round_winner(
    *,
    critic_generator: CriticGenerator,
    query: str,
    current_node: TopologyNode,
    depth_index: int,
    service_policy: dict[str, Any],
    candidate_results: dict[str, HopSearchResult],
    round_candidates: list[dict[str, Any]],
    best: HopSearchResult | None,
) -> tuple[HopSearchResult | None, dict[str, Any] | None]:
    if not best or not _should_run_topology_candidate_critic(round_candidates, service_policy):
        return best, None

    supported = [item for item in round_candidates if item.get("status") != "rejected"]
    supported.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    critic_payload = critic_generator.review_topology_candidates(
        {
            "query": query,
            "source_node": {
                "node_id": current_node.node_id,
                "service": current_node.service,
                "domain": current_node.domain,
            },
            "round_depth": depth_index,
            "service_policy": _public_service_policy(service_policy),
            "scored_best_node_id": best.target_node_id,
            "candidates": [
                {
                    "node_id": item.get("node_id"),
                    "service": item.get("service"),
                    "domain": item.get("domain"),
                    "hop_type": item.get("hop_type"),
                    "status": item.get("status"),
                    "matched_signal_count": item.get("matched_signal_count"),
                    "signalized_match_count": item.get("signalized_match_count"),
                    "event_count": item.get("event_count"),
                    "chronology_ok": item.get("chronology_ok"),
                    "used_generic": item.get("used_generic"),
                    "score": item.get("score"),
                    "score_breakdown": item.get("score_breakdown"),
                }
                for item in supported[:5]
            ],
        }
    )
    validated = _validate_topology_candidate_critic(
        critic_payload if isinstance(critic_payload, dict) else None,
        round_candidates=round_candidates,
        scored_best_node_id=best.target_node_id,
    )
    review = {
        "invoked": True,
        "accepted": bool(validated.get("accepted")),
        "reason": validated.get("reason"),
        "verdict": (critic_payload or {}).get("verdict") if isinstance(critic_payload, dict) else None,
        "selected_node_id": validated.get("selected_node_id"),
        "reasoning": (critic_payload or {}).get("reasoning") if isinstance(critic_payload, dict) else None,
        "risk_note": (critic_payload or {}).get("risk_note") if isinstance(critic_payload, dict) else None,
        "request": (critic_payload or {}).get("request") if isinstance(critic_payload, dict) else None,
        "response": critic_payload,
    }
    if not validated.get("accepted"):
        return best, review

    selected_node_id = str(validated["selected_node_id"])
    score_adjustment = float(validated.get("score_adjustment") or 0.0)
    for item in round_candidates:
        if not isinstance(item, dict) or item.get("node_id") != selected_node_id:
            continue
        item["critic_adjustment"] = round(score_adjustment, 3)
        item["score"] = round(float(item.get("score") or 0.0) + score_adjustment, 3)
        item["critic_reasoning"] = review["reasoning"]
        break
    if selected_node_id in candidate_results:
        best = candidate_results[selected_node_id]
    return best, review


def _retain_alternate_paths(
    *,
    round_candidates: list[dict[str, Any]],
    selected_node_id: str | None,
    depth: int,
    source_node_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    alternates: list[dict[str, Any]] = []
    for item in round_candidates:
        if not isinstance(item, dict):
            continue
        if item.get("status") == "rejected" or item.get("node_id") == selected_node_id:
            continue
        alternates.append(
            {
                "depth": depth,
                "source_node_id": source_node_id,
                "target_node_id": item.get("node_id"),
                "service": item.get("service"),
                "domain": item.get("domain"),
                "hop_type": item.get("hop_type"),
                "score": item.get("score"),
                "matched_signal_count": item.get("matched_signal_count"),
                "signalized_match_count": item.get("signalized_match_count"),
                "chronology_ok": item.get("chronology_ok"),
                "used_generic": item.get("used_generic"),
                "status": item.get("status"),
                "why_not_selected": item.get("rejection_reason") or "Another candidate scored higher in this round.",
            }
        )
    alternates.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return alternates[:limit]


def _service_rule_hit(
    *,
    rule_id: str,
    service: str,
    severity: str,
    message: str,
    evidence_basis: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "service": service,
        "severity": severity,
        "message": message,
        "evidence_basis": list(evidence_basis or []),
    }


def _selected_node_inspection_logs(topology_walk: dict[str, Any], node_id: str | None) -> list[dict[str, Any]]:
    if not node_id:
        return []
    inspections = topology_walk.get("node_inspections")
    if not isinstance(inspections, list):
        return []
    for item in inspections:
        if not isinstance(item, dict):
            continue
        if item.get("node_id") != node_id or item.get("status") != "validated":
            continue
        fetched_logs = item.get("fetched_logs")
        if isinstance(fetched_logs, list):
            return [log for log in fetched_logs if isinstance(log, dict)]
    return []


def _log_messages_from_records(records: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for item in records:
        message = item.get("message")
        if isinstance(message, str) and message.strip():
            messages.append(message.strip())
    return messages


def _contains_keywords(texts: list[str], keywords: tuple[str, ...]) -> bool:
    haystack = " ".join(texts).lower()
    return any(keyword in haystack for keyword in keywords)


def _count_matching_patterns(texts: list[str], patterns: tuple[str, ...]) -> int:
    count = 0
    lowered = [item.lower() for item in texts]
    for text in lowered:
        if any(pattern in text for pattern in patterns):
            count += 1
    return count


def _build_service_specific_contradictions(
    *,
    impacted_service: str | None,
    root_service: str | None,
    root_node_id: str | None,
    first_circle: SearchSummary,
    hops: list[HopSearchResult],
    topology_walk: dict[str, Any],
    raw_context: list[str],
    alternate_paths: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    root_service_name = (root_service or impacted_service or "").strip().lower()
    impacted_service_name = (impacted_service or "").strip().lower()
    root_profile = _service_contradiction_profile(root_service_name)
    impacted_profile = _service_contradiction_profile(impacted_service_name)

    first_circle_messages = [item.message for item in first_circle.events if item.message]
    root_logs = _selected_node_inspection_logs(topology_walk, root_node_id)
    root_messages = _log_messages_from_records(root_logs)
    combined_root_text = root_messages + raw_context[:8]

    if impacted_service_name == "nginx":
        success_patterns = tuple(impacted_profile.get("success_patterns", ()))
        success_count = _count_matching_patterns(first_circle_messages, success_patterns)
        if first_circle.events and success_count >= max(1, len(first_circle.events) // 2) and first_circle.matched_signal_count == 0:
            hits.append(
                _service_rule_hit(
                    rule_id="nginx_success_traffic_without_failure_signal",
                    service="nginx",
                    severity="high",
                    message="The nginx first-circle evidence is dominated by successful access traffic without corroborating failure signals, so the scoped impact may include normal traffic noise.",
                    evidence_basis=["first_circle_events", "missing_signalized_nginx_failure"],
                )
            )
        expected_upstreams = list(impacted_profile.get("expected_upstream_services", []))
        if hops:
            immediate_upstream = hops[0].service.strip().lower() if hops[0].service else ""
            if expected_upstreams and immediate_upstream not in expected_upstreams:
                hits.append(
                    _service_rule_hit(
                        rule_id="nginx_unexpected_upstream_root_path",
                        service="nginx",
                        severity="medium",
                        message=f"The selected nginx path did not validate the expected immediate upstream dependency set {expected_upstreams}; current hop is {immediate_upstream or 'unknown'}.",
                        evidence_basis=["validated_hops", "expected_nginx_upstream"],
                    )
                )
        elif first_circle.events:
            hits.append(
                _service_rule_hit(
                    rule_id="nginx_no_upstream_corroboration",
                    service="nginx",
                    severity="medium",
                    message="Nginx showed impact-local activity, but no upstream corroboration was validated, so the conclusion remains symptom-heavy.",
                    evidence_basis=["first_circle_events", "no_validated_upstream_hop"],
                )
            )

    if root_service_name:
        root_keywords = tuple(root_profile.get("root_keywords", ()))
        if root_keywords and root_node_id and not _contains_keywords(combined_root_text, root_keywords):
            hits.append(
                _service_rule_hit(
                    rule_id=f"{root_service_name}_missing_service_specific_symptoms",
                    service=root_service_name,
                    severity="medium",
                    message=f"The selected {root_service_name} root-cause path lacks clear service-specific symptom language in the fetched logs or raw context.",
                    evidence_basis=["validated_node_logs", "raw_context"],
                )
            )

    if hops:
        deepest_hop = hops[-1]
        if _hop_uses_generic(deepest_hop):
            hits.append(
                _service_rule_hit(
                    rule_id="generic_only_deepest_root_path",
                    service=root_service_name or deepest_hop.service,
                    severity="medium",
                    message="The deepest selected root-cause node is supported primarily by generic error evidence rather than strong service-specific signals.",
                    evidence_basis=["generic_root_hop", "weak_signalization"],
                )
            )

    if alternate_paths:
        top_alternate = max(alternate_paths, key=lambda item: float(item.get("score") or 0.0))
        selected_score = 0.0
        if hops:
            selected_score = float(
                next(
                    (
                        candidate.get("score")
                        for round_item in topology_walk.get("topology_comparison_rounds", [])
                        if isinstance(round_item, dict)
                        for candidate in round_item.get("candidates", [])
                        if isinstance(candidate, dict) and candidate.get("node_id") == hops[-1].target_node_id and candidate.get("status") == "validated"
                    ),
                    0.0,
                )
            )
        if float(top_alternate.get("score") or 0.0) >= max(selected_score - 0.75, 0.0):
            hits.append(
                _service_rule_hit(
                    rule_id="alternate_path_competition",
                    service=root_service_name or impacted_service_name or "unknown",
                    severity="low",
                    message=f"An alternate path to {top_alternate.get('target_node_id')} remained competitively scored, so the selected branch should be treated as the best current explanation rather than the only plausible one.",
                    evidence_basis=["alternate_paths", "topology_comparison_rounds"],
                )
            )

    return hits


def _apply_service_contradiction_adjustment(
    *,
    confidence: float,
    classification: str,
    confidence_breakdown: dict[str, Any],
    rule_hits: list[dict[str, Any]],
) -> tuple[float, str, dict[str, Any]]:
    if not rule_hits:
        adjusted = dict(confidence_breakdown)
        adjusted["service_contradiction_penalty"] = 0.0
        adjusted["service_contradiction_rule_count"] = 0
        adjusted["final_confidence"] = confidence
        return confidence, classification, adjusted
    severity_weights = {"high": 0.05, "medium": 0.03, "low": 0.015}
    penalty = round(min(sum(severity_weights.get(str(item.get("severity")), 0.02) for item in rule_hits), 0.12), 3)
    adjusted = dict(confidence_breakdown)
    confidence = round(max(0.02, confidence - penalty), 2)
    if penalty >= 0.06 and classification == "confirmed_rca":
        classification = "probable_cause"
    elif penalty >= 0.09 and classification == "probable_cause":
        classification = "insufficient_evidence"
    adjusted["service_contradiction_penalty"] = penalty
    adjusted["service_contradiction_rule_count"] = len(rule_hits)
    adjusted["final_confidence"] = confidence
    return confidence, classification, adjusted
    anomaly_score = round(min(max(sum(float(item) for item in components.values()), 0.0), 1.0), 3)
    return {
        "incident_event_rate": round(incident_rate, 3),
        "healthy_event_rate": round(baseline_rate, 3),
        "event_ratio": round(event_ratio, 3),
        "signal_ratio": round(signal_ratio, 3),
        "severity_ratio": round(severity_ratio, 3),
        "signal_drift_score": signal_drift_score,
        "message_novelty_score": message_novelty_score,
        "error_keyword_delta": error_keyword_delta,
        "incident_event_count": incident_event_count,
        "healthy_event_count": baseline_event_count,
        "incident_signal_count": incident_signal_count,
        "healthy_signal_count": baseline_signal_count,
        "components": components,
        "anomaly_score": anomaly_score,
    }


def _score_topology_candidate(
    *,
    neighbor: TopologyNode,
    current_node: TopologyNode,
    hop_type: str,
    matched_signal_count: int,
    signalized_match_count: int,
    event_count: int,
    chronology_ok: bool,
    first_seen: str | None,
    current_first_seen: str,
    used_generic: bool,
    parsed: QueryIntent,
    policy: dict[str, Any],
) -> dict[str, float | bool | str | None]:
    explicit_signal_weight = min(float(signalized_match_count) * float(policy["signal_evidence_weight"]), 5.5)
    generic_event_weight = 0.0
    if used_generic or signalized_match_count == 0:
        generic_event_weight = min(float(max(event_count, matched_signal_count)) * float(policy["generic_evidence_weight"]), 1.8)
    chronology_bonus = (3.0 if chronology_ok else -1.0) * float(policy["chronology_multiplier"])
    timing_bonus = 0.0
    if first_seen and first_seen < current_first_seen:
        delta_minutes = max((parse_utc(current_first_seen) - parse_utc(first_seen)).total_seconds() / 60.0, 0.0)
        timing_bonus = min(delta_minutes / 3.0, 3.0) * float(policy["timing_multiplier"])
    generic_penalty = -0.5 if used_generic and signalized_match_count == 0 else 0.0
    domain_alignment = 0.0
    if parsed.domain_hint and neighbor.domain and parsed.domain_hint == neighbor.domain:
        domain_alignment = float(policy["domain_alignment_bonus"])
    elif parsed.domain_hint and current_node.domain and parsed.domain_hint == current_node.domain:
        domain_alignment = 0.25
    service_alignment = 0.0
    neighbor_identity = " ".join(
        [neighbor.service, neighbor.host or "", neighbor.ip or "", " ".join(neighbor.aliases)]
    ).lower()
    if any(term for term in parsed.search_terms if term and term.lower() in neighbor_identity):
        service_alignment = float(policy["service_alignment_bonus"])
    dependency_bias = 0.0
    if neighbor.service in set(policy.get("preferred_dependencies", [])):
        dependency_bias += 0.75
    if neighbor.service in set(policy.get("deemphasized_dependencies", [])):
        dependency_bias -= 0.75
    hop_priority = float(policy["hop_biases"].get(hop_type, 0.0))
    total_score = round(
        explicit_signal_weight
        + generic_event_weight
        + chronology_bonus
        + timing_bonus
        + generic_penalty
        + domain_alignment
        + service_alignment
        + dependency_bias
        + hop_priority,
        3,
    )
    return {
        "explicit_signal_weight": round(explicit_signal_weight, 3),
        "generic_event_weight": round(generic_event_weight, 3),
        "chronology_bonus": round(chronology_bonus, 3),
        "timing_bonus": round(timing_bonus, 3),
        "generic_penalty": round(generic_penalty, 3),
        "domain_alignment": round(domain_alignment, 3),
        "service_alignment": round(service_alignment, 3),
        "dependency_bias": round(dependency_bias, 3),
        "hop_priority": round(hop_priority, 3),
        "policy_name": str(policy["policy_name"]),
        "total_score": total_score,
        "used_generic": used_generic,
    }


def _score_and_classify(
    first_circle: SearchSummary,
    hops: list[HopSearchResult],
    rejected_paths: list[str],
    raw_context: list[str],
) -> tuple[float, str, dict[str, Any]]:
    dominant_signal_count = max(first_circle.signal_counts.values(), default=0)
    current_service = first_circle.events[0].service if first_circle.events else (hops[0].service if hops else None)
    policy = _service_rca_policy(current_service, None)
    evidence_base = 0.22 if first_circle.events else 0.05
    explicit_signal_support = first_circle.matched_signal_count + sum(
        hop.matched_signal_count for hop in hops if not _hop_uses_generic(hop)
    )
    generic_log_support = (len(first_circle.events) if first_circle.matched_signal_count == 0 else 0) + sum(
        hop.matched_signal_count for hop in hops if _hop_uses_generic(hop)
    )
    explicit_signal_weight = min(explicit_signal_support * 0.028 * float(policy["signal_evidence_weight"]), 0.34)
    generic_log_weight = min(generic_log_support * 0.012 * max(float(policy["generic_evidence_weight"]), 0.1), 0.12)
    if dominant_signal_count >= 2:
        evidence_base += 0.18

    chronology_score = sum(0.07 * float(policy["chronology_multiplier"]) for hop in hops if hop.chronology_ok)
    topology_inference_weight = min(len(hops) * 0.11, 0.33)
    raw_context_bonus = 0.04 if raw_context else 0.0
    contradiction_penalty = min(len(rejected_paths) * 0.04, 0.16)
    confidence = round(
        max(
            0.02,
            min(
                evidence_base
                + explicit_signal_weight
                + generic_log_weight
                + chronology_score
                + topology_inference_weight
                + raw_context_bonus
                - contradiction_penalty,
                0.96,
            ),
        ),
        2,
    )

    if not first_circle.events:
        classification = "insufficient_evidence"
    elif confidence >= 0.85 and len(hops) >= 2:
        classification = "confirmed_rca"
    elif confidence >= 0.5:
        classification = "probable_cause"
    else:
        classification = "insufficient_evidence"
    breakdown = {
        "evidence_base": round(evidence_base, 3),
        "signalization_score": round(min(first_circle.matched_signal_count * 0.04, 0.2), 3),
        "explicit_signal_weight": round(explicit_signal_weight, 3),
        "generic_log_weight": round(generic_log_weight, 3),
        "chronology_score": round(chronology_score, 3),
        "topology_score": round(topology_inference_weight, 3),
        "raw_context_bonus": round(raw_context_bonus, 3),
        "baseline_anomaly_weight": 0.0,
        "critic_adjustment": 0.0,
        "service_policy": str(policy["policy_name"]),
        "evidence_source_weights": {
            "explicit_signals": round(explicit_signal_weight, 3),
            "generic_logs": round(generic_log_weight, 3),
            "topology_inference": round(topology_inference_weight, 3),
            "raw_context": round(raw_context_bonus, 3),
        },
        "contradiction_penalty": round(contradiction_penalty, 3),
        "final_confidence": confidence,
    }
    return confidence, classification, breakdown


def _apply_healthy_window_adjustment(
    *,
    confidence: float,
    classification: str,
    confidence_breakdown: dict[str, Any],
    healthy_window: dict[str, Any] | None,
) -> tuple[float, str, dict[str, Any]]:
    if not healthy_window:
        return confidence, classification, confidence_breakdown
    comparison = healthy_window.get("comparison") if isinstance(healthy_window.get("comparison"), dict) else {}
    anomaly_score = float(comparison.get("anomaly_score") or 0.0)
    adjusted = dict(confidence_breakdown)
    if anomaly_score < 0.35:
        confidence = round(max(0.02, confidence - 0.08), 2)
        adjusted["healthy_window_adjustment"] = -0.08
        adjusted["baseline_anomaly_weight"] = -0.08
        if classification == "confirmed_rca":
            classification = "probable_cause"
    elif anomaly_score >= 0.7:
        confidence = round(min(0.96, confidence + 0.06), 2)
        adjusted["healthy_window_adjustment"] = 0.06
        adjusted["baseline_anomaly_weight"] = 0.06
    elif anomaly_score >= 0.5:
        confidence = round(min(0.96, confidence + 0.02), 2)
        adjusted["healthy_window_adjustment"] = 0.02
        adjusted["baseline_anomaly_weight"] = 0.02
    else:
        adjusted["healthy_window_adjustment"] = 0.0
        adjusted["baseline_anomaly_weight"] = 0.0
    adjusted["final_confidence"] = confidence
    return confidence, classification, adjusted


def _apply_critic_adjustment(
    *,
    confidence: float,
    classification: str,
    confidence_breakdown: dict[str, Any],
    critic_pass: dict[str, Any] | None,
) -> tuple[float, str, dict[str, Any]]:
    critic_payload = (critic_pass or {}).get("critic") if isinstance(critic_pass, dict) else None
    if not isinstance(critic_payload, dict):
        return confidence, classification, confidence_breakdown
    delta = float(critic_payload.get("confidence_delta") or 0.0)
    adjusted = dict(confidence_breakdown)
    confidence = round(max(0.02, min(confidence + delta, 0.96)), 2)
    adjusted["critic_adjustment"] = round(delta, 3)
    recommended = critic_payload.get("recommended_classification")
    if isinstance(recommended, str) and recommended:
        classification = recommended
    adjusted["final_confidence"] = confidence
    return confidence, classification, adjusted


def _build_timeline(impacted_label: str, first_circle: SearchSummary, hops: list[HopSearchResult]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    if first_circle.first_seen:
        timeline.append(
            {
                "timestamp": first_circle.first_seen,
                "event": f"{'Impact' if first_circle.matched_signal_count else 'Activity'} observed on {impacted_label}",
                "evidence_ids": [log.doc_id for log in first_circle.events[:3]],
            }
        )
    for hop in hops:
        if not hop.first_seen:
            continue
        timeline.append(
            {
                "timestamp": hop.first_seen,
                "event": f"{hop.hop_type.capitalize()} evidence on {hop.target_node_id}: {hop.summary}",
                "evidence_ids": list(hop.event_ids[:3]),
            }
        )
    timeline.sort(key=lambda item: item["timestamp"])
    return timeline


def _build_supporting_evidence(impacted_label: str, first_circle: SearchSummary, hops: list[HopSearchResult]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if first_circle.events:
        if first_circle.matched_signal_count:
            claim = f"The impacted node {impacted_label} emitted the strongest visible symptom signals in the first circle."
        else:
            claim = f"Logs were observed on the impacted node {impacted_label}, but no candidate signal family matched directly in the first circle."
        evidence.append(
            {
                "claim": claim,
                "evidence_ids": [log.doc_id for log in first_circle.events[:4]],
            }
        )

    previous_label = impacted_label
    previous_ids = [log.doc_id for log in first_circle.events[:2]]
    for hop in hops:
        evidence.append(
            {
                "claim": f"{hop.target_node_id} showed earlier {hop.hop_type} evidence before the failure surfaced on {previous_label}.",
                "evidence_ids": list(dict.fromkeys(list(hop.event_ids[:3]) + previous_ids)),
            }
        )
        previous_label = hop.target_node_id
        previous_ids = list(hop.event_ids[:2])
    return evidence


def _build_evidence_logs(first_circle: SearchSummary, limit: int = 40) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for log in first_circle.events[:limit]:
        rows.append(
            {
                "timestamp": log.timestamp,
                "service": log.service or "",
                "host": log.host or "",
                "ip": log.ip or "",
                "severity": log.severity or "",
                "signal": log.signal or "-",
                "message": _truncate(log.message, 220),
                "doc_id": log.doc_id,
            }
        )
    return rows


def _build_summary(likely_root_cause: str, impacted_label: str, hops: list[HopSearchResult], classification: str) -> str:
    if not hops:
        return f"The investigator found incident evidence on {impacted_label}, but the strongest explanation remains local to that impacted node: {likely_root_cause}."
    path_text = " -> ".join([hop.target_node_id for hop in reversed(hops)] + [impacted_label])
    confidence_text = "confirmed" if classification == "confirmed_rca" else "probable"
    return f"The {confidence_text} incident path is {path_text}, with the deepest supported cause centered on {likely_root_cause}."


def _fallback_root_cause(first_circle: SearchSummary, impacted_label: str) -> str:
    if not first_circle.signal_counts:
        return f"insufficient evidence near {impacted_label}"
    signal, count = max(first_circle.signal_counts.items(), key=lambda item: item[1])
    return f"{signal} on {impacted_label} ({count} matches)"


def _entity_label(service: str | None, host: str | None, ip: str | None) -> str:
    service_part = service or "unknown-service"
    entity_part = ip or host or "unknown-entity"
    return f"{entity_part}::{service_part}"


def _first_value(items: list[dict[str, str | int]], key: str) -> str | None:
    if not items:
        return None
    value = items[0].get(key)
    return str(value) if value else None


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _clear_debug_queries(log_store: LogStore) -> None:
    clear_fn = getattr(log_store, "clear_debug_queries", None)
    if callable(clear_fn):
        clear_fn()


def _consume_debug_queries(log_store: LogStore) -> list[dict[str, Any]]:
    consume_fn = getattr(log_store, "consume_debug_queries", None)
    if callable(consume_fn):
        payload = consume_fn()
        if isinstance(payload, list):
            return payload
    return []


def _mark_selected_round_inspections(inspections: list[dict[str, Any]], best: HopSearchResult | None) -> None:
    if not inspections:
        return
    selected_node_id = best.target_node_id if best else None
    for item in inspections:
        if item.get("status") != "candidate":
            continue
        if item.get("node_id") == selected_node_id:
            item["status"] = "validated"
        else:
            item["status"] = "considered_not_selected"


def _mark_selected_round_comparison(candidates: list[dict[str, Any]], best: HopSearchResult | None) -> None:
    if not candidates:
        return
    selected_node_id = best.target_node_id if best else None
    for item in candidates:
        if item.get("status") == "rejected":
            continue
        if item.get("node_id") == selected_node_id:
            item["status"] = "validated"
        else:
            item["status"] = "considered_not_selected"


def _topology_graph_to_dict(topology: Any, impacted_node: TopologyNode | None, hops: list[HopSearchResult]) -> dict[str, Any]:
    path_depths: dict[str, int] = {}
    if impacted_node:
        path_depths[impacted_node.node_id] = 0
    for depth_index, hop in enumerate(hops, start=1):
        path_depths[hop.target_node_id] = depth_index

    nodes = []
    for node in topology.nodes():
        nodes.append(
            {
                "node_id": node.node_id,
                "service": node.service,
                "host": node.host,
                "ip": node.ip,
                "domain": node.domain,
                "aliases": list(node.aliases),
                "node_type": node.node_type,
                "platform": node.platform,
                "tier": node.tier,
                "role": node.role,
                "criticality": node.criticality,
                "path_depth": path_depths.get(node.node_id),
                "is_impacted": bool(impacted_node and node.node_id == impacted_node.node_id),
            }
        )

    validated_pairs = {frozenset({hop.source_node_id, hop.target_node_id}) for hop in hops}
    edges: list[dict[str, Any]] = []
    for edge in topology.edges():
        graph_edge = _topology_edge_to_dict(edge, validated_pairs)
        if graph_edge:
            edges.append(graph_edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "validated_path": [impacted_node.node_id] + [hop.target_node_id for hop in hops] if impacted_node else [],
    }


def _topology_edge_to_dict(edge: TopologyEdge, validated_pairs: set[frozenset[str]]) -> dict[str, Any]:
    relation_type = edge.relation_type.strip().lower()
    if relation_type == "underlay":
        label = "underlay"
        semantic_relation = "underlay"
        description = f"{edge.from_node_id} relies on the underlay path through {edge.to_node_id}."
        graphviz_dir = "forward"
        relation = "underlay"
    else:
        label = "depends on"
        semantic_relation = "depends_on"
        description = f"{edge.from_node_id} depends on {edge.to_node_id}."
        graphviz_dir = "forward"
        relation = "depends_on"

    return {
        "edge_id": edge.edge_id,
        "source": edge.from_node_id,
        "target": edge.to_node_id,
        "relation": relation,
        "relation_type": edge.relation_type,
        "relation_label": edge.relation_label,
        "label": label,
        "semantic_relation": semantic_relation,
        "description": description,
        "graphviz_dir": graphviz_dir,
        "is_bidirectional": False,
        "weight": edge.weight,
        "criticality": edge.criticality,
        "source_refs": list(edge.source_refs),
        "is_validated_path": frozenset({edge.from_node_id, edge.to_node_id}) in validated_pairs,
    }


def _context_service(scope_service: str | None, first_circle: SearchSummary) -> str | None:
    if scope_service:
        return scope_service
    if first_circle.entities:
        service = first_circle.entities[0].get("service")
        if service:
            return str(service)
    if first_circle.events:
        service = first_circle.events[0].service
        if service:
            return service
    return None


def _build_scope_resolution_candidates(
    *,
    query: str,
    parsed: QueryIntent,
    memory: dict[str, Any],
    topology: Any,
    explicit_service: str | None,
    explicit_host: str | None,
    explicit_ip: str | None,
) -> dict[str, Any]:
    service_hint = explicit_service or parsed.service_hint
    host_hint = explicit_host or parsed.host_hint
    ip_hint = explicit_ip or parsed.ip_hint

    candidate_nodes: list[TopologyNode] = []
    candidate_nodes.extend(topology.nodes_for_ip(ip_hint))
    candidate_nodes.extend(topology.nodes_for_host(host_hint))
    candidate_nodes.extend(topology.nodes_for_service(service_hint))

    fuzzy_services = _fuzzy_service_candidates(query, topology.known_services())
    for service_name in fuzzy_services:
        candidate_nodes.extend(topology.nodes_for_service(service_name))

    if parsed.domain_hint:
        candidate_nodes.extend(topology.nodes_for_domain(parsed.domain_hint))

    candidate_nodes = _unique_nodes(candidate_nodes)[:8]
    candidate_services = _unique_strings([node.service for node in candidate_nodes])[:10]
    if not candidate_services:
        candidate_services = _fuzzy_service_candidates(query, topology.known_services())[:10]

    candidate_hosts = _unique_strings([node.host for node in candidate_nodes if node.host])[:8]
    candidate_ips = _unique_strings([node.ip for node in candidate_nodes if node.ip])[:8]

    return {
        "query": parsed.raw_query,
        "deterministic_hints": {
            "service": parsed.service_hint,
            "host": parsed.host_hint,
            "ip": parsed.ip_hint,
            "domain": parsed.domain_hint,
            "time_phrase": parsed.time_phrase,
            "vague": parsed.vague,
        },
        "thread_memory": {
            "service": _optional_text(memory.get("service")),
            "host": _optional_text(memory.get("host")),
            "ip": _optional_text(memory.get("ip")),
            "last_impacted_node": _optional_text(memory.get("last_impacted_node")),
        },
        "candidate_services": candidate_services,
        "candidate_hosts": candidate_hosts,
        "candidate_ips": candidate_ips,
        "candidate_nodes": [
            {
                "node_id": node.node_id,
                "service": node.service,
                "host": node.host,
                "ip": node.ip,
                "domain": node.domain,
                "aliases": list(node.aliases[:3]),
            }
            for node in candidate_nodes
        ],
    }


def _select_anchor_signal_set(
    candidate_signals: list[dict[str, Any]],
    candidate_signal_names: list[str],
    *,
    score_threshold: float = 10.0,
) -> list[str]:
    selected: list[str] = []
    selected_set: set[str] = set()
    for item in candidate_signals:
        signal = _optional_text(item.get("signal"))
        if not signal:
            continue
        try:
            score = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score < score_threshold:
            continue
        if signal in selected_set:
            continue
        selected.append(signal)
        selected_set.add(signal)

    if selected:
        return selected

    ordered_fallback: list[str] = []
    seen: set[str] = set()
    for signal in candidate_signal_names:
        if not signal or signal in seen:
            continue
        seen.add(signal)
        ordered_fallback.append(signal)
    return ordered_fallback[:5]


def _should_invoke_scope_resolution(
    *,
    parsed: QueryIntent,
    memory: dict[str, Any],
    topology: Any,
    explicit_service: str | None,
    explicit_host: str | None,
    explicit_ip: str | None,
    candidates: dict[str, Any],
) -> bool:
    if not candidates["candidate_nodes"] and not candidates["candidate_services"]:
        return False
    if memory and any(memory.get(key) for key in ("service", "host", "ip")) and not any(
        [explicit_service, explicit_host, explicit_ip, parsed.service_hint, parsed.host_hint, parsed.ip_hint]
    ):
        return False

    resolved_service = explicit_service or parsed.service_hint
    resolved_host = explicit_host or parsed.host_hint
    resolved_ip = explicit_ip or parsed.ip_hint

    same_ip_nodes = topology.nodes_for_ip(resolved_ip)
    same_host_nodes = topology.nodes_for_host(resolved_host)
    current_node = topology.resolve_node(service=resolved_service, host=resolved_host, ip=resolved_ip)

    if current_node and explicit_service and explicit_host and explicit_ip:
        return False
    if resolved_ip and len(same_ip_nodes) > 1 and not resolved_service:
        return True
    if resolved_host and len(same_host_nodes) > 1 and not resolved_service:
        return True
    if not resolved_service and (resolved_ip or resolved_host):
        return True
    if parsed.vague and len(candidates["candidate_nodes"]) > 1:
        return True
    if not current_node and len(candidates["candidate_nodes"]) > 1:
        return True
    return False


def _validate_scope_resolution(
    payload: dict[str, Any] | None,
    *,
    candidates: dict[str, Any],
    topology: Any,
    confidence_threshold: float,
) -> dict[str, Any]:
    candidate_node_ids = {str(item["node_id"]) for item in candidates["candidate_nodes"]}
    candidate_services = {str(item) for item in candidates["candidate_services"]}
    candidate_hosts = {str(item) for item in candidates["candidate_hosts"]}
    candidate_ips = {str(item) for item in candidates["candidate_ips"]}

    result = {
        "accepted": False,
        "selected_node_id": None,
        "service": None,
        "host": None,
        "ip": None,
        "confidence": 0.0,
        "rejection_reason": None,
    }
    if not payload:
        result["rejection_reason"] = "no LLM scope suggestion was produced."
        return result

    confidence = float(payload.get("confidence") or 0.0)
    result["confidence"] = round(confidence, 3)
    if confidence < confidence_threshold:
        result["rejection_reason"] = f"the model confidence {confidence:.2f} was below the acceptance threshold {confidence_threshold:.2f}."
        return result

    node_id = _optional_text(payload.get("selected_node_id"))
    service = _optional_text(payload.get("service"))
    host = _optional_text(payload.get("host"))
    ip = _optional_text(payload.get("ip"))

    if node_id:
        if node_id not in candidate_node_ids:
            result["rejection_reason"] = f"the selected node '{node_id}' was outside the candidate set."
            return result
        node = topology.get(node_id)
        if node is None:
            result["rejection_reason"] = f"the selected node '{node_id}' did not exist in topology."
            return result
        service = node.service
        host = node.host
        ip = node.ip
    else:
        if service and service not in candidate_services:
            result["rejection_reason"] = f"the selected service '{service}' was outside the candidate set."
            return result
        if host and host not in candidate_hosts:
            result["rejection_reason"] = f"the selected host '{host}' was outside the candidate set."
            return result
        if ip and ip not in candidate_ips:
            result["rejection_reason"] = f"the selected IP '{ip}' was outside the candidate set."
            return result
        node = topology.resolve_node(service=service, host=host, ip=ip)
        node_id = node.node_id if node else None

    result.update(
        {
            "accepted": True,
            "selected_node_id": node_id,
            "service": service,
            "host": host,
            "ip": ip,
            "rejection_reason": None,
        }
    )
    return result


def _fuzzy_service_candidates(query: str, known_services: set[str]) -> list[str]:
    tokens = [token for token in re.split(r"[^a-z0-9]+", query.lower()) if len(token) >= 3]
    candidates: list[str] = []
    for token in tokens:
        matches = difflib.get_close_matches(token, sorted(known_services), n=3, cutoff=0.75)
        for match in matches:
            if match not in candidates:
                candidates.append(match)
    return candidates


def _unique_nodes(nodes: list[TopologyNode]) -> list[TopologyNode]:
    seen: set[str] = set()
    ordered: list[TopologyNode] = []
    for node in nodes:
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        ordered.append(node)
    return ordered


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truncate(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _query_intent_to_dict(item: QueryIntent) -> dict[str, Any]:
    return asdict(item)


def _query_intent_from_dict(payload: dict[str, Any]) -> QueryIntent:
    return QueryIntent(**payload)


def _scope_to_dict(item: InvestigationScope) -> dict[str, Any]:
    return {
        "organization_id": item.organization_id,
        "time_window": asdict(item.time_window),
        "service": item.service,
        "vendor": item.vendor,
        "host": item.host,
        "ip": item.ip,
        "selected_node_id": item.selected_node_id,
        "domain_hint": item.domain_hint,
        "assumptions": list(item.assumptions),
    }


def _scope_from_dict(payload: dict[str, Any]) -> InvestigationScope:
    return InvestigationScope(
        organization_id=str(payload["organization_id"]),
        time_window=TimeWindow(**payload["time_window"]),
        service=payload.get("service"),
        vendor=payload.get("vendor"),
        host=payload.get("host"),
        ip=payload.get("ip"),
        selected_node_id=payload.get("selected_node_id"),
        domain_hint=payload.get("domain_hint"),
        assumptions=tuple(payload.get("assumptions", [])),
    )


def _rag_scope_to_dict(item: Any) -> dict[str, Any]:
    return {
        "type": item.scope_type,
        "key": item.scope_key,
        "domain_bias": item.domain_bias,
    }


def _anchor_to_dict(item: Anchor) -> dict[str, Any]:
    return {
        "service": item.service,
        "host": item.host,
        "ip": item.ip,
        "signal_set": list(item.signal_set),
        "time_window": asdict(item.time_window),
        "node_id": item.node_id,
        "reason": item.reason,
    }


def _anchor_from_dict(payload: dict[str, Any]) -> Anchor:
    return Anchor(
        service=payload.get("service"),
        host=payload.get("host"),
        ip=payload.get("ip"),
        signal_set=tuple(payload.get("signal_set", [])),
        time_window=TimeWindow(**payload["time_window"]),
        node_id=payload.get("node_id"),
        reason=str(payload.get("reason", "")),
    )


def _search_summary_to_dict(item: SearchSummary) -> dict[str, Any]:
    return {
        "events": [asdict(log) for log in item.events],
        "signal_counts": dict(item.signal_counts),
        "first_seen": item.first_seen,
        "last_seen": item.last_seen,
        "entities": list(item.entities),
    }


def _search_summary_from_dict(payload: dict[str, Any]) -> SearchSummary:
    from .models import LogRecord

    return SearchSummary(
        events=tuple(LogRecord(**item) for item in payload.get("events", [])),
        signal_counts={str(key): int(value) for key, value in payload.get("signal_counts", {}).items()},
        first_seen=payload.get("first_seen"),
        last_seen=payload.get("last_seen"),
        entities=tuple(dict(item) for item in payload.get("entities", [])),
    )


def _topology_node_to_dict(item: TopologyNode | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return asdict(item)


def _topology_node_from_dict(payload: dict[str, Any] | None) -> TopologyNode | None:
    if payload is None:
        return None
    return TopologyNode(
        node_id=str(payload["node_id"]),
        service=str(payload["service"]),
        host=str(payload["host"]),
        ip=str(payload["ip"]),
        domain=str(payload["domain"]),
        aliases=tuple(payload.get("aliases", [])),
        node_type=str(payload.get("node_type", "service")),
        service_aliases=tuple(payload.get("service_aliases", [])),
        ip_aliases=tuple(payload.get("ip_aliases", [])),
        host_aliases=tuple(payload.get("host_aliases", [])),
        vendor=payload.get("vendor"),
        platform=payload.get("platform"),
        tier=payload.get("tier"),
        role=payload.get("role"),
        cluster_id=payload.get("cluster_id"),
        replica_set=payload.get("replica_set"),
        is_entrypoint=bool(payload.get("is_entrypoint", False)),
        criticality=str(payload.get("criticality", "medium")),
        match_fields=tuple(payload.get("match_fields", [])),
        tags=tuple(payload.get("tags", [])),
        upstream=tuple(payload.get("upstream", [])),
        downstream=tuple(payload.get("downstream", [])),
        underlay=tuple(payload.get("underlay", [])),
    )


def _hop_to_dict(item: HopSearchResult) -> dict[str, Any]:
    return {
        "source_node_id": item.source_node_id,
        "target_node_id": item.target_node_id,
        "hop_type": item.hop_type,
        "service": item.service,
        "ip": item.ip,
        "time_window": asdict(item.time_window),
        "signals": list(item.signals),
        "event_ids": list(item.event_ids),
        "first_seen": item.first_seen,
        "last_seen": item.last_seen,
        "matched_signal_count": item.matched_signal_count,
        "summary": item.summary,
        "chronology_ok": item.chronology_ok,
    }


def _hop_from_dict(payload: dict[str, Any]) -> HopSearchResult:
    return HopSearchResult(
        source_node_id=str(payload["source_node_id"]),
        target_node_id=str(payload["target_node_id"]),
        hop_type=str(payload["hop_type"]),
        service=str(payload["service"]),
        ip=str(payload["ip"]),
        time_window=TimeWindow(**payload["time_window"]),
        signals=tuple(payload.get("signals", [])),
        event_ids=tuple(payload.get("event_ids", [])),
        first_seen=payload.get("first_seen"),
        last_seen=payload.get("last_seen"),
        matched_signal_count=int(payload.get("matched_signal_count", 0)),
        summary=str(payload.get("summary", "")),
        chronology_ok=bool(payload.get("chronology_ok", False)),
    )
