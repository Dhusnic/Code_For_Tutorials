from __future__ import annotations

import concurrent.futures
import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st
try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - optional in local runtime
    go = None


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from logs_only_investigator.runner import (  # noqa: E402
    InvestigationRequest,
    default_catalog_root,
    default_config_file,
    default_env_file,
    load_runtime_for_request,
    run_investigation,
    run_investigation_with_artifacts,
)


st.set_page_config(
    page_title="Logs-Only Investigator",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def get_runtime(
    *,
    config_path: str,
    env_path: str,
    catalog_root: str,
    max_hops: int | None,
):
    return load_runtime_for_request(
        config_path=Path(config_path),
        env_path=Path(env_path) if env_path else None,
        catalog_root=Path(catalog_root),
        max_hops_override=max_hops,
    )


def main() -> None:
    _initialize_session()
    st.title("Logs-Only RCA Investigator")
    st.caption("Temporary Streamlit UI over the existing LangGraph + Elasticsearch + MongoDB runtime.")

    with st.sidebar:
        st.subheader("Runtime")
        config_path = st.text_input("Config File", value=str(default_config_file()))
        env_path = st.text_input("Env File", value=str(default_env_file()))
        catalog_root = st.text_input("Catalog Root", value=str(default_catalog_root()))
        max_hops = st.number_input("Max Hops", min_value=1, max_value=12, value=4, step=1)
        fresh_runtime_on_run = st.checkbox("Force Fresh Runtime On Run", value=True)

        st.subheader("Scope")
        organization_id = st.text_input("Organization ID", value="135098068173316952064")
        thread_id = st.text_input("Thread ID", value=st.session_state.thread_id)
        service = st.text_input("Service Override", value="")
        host = st.text_input("Host Override", value="")
        ip = st.text_input("IP Override", value="")
        start_time = st.text_input("Start Time", value="", placeholder="2026-05-19T23:54:59Z")
        end_time = st.text_input("End Time", value="", placeholder="2026-05-19T23:59:59Z")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("New Thread", use_container_width=True):
                st.session_state.thread_id = f"streamlit-{uuid4().hex[:10]}"
                st.rerun()
        with col_b:
            if st.button("Clear History", use_container_width=True):
                st.session_state.history = []
                st.rerun()

        if st.button("Hard Reset Runtime", use_container_width=True):
            get_runtime.clear()
            _reset_streamlit_state()
            st.rerun()

        with st.expander("RAG Rebuild", expanded=False):
            st.caption("Dedicated rebuild command for JSON catalogs plus vector DBs")
            st.code(
                ".\\.venv\\Scripts\\python.exe -m logs_only_investigator.rebuild_rag --build-vector-db=yes",
                language="powershell",
            )
            st.caption("If the package entrypoint is installed in the venv, you can also use:")
            st.code(
                "logs-investigator-rebuild-rag --build-vector-db=yes",
                language="powershell",
            )

    query = st.text_area(
        "Incident Query",
        value="my nginx is slowing down in 10.0.4.72 for last 5 min why?",
        height=120,
        placeholder="Ask a root-cause question in natural language.",
    )

    submit = st.button("Run Investigation", type="primary", use_container_width=True)

    if submit:
        live_status = st.empty()
        live_tools = st.empty()
        live_logs = st.empty()
        trace_handler = _build_trace_handler()
        with st.spinner("Running investigator..."):
            try:
                current_thread_id = thread_id
                if fresh_runtime_on_run:
                    get_runtime.clear()
                    st.session_state.history = []
                    st.session_state.thread_id = f"streamlit-{uuid4().hex[:10]}"
                    st.session_state.pop("topology_selected_node_id", None)
                    current_thread_id = st.session_state.thread_id
                logger = logging.getLogger("logs_only_investigator")
                logger.addHandler(trace_handler)
                runtime = get_runtime(
                    config_path=config_path,
                    env_path=env_path,
                    catalog_root=catalog_root,
                    max_hops=max_hops,
                )
                request = InvestigationRequest(
                    query=query,
                    organization_id=organization_id or None,
                    thread_id=current_thread_id or None,
                    start_time=start_time or None,
                    end_time=end_time or None,
                    service=service or None,
                    host=host or None,
                    ip=ip or None,
                )
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_investigation_with_artifacts, runtime, request)
                    while not future.done():
                        _render_live_trace(
                            trace_handler,
                            status_placeholder=live_status,
                            tools_placeholder=live_tools,
                            logs_placeholder=live_logs,
                        )
                        time.sleep(0.15)
                    outcome = future.result()
                    report = outcome["report"]
                _render_live_trace(
                    trace_handler,
                    status_placeholder=live_status,
                    tools_placeholder=live_tools,
                    logs_placeholder=live_logs,
                )
                st.session_state.thread_id = current_thread_id
                st.session_state.history.insert(
                    0,
                    {
                        "query": query,
                        "report": report,
                        "tool_results": outcome.get("tool_results", {}),
                        "planner_trace": outcome.get("planner_trace", []),
                        "process_logs": trace_handler.snapshot_lines(),
                        "tool_events": trace_handler.snapshot_events(),
                    },
                )
            except Exception as exc:
                _render_live_trace(
                    trace_handler,
                    status_placeholder=live_status,
                    tools_placeholder=live_tools,
                    logs_placeholder=live_logs,
                )
                st.error(f"Investigation failed: {exc}")
                st.exception(exc)
            finally:
                logger = logging.getLogger("logs_only_investigator")
                logger.removeHandler(trace_handler)

    if st.session_state.history:
        current = st.session_state.history[0]
        render_report(
            current["query"],
            current["report"],
            exact_tool_results=current.get("tool_results", {}),
            planner_trace=current.get("planner_trace", []),
            process_logs=current.get("process_logs", []),
            tool_events=current.get("tool_events", []),
        )

        with st.expander("Recent Runs", expanded=False):
            for index, item in enumerate(st.session_state.history[1:], start=1):
                with st.expander(f"Run {index}: {item['query']}", expanded=False):
                    render_report(
                        item["query"],
                        item["report"],
                        exact_tool_results=item.get("tool_results", {}),
                        planner_trace=item.get("planner_trace", []),
                        process_logs=item.get("process_logs", []),
                        tool_events=item.get("tool_events", []),
                        title="Saved Result",
                    )
    else:
        st.info("Run an investigation to view the structured RCA report.")


def render_report(
    query: str,
    report: dict[str, Any],
    *,
    exact_tool_results: dict[str, Any],
    planner_trace: list[dict[str, Any]],
    process_logs: list[str],
    tool_events: list[dict[str, str | None]],
    title: str = "Latest Result",
) -> None:
    st.subheader(title)
    st.write(f"**Query:** `{query}`")

    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Classification", str(report.get("classification", "unknown")))
    metric_b.metric("Confidence", str(report.get("confidence", "n/a")))
    metric_c.metric("Tokens Used", str(report.get("total_tokens_used", "n/a")))
    metric_d.metric("Summary Source", str(report.get("analyst_summary_source", "unknown")))

    _render_retrieval_runtime_summary(exact_tool_results)

    st.markdown("### Analyst Summary")
    st.write(report.get("analyst_summary") or report.get("summary") or "No summary available.")

    if report.get("llm_error"):
        st.warning(report["llm_error"])

    st.markdown("### Evidence Logs")
    evidence_logs = report.get("evidence_logs", [])
    if evidence_logs:
        st.dataframe(
            evidence_logs,
            use_container_width=True,
            hide_index=True,
            column_order=["timestamp", "service", "host", "ip", "severity", "signal", "message", "doc_id"],
        )
    else:
        st.write("No evidence logs were captured for this run.")

    left, right = st.columns([1.3, 1.0])
    with left:
        st.markdown("### Core Findings")
        st.write(f"**Likely Root Cause:** `{report.get('likely_root_cause', 'unknown')}`")
        st.write(f"**Incident Window:** `{json.dumps(report.get('incident_window', {}))}`")
        st.write(f"**Primary Entities:** `{', '.join(report.get('primary_entities', [])) or 'none'}`")

        st.markdown("### Timeline")
        timeline = report.get("timeline", [])
        if timeline:
            for item in timeline:
                st.write(f"- `{item.get('timestamp')}` {item.get('event')}")
        else:
            st.write("No timeline entries.")

        st.markdown("### Supporting Evidence")
        for item in report.get("supporting_evidence", []):
            st.write(f"- {item.get('claim')}")

        st.markdown("### Contradictions")
        contradictions = report.get("contradictions", [])
        if contradictions:
            for item in contradictions:
                st.write(f"- {item}")
        else:
            st.write("No contradictions recorded.")

        rule_hits = report.get("service_specific_contradictions", [])
        st.markdown("### Contradiction Rule Hits")
        if isinstance(rule_hits, list) and rule_hits:
            st.dataframe(rule_hits, use_container_width=True, hide_index=True)
        else:
            st.write("No service-specific contradiction rules were triggered.")

    with right:
        st.markdown("### Candidate Signals")
        candidate_signals = report.get("candidate_signals", [])
        if candidate_signals:
            st.dataframe(candidate_signals, use_container_width=True, hide_index=True)
        else:
            st.write("No candidate signals.")

        alternate_paths = report.get("alternate_paths", [])
        st.markdown("### Alternate Paths")
        if isinstance(alternate_paths, list) and alternate_paths:
            st.dataframe(alternate_paths, use_container_width=True, hide_index=True)
        else:
            st.write("No alternate supported paths were retained.")

        st.markdown("### Confidence Breakdown")
        confidence_breakdown = report.get("confidence_breakdown", {})
        if isinstance(confidence_breakdown, dict) and confidence_breakdown:
            st.json(confidence_breakdown)
        else:
            st.write("No confidence breakdown was recorded.")

        st.markdown("### Unknowns")
        unknowns = report.get("unknowns", [])
        if unknowns:
            for item in unknowns:
                st.write(f"- {item}")
        else:
            st.write("No unknowns recorded.")

        st.markdown("### Next Checks")
        for item in report.get("next_log_checks", []):
            st.write(f"- {item}")

    with st.expander("Raw Context", expanded=False):
        for line in report.get("raw_context", []):
            st.code(line, language="text")

    with st.expander("Investigation Trace", expanded=False):
        for line in report.get("investigation_trace", []):
            st.write(f"- {line}")

    if isinstance(report.get("healthy_window_comparison"), dict):
        with st.expander("Healthy Window Comparison", expanded=False):
            st.json(report.get("healthy_window_comparison"))

    if isinstance(report.get("critic_pass"), dict):
        with st.expander("Weak RCA Critic", expanded=False):
            st.json(report.get("critic_pass"))

    with st.expander("Tool Process", expanded=True):
        display_tool_events = _merge_exact_tool_results(tool_events, exact_tool_results, planner_trace)
        if display_tool_events:
            for index, event in enumerate(display_tool_events, start=1):
                label = f"{index}. {event['tool_name']} [{event['status']}]"
                with st.expander(label, expanded=index == len(display_tool_events)):
                    if event.get("planner_thought"):
                        st.write(f"**Planner Thought:** {event['planner_thought']}")
                    if event.get("planner_selection_source"):
                        st.write(f"**Planner Mode:** `{event['planner_selection_source']}`")
                    if event.get("planner_fallback_reason"):
                        st.warning(str(event["planner_fallback_reason"]))
                    if event.get("planner_request"):
                        st.markdown("**Planner Request**")
                        _render_payload(event["planner_request"])
                    if event.get("planner_response"):
                        st.markdown("**Planner Response**")
                        _render_payload(event["planner_response"])
                    if event.get("inputs"):
                        st.markdown("**Inputs**")
                        _render_payload(event["inputs"])
                    if event.get("output"):
                        _render_step_specific_output(event["tool_name"], event["output"])
                        st.markdown("**Output**")
                        _render_payload(event["output"])
                    if event.get("error"):
                        st.error(str(event["error"]))
        else:
            st.write("No tool events were captured for this run.")

    with st.expander("Execution Logs", expanded=False):
        if process_logs:
            st.code("\n".join(process_logs), language="text")
        else:
            st.write("No execution logs were captured for this run.")

    with st.expander("Full JSON", expanded=False):
        st.json(report)


def _initialize_session() -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"streamlit-{uuid4().hex[:10]}"
    if "history" not in st.session_state:
        st.session_state.history = []


def _reset_streamlit_state() -> None:
    st.session_state.thread_id = f"streamlit-{uuid4().hex[:10]}"
    st.session_state.history = []
    st.session_state.pop("topology_selected_node_id", None)


def _build_trace_handler() -> logging.Handler:
    class StreamlitTraceHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__(level=logging.INFO)
            self.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._lock = threading.Lock()
            self._lines: list[str] = []
            self._tool_events: list[dict[str, str | None]] = []

        def emit(self, record: logging.LogRecord) -> None:
            line = self.format(record)
            event = _parse_trace_event(record.getMessage())
            with self._lock:
                self._lines.append(line)
                self._lines = self._lines[-250:]
                if event:
                    self._merge_event_locked(event)

        def snapshot_lines(self) -> list[str]:
            with self._lock:
                return list(self._lines)

        def snapshot_events(self) -> list[dict[str, str | None]]:
            with self._lock:
                return [dict(item) for item in self._tool_events]

        def _merge_event_locked(self, event: dict[str, str]) -> None:
            tool_name = event["tool_name"]
            pending = next(
                (
                    item
                    for item in reversed(self._tool_events)
                    if item["tool_name"] == tool_name and item["status"] in {"planned", "running"}
                ),
                None,
            )
            if pending is None:
                pending = {
                    "tool_name": tool_name,
                    "status": "planned",
                    "planner_thought": None,
                    "planner_selection_source": None,
                    "planner_fallback_reason": None,
                    "planner_request": None,
                    "planner_response": None,
                    "inputs": None,
                    "output": None,
                    "error": None,
                }
                self._tool_events.append(pending)

            if event["step"] == "Planner selected next tool":
                pending["status"] = "planned"
                pending["planner_thought"] = event.get("thought")
            elif event["step"] == "Tool execution started":
                pending["status"] = "running"
                pending["inputs"] = event.get("inputs")
            elif event["step"] == "Tool execution completed":
                pending["status"] = "completed"
                pending["output"] = event.get("output")
            elif event["step"] == "Tool execution failed":
                pending["status"] = "failed"
                pending["error"] = event.get("error")

    return StreamlitTraceHandler()


def _render_live_trace(
    trace_handler: Any,
    *,
    status_placeholder: Any,
    tools_placeholder: Any,
    logs_placeholder: Any,
) -> None:
    tool_events = trace_handler.snapshot_events()
    process_logs = trace_handler.snapshot_lines()
    current = tool_events[-1] if tool_events else None
    if current:
        status_placeholder.info(f"Current tool: `{current['tool_name']}` | status: `{current['status']}`")
    else:
        status_placeholder.info("Waiting for the investigator to choose the first tool.")

    with tools_placeholder.container():
        st.markdown("### Live Tool Process")
        if not tool_events:
            st.caption("The planner and tool sequence will appear here as the run progresses.")
        for index, event in enumerate(tool_events, start=1):
            label = f"{index}. {event['tool_name']} [{event['status']}]"
            with st.expander(label, expanded=index == len(tool_events)):
                if event.get("planner_thought"):
                    st.write(f"**Planner Thought:** {event['planner_thought']}")
                if event.get("planner_selection_source"):
                    st.write(f"**Planner Mode:** `{event['planner_selection_source']}`")
                if event.get("planner_fallback_reason"):
                    st.warning(str(event["planner_fallback_reason"]))
                if event.get("planner_request"):
                    st.markdown("**Planner Request**")
                    _render_payload(event["planner_request"])
                if event.get("planner_response"):
                    st.markdown("**Planner Response**")
                    _render_payload(event["planner_response"])
                if event.get("inputs"):
                    st.markdown("**Inputs**")
                    _render_payload(event["inputs"])
                if event.get("output"):
                    _render_step_specific_output(event["tool_name"], event["output"])
                    st.markdown("**Output**")
                    _render_payload(event["output"])
                if event.get("error"):
                    st.error(str(event["error"]))

    with logs_placeholder.container():
        st.markdown("### Live Execution Logs")
        st.code("\n".join(process_logs[-80:]) or "Waiting for runtime logs...", language="text")


def _parse_trace_event(message: str) -> dict[str, str] | None:
    parts = message.split(" | ")
    if not parts:
        return None
    step = parts[0]
    if step not in {
        "Planner selected next tool",
        "Tool execution started",
        "Tool execution completed",
        "Tool execution failed",
    }:
        return None

    details: dict[str, str] = {"step": step}
    for fragment in parts[1:]:
        if "=" not in fragment:
            continue
        key, value = fragment.split("=", 1)
        details[key] = value

    if "tool_name" not in details:
        return None
    return details


def _render_payload(payload: str | None) -> None:
    if not payload:
        st.write("No payload captured.")
        return
    try:
        st.json(json.loads(payload))
    except json.JSONDecodeError:
        st.code(payload, language="text")


def _render_step_specific_output(tool_name: str | None, payload: str | None) -> None:
    parsed = _try_parse_json(payload) if payload else None
    if isinstance(parsed, dict):
        _render_elasticsearch_queries(parsed)

    if tool_name == "topology_walk":
        _render_topology_walk_output(parsed)
        return
    if tool_name == "healthy_window_comparison":
        _render_healthy_window_output(parsed)
        return
    if tool_name == "critic_pass":
        _render_critic_output(parsed)
        return
    if tool_name == "retrieve_signal_candidates":
        _render_signal_retrieval_output(payload)
        return
    if tool_name != "resolve_scope" or not payload:
        return
    if not isinstance(parsed, dict):
        return
    details = parsed.get("scope_resolution")
    if not isinstance(details, dict):
        return

    st.markdown("**Scope Resolution**")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("LLM Invoked", "Yes" if details.get("llm_invoked") else "No")
    validated = details.get("validated_resolution") if isinstance(details.get("validated_resolution"), dict) else {}
    metric_b.metric("Accepted", "Yes" if validated.get("accepted") else "No")
    llm_response = details.get("llm_response") if isinstance(details.get("llm_response"), dict) else {}
    usage = llm_response.get("usage") if isinstance(llm_response.get("usage"), dict) else {}
    metric_c.metric("Scope Tokens", str(usage.get("total_tokens", "n/a")))

    deterministic_hints = details.get("deterministic_hints")
    if isinstance(deterministic_hints, dict):
        st.caption("Deterministic hints")
        st.json(deterministic_hints)

    chosen = {
        "selected_node_id": validated.get("selected_node_id"),
        "service": validated.get("service"),
        "host": validated.get("host"),
        "ip": validated.get("ip"),
        "confidence": validated.get("confidence"),
    }
    st.caption("Chosen scope")
    st.json(chosen)

    if validated.get("accepted"):
        if llm_response.get("reason"):
            st.success(str(llm_response["reason"]))
    elif validated.get("rejection_reason"):
        st.warning(str(validated["rejection_reason"]))

    llm_request = details.get("llm_request")
    if isinstance(llm_request, dict):
        st.caption("LLM request")
        st.json(llm_request)

    if isinstance(llm_response, dict) and llm_response:
        st.caption("LLM response")
        st.json(llm_response)

    candidate_nodes = details.get("candidate_nodes")
    if isinstance(candidate_nodes, list) and candidate_nodes:
        st.caption("Candidate nodes")
        st.dataframe(
            candidate_nodes,
            use_container_width=True,
            hide_index=True,
            column_order=["node_id", "service", "host", "ip", "domain", "aliases"],
        )

    candidate_services = details.get("candidate_services")
    if isinstance(candidate_services, list) and candidate_services:
        st.caption("Candidate services")
        st.write(", ".join(str(item) for item in candidate_services))


def _render_elasticsearch_queries(payload: dict[str, Any]) -> None:
    queries = payload.get("elasticsearch_queries")
    if not isinstance(queries, list) or not queries:
        return

    st.markdown("**Elasticsearch DSL Queries**")
    st.caption("These are the exact Elasticsearch request bodies executed during this tool step.")
    for index, item in enumerate(queries, start=1):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "search"))
        page_number = item.get("page_number")
        pit_enabled = item.get("pit_enabled")
        index_value = item.get("index")
        label_parts = [f"{index}. {kind}"]
        if page_number is not None:
            label_parts.append(f"page {page_number}")
        if pit_enabled is not None:
            label_parts.append(f"PIT={'on' if pit_enabled else 'off'}")
        with st.expander(" | ".join(label_parts), expanded=index == 1):
            meta = {
                "kind": kind,
                "page_number": page_number,
                "pit_enabled": pit_enabled,
                "index": index_value,
            }
            st.caption("Query metadata")
            st.json(meta)
            if "body" in item:
                st.caption("Request body")
                st.json(item["body"])


def _render_topology_walk_output(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    topology_graph = payload.get("topology_graph")
    node_inspections = payload.get("node_inspections")
    impacted_node = payload.get("impacted_node")
    topology_hops = payload.get("topology_hops")
    topology_metadata = payload.get("topology_metadata")
    topology_comparison_rounds = payload.get("topology_comparison_rounds")
    if not isinstance(topology_graph, dict) or not isinstance(node_inspections, list):
        return

    st.markdown("**Topology Walk Graph**")
    _render_topology_legend()

    if isinstance(topology_metadata, dict):
        st.caption("Selected topology document for this run")
        st.json(topology_metadata)

    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Impacted Node", str((impacted_node or {}).get("node_id", "unknown")))
    metric_b.metric("Validated Hops", str(len(topology_hops) if isinstance(topology_hops, list) else 0))
    metric_c.metric("Topology Nodes", str(len(topology_graph.get("nodes", [])) if isinstance(topology_graph.get("nodes"), list) else 0))

    st.caption("Whole-topology overview")
    _render_topology_graphviz(topology_graph)

    node_options = _topology_node_options(topology_graph, node_inspections)
    selected_node_id = None
    if go is not None:
        st.caption("Interactive topology graph")
        selection = _render_topology_graph_plot(topology_graph, node_inspections)
        selected_node_id = _extract_selected_node_id(selection)
        if selected_node_id:
            st.session_state["topology_selected_node_id"] = selected_node_id
    else:
        st.info("Interactive click-to-select graph is available after installing `plotly`, but the full topology overview is already shown above.")

    selected_node_id = (
        selected_node_id
        or st.session_state.get("topology_selected_node_id")
        or ((impacted_node or {}).get("node_id") if isinstance(impacted_node, dict) else None)
    )

    default_index = 0
    option_values = [item["node_id"] for item in node_options]
    if selected_node_id in option_values:
        default_index = option_values.index(selected_node_id)
    chosen_node_id = st.selectbox(
        "Selected topology node",
        options=option_values,
        index=default_index if option_values else 0,
        format_func=lambda node_id: _format_topology_node_option(node_id, node_options),
        key=f"topology-node-select-{(impacted_node or {}).get('node_id', 'unknown')}",
    ) if option_values else None
    if chosen_node_id:
        st.session_state["topology_selected_node_id"] = chosen_node_id
        _render_topology_node_details(chosen_node_id, topology_graph, node_inspections)

    if isinstance(topology_comparison_rounds, list) and topology_comparison_rounds:
        with st.expander("Topology Candidate Comparison", expanded=True):
            for round_item in topology_comparison_rounds:
                if not isinstance(round_item, dict):
                    continue
                round_depth = round_item.get("depth")
                source_node_id = round_item.get("source_node_id")
                selected_node_id = round_item.get("selected_node_id")
                candidates = round_item.get("candidates")
                critic_review = round_item.get("critic_review")
                service_policy = round_item.get("service_policy")
                if not isinstance(candidates, list):
                    continue
                st.markdown(f"**Round {round_depth}: source `{source_node_id}`**")
                if selected_node_id:
                    st.write(f"Selected next hop: `{selected_node_id}`")
                if isinstance(service_policy, dict):
                    st.caption("Applied service policy")
                    st.json(service_policy)
                if isinstance(critic_review, dict):
                    st.caption("Topology round critic")
                    st.json(critic_review)
                rows = [
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
                        "first_seen": item.get("first_seen"),
                        "policy_name": item.get("policy_name"),
                        "critic_adjustment": item.get("critic_adjustment"),
                        "score": item.get("score"),
                        "rejection_reason": item.get("rejection_reason"),
                    }
                    for item in candidates
                    if isinstance(item, dict)
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
                with st.expander(f"Round {round_depth} score breakdowns", expanded=False):
                    st.json(candidates)

    alternate_paths = payload.get("alternate_paths")
    if isinstance(alternate_paths, list) and alternate_paths:
        with st.expander("Retained Alternate Paths", expanded=False):
            st.dataframe(alternate_paths, use_container_width=True, hide_index=True)

    with st.expander("Topology Connections", expanded=False):
        edges = topology_graph.get("edges")
        if isinstance(edges, list) and edges:
            rows = [
                {
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "relation": edge.get("relation"),
                    "relation_type": edge.get("relation_type"),
                    "relation_label": edge.get("relation_label"),
                    "semantic_relation": edge.get("semantic_relation"),
                    "description": edge.get("description"),
                    "weight": edge.get("weight"),
                    "criticality": edge.get("criticality"),
                    "direction": _edge_direction_text(edge),
                    "validated_path": edge.get("is_validated_path"),
                }
                for edge in edges
                if isinstance(edge, dict)
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.write("No topology edges were available.")


def _render_topology_legend() -> None:
    badges = [
        _badge_html("impacted", "#dc2626"),
        _badge_html("hop 1", "#f59e0b"),
        _badge_html("hop 2", "#2563eb"),
        _badge_html("hop 3+", "#16a34a"),
        _badge_html("tested not selected", "#a16207"),
        _badge_html("rejected", "#64748b"),
        _badge_html("other topology", "#cbd5e1"),
    ]
    st.markdown(" ".join(badges), unsafe_allow_html=True)


def _render_topology_graphviz(topology_graph: dict[str, Any]) -> None:
    dot = _build_topology_dot(topology_graph)
    st.graphviz_chart(dot, use_container_width=True)


def _build_topology_dot(topology_graph: dict[str, Any]) -> str:
    nodes = topology_graph.get("nodes") if isinstance(topology_graph.get("nodes"), list) else []
    edges = topology_graph.get("edges") if isinstance(topology_graph.get("edges"), list) else []
    lines = [
        "digraph Topology {",
        '  graph [rankdir=LR, bgcolor="#0b1220", pad="0.3", nodesep="0.55", ranksep="1.0"];',
        '  node [shape=box, style="rounded,filled", color="#111827", fontname="Helvetica", fontsize=11, fontcolor="#e5e7eb", margin="0.18,0.1"];',
        '  edge [fontname="Helvetica", fontsize=10, color="#94a3b8", fontcolor="#cbd5e1", arrowsize=0.8];',
    ]

    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        node_id = str(node["node_id"])
        label = f'{node.get("service", "unknown")}\\n{node.get("ip", "")}'
        fill = _topology_node_color(node, None)
        border = "#ef4444" if node.get("is_impacted") else "#1f2937"
        penwidth = "3" if node.get("is_impacted") else "1.5"
        lines.append(
            f'  "{_dot_escape(node_id)}" [label="{_dot_escape(label)}", fillcolor="{fill}", color="{border}", penwidth="{penwidth}"];'
        )

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        color = "#ef4444" if edge.get("is_validated_path") else "#64748b"
        penwidth = "3" if edge.get("is_validated_path") else "1.3"
        label = str(edge.get("label", edge.get("relation", "")))
        direction = str(edge.get("graphviz_dir", "forward"))
        style = "dashed" if edge.get("relation") == "underlay" else "solid"
        lines.append(
            f'  "{_dot_escape(str(source))}" -> "{_dot_escape(str(target))}" [label="{_dot_escape(label)}", color="{color}", penwidth="{penwidth}", dir="{direction}", style="{style}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def _render_topology_graph_plot(topology_graph: dict[str, Any], node_inspections: list[dict[str, Any]]) -> Any:
    fig = _build_topology_figure(topology_graph, node_inspections)
    return st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key=f"topology-graph-{len(topology_graph.get('nodes', []))}-{len(topology_graph.get('edges', []))}",
    )


def _build_topology_figure(topology_graph: dict[str, Any], node_inspections: list[dict[str, Any]]) -> Any:
    nodes = topology_graph.get("nodes") if isinstance(topology_graph.get("nodes"), list) else []
    edges = topology_graph.get("edges") if isinstance(topology_graph.get("edges"), list) else []
    positions = _compute_topology_positions(nodes, edges, topology_graph.get("validated_path"))
    node_lookup = {node["node_id"]: node for node in nodes if isinstance(node, dict) and node.get("node_id")}
    inspection_lookup = {
        item["node_id"]: item
        for item in node_inspections
        if isinstance(item, dict) and item.get("node_id")
    }

    fig = go.Figure()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source not in positions or target not in positions:
            continue
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line={
                    "color": "#ef4444" if edge.get("is_validated_path") else "#94a3b8",
                    "width": 3 if edge.get("is_validated_path") else 1.5,
                    "dash": "dot" if edge.get("relation") == "underlay" else "solid",
                },
                hoverinfo="skip",
                showlegend=False,
            )
        )
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        fig.add_trace(
            go.Scatter(
                x=[mid_x],
                y=[mid_y],
                mode="text",
                text=[str(edge.get("label", ""))],
                textfont={"size": 11, "color": "#cbd5e1"},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    x_values: list[float] = []
    y_values: list[float] = []
    texts: list[str] = []
    customdata: list[list[str]] = []
    colors: list[str] = []
    sizes: list[int] = []
    for node_id, (x, y) in positions.items():
        node = node_lookup.get(node_id, {})
        inspection = inspection_lookup.get(node_id)
        x_values.append(x)
        y_values.append(y)
        texts.append(f"{node.get('service', 'unknown')}<br>{node.get('ip', '')}")
        customdata.append([node_id])
        colors.append(_topology_node_color(node, inspection))
        sizes.append(30 if node.get("is_impacted") else 24 if node.get("path_depth") is not None else 18)

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers+text",
            text=texts,
            textposition="top center",
            customdata=customdata,
            marker={
                "size": sizes,
                "color": colors,
                "line": {"width": 2, "color": "#111827"},
            },
            hovertemplate="<b>%{customdata[0]}</b><br>%{text}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=640,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        plot_bgcolor="#0b1220",
        paper_bgcolor="#0b1220",
        xaxis={"visible": False},
        yaxis={"visible": False},
        dragmode="select",
        font={"color": "#e5e7eb"},
    )
    return fig


def _compute_topology_positions(nodes: list[Any], edges: list[Any], validated_path: Any) -> dict[str, tuple[float, float]]:
    node_ids = [str(node.get("node_id")) for node in nodes if isinstance(node, dict) and node.get("node_id")]
    impacted = None
    if isinstance(validated_path, list) and validated_path:
        impacted = str(validated_path[0])
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)

    distances: dict[str, int] = {}
    if impacted and impacted in adjacency:
        frontier = [impacted]
        distances[impacted] = 0
        while frontier:
            current = frontier.pop(0)
            for neighbor in adjacency.get(current, set()):
                if neighbor in distances:
                    continue
                distances[neighbor] = distances[current] + 1
                frontier.append(neighbor)

    layers: dict[int, list[str]] = {}
    fallback_layer = (max(distances.values()) + 1) if distances else 0
    for node_id in node_ids:
        layer = distances.get(node_id, fallback_layer)
        layers.setdefault(layer, []).append(node_id)

    positions: dict[str, tuple[float, float]] = {}
    for layer, layer_nodes in sorted(layers.items()):
        layer_nodes.sort()
        total = len(layer_nodes)
        for index, node_id in enumerate(layer_nodes):
            y = 0.0 if total == 1 else (total - 1) / 2 - index
            positions[node_id] = (float(layer), y * 1.8)
    return positions


def _topology_node_color(node: dict[str, Any], inspection: dict[str, Any] | None) -> str:
    path_depth = node.get("path_depth")
    if node.get("is_impacted"):
        return "#dc2626"
    if path_depth == 1:
        return "#f59e0b"
    if path_depth == 2:
        return "#2563eb"
    if isinstance(path_depth, int) and path_depth >= 3:
        return "#16a34a"
    if inspection and inspection.get("status") == "considered_not_selected":
        return "#a16207"
    if inspection and inspection.get("status") == "rejected":
        return "#64748b"
    if inspection:
        return "#0ea5e9"
    return "#cbd5e1"


def _extract_selected_node_id(selection: Any) -> str | None:
    if selection is None:
        return None
    points = None
    if isinstance(selection, dict):
        if isinstance(selection.get("selection"), dict):
            points = selection.get("selection", {}).get("points")
        elif isinstance(selection.get("points"), list):
            points = selection.get("points")
    else:
        selection_attr = getattr(selection, "selection", None)
        if selection_attr is not None:
            points = getattr(selection_attr, "points", None)
    if not isinstance(points, list) or not points:
        return None
    first_point = points[0]
    if isinstance(first_point, dict):
        customdata = first_point.get("customdata")
        if isinstance(customdata, list) and customdata:
            return str(customdata[0])
    return None


def _topology_node_options(topology_graph: dict[str, Any], node_inspections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = topology_graph.get("nodes") if isinstance(topology_graph.get("nodes"), list) else []
    inspection_lookup = {
        item["node_id"]: item
        for item in node_inspections
        if isinstance(item, dict) and item.get("node_id")
    }
    options: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        merged = dict(node)
        merged["inspection_status"] = (inspection_lookup.get(node["node_id"]) or {}).get("status")
        options.append(merged)
    options.sort(key=lambda item: ((item.get("path_depth") is None), item.get("path_depth") or 99, item["node_id"]))
    return options


def _format_topology_node_option(node_id: str, options: list[dict[str, Any]]) -> str:
    option = next((item for item in options if item.get("node_id") == node_id), None)
    if not option:
        return node_id
    service = option.get("service", "unknown")
    ip = option.get("ip", "")
    status = option.get("inspection_status") or "topology"
    return f"{service} | {ip} | {status}"


def _render_topology_node_details(node_id: str, topology_graph: dict[str, Any], node_inspections: list[dict[str, Any]]) -> None:
    node = next(
        (item for item in topology_graph.get("nodes", []) if isinstance(item, dict) and item.get("node_id") == node_id),
        None,
    )
    inspection = next(
        (item for item in node_inspections if isinstance(item, dict) and item.get("node_id") == node_id),
        None,
    )
    if not node:
        st.write("No topology details were available for the selected node.")
        return

    st.markdown("**Selected Node Details**")
    info_a, info_b = st.columns(2)
    with info_a:
        st.json(
            {
                "node_id": node.get("node_id"),
                "service": node.get("service"),
                "host": node.get("host"),
                "ip": node.get("ip"),
                "domain": node.get("domain"),
                "path_depth": node.get("path_depth"),
            }
        )
    with info_b:
        if inspection:
            st.json(
                {
                    "status": inspection.get("status"),
                    "hop_type": inspection.get("hop_type"),
                    "source_node_id": inspection.get("source_node_id"),
                    "matched_signal_count": inspection.get("matched_signal_count"),
                    "chronology_ok": inspection.get("chronology_ok"),
                    "candidate_signals": inspection.get("candidate_signals"),
                    "time_window": inspection.get("time_window"),
                }
            )
        else:
            st.write("This node is part of the topology but was not directly inspected during the current walk.")

    if inspection and inspection.get("summary"):
        st.info(str(inspection["summary"]))

    if inspection and isinstance(inspection.get("elasticsearch_queries"), list) and inspection["elasticsearch_queries"]:
        st.caption("Queries executed for this node")
        for index, query in enumerate(inspection["elasticsearch_queries"], start=1):
            with st.expander(f"Node query {index}", expanded=index == 1):
                st.json(query)

    if inspection and isinstance(inspection.get("fetched_logs"), list) and inspection["fetched_logs"]:
        st.caption("Fetched logs for this node")
        st.dataframe(
            inspection["fetched_logs"],
            use_container_width=True,
            hide_index=True,
            column_order=["timestamp", "service", "host", "ip", "severity", "signal", "message", "doc_id"],
        )


def _try_parse_json(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _render_signal_retrieval_output(payload: str | None) -> None:
    if not payload:
        return
    parsed = _try_parse_json(payload)
    if not isinstance(parsed, dict):
        return
    details = parsed.get("retrieval_details")
    if not isinstance(details, dict):
        return

    st.markdown("**Two-Layer Retrieval**")
    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    layer_1_scope = details.get("layer_1_scope") if isinstance(details.get("layer_1_scope"), dict) else {}
    metric_a.metric("Layer 1 Scope", f"{layer_1_scope.get('type', 'unknown')}:{layer_1_scope.get('key', 'unknown')}")
    modes = details.get("layer_2_modes") if isinstance(details.get("layer_2_modes"), list) else []
    metric_b.metric("Layer 2 Mode", ", ".join(_format_retrieval_mode(str(item)) for item in modes) or "none")
    metric_c.metric("Semantic Candidates", str(details.get("semantic_candidate_count", 0)))
    metric_d.metric("Expanded signal_set", str(details.get("expanded_signal_count", 0)))

    _render_mode_badges(modes)

    if layer_1_scope:
        st.caption("Layer 1 deterministic routing")
        st.json(layer_1_scope)

    candidate_signals = parsed.get("candidate_signals")
    if isinstance(candidate_signals, list) and candidate_signals:
        st.caption("Layer 2 ranked candidate signals")
        st.dataframe(
            candidate_signals,
            use_container_width=True,
            hide_index=True,
            column_order=["signal", "service", "domain", "score", "semantic_score", "retrieval_mode", "matched_terms"],
        )

    expanded_names = parsed.get("candidate_signal_names")
    if isinstance(expanded_names, list) and expanded_names:
        st.caption("Final expanded signal_set used downstream")
        st.code("\n".join(f"- {item}" for item in expanded_names), language="text")


def _render_healthy_window_output(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    comparison = payload.get("comparison")
    if not isinstance(comparison, dict):
        return
    st.markdown("**Healthy Window Comparison**")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Anomaly Score", str(comparison.get("anomaly_score", "n/a")))
    metric_b.metric("Event Ratio", str(comparison.get("event_ratio", "n/a")))
    metric_c.metric("Signal Ratio", str(comparison.get("signal_ratio", "n/a")))
    st.caption("Comparison summary")
    st.json(
        {
            "target_node_id": payload.get("target_node_id"),
            "incident_window": payload.get("incident_window"),
            "healthy_window": payload.get("healthy_window"),
            "incident_summary": payload.get("incident_summary"),
            "healthy_summary": payload.get("healthy_summary"),
            "comparison": comparison,
        }
    )


def _render_critic_output(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    critic = payload.get("critic")
    if not isinstance(critic, dict):
        return
    st.markdown("**Weak RCA Critic**")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Verdict", str(critic.get("verdict", "unknown")))
    metric_b.metric("Recommended Classification", str(critic.get("recommended_classification", "none")))
    metric_c.metric("Confidence Delta", str(critic.get("confidence_delta", 0.0)))
    st.caption("Critic result")
    st.json(critic)


def _merge_exact_tool_results(
    tool_events: list[dict[str, str | None]],
    exact_tool_results: dict[str, Any],
    planner_trace: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    merged: list[dict[str, str | None]] = []
    planner_entries = [item for item in planner_trace if isinstance(item, dict)]
    planner_index = 0
    for event in tool_events:
        item = dict(event)
        tool_name = item.get("tool_name")
        if tool_name and tool_name in exact_tool_results and item.get("status") == "completed":
            item["output"] = json.dumps(exact_tool_results[tool_name], ensure_ascii=False, indent=2)
        if tool_name and planner_index < len(planner_entries):
            while planner_index < len(planner_entries):
                planner_item = planner_entries[planner_index]
                planner_index += 1
                if planner_item.get("selected_tool_name") != tool_name:
                    continue
                item["planner_selection_source"] = str(planner_item.get("selection_source") or "")
                item["planner_fallback_reason"] = str(planner_item.get("fallback_reason") or "") or None
                request_payload = planner_item.get("request")
                response_payload = planner_item.get("response")
                item["planner_request"] = (
                    json.dumps(request_payload, ensure_ascii=False, indent=2) if isinstance(request_payload, dict) else None
                )
                item["planner_response"] = (
                    json.dumps(response_payload, ensure_ascii=False, indent=2) if isinstance(response_payload, dict) else None
                )
                if planner_item.get("thought") and not item.get("planner_thought"):
                    item["planner_thought"] = str(planner_item["thought"])
                break
        merged.append(item)
    return merged


def _render_retrieval_runtime_summary(exact_tool_results: dict[str, Any]) -> None:
    payload = exact_tool_results.get("retrieve_signal_candidates")
    if not isinstance(payload, dict):
        return
    details = payload.get("retrieval_details")
    if not isinstance(details, dict):
        return

    st.markdown("### Retrieval Runtime")
    layer_1_scope = details.get("layer_1_scope") if isinstance(details.get("layer_1_scope"), dict) else {}
    modes = details.get("layer_2_modes") if isinstance(details.get("layer_2_modes"), list) else []

    info_a, info_b = st.columns([1.2, 2.0])
    with info_a:
        st.write(f"**Layer 1 Scope:** `{layer_1_scope.get('type', 'unknown')}:{layer_1_scope.get('key', 'unknown')}`")
        st.write(f"**Semantic Candidates:** `{details.get('semantic_candidate_count', 0)}`")
    with info_b:
        st.write("**Retrieval Mode Badges**")
        _render_mode_badges(modes)


def _render_mode_badges(modes: list[Any]) -> None:
    if not modes:
        st.caption("No retrieval mode metadata was recorded.")
        return
    badges = " ".join(_badge_html(_format_retrieval_mode(str(mode)), _badge_color(str(mode))) for mode in modes)
    st.markdown(badges, unsafe_allow_html=True)


def _format_retrieval_mode(mode: str) -> str:
    mapping = {
        "hybrid_vector": "hybrid_vector",
        "lexical_fallback": "lexical fallback",
        "domain_fallback": "domain fallback",
    }
    return mapping.get(mode, mode.replace("_", " "))


def _badge_color(mode: str) -> str:
    mapping = {
        "hybrid_vector": "#0f766e",
        "lexical_fallback": "#92400e",
        "domain_fallback": "#7c3aed",
    }
    return mapping.get(mode, "#334155")


def _badge_html(label: str, color: str) -> str:
    return (
        f"<span style='display:inline-block;padding:0.3rem 0.65rem;margin:0 0.45rem 0.45rem 0;"
        f"border-radius:999px;background:{color};color:white;font-size:0.85rem;font-weight:600;'>"
        f"{label}</span>"
    )


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def _edge_direction_text(edge: dict[str, Any]) -> str:
    relation = str(edge.get("relation", ""))
    source = str(edge.get("source", ""))
    target = str(edge.get("target", ""))
    if relation == "depends_on":
        return f"{source} -> {target}"
    if relation == "underlay":
        return f"{source} -> {target}"
    return f"{source} -> {target}"


if __name__ == "__main__":
    main()
