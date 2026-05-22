from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage

from logs_only_investigator.config import ElasticsearchConfig, OpenAIConfig
from logs_only_investigator.graph import _collect_tool_results, build_graph
from logs_only_investigator.llm import DeterministicExplanationGenerator
from logs_only_investigator.models import LogRecord, SearchSummary, TimeWindow, TopologyEdge, TopologyNode
from logs_only_investigator.rag import CatalogRepository
from logs_only_investigator.service import (
    InvestigationService,
    _apply_service_contradiction_adjustment,
    _build_service_specific_contradictions,
    _compare_against_healthy_window,
    _event_matches_neighbor_identity,
    _generic_supporting_events,
    _service_rca_policy,
    _validate_topology_candidate_critic,
)
from logs_only_investigator.topology_converter import build_agent_topology_documents

from logs_only_investigator.tools.log_store import ElasticsearchLogStore, FakeLogStore, LogSearchRequest, build_signal_search_query
from logs_only_investigator.tools import log_store as log_store_module
from logs_only_investigator.topology import TopologyGraph
from logs_only_investigator.topology_source import StaticTopologySource


FIXTURE_ROOT = Path(__file__).resolve().parents[1]


class StubScopeResolutionGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def resolve_scope(self, context: dict[str, object]) -> dict[str, object]:
        return dict(self.payload)


class StubPlannerGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def choose_next_action(self, context: dict[str, object]) -> dict[str, object]:
        return dict(self.payload)


class StubCriticGenerator:
    def __init__(self, weak_payload: dict[str, object] | None = None, topology_payload: dict[str, object] | None = None) -> None:
        self.weak_payload = weak_payload or {
            "verdict": "inconclusive",
            "recommended_classification": None,
            "confidence_delta": 0.0,
            "reasoning": "stub weak critic",
            "alternate_focus": [],
            "key_risks": [],
        }
        self.topology_payload = topology_payload or {
            "verdict": "inconclusive",
            "selected_node_id": None,
            "score_adjustment": 0.0,
            "reasoning": "stub topology critic",
            "risk_note": None,
        }

    def review_weak_rca(self, context: dict[str, object]) -> dict[str, object]:
        return dict(self.weak_payload)

    def review_topology_candidates(self, context: dict[str, object]) -> dict[str, object]:
        return dict(self.topology_payload)


def _build_runtime():
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    return build_graph(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=StaticTopologySource(topology),
        explanation_generator=DeterministicExplanationGenerator(),
        max_hops=4,
    )


def test_application_outage_walks_the_topology_path() -> None:
    graph = _build_runtime()

    result = graph.invoke(
        {
            "user_query": "why did the application go down?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "app-outage"}},
    )

    report = result["report"]
    assert report["classification"] == "confirmed_rca"
    assert "10.0.4.72::system" in report["likely_root_cause"]
    assert "10.0.4.72::mongodb" in report["primary_entities"]
    assert any(item["event"].startswith("Upstream evidence on 10.0.4.72::app-api") for item in report["timeline"])
    assert any("10.0.4.1::network had no supporting" in detail for detail in report["contradictions"])


def test_network_slow_query_surfaces_network_signals() -> None:
    graph = _build_runtime()

    result = graph.invoke(
        {
            "user_query": "why was the network slow around 10:35?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "network-slow"}},
    )

    report = result["report"]
    signals = {item["signal"] for item in report["candidate_signals"]}
    assert "network_cisco_ios_link_updown" in signals
    assert report["primary_entities"][0] == "10.0.4.1::network"
    assert report["confidence"] >= 0.3


def test_resolve_scope_uses_scoped_time_bounds_for_relative_time_hints() -> None:
    log_store = FakeLogStore(
        [
            LogRecord(
                doc_id="mongo-1",
                timestamp="2026-05-20T15:24:20Z",
                service="mongodb",
                host="localhost.localdomain",
                severity="info",
                signal="mongodb_slow_command",
                message="slow mongodb command",
                ip="10.0.4.72",
            ),
            LogRecord(
                doc_id="mongo-2",
                timestamp="2026-05-20T15:24:21Z",
                service="mongodb",
                host="localhost.localdomain",
                severity="info",
                signal="mongodb_slow_command",
                message="slow mongodb command",
                ip="10.0.4.72",
            ),
            LogRecord(
                doc_id="other-1",
                timestamp="2026-05-20T16:21:44Z",
                service="nginx",
                host="localhost.localdomain",
                severity="warn",
                signal="nginx_access_504_timeout",
                message="upstream timed out",
                ip="10.0.4.72",
            ),
        ]
    )
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph(
        {
            "10.0.4.72::mongodb": TopologyNode(
                node_id="10.0.4.72::mongodb",
                service="mongodb",
                host="localhost.localdomain",
                ip="10.0.4.72",
                domain="database",
            )
        }
    )
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=StaticTopologySource(topology),
        explanation_generator=DeterministicExplanationGenerator(),
        scope_resolution_generator=StubScopeResolutionGenerator({}),
        max_hops=4,
    )

    result = service.resolve_scope(
        query="my mongo db is slowing down in 10.0.4.72 for last 5 min why?",
        organization_id="demo-org",
        service="mongodb",
        ip="10.0.4.72",
        session_memory={},
    )

    scope = result["scope"]
    assert scope["time_window"]["end"] == "2026-05-20T15:24:21Z"
    assert scope["time_window"]["start"] == "2026-05-20T15:19:21Z"
    assert any("latest matching logs" in line for line in result["trace"])


def test_same_thread_persists_memory_and_message_history() -> None:
    graph = _build_runtime()

    first = graph.invoke(
        {
            "user_query": "why did the application go down?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "memory-thread"}},
    )
    assert first["report"]["classification"] == "confirmed_rca"

    second = graph.invoke(
        {
            "user_query": "check again around 09:33",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "memory-thread"}},
    )

    assert second["report"]["incident_window"]["label"] in {"around_0933", "around_0933_previous_day", "first_circle_hotspot"}
    assert second["report"]["primary_entities"][0] == "10.0.4.72::nginx"
    assert any("Reused prior thread scope memory" in line for line in second["report"]["investigation_trace"])

    persisted = graph.get_state("memory-thread")
    assert persisted.values["session_memory"]["service"] == "nginx"
    assert sum(1 for message in persisted.values["messages"] if isinstance(message, HumanMessage)) == 2


def test_hybrid_planner_records_llm_trace_and_falls_back_when_invalid() -> None:
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    graph = build_graph(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=StaticTopologySource(topology),
        explanation_generator=DeterministicExplanationGenerator(),
        openai_config=OpenAIConfig(
            api_key_env="OPENAI_API_KEY",
            model="gpt-4o-mini",
            reasoning_effort="medium",
            text_verbosity="low",
            max_output_tokens=800,
            planner_enabled=True,
            planner_mode="hybrid",
            planner_max_output_tokens=260,
            critic_enabled=True,
            critic_max_output_tokens=260,
            scope_resolution_enabled=False,
            scope_resolution_max_output_tokens=220,
            scope_resolution_confidence_threshold=0.6,
            timeout_seconds=60,
            instructions="",
        ),
        planner_generator=StubPlannerGenerator(
            {
                "thought": "Resolve the scope first from the user query.",
                "action": "tool_call",
                "tool_name": "resolve_scope",
                "tool_args": None,
                "stop_reason": None,
                "confidence_note": "This is the required first step.",
                "request": {"model": "stub"},
            }
        ),
        max_hops=4,
    )

    result = graph.invoke(
        {
            "user_query": "why did the application go down?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "hybrid-planner-trace"}},
    )

    planner_trace = result["planner_trace"]
    assert planner_trace[0]["selected_tool_name"] == "resolve_scope"
    assert planner_trace[0]["selection_source"] == "llm_hybrid"
    assert any(item["selection_source"] == "deterministic_fallback" for item in planner_trace[1:])
    assert any(item["selection_source"] == "forced_single_option" for item in planner_trace)
    assert "confidence_breakdown" in result["report"]


def test_healthy_window_and_critic_methods_return_structured_payloads() -> None:
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    source = StaticTopologySource(topology)
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=source,
        explanation_generator=DeterministicExplanationGenerator(),
        scope_resolution_generator=StubScopeResolutionGenerator({}),
        max_hops=4,
    )
    graph = build_graph(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=source,
        explanation_generator=DeterministicExplanationGenerator(),
        max_hops=4,
    )

    result = graph.invoke(
        {
            "user_query": "why did the application go down?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "healthy-critic-test"}},
    )
    tools = result["tool_results"]
    healthy = service.healthy_window_comparison(
        scope=tools["resolve_scope"]["scope"],
        anchor=tools["first_circle_search"]["anchor"],
        first_circle=tools["first_circle_search"]["first_circle"],
        topology_walk=tools["topology_walk"],
    )
    critic = service.critic_pass(
        query="why did the application go down?",
        scope=tools["resolve_scope"]["scope"],
        anchor=tools["first_circle_search"]["anchor"],
        first_circle=tools["first_circle_search"]["first_circle"],
        topology_walk=tools["topology_walk"],
        raw_context=tools["raw_log_context"]["raw_context"],
        healthy_window=healthy,
    )

    assert "comparison" in healthy
    assert "anomaly_score" in healthy["comparison"]
    assert "critic" in critic
    assert "verdict" in critic["critic"]


def test_topology_walk_retains_alternate_paths_and_new_policy_helpers_are_available() -> None:
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    source = StaticTopologySource(topology)
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=source,
        explanation_generator=DeterministicExplanationGenerator(),
        scope_resolution_generator=StubScopeResolutionGenerator({}),
        critic_generator=StubCriticGenerator(),
        max_hops=4,
    )
    graph = build_graph(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=source,
        explanation_generator=DeterministicExplanationGenerator(),
        max_hops=4,
    )
    result = graph.invoke(
        {
            "user_query": "why did the application go down?",
            "organization_id": "demo-org",
        },
        config={"configurable": {"thread_id": "alternate-path-test"}},
    )
    tools = result["tool_results"]
    topology_walk = service.topology_walk(
        anchor=tools["first_circle_search"]["anchor"],
        first_circle=tools["first_circle_search"]["first_circle"],
        parsed_query=tools["resolve_scope"]["parsed_query"],
        scope=tools["resolve_scope"]["scope"],
    )

    assert "alternate_paths" in topology_walk
    assert isinstance(topology_walk["alternate_paths"], list)
    assert isinstance(topology_walk["topology_comparison_rounds"], list)

    policy = _service_rca_policy("nginx", "gateway")
    assert policy["policy_name"] == "nginx_gateway"

    comparison = _compare_against_healthy_window(
        incident_summary=SearchSummary(
            events=(
                LogRecord(
                    doc_id="incident-1",
                    timestamp="2026-05-22T10:00:00Z",
                    service="nginx",
                    host="localhost.localdomain",
                    severity="error",
                    signal="nginx_access_502_bad_gateway",
                    message="upstream timeout while connecting to upstream",
                    ip="10.0.4.72",
                ),
            ),
            signal_counts={"nginx_access_502_bad_gateway": 1},
            first_seen="2026-05-22T10:00:00Z",
            last_seen="2026-05-22T10:00:00Z",
            entities=({"service": "nginx", "host": "localhost.localdomain", "ip": "10.0.4.72"},),
        ),
        baseline_summary=SearchSummary(
            events=(
                LogRecord(
                    doc_id="baseline-1",
                    timestamp="2026-05-22T09:00:00Z",
                    service="nginx",
                    host="localhost.localdomain",
                    severity="info",
                    signal="",
                    message="GET / 200",
                    ip="10.0.4.72",
                ),
            ),
            signal_counts={},
            first_seen="2026-05-22T09:00:00Z",
            last_seen="2026-05-22T09:00:00Z",
            entities=({"service": "nginx", "host": "localhost.localdomain", "ip": "10.0.4.72"},),
        ),
        incident_minutes=5.0,
    )
    assert "components" in comparison
    assert comparison["anomaly_score"] >= 0.0

    validated = _validate_topology_candidate_critic(
        {
            "verdict": "select_alternate",
            "selected_node_id": "10.0.4.72::mongodb",
            "score_adjustment": 0.4,
        },
        round_candidates=[
            {"node_id": "10.0.4.72::mongodb", "status": "candidate"},
            {"node_id": "10.0.4.72::redis", "status": "candidate"},
        ],
        scored_best_node_id="10.0.4.72::redis",
    )
    assert validated["accepted"] is True
    assert validated["selected_node_id"] == "10.0.4.72::mongodb"


def test_service_specific_contradiction_rules_flag_unsignalized_nginx_noise() -> None:
    first_circle = SearchSummary(
        events=(
            LogRecord(
                doc_id="nginx-1",
                timestamp="2026-05-22T10:00:00Z",
                service="nginx",
                host="localhost.localdomain",
                severity="info",
                signal="",
                message='10.0.4.1 - root "GET / HTTP/1.1" 200 615 "-"',
                ip="10.0.4.72",
            ),
            LogRecord(
                doc_id="nginx-2",
                timestamp="2026-05-22T10:00:01Z",
                service="nginx",
                host="localhost.localdomain",
                severity="info",
                signal="",
                message='10.0.4.1 - root "GET /health HTTP/1.1" 200 12 "-"',
                ip="10.0.4.72",
            ),
        ),
        signal_counts={},
        first_seen="2026-05-22T10:00:00Z",
        last_seen="2026-05-22T10:00:01Z",
        entities=({"service": "nginx", "host": "localhost.localdomain", "ip": "10.0.4.72"},),
    )

    hits = _build_service_specific_contradictions(
        impacted_service="nginx",
        root_service="nginx",
        root_node_id="10.0.4.72::nginx",
        first_circle=first_circle,
        hops=[],
        topology_walk={"node_inspections": []},
        raw_context=[],
        alternate_paths=[],
    )

    rule_ids = {item["rule_id"] for item in hits}
    assert "nginx_success_traffic_without_failure_signal" in rule_ids
    assert "nginx_no_upstream_corroboration" in rule_ids


def test_service_contradiction_penalty_reduces_confidence() -> None:
    confidence, classification, breakdown = _apply_service_contradiction_adjustment(
        confidence=0.81,
        classification="confirmed_rca",
        confidence_breakdown={"final_confidence": 0.81},
        rule_hits=[
            {"severity": "high"},
            {"severity": "medium"},
        ],
    )

    assert confidence < 0.81
    assert classification == "probable_cause"
    assert breakdown["service_contradiction_penalty"] > 0.0


def test_build_signal_search_query_adds_filters_and_pit_state() -> None:
    config = ElasticsearchConfig(
        hosts=("http://localhost:9200",),
        index="signalized-logs-*",
        username=None,
        password=None,
        api_key=None,
        verify_certs=False,
        ca_certs=None,
        request_timeout_seconds=30,
        timestamp_field="@timestamp",
        organization_field="organization_id",
        service_field="service",
        host_field="host",
        ip_field="ip",
        signal_field="signal",
        message_field="message",
        severity_field="severity",
        vendor_field="vendor",
        domain_field="domain",
        searchable_fields=("message", "signal", "service"),
        source_fields=("doc_id", "@timestamp", "service", "host", "ip", "signal", "message"),
        search_page_size=250,
        max_records_per_query=1000,
        use_point_in_time=True,
        point_in_time_keep_alive="2m",
    )
    request = LogSearchRequest(
        organization_id="demo-org",
        query_terms=("connection", "timeout"),
        signals=("app_error", "db_down"),
        start_time="2026-05-19T09:30:00Z",
        end_time="2026-05-19T09:40:00Z",
        service="nginx",
        host="edge-01",
        ip="10.0.4.10",
        limit=100,
        source_fields=config.source_fields,
    )

    query = build_signal_search_query(
        config,
        request,
        page_size=50,
        search_after=["2026-05-19T09:35:00Z", 42],
        pit_id="pit-123",
    )

    bool_query = query["query"]["bool"]
    filters = bool_query["filter"]
    must = bool_query["must"]

    assert query["size"] == 50
    assert query["pit"]["id"] == "pit-123"
    assert query["search_after"] == ["2026-05-19T09:35:00Z", 42]
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"organization_id.keyword": "demo-org"}}, {"term": {"organization_id": "demo-org"}}],
        }
    } in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"service.keyword": "nginx"}}, {"term": {"service": "nginx"}}],
        }
    } in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"host.keyword": "edge-01"}}, {"term": {"host": "edge-01"}}],
        }
    } in filters
    assert {"term": {"ip": "10.0.4.10"}} in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"terms": {"signal.keyword": ["app_error", "db_down"]}}, {"terms": {"signal": ["app_error", "db_down"]}}],
        }
    } in filters
    assert must[0]["simple_query_string"]["default_operator"] == "and"
    assert must[0]["simple_query_string"]["query"] == "connection timeout"


def test_fake_store_accepts_repo_style_nested_field_config_for_query_builder() -> None:
    config = ElasticsearchConfig(
        hosts=("http://10.0.5.60:9200",),
        index="linux*,network-*",
        username="elastic",
        password="elastic",
        api_key=None,
        verify_certs=False,
        ca_certs=None,
        request_timeout_seconds=30,
        timestamp_field="@timestamp",
        organization_field="event.organization",
        service_field="event.module",
        host_field="host.name",
        ip_field="host.ip",
        signal_field="signal",
        message_field="message",
        severity_field="log.level",
        vendor_field="vendor",
        domain_field="domain",
        searchable_fields=("message", "signal", "event.module", "host.name", "host.ip"),
        source_fields=("@timestamp", "event.organization", "event.module", "host.name", "host.ip", "signal", "message"),
        search_page_size=250,
        max_records_per_query=1000,
        use_point_in_time=True,
        point_in_time_keep_alive="2m",
    )
    request = LogSearchRequest(
        organization_id="org-1",
        query_terms=("disk", "full"),
        signals=("mongodb_out_of_disk_space",),
        start_time="2026-05-19T09:30:00Z",
        end_time="2026-05-19T09:40:00Z",
        service="mongodb",
        host="db-01",
        ip="10.0.4.72",
        limit=25,
        source_fields=config.source_fields,
    )

    query = build_signal_search_query(config, request, page_size=25, pit_id="pit-1")
    filters = query["query"]["bool"]["filter"]

    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"event.organization.keyword": "org-1"}}, {"term": {"event.organization": "org-1"}}],
        }
    } in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"event.module.keyword": "mongodb"}}, {"term": {"event.module": "mongodb"}}],
        }
    } in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"host.name.keyword": "db-01"}}, {"term": {"host.name": "db-01"}}],
        }
    } in filters
    assert {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {"host.ip.keyword": "10.0.4.72"}}, {"term": {"host.ip": "10.0.4.72"}}],
        }
    } in filters


def test_record_from_hit_extracts_nested_source_fields() -> None:
    config = ElasticsearchConfig(
        hosts=("http://10.0.5.60:9200",),
        index="linux*,network-*",
        username="elastic",
        password="elastic",
        api_key=None,
        verify_certs=False,
        ca_certs=None,
        request_timeout_seconds=30,
        timestamp_field="@timestamp",
        organization_field="event.organization",
        service_field="event.module",
        host_field="host.name",
        ip_field="host.ip",
        signal_field="signal",
        message_field="message",
        severity_field="log.level",
        vendor_field="vendor",
        domain_field="domain",
        searchable_fields=("message", "signal"),
        source_fields=("@timestamp", "event.organization", "event.module", "host.name", "host.ip", "signal", "message"),
        search_page_size=250,
        max_records_per_query=1000,
        use_point_in_time=True,
        point_in_time_keep_alive="2m",
    )

    record = log_store_module._record_from_hit(
        config,
        {
            "_id": "doc-1",
            "_source": {
                "@timestamp": "2026-05-19T09:34:12Z",
                "event": {"organization": "org-1", "module": "mongodb"},
                "host": {"name": "db-01", "ip": ["10.0.4.72", "10.0.4.73"]},
                "signal": "mongodb_out_of_disk_space",
                "message": "Disk full on mongodb volume",
                "log": {"level": "error"},
            },
        },
    )

    assert record.timestamp == "2026-05-19T09:34:12Z"
    assert record.service == "mongodb"
    assert record.host == "db-01"
    assert record.ip == "10.0.4.72"
    assert record.signal == "mongodb_out_of_disk_space"
    assert record.severity == "error"


def test_build_agent_topology_documents_flattens_rca_topology_schema() -> None:
    documents = [
        {
            "organization_id": "org-1",
            "topology_id": "topology-a",
            "topology": {
                "services": [
                    {"service_name": "nginx", "device_ip": "10.0.5.97"},
                    {"service_name": "api", "device_ip": "10.0.5.97"},
                    {"service_name": "mongodb", "device_ip": "10.0.5.97"},
                ],
                "dependencies": [
                    {"from": "10.0.5.97::nginx", "to": "10.0.5.97::api", "relation": "upstream"},
                    {"from": "10.0.5.97::api", "to": "10.0.5.97::mongodb", "relation": "depends_on"},
                ],
                "devices": [
                    {
                        "device_ip": "10.0.5.97",
                        "host_name": "node-1",
                        "services": [
                            {"service_name": "nginx", "role": "upstream", "upstream_for": ["api"]},
                            {"service_name": "api", "role": "application", "depends_on": ["mongodb"]},
                            {"service_name": "mongodb", "role": "database"},
                        ],
                    }
                ],
            },
        }
    ]

    payloads = build_agent_topology_documents(documents)

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["_id"].startswith("org-1::topology-a::")
    assert payload["organization_id"] == "org-1"
    assert payload["topology_id"] == "topology-a"
    assert payload["is_enabled"] is False
    assert "topology" not in payload
    assert payload["version"]["version_id"]
    assert payload["incident_time_lookup"]["selection_mode"] == "version_window"
    assert {edge["from_node_id"] for edge in payload["edges"]} >= {"10.0.5.97::nginx", "10.0.5.97::api"}
    assert {edge["relation_type"] for edge in payload["edges"]} == {"depends_on"}

    graph = TopologyGraph.from_payload(payload)
    nginx = graph.get("10.0.5.97::nginx")
    api = graph.get("10.0.5.97::api")
    mongodb = graph.get("10.0.5.97::mongodb")

    assert nginx is not None
    assert api is not None
    assert mongodb is not None
    assert nginx.host == "node-1"
    assert nginx.domain == "gateway"
    assert api.domain == "application"
    assert mongodb.domain == "database"
    assert "10.0.5.97::api" in nginx.upstream
    assert "10.0.5.97::mongodb" in api.upstream


def test_topology_graph_derives_upstream_downstream_from_canonical_edges() -> None:
    graph = TopologyGraph(
        {
            "10.0.4.72::nginx": TopologyNode(
                node_id="10.0.4.72::nginx",
                service="nginx",
                host="app-01",
                ip="10.0.4.72",
                domain="gateway",
            ),
            "10.0.4.72::app-api": TopologyNode(
                node_id="10.0.4.72::app-api",
                service="app-api",
                host="app-01",
                ip="10.0.4.72",
                domain="application",
            ),
            "10.0.4.72::system": TopologyNode(
                node_id="10.0.4.72::system",
                service="system",
                host="app-01",
                ip="10.0.4.72",
                domain="system",
            ),
        },
        (
            TopologyEdge(
                edge_id="nginx-api",
                from_node_id="10.0.4.72::nginx",
                to_node_id="10.0.4.72::app-api",
                relation_type="depends_on",
            ),
            TopologyEdge(
                edge_id="api-system",
                from_node_id="10.0.4.72::app-api",
                to_node_id="10.0.4.72::system",
                relation_type="underlay",
            ),
        ),
    )

    nginx = graph.get("10.0.4.72::nginx")
    api = graph.get("10.0.4.72::app-api")
    system = graph.get("10.0.4.72::system")

    assert nginx is not None and api is not None and system is not None
    assert nginx.upstream == ("10.0.4.72::app-api",)
    assert api.downstream == ("10.0.4.72::nginx",)
    assert api.underlay == ("10.0.4.72::system",)
    assert graph.prioritized_neighbors("10.0.4.72::nginx")[0] == ("upstream", "10.0.4.72::app-api")


def test_aggregate_discovery_falls_back_when_terms_agg_is_not_supported() -> None:
    config = ElasticsearchConfig(
        hosts=("http://10.0.5.60:9200",),
        index="linux*,network-*",
        username="elastic",
        password="elastic",
        api_key=None,
        verify_certs=False,
        ca_certs=None,
        request_timeout_seconds=30,
        timestamp_field="@timestamp",
        organization_field="event.organization",
        service_field="event.module",
        host_field="host.name",
        ip_field="host.ip",
        signal_field="signal",
        message_field="message",
        severity_field="log.level",
        vendor_field="vendor",
        domain_field="domain",
        searchable_fields=("message", "signal", "event.module"),
        source_fields=("@timestamp", "event.organization", "event.module", "host.name", "host.ip", "signal", "message"),
        search_page_size=250,
        max_records_per_query=1000,
        use_point_in_time=False,
        point_in_time_keep_alive="2m",
    )
    sample_logs = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")

    class FailingClient:
        def search(self, **kwargs):
            raise RuntimeError("Fielddata is disabled on [host.ip]")

    store = ElasticsearchLogStore(FailingClient(), config)
    store.search = sample_logs.search  # type: ignore[method-assign]
    summary = store.aggregate_discovery(
        candidate_signals=["nginx_access_502_bad_gateway", "nginx_access_504_timeout"],
        time_window=TimeWindow(
            start="2026-05-20T09:25:00Z",
            end="2026-05-20T09:40:00Z",
            label="fallback_window",
        ),
    )

    assert summary["top_ips"][0]["ip"] == "10.0.4.72"
    assert summary["top_services"][0]["service"] == "nginx"


def test_collect_tool_results_accepts_text_block_payloads() -> None:
    messages = [
        ToolMessage(
            name="resolve_scope",
            tool_call_id="call-1",
            content=[{"type": "text", "text": '{"scope": {"service": "nginx"}, "trace": ["ok"]}'}],
        )
    ]

    results = _collect_tool_results(messages)

    assert results["resolve_scope"]["scope"]["service"] == "nginx"
    assert results["resolve_scope"]["trace"] == ["ok"]


def test_collect_tool_results_turns_empty_payload_into_tool_error() -> None:
    messages = [
        ToolMessage(
            name="resolve_scope",
            tool_call_id="call-2",
            content="",
        )
    ]

    results = _collect_tool_results(messages)

    assert "returned an unreadable payload" in results["resolve_scope"]["error"]


def test_collect_tool_results_preserves_tool_error_status() -> None:
    messages = [
        ToolMessage(
            name="resolve_scope",
            tool_call_id="call-3",
            status="error",
            content="Error: logger handler failed",
        )
    ]

    results = _collect_tool_results(messages)

    assert results["resolve_scope"]["error"] == "Error: logger handler failed"


def test_generic_supporting_events_accept_alias_matched_logs_without_signals() -> None:
    neighbor = TopologyNode(
        node_id="10.0.4.72::instancegunicorn",
        service="instancegunicorn",
        host="localhost.localdomain",
        ip="10.0.4.72",
        domain="application",
        aliases=("gunicorn", "instancegunicorn.service"),
    )
    current = TopologyNode(
        node_id="10.0.4.72::nginx",
        service="nginx",
        host="localhost.localdomain",
        ip="10.0.4.72",
        domain="gateway",
    )
    event = LogRecord(
        doc_id="1",
        timestamp="2026-05-19T23:00:00Z",
        service="system",
        host="localhost.localdomain",
        severity="error",
        signal="",
        message="instancegunicorn.service failed because upstream worker timed out",
        ip="10.0.4.72",
    )

    assert _event_matches_neighbor_identity(event, neighbor)

    supporting = _generic_supporting_events(
        events=(event,),
        neighbor=neighbor,
        current_node=current,
        hop_type="upstream",
        parsed_terms=["application", "down", "timeout"],
        require_neighbor_identity=True,
    )

    assert supporting[0].doc_id == "1"


def test_resolve_scope_accepts_valid_llm_selected_candidate_node() -> None:
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=StaticTopologySource(topology),
        explanation_generator=DeterministicExplanationGenerator(),
        scope_resolution_generator=StubScopeResolutionGenerator(
            {
                "selected_node_id": "10.0.4.72::nginx",
                "service": "nginx",
                "host": "localhost.localdomain",
                "ip": "10.0.4.72",
                "confidence": 0.91,
                "reason": "The same-IP candidate set contains nginx and the query refers to the gateway symptom.",
            }
        ),
        max_hops=4,
    )

    result = service.resolve_scope(
        query="my ngnix is slowing down in 10.0.4.72 for last 5 min why?",
        organization_id="demo-org",
    )

    assert result["scope"]["service"] == "nginx"
    assert result["scope"]["selected_node_id"] == "10.0.4.72::nginx"
    assert any("LLM scope resolution selected node=10.0.4.72::nginx" in line for line in result["trace"])


def test_resolve_scope_rejects_invalid_llm_selected_candidate_node() -> None:
    log_store = FakeLogStore.from_json(FIXTURE_ROOT / "samples" / "logs.json")
    catalogs = CatalogRepository(FIXTURE_ROOT / "rag")
    topology = TopologyGraph.from_json(FIXTURE_ROOT / "samples" / "topology.json")
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=StaticTopologySource(topology),
        explanation_generator=DeterministicExplanationGenerator(),
        scope_resolution_generator=StubScopeResolutionGenerator(
            {
                "selected_node_id": "10.0.4.72::nonexistent",
                "service": "nonexistent",
                "host": "localhost.localdomain",
                "ip": "10.0.4.72",
                "confidence": 0.95,
                "reason": "Bad candidate.",
            }
        ),
        max_hops=4,
    )

    result = service.resolve_scope(
        query="my ngnix is slowing down in 10.0.4.72 for last 5 min why?",
        organization_id="demo-org",
    )

    assert result["scope"]["service"] is None
    assert result["scope"]["selected_node_id"] is None
    assert any("Ignored the LLM scope suggestion" in line for line in result["trace"])
