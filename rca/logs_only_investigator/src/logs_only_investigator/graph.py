from __future__ import annotations

import json
import logging
import warnings
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change in a future version\..*",
    category=LangChainPendingDeprecationWarning,
)

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .config import LoggingConfig, OpenAIConfig
from .llm import (
    CriticGenerator,
    DeterministicExplanationGenerator,
    DisabledCriticGenerator,
    DisabledPlannerGenerator,
    DisabledScopeResolutionGenerator,
    ExplanationGenerator,
    PlannerGenerator,
    ScopeResolutionGenerator,
)
from .observability import log_step, redact_for_logging
from .rag import CatalogRepository
from .service import InvestigationService, _score_and_classify
from .tools.log_store import LogStore
from .topology_source import TopologySource


class InvestigatorState(MessagesState, total=False):
    request_options: dict[str, Any]
    session_memory: dict[str, Any]
    report: dict[str, Any]
    tool_results: dict[str, Any]
    planner_trace: list[dict[str, Any]]


@dataclass
class InvestigatorAgent:
    graph: Any
    logger: logging.Logger | None = None

    def invoke(self, input_state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        prepared = dict(input_state)
        if "messages" not in prepared:
            query = prepared.pop("user_query", "")
            prepared["messages"] = [HumanMessage(content=query)]
        prepared["request_options"] = {
            "organization_id": prepared.pop("organization_id", "default-org"),
            "start_time": prepared.pop("start_time", None),
            "end_time": prepared.pop("end_time", None),
            "service": prepared.pop("service", None),
            "host": prepared.pop("host", None),
            "ip": prepared.pop("ip", None),
        }
        runtime_config = config or {"configurable": {"thread_id": f"thread-{uuid4()}"}}
        thread_id = runtime_config.get("configurable", {}).get("thread_id", "unknown-thread")
        if self.logger:
            _safe_log_step(
                self.logger,
                logging.INFO,
                "Agent invocation started",
                thread_id=thread_id,
                request_options=redact_for_logging(prepared["request_options"]),
            )
        result = self.graph.invoke(prepared, config=runtime_config)
        if self.logger:
            report = result.get("report", {})
            _safe_log_step(
                self.logger,
                logging.INFO,
                "Agent invocation completed",
                thread_id=thread_id,
                classification=report.get("classification"),
                confidence=report.get("confidence"),
                likely_root_cause=report.get("likely_root_cause"),
            )
        return result

    def get_state(self, thread_id: str):
        return self.graph.get_state({"configurable": {"thread_id": thread_id}})


def build_graph(
    log_store: LogStore,
    catalogs: CatalogRepository,
    topology_source: TopologySource,
    explanation_generator: ExplanationGenerator | None = None,
    scope_resolution_generator: ScopeResolutionGenerator | None = None,
    planner_generator: PlannerGenerator | None = None,
    critic_generator: CriticGenerator | None = None,
    openai_config: OpenAIConfig | None = None,
    max_hops: int = 4,
    logger: logging.Logger | None = None,
    logging_config: LoggingConfig | None = None,
) -> InvestigatorAgent:
    service = InvestigationService(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=topology_source,
        explanation_generator=explanation_generator or DeterministicExplanationGenerator(),
        scope_resolution_generator=scope_resolution_generator or DisabledScopeResolutionGenerator(),
        critic_generator=critic_generator or DisabledCriticGenerator(),
        openai_config=openai_config,
        max_hops=max_hops,
    )
    planner_generator = planner_generator or DisabledPlannerGenerator()
    tools = _build_tools(service, logger=logger, logging_config=logging_config)
    tool_node = ToolNode(tools)

    def planner_node(state: InvestigatorState) -> dict[str, Any]:
        messages = state["messages"]
        current_turn = _current_turn_messages(messages)
        current_human = next((message for message in reversed(current_turn) if isinstance(message, HumanMessage)), None)
        if current_human is None:
            return {"messages": [AIMessage(content="No user query was available for investigation.")]}

        tool_results = _collect_tool_results(current_turn, logger=logger)
        planner_trace = [] if len(current_turn) == 1 else list(state.get("planner_trace", []))
        tool_error = next(
            (
                {
                    "tool_name": name,
                    "error": payload["error"],
                }
                for name, payload in tool_results.items()
                if isinstance(payload, dict) and payload.get("error")
            ),
            None,
        )
        if tool_error:
            error_message = f"Investigation stopped in tool '{tool_error['tool_name']}': {tool_error['error']}"
            return {
                "report": {
                    "summary": error_message,
                    "analyst_summary": error_message,
                    "classification": "execution_error",
                    "confidence": 0.0,
                },
                "tool_results": tool_results,
                "planner_trace": planner_trace,
                "messages": [AIMessage(content=error_message)],
            }
        request = dict(state.get("request_options", {}))
        session_memory = dict(state.get("session_memory", {}))

        if "compose_report" in tool_results:
            compose_payload = tool_results["compose_report"]
            report = compose_payload["report"]
            return {
                "report": report,
                "session_memory": compose_payload["session_memory"],
                "tool_results": tool_results,
                "planner_trace": planner_trace,
                "messages": [AIMessage(content=report["analyst_summary"])],
            }

        available_tool_calls = _available_tool_calls(
            query=current_human.content,
            request=request,
            session_memory=session_memory,
            tool_results=tool_results,
        )
        deterministic_next = _next_tool_call(
            query=current_human.content,
            request=request,
            session_memory=session_memory,
            tool_results=tool_results,
            available_tool_calls=available_tool_calls,
        )
        next_call = dict(deterministic_next)
        planner_decision: dict[str, Any] | None = None
        planner_selection_source = "deterministic"
        planner_fallback_reason: str | None = None
        if len(available_tool_calls) == 1:
            planner_selection_source = "forced_single_option"
        elif openai_config and openai_config.planner_enabled and openai_config.planner_mode != "deterministic":
            planner_context = _build_planner_context(
                query=current_human.content,
                request=request,
                session_memory=session_memory,
                tool_results=tool_results,
                available_tool_calls=available_tool_calls,
            )
            planner_decision = planner_generator.choose_next_action(planner_context)
            validated = _validate_planner_decision(
                planner_decision=planner_decision,
                available_tool_calls=available_tool_calls,
            )
            if validated["accepted"]:
                llm_choice = available_tool_calls[validated["tool_name"]]
                next_call = {
                    "name": llm_choice["name"],
                    "thought": str(planner_decision.get("thought") or llm_choice["thought"]),
                    "args": dict(llm_choice["args"]),
                }
                planner_selection_source = "llm_hybrid"
            else:
                planner_selection_source = "deterministic_fallback"
                planner_fallback_reason = validated["reason"]
        planner_trace.append(
            {
                "selected_tool_name": next_call["name"],
                "selection_source": planner_selection_source,
                "fallback_reason": planner_fallback_reason,
                "available_tools": list(available_tool_calls.keys()),
                "request": planner_decision.get("request") if isinstance(planner_decision, dict) else None,
                "response": planner_decision,
                "thought": next_call["thought"],
            }
        )
        if logger:
            _safe_log_step(
                logger,
                logging.INFO,
                "Planner selected next tool",
                tool_name=next_call["name"],
                thought=next_call["thought"],
                planner_mode=planner_selection_source,
                fallback_reason=planner_fallback_reason,
            )
        return {
            "planner_trace": planner_trace,
            "tool_results": tool_results,
            "messages": [
                AIMessage(
                    content=next_call["thought"],
                    tool_calls=[
                        {
                            "name": next_call["name"],
                            "args": next_call["args"],
                            "id": str(uuid4()),
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    builder = StateGraph(InvestigatorState)
    builder.add_node("planner", planner_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", tools_condition, {"tools": "tools", "__end__": END})
    builder.add_edge("tools", "planner")

    graph = builder.compile(
        checkpointer=InMemorySaver(serde=JsonPlusSerializer())
    )
    return InvestigatorAgent(graph=graph, logger=logger)


def _build_tools(
    service: InvestigationService,
    *,
    logger: logging.Logger | None,
    logging_config: LoggingConfig | None,
) -> list[Any]:
    preview_chars = logging_config.payload_preview_chars if logging_config else 1200
    log_inputs = logging_config.log_inputs if logging_config else True
    log_outputs = logging_config.log_outputs if logging_config else True

    def run_tool(tool_name: str, arguments: dict[str, Any], operation: Any) -> str:
        if logger:
            details: dict[str, Any] = {"tool_name": tool_name}
            if log_inputs:
                details["inputs"] = redact_for_logging(arguments, max_chars=preview_chars)
            _safe_log_step(logger, logging.INFO, "Tool execution started", **details)
        try:
            payload = operation()
        except Exception as exc:
            if logger:
                _safe_log_step(
                    logger,
                    logging.ERROR,
                    "Tool execution failed",
                    tool_name=tool_name,
                    error=str(exc),
                )
            return json.dumps(
                {
                    "error": str(exc),
                    "trace": [f"Tool {tool_name} failed: {exc}"],
                }
            )
        if logger:
            details = {"tool_name": tool_name}
            if log_outputs:
                details["output"] = redact_for_logging(payload, max_chars=preview_chars)
            _safe_log_step(logger, logging.INFO, "Tool execution completed", **details)
        return json.dumps(payload)

    @tool
    def resolve_scope(
        query: str,
        organization_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        service_name: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        session_memory_json: str | None = None,
    ) -> str:
        """Resolve the bounded RCA scope for the current turn.

        Inputs:
        - `query`: the user's natural-language incident question.
        - `organization_id`: tenant or organization identifier used for log and topology lookup.
        - `start_time` and `end_time`: optional explicit ISO8601 bounds.
        - `service_name`, `host`, `ip`: optional hard filters that override inferred scope.
        - `session_memory_json`: prior thread memory serialized as JSON.

        Output:
        - JSON with `parsed_query`, resolved `scope`, and a human-readable `trace`.
        """
        arguments = {
            "query": query,
            "organization_id": organization_id,
            "start_time": start_time,
            "end_time": end_time,
            "service_name": service_name,
            "host": host,
            "ip": ip,
            "session_memory_json": session_memory_json,
        }
        return run_tool(
            "resolve_scope",
            arguments,
            lambda: service.resolve_scope(
                query=query,
                organization_id=organization_id,
                start_time=start_time,
                end_time=end_time,
                service=service_name,
                host=host,
                ip=ip,
                session_memory=_json_loads(session_memory_json) if session_memory_json else {},
            ),
        )

    @tool
    def retrieve_signal_candidates(query: str, parsed_query_json: str, scope_json: str) -> str:
        """Rank the most relevant signal definitions for the incident wording.

        Inputs:
        - `query`: the user's natural-language question.
        - `parsed_query_json`: structured query intent from `resolve_scope`.
        - `scope_json`: resolved scope from `resolve_scope`.

        Output:
        - JSON containing `rag_scope`, ranked `candidate_signals`, `candidate_signal_names`, `needs_discovery`, and `trace`.
        """
        arguments = {
            "query": query,
            "parsed_query_json": parsed_query_json,
            "scope_json": scope_json,
        }
        return run_tool(
            "retrieve_signal_candidates",
            arguments,
            lambda: service.retrieve_signal_candidates(
                query=query,
                parsed_query=_json_loads(parsed_query_json),
                scope=_json_loads(scope_json),
            ),
        )

    @tool
    def aggregate_discovery(scope_json: str, candidate_signal_names_json: str) -> str:
        """Find hotspot buckets and dominant entities when the query is too broad.

        Inputs:
        - `scope_json`: resolved incident scope.
        - `candidate_signal_names_json`: candidate signal names chosen from the catalog.

        Output:
        - JSON containing `discovery_summary` and `trace`.
        """
        arguments = {
            "scope_json": scope_json,
            "candidate_signal_names_json": candidate_signal_names_json,
        }
        return run_tool(
            "aggregate_discovery",
            arguments,
            lambda: service.aggregate_discovery(
                scope=_json_loads(scope_json),
                candidate_signal_names=_json_loads(candidate_signal_names_json),
            ),
        )

    @tool
    def build_initial_anchor(
        scope_json: str,
        candidate_signals_json: str,
        candidate_signal_names_json: str,
        discovery_summary_json: str | None = None,
    ) -> str:
        """Construct the initial evidence anchor used for the first-circle search.

        Inputs:
        - `scope_json`: resolved incident scope.
        - `candidate_signals_json`: ranked candidate signals with scores.
        - `candidate_signal_names_json`: prioritized signal names.
        - `discovery_summary_json`: optional hotspot summary from `aggregate_discovery`.

        Output:
        - JSON containing the `anchor` and `trace`.
        """
        arguments = {
            "scope_json": scope_json,
            "candidate_signals_json": candidate_signals_json,
            "candidate_signal_names_json": candidate_signal_names_json,
            "discovery_summary_json": discovery_summary_json,
        }
        return run_tool(
            "build_initial_anchor",
            arguments,
            lambda: service.build_initial_anchor(
                scope=_json_loads(scope_json),
                candidate_signals=_json_loads(candidate_signals_json),
                candidate_signal_names=_json_loads(candidate_signal_names_json),
                discovery_summary=_json_loads(discovery_summary_json) if discovery_summary_json else None,
            ),
        )

    @tool
    def first_circle_search(anchor_json: str, parsed_query_json: str, organization_id: str) -> str:
        """Fetch the first bounded set of evidence around the active anchor.

        Inputs:
        - `anchor_json`: anchor created by `build_initial_anchor`.
        - `parsed_query_json`: query intent from `resolve_scope`.
        - `organization_id`: tenant identifier used for Elasticsearch queries.

        Output:
        - JSON containing the active `anchor`, `first_circle` summary, and `trace`.
        """
        arguments = {
            "anchor_json": anchor_json,
            "parsed_query_json": parsed_query_json,
            "organization_id": organization_id,
        }
        return run_tool(
            "first_circle_search",
            arguments,
            lambda: service.first_circle_search(
                anchor=_json_loads(anchor_json),
                parsed_query=_json_loads(parsed_query_json),
                organization_id=organization_id,
            ),
        )

    @tool
    def topology_walk(anchor_json: str, first_circle_json: str, parsed_query_json: str, scope_json: str) -> str:
        """Walk topology relationships to validate earlier upstream or underlay evidence.

        Inputs:
        - `anchor_json`: current impact anchor.
        - `first_circle_json`: first-circle evidence summary.
        - `parsed_query_json`: query intent from `resolve_scope`.
        - `scope_json`: resolved investigation scope.

        Output:
        - JSON containing `impacted_node`, `topology_hops`, `rejected_paths`, and `trace`.
        """
        arguments = {
            "anchor_json": anchor_json,
            "first_circle_json": first_circle_json,
            "parsed_query_json": parsed_query_json,
            "scope_json": scope_json,
        }
        return run_tool(
            "topology_walk",
            arguments,
            lambda: service.topology_walk(
                anchor=_json_loads(anchor_json),
                first_circle=_json_loads(first_circle_json),
                parsed_query=_json_loads(parsed_query_json),
                scope=_json_loads(scope_json),
            ),
        )

    @tool
    def raw_log_context(scope_json: str, first_circle_json: str, topology_walk_json: str) -> str:
        """Fetch a small raw-log slice around the strongest validated evidence IDs.

        Inputs:
        - `scope_json`: resolved incident scope.
        - `first_circle_json`: first-circle evidence summary.
        - `topology_walk_json`: topology validation output.

        Output:
        - JSON containing `raw_context` and `trace`.
        """
        arguments = {
            "scope_json": scope_json,
            "first_circle_json": first_circle_json,
            "topology_walk_json": topology_walk_json,
        }
        return run_tool(
            "raw_log_context",
            arguments,
            lambda: service.raw_log_context(
                scope=_json_loads(scope_json),
                first_circle=_json_loads(first_circle_json),
                topology_walk=_json_loads(topology_walk_json),
            ),
        )

    @tool
    def healthy_window_comparison(scope_json: str, anchor_json: str, first_circle_json: str, topology_walk_json: str) -> str:
        """Compare the incident window against a nearby healthy baseline for the same scoped entity.

        Inputs:
        - `scope_json`: resolved incident scope.
        - `anchor_json`: active anchor for the incident window.
        - `first_circle_json`: first-circle evidence summary.
        - `topology_walk_json`: topology validation output.

        Output:
        - JSON containing a healthy baseline window comparison and `trace`.
        """
        arguments = {
            "scope_json": scope_json,
            "anchor_json": anchor_json,
            "first_circle_json": first_circle_json,
            "topology_walk_json": topology_walk_json,
        }
        return run_tool(
            "healthy_window_comparison",
            arguments,
            lambda: service.healthy_window_comparison(
                scope=_json_loads(scope_json),
                anchor=_json_loads(anchor_json),
                first_circle=_json_loads(first_circle_json),
                topology_walk=_json_loads(topology_walk_json),
            ),
        )

    @tool
    def critic_pass(
        query: str,
        scope_json: str,
        anchor_json: str,
        first_circle_json: str,
        topology_walk_json: str,
        raw_context_json: str,
        healthy_window_json: str | None = None,
    ) -> str:
        """Review weak RCA evidence and decide whether the current conclusion should be weakened.

        Inputs:
        - `query`: user query wording.
        - `scope_json`, `anchor_json`, `first_circle_json`, `topology_walk_json`: compact RCA evidence state.
        - `raw_context_json`: nearby raw context.
        - `healthy_window_json`: optional healthy-window comparison result.

        Output:
        - JSON containing the critic result and `trace`.
        """
        arguments = {
            "query": query,
            "scope_json": scope_json,
            "anchor_json": anchor_json,
            "first_circle_json": first_circle_json,
            "topology_walk_json": topology_walk_json,
            "raw_context_json": raw_context_json,
            "healthy_window_json": healthy_window_json,
        }
        return run_tool(
            "critic_pass",
            arguments,
            lambda: service.critic_pass(
                query=query,
                scope=_json_loads(scope_json),
                anchor=_json_loads(anchor_json),
                first_circle=_json_loads(first_circle_json),
                topology_walk=_json_loads(topology_walk_json),
                raw_context=_json_loads(raw_context_json),
                healthy_window=_json_loads(healthy_window_json) if healthy_window_json else None,
            ),
        )

    @tool
    def compose_report(
        scope_json: str,
        rag_scope_json: str,
        candidate_signals_json: str,
        anchor_json: str,
        first_circle_json: str,
        topology_walk_json: str,
        raw_context_json: str,
        investigation_trace_json: str,
        healthy_window_json: str | None = None,
        critic_pass_json: str | None = None,
        session_memory_json: str | None = None,
    ) -> str:
        """Assemble the final RCA report and update checkpointed thread memory.

        Inputs:
        - `scope_json`, `rag_scope_json`, `candidate_signals_json`: scope and ranking context.
        - `anchor_json`, `first_circle_json`, `topology_walk_json`, `raw_context_json`: evidence-gathering outputs.
        - `investigation_trace_json`: ordered step trace collected during the run.
        - `session_memory_json`: prior thread memory serialized as JSON.

        Output:
        - JSON containing the final `report` and updated `session_memory`.
        """
        arguments = {
            "scope_json": scope_json,
            "rag_scope_json": rag_scope_json,
            "candidate_signals_json": candidate_signals_json,
            "anchor_json": anchor_json,
            "first_circle_json": first_circle_json,
            "topology_walk_json": topology_walk_json,
            "raw_context_json": raw_context_json,
            "investigation_trace_json": investigation_trace_json,
            "healthy_window_json": healthy_window_json,
            "critic_pass_json": critic_pass_json,
            "session_memory_json": session_memory_json,
        }
        return run_tool(
            "compose_report",
            arguments,
            lambda: service.compose_report(
                scope=_json_loads(scope_json),
                rag_scope=_json_loads(rag_scope_json),
                candidate_signals=_json_loads(candidate_signals_json),
                anchor=_json_loads(anchor_json),
                first_circle=_json_loads(first_circle_json),
                topology_walk=_json_loads(topology_walk_json),
                raw_context=_json_loads(raw_context_json),
                investigation_trace=_json_loads(investigation_trace_json),
                healthy_window=_json_loads(healthy_window_json) if healthy_window_json else None,
                critic_pass=_json_loads(critic_pass_json) if critic_pass_json else None,
                session_memory=_json_loads(session_memory_json) if session_memory_json else {},
            ),
        )

    return [
        resolve_scope,
        retrieve_signal_candidates,
        aggregate_discovery,
        build_initial_anchor,
        first_circle_search,
        topology_walk,
        raw_log_context,
        healthy_window_comparison,
        critic_pass,
        compose_report,
    ]


def _available_tool_calls(
    *,
    query: str,
    request: dict[str, Any],
    session_memory: dict[str, Any],
    tool_results: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    available: dict[str, dict[str, Any]] = {}
    if "resolve_scope" not in tool_results:
        available["resolve_scope"] = {
            "name": "resolve_scope",
            "thought": "Resolving the current incident scope from the new user message and any saved thread context.",
            "args": {
                "query": query,
                "organization_id": request.get("organization_id", "default-org"),
                "start_time": request.get("start_time"),
                "end_time": request.get("end_time"),
                "service_name": request.get("service"),
                "host": request.get("host"),
                "ip": request.get("ip"),
                "session_memory_json": json.dumps(session_memory),
            },
        }
        return available

    resolved = tool_results["resolve_scope"]
    if "retrieve_signal_candidates" not in tool_results:
        available["retrieve_signal_candidates"] = {
            "name": "retrieve_signal_candidates",
            "thought": "Routing into the signal catalog before touching broader evidence.",
            "args": {
                "query": query,
                "parsed_query_json": json.dumps(resolved["parsed_query"]),
                "scope_json": json.dumps(resolved["scope"]),
            },
        }
        return available

    candidate_payload = tool_results["retrieve_signal_candidates"]
    if candidate_payload["needs_discovery"] and "aggregate_discovery" not in tool_results:
        available["aggregate_discovery"] = {
            "name": "aggregate_discovery",
            "thought": "The query is underspecified, so finding a hotspot before deep RCA.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "candidate_signal_names_json": json.dumps(candidate_payload["candidate_signal_names"]),
            },
        }
        available["build_initial_anchor"] = {
            "name": "build_initial_anchor",
            "thought": "Building the first anchor directly from the current scope and ranked signals when hotspot discovery is optional.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "candidate_signals_json": json.dumps(candidate_payload["candidate_signals"]),
                "candidate_signal_names_json": json.dumps(candidate_payload["candidate_signal_names"]),
                "discovery_summary_json": None,
            },
        }
    elif "build_initial_anchor" not in tool_results:
        available["build_initial_anchor"] = {
            "name": "build_initial_anchor",
            "thought": "Building the first anchor from the active scope and the ranked signal set.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "candidate_signals_json": json.dumps(candidate_payload["candidate_signals"]),
                "candidate_signal_names_json": json.dumps(candidate_payload["candidate_signal_names"]),
                "discovery_summary_json": json.dumps(tool_results["aggregate_discovery"]["discovery_summary"])
                if "aggregate_discovery" in tool_results
                else None,
            },
        }

    anchor_payload = tool_results.get("build_initial_anchor")
    if isinstance(anchor_payload, dict) and "first_circle_search" not in tool_results:
        available["first_circle_search"] = {
            "name": "first_circle_search",
            "thought": "Searching the first evidence circle around the active anchor.",
            "args": {
                "anchor_json": json.dumps(anchor_payload["anchor"]),
                "parsed_query_json": json.dumps(resolved["parsed_query"]),
                "organization_id": resolved["scope"]["organization_id"],
            },
        }

    first_circle_payload = tool_results.get("first_circle_search")
    if isinstance(first_circle_payload, dict) and "topology_walk" not in tool_results:
        available["topology_walk"] = {
            "name": "topology_walk",
            "thought": "Walking topology hop by hop to test upstream and underlay explanations.",
            "args": {
                "anchor_json": json.dumps(first_circle_payload["anchor"]),
                "first_circle_json": json.dumps(first_circle_payload["first_circle"]),
                "parsed_query_json": json.dumps(resolved["parsed_query"]),
                "scope_json": json.dumps(resolved["scope"]),
            },
        }

    topology_walk_payload = tool_results.get("topology_walk")
    if isinstance(first_circle_payload, dict) and isinstance(topology_walk_payload, dict) and "raw_log_context" not in tool_results:
        available["raw_log_context"] = {
            "name": "raw_log_context",
            "thought": "Adding a small raw-log context slice near the validated evidence path.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "first_circle_json": json.dumps(first_circle_payload["first_circle"]),
                "topology_walk_json": json.dumps(topology_walk_payload),
            },
        }

    provisional_confidence, provisional_classification, _ = _score_tool_state_for_followups(tool_results)
    healthy_required = _needs_healthy_window_followup(
        confidence=provisional_confidence,
        classification=provisional_classification,
        tool_results=tool_results,
    )
    if (
        healthy_required
        and "healthy_window_comparison" not in tool_results
        and isinstance(anchor_payload, dict)
        and isinstance(first_circle_payload, dict)
        and isinstance(topology_walk_payload, dict)
    ):
        available["healthy_window_comparison"] = {
            "name": "healthy_window_comparison",
            "thought": "Comparing the incident window against a nearby healthy baseline for the same scoped entity.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "anchor_json": json.dumps(first_circle_payload["anchor"]),
                "first_circle_json": json.dumps(first_circle_payload["first_circle"]),
                "topology_walk_json": json.dumps(topology_walk_payload),
            },
        }

    critic_required = _needs_critic_followup(
        confidence=provisional_confidence,
        classification=provisional_classification,
        tool_results=tool_results,
    )
    raw_context_payload = tool_results.get("raw_log_context")
    if (
        critic_required
        and "critic_pass" not in tool_results
        and isinstance(anchor_payload, dict)
        and isinstance(first_circle_payload, dict)
        and isinstance(topology_walk_payload, dict)
        and isinstance(raw_context_payload, dict)
    ):
        available["critic_pass"] = {
            "name": "critic_pass",
            "thought": "Running the weak-RCA critic to pressure-test the current explanation before finalizing the report.",
            "args": {
                "query": query,
                "scope_json": json.dumps(resolved["scope"]),
                "anchor_json": json.dumps(first_circle_payload["anchor"]),
                "first_circle_json": json.dumps(first_circle_payload["first_circle"]),
                "topology_walk_json": json.dumps(topology_walk_payload),
                "raw_context_json": json.dumps(raw_context_payload["raw_context"]),
                "healthy_window_json": json.dumps(tool_results["healthy_window_comparison"])
                if "healthy_window_comparison" in tool_results
                else None,
            },
        }

    if (
        isinstance(anchor_payload, dict)
        and isinstance(first_circle_payload, dict)
        and isinstance(topology_walk_payload, dict)
        and isinstance(raw_context_payload, dict)
    ):
        available["compose_report"] = {
            "name": "compose_report",
            "thought": "Composing the final RCA report and updating thread memory for follow-up turns.",
            "args": {
                "scope_json": json.dumps(resolved["scope"]),
                "rag_scope_json": json.dumps(candidate_payload["rag_scope"]),
                "candidate_signals_json": json.dumps(candidate_payload["candidate_signals"]),
                "anchor_json": json.dumps(first_circle_payload["anchor"]),
                "first_circle_json": json.dumps(first_circle_payload["first_circle"]),
                "topology_walk_json": json.dumps(topology_walk_payload),
                "raw_context_json": json.dumps(raw_context_payload["raw_context"]),
                "investigation_trace_json": json.dumps(_collect_trace(tool_results)),
                "healthy_window_json": json.dumps(tool_results["healthy_window_comparison"])
                if "healthy_window_comparison" in tool_results
                else None,
                "critic_pass_json": json.dumps(tool_results["critic_pass"]) if "critic_pass" in tool_results else None,
                "session_memory_json": json.dumps(session_memory),
            },
        }
    return available


def _next_tool_call(
    *,
    query: str,
    request: dict[str, Any],
    session_memory: dict[str, Any],
    tool_results: dict[str, dict[str, Any]],
    available_tool_calls: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    available = available_tool_calls or _available_tool_calls(
        query=query,
        request=request,
        session_memory=session_memory,
        tool_results=tool_results,
    )
    ordered_names = [
        "resolve_scope",
        "retrieve_signal_candidates",
        "aggregate_discovery",
        "build_initial_anchor",
        "first_circle_search",
        "topology_walk",
        "raw_log_context",
        "healthy_window_comparison",
        "critic_pass",
        "compose_report",
    ]
    for name in ordered_names:
        if name in available:
            return dict(available[name])
    raise ValueError("No valid next tool call was available for the current investigation state.")


def _build_planner_context(
    *,
    query: str,
    request: dict[str, Any],
    session_memory: dict[str, Any],
    tool_results: dict[str, Any],
    available_tool_calls: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    recommended = _next_tool_call(
        query=query,
        request=request,
        session_memory=session_memory,
        tool_results=tool_results,
        available_tool_calls=available_tool_calls,
    )
    return {
        "user_query": query,
        "request_options": request,
        "session_memory": {
            "service": session_memory.get("service"),
            "host": session_memory.get("host"),
            "ip": session_memory.get("ip"),
            "node_id": session_memory.get("node_id"),
        },
        "completed_tools": list(tool_results.keys()),
        "available_tools": [
            {
                "tool_name": payload["name"],
                "thought": payload["thought"],
                "arg_keys": sorted(payload["args"].keys()),
            }
            for payload in available_tool_calls.values()
        ],
        "recommended_next_tool": {
            "tool_name": recommended["name"],
            "reason": recommended["thought"],
        },
        "current_findings": _summarize_tool_results_for_planner(tool_results),
        "tool_dependency_hints": _planner_tool_dependency_hints(),
    }


def _summarize_tool_results_for_planner(tool_results: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    resolved = tool_results.get("resolve_scope")
    if isinstance(resolved, dict):
        scope = resolved.get("scope") if isinstance(resolved.get("scope"), dict) else {}
        parsed = resolved.get("parsed_query") if isinstance(resolved.get("parsed_query"), dict) else {}
        summary["resolve_scope"] = {
            "service": scope.get("service"),
            "host": scope.get("host"),
            "ip": scope.get("ip"),
            "time_window": scope.get("time_window"),
            "domain_hint": scope.get("domain_hint"),
            "vague": parsed.get("vague"),
        }
    candidates = tool_results.get("retrieve_signal_candidates")
    if isinstance(candidates, dict):
        summary["retrieve_signal_candidates"] = {
            "needs_discovery": candidates.get("needs_discovery"),
            "top_candidate_signals": list(candidates.get("candidate_signal_names", []))[:6],
            "retrieval_details": candidates.get("retrieval_details"),
        }
    discovery = tool_results.get("aggregate_discovery")
    if isinstance(discovery, dict):
        discovery_summary = discovery.get("discovery_summary") if isinstance(discovery.get("discovery_summary"), dict) else {}
        summary["aggregate_discovery"] = {
            "top_services": discovery_summary.get("top_services"),
            "top_hosts": discovery_summary.get("top_hosts"),
            "top_ips": discovery_summary.get("top_ips"),
            "hottest_bucket": discovery_summary.get("hottest_bucket"),
        }
    anchor = tool_results.get("build_initial_anchor")
    if isinstance(anchor, dict):
        anchor_payload = anchor.get("anchor") if isinstance(anchor.get("anchor"), dict) else {}
        summary["build_initial_anchor"] = {
            "service": anchor_payload.get("service"),
            "host": anchor_payload.get("host"),
            "ip": anchor_payload.get("ip"),
            "node_id": anchor_payload.get("node_id"),
            "signal_count": len(anchor_payload.get("signal_set", [])),
            "time_window": anchor_payload.get("time_window"),
        }
    first_circle = tool_results.get("first_circle_search")
    if isinstance(first_circle, dict):
        circle = first_circle.get("first_circle") if isinstance(first_circle.get("first_circle"), dict) else {}
        summary["first_circle_search"] = {
            "event_count": len(circle.get("events", [])),
            "matched_signal_count": len(circle.get("signal_counts", {})),
            "first_seen": circle.get("first_seen"),
            "last_seen": circle.get("last_seen"),
            "entities": circle.get("entities"),
        }
    topology_walk = tool_results.get("topology_walk")
    if isinstance(topology_walk, dict):
        impacted = topology_walk.get("impacted_node") if isinstance(topology_walk.get("impacted_node"), dict) else {}
        summary["topology_walk"] = {
            "impacted_node_id": impacted.get("node_id"),
            "hop_count": len(topology_walk.get("topology_hops", [])),
            "rejected_paths": list(topology_walk.get("rejected_paths", []))[:5],
        }
    raw_context = tool_results.get("raw_log_context")
    if isinstance(raw_context, dict):
        summary["raw_log_context"] = {
            "raw_context_count": len(raw_context.get("raw_context", [])),
        }
    return summary


def _planner_tool_dependency_hints() -> dict[str, str]:
    return {
        "resolve_scope": "Use first. Required before all scoped investigation steps.",
        "retrieve_signal_candidates": "Use after resolve_scope to rank the signal families.",
        "aggregate_discovery": "Use when the query is under-specified and hotspot discovery may reduce ambiguity.",
        "build_initial_anchor": "Use once scope and candidate signals are ready.",
        "first_circle_search": "Use to fetch the first local evidence ring around the anchor.",
        "topology_walk": "Use after first_circle_search to test upstream and underlay explanations.",
        "raw_log_context": "Use after topology_walk to fetch a compact human-readable context slice. Usually helpful before finalizing or running the critic.",
        "healthy_window_comparison": "Use after topology_walk when the RCA is still weak, ambiguous, or lacks a strong incident-vs-healthy contrast.",
        "critic_pass": "Use after raw_log_context when the current RCA is weak or you want the model to pressure-test the explanation before finishing.",
        "compose_report": "Use after raw_log_context when the current evidence is already sufficient for a final RCA output.",
    }


def _validate_planner_decision(
    *,
    planner_decision: dict[str, Any],
    available_tool_calls: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(planner_decision, dict):
        return {"accepted": False, "reason": "The planner did not return a structured object."}
    if planner_decision.get("error"):
        return {"accepted": False, "reason": str(planner_decision["error"])}
    if planner_decision.get("action") != "tool_call":
        return {"accepted": False, "reason": "Only tool_call actions are accepted in hybrid planner mode."}
    tool_name = planner_decision.get("tool_name")
    if not isinstance(tool_name, str) or tool_name not in available_tool_calls:
        return {"accepted": False, "reason": "The planner selected a tool that is not valid for the current state."}
    return {"accepted": True, "tool_name": tool_name}


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index:]
    return messages


def _collect_tool_results(
    messages: list[Any],
    *,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for message in messages:
        if isinstance(message, ToolMessage) and message.name:
            results[message.name] = _parse_tool_message_payload(
                tool_name=message.name,
                content=message.content,
                status=message.status,
                logger=logger,
            )
    return results


def _collect_trace(tool_results: dict[str, Any]) -> list[str]:
    trace: list[str] = []
    ordered_names = [
        "resolve_scope",
        "retrieve_signal_candidates",
        "aggregate_discovery",
        "build_initial_anchor",
        "first_circle_search",
        "topology_walk",
        "raw_log_context",
        "healthy_window_comparison",
        "critic_pass",
    ]
    for name in ordered_names:
        if name in tool_results and isinstance(tool_results[name], dict):
            trace.extend(tool_results[name].get("trace", []))
    return trace


def _score_tool_state_for_followups(tool_results: dict[str, Any]) -> tuple[float, str, dict[str, Any]]:
    first_circle_payload = tool_results.get("first_circle_search")
    topology_walk_payload = tool_results.get("topology_walk")
    raw_context_payload = tool_results.get("raw_log_context")
    if not isinstance(first_circle_payload, dict) or not isinstance(topology_walk_payload, dict):
        return 0.0, "insufficient_evidence", {}
    first_circle = _search_summary_from_tool_payload(first_circle_payload.get("first_circle"))
    hops = _hop_results_from_tool_payload(topology_walk_payload.get("topology_hops"))
    rejected_paths = list(topology_walk_payload.get("rejected_paths", []))
    raw_context = list(raw_context_payload.get("raw_context", [])) if isinstance(raw_context_payload, dict) else []
    return _score_and_classify(first_circle, hops, rejected_paths, raw_context)


def _needs_healthy_window_followup(*, confidence: float, classification: str, tool_results: dict[str, Any]) -> bool:
    first_circle_payload = tool_results.get("first_circle_search")
    if not isinstance(first_circle_payload, dict):
        return False
    first_circle = first_circle_payload.get("first_circle") if isinstance(first_circle_payload.get("first_circle"), dict) else {}
    matched_signal_count = len((first_circle.get("signal_counts") or {}).keys())
    return classification != "confirmed_rca" or confidence < 0.78 or matched_signal_count == 0


def _needs_critic_followup(*, confidence: float, classification: str, tool_results: dict[str, Any]) -> bool:
    if classification == "confirmed_rca" and confidence >= 0.82:
        return False
    healthy_payload = tool_results.get("healthy_window_comparison")
    if isinstance(healthy_payload, dict):
        comparison = healthy_payload.get("comparison") if isinstance(healthy_payload.get("comparison"), dict) else {}
        anomaly_score = float(comparison.get("anomaly_score") or 0.0)
        if anomaly_score < 0.4:
            return True
    return classification != "confirmed_rca" or confidence < 0.72


def _search_summary_from_tool_payload(payload: Any) -> Any:
    from .service import _search_summary_from_dict

    return _search_summary_from_dict(payload if isinstance(payload, dict) else {})


def _hop_results_from_tool_payload(payload: Any) -> list[Any]:
    from .service import _hop_from_dict

    if not isinstance(payload, list):
        return []
    return [_hop_from_dict(item) for item in payload if isinstance(item, dict)]


def _json_loads(value: str | list[Any] | dict[str, Any] | None) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    text = value.strip()
    if not text:
        raise ValueError("The payload was empty.")
    return json.loads(text)


def _parse_tool_message_payload(
    *,
    tool_name: str,
    content: Any,
    status: str,
    logger: logging.Logger | None,
) -> Any:
    normalized = _normalize_tool_message_content(content)
    if status == "error":
        message = str(normalized).strip() if normalized is not None else "Unknown tool error."
        return {
            "error": message,
            "trace": [f"Tool {tool_name} returned an error status."],
            "raw_content": message,
        }
    if isinstance(normalized, (dict, list)):
        return normalized
    try:
        return _json_loads(normalized)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        if logger:
            _safe_log_step(
                logger,
                logging.ERROR,
                "Tool payload parse failed",
                tool_name=tool_name,
                error=str(exc),
                raw_content=redact_for_logging(normalized),
            )
        return {
            "error": f"Tool {tool_name} returned an unreadable payload: {exc}",
            "trace": [f"Tool {tool_name} produced a payload that could not be parsed back into JSON."],
            "raw_content": str(normalized) if normalized is not None else None,
        }


def _normalize_tool_message_content(content: Any) -> Any:
    if isinstance(content, dict):
        if "json" in content:
            return content["json"]
        if "text" in content:
            return content["text"]
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
                continue
            if isinstance(item, dict):
                if "json" in item:
                    return item["json"]
                text = item.get("text")
                if isinstance(text, str):
                    fragments.append(text)
                    continue
            fragments.append(str(item))
        merged = "".join(fragments).strip()
        return merged or None
    return content


def _safe_log_step(logger: logging.Logger | None, level: int, step: str, **details: Any) -> None:
    if logger is None:
        return
    try:
        log_step(logger, level, step, **details)
    except Exception:
        pass
