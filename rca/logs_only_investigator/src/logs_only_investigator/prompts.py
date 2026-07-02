from __future__ import annotations

import json
from typing import Any


SCOPE_RESOLUTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "scope_resolution",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "selected_node_id": {"type": ["string", "null"]},
            "service": {"type": ["string", "null"]},
            "host": {"type": ["string", "null"]},
            "ip": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason": {"type": "string"},
        },
        "required": [
            "selected_node_id",
            "service",
            "host",
            "ip",
            "confidence",
            "reason",
        ],
    },
}


SCOPE_RESOLUTION_SYSTEM_PROMPT = """You are the scope resolution specialist inside an industrial log investigation agent.

Your job is to resolve the most likely service, host, IP, and topology node for the current investigation turn.

Operating rules:
- Use only the user query, deterministic hints, thread memory, and the provided candidate lists.
- Do not invent services, hosts, IPs, or node IDs that are not present in the candidate payload.
- Prefer an exact candidate node when the query and hints support it.
- Respect explicit operator overrides. They are already reflected in the payload and should not be contradicted.
- When the query is vague, use thread memory only if the payload still supports it.
- If the evidence is insufficient, return nulls for uncertain fields and explain why.
- Keep the reasoning short and operational, not conversational.
"""


PLANNER_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "investigation_plan_step",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "thought": {"type": "string"},
            "action": {"type": "string", "enum": ["tool_call", "finish"]},
            "tool_name": {
                "type": ["string", "null"],
                "enum": [
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
                None,
            ],
            },
            "tool_args": {
                "type": ["object", "null"],
                "properties": {},
                "additionalProperties": False,
            },
            "stop_reason": {"type": ["string", "null"]},
            "confidence_note": {"type": ["string", "null"]},
        },
        "required": [
            "thought",
            "action",
            "tool_name",
            "tool_args",
            "stop_reason",
            "confidence_note",
        ],
    },
}


PLANNER_SYSTEM_PROMPT = """You are the planning policy for an industrial log RCA agent.

Your job is to choose the single best next action for the investigation.

Operating rules:
- Use only the supplied state, completed tool results, and available tools.
- Prefer the smallest next action that most reduces uncertainty.
- Treat `recommended_next_tool` as the deterministic baseline, but you may choose another available tool when it will improve the investigation more.
- Do not invent tool names.
- Do not request a tool that is not listed in available_tools.
- Prefer `finish` only when the investigation already has enough evidence or no remaining tool is likely to improve the result.
- Do not assume a missing tool result exists.
- Keep the reasoning short and operational.
- Return only JSON that matches the provided schema.
"""


CRITIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "weak_rca_critic",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["accept_current_path", "downgrade_confidence", "inconclusive"],
            },
            "recommended_classification": {
                "type": ["string", "null"],
                "enum": ["confirmed_rca", "probable_cause", "insufficient_evidence", None],
            },
            "confidence_delta": {"type": "number", "minimum": -0.25, "maximum": 0.1},
            "reasoning": {"type": "string"},
            "alternate_focus": {
                "type": "array",
                "items": {"type": "string"},
            },
            "key_risks": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "verdict",
            "recommended_classification",
            "confidence_delta",
            "reasoning",
            "alternate_focus",
            "key_risks",
        ],
    },
}


TOPOLOGY_CANDIDATE_CRITIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "topology_candidate_critic",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["keep_scored_best", "select_alternate", "inconclusive"],
            },
            "selected_node_id": {"type": ["string", "null"]},
            "score_adjustment": {"type": "number", "minimum": -1.5, "maximum": 1.5},
            "reasoning": {"type": "string"},
            "risk_note": {"type": ["string", "null"]},
        },
        "required": [
            "verdict",
            "selected_node_id",
            "score_adjustment",
            "reasoning",
            "risk_note",
        ],
    },
}


CRITIC_SYSTEM_PROMPT = """You are the weak-RCA critic inside an industrial log investigation agent.

Your job is to review a low-confidence or mixed-evidence RCA path and decide whether the current explanation should stand, be weakened, or remain inconclusive.

Operating rules:
- Use only the supplied compact evidence summary.
- Do not invent new evidence or topology.
- Prefer lowering confidence when chronology, anomaly strength, or topology support are weak.
- Recommend an alternate focus only if it is explicitly present in the supplied candidate comparison.
- Keep the reasoning short and operational.
- Return only JSON that matches the provided schema.
"""


TOPOLOGY_CANDIDATE_CRITIC_SYSTEM_PROMPT = """You are the topology candidate critic inside an industrial log RCA agent.

Your job is to review one topology-walk candidate round and decide whether the current score leader should stand or whether another candidate is more causally plausible.

Operating rules:
- Use only the supplied compact round summary and candidate list.
- Do not invent nodes, evidence, or relationships.
- Prefer keeping the scored best candidate unless another candidate has clearer chronology, stronger signalized evidence, or better service-policy alignment.
- Only select an alternate node when it is explicitly present in the candidate list.
- Keep the reasoning short and operational.
- Return only JSON that matches the provided schema.
"""


SUMMARY_PROMPT_PREFIX = """Write a concise industrial RCA explanation for an operations analyst.
Use only the supplied evidence.
State the most likely cause, the causality chain, the confidence meaning, and the key unknowns.
Do not invent facts.
Keep it to one short paragraph.
"""


def build_scope_resolution_prompt(context: dict[str, Any]) -> str:
    """Build a compact, candidate-bounded prompt for scope resolution.

    The payload intentionally sends only the minimal context needed for
    disambiguation so the resolver can choose from known topology-backed options
    without seeing the entire topology graph.
    """
    payload = {
        "query": context["query"],
        "deterministic_hints": context["deterministic_hints"],
        "thread_memory": context["thread_memory"],
        "candidate_services": context["candidate_services"],
        "candidate_hosts": context["candidate_hosts"],
        "candidate_ips": context["candidate_ips"],
        "candidate_nodes": context["candidate_nodes"],
        "output_schema": SCOPE_RESOLUTION_OUTPUT_SCHEMA["schema"],
    }
    return (
        "Resolve the best investigation scope from the bounded candidate set.\n"
        "Return only JSON that matches the provided schema.\n\n"
        f"Scope resolution payload:\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}"
    )


def build_planner_prompt(context: dict[str, Any]) -> str:
    """Build a compact prompt for the hybrid LLM planner."""
    payload = {
        "user_query": context["user_query"],
        "request_options": context["request_options"],
        "session_memory": context["session_memory"],
        "completed_tools": context["completed_tools"],
        "available_tools": context["available_tools"],
        "current_findings": context["current_findings"],
        "tool_dependency_hints": context["tool_dependency_hints"],
        "output_schema": PLANNER_OUTPUT_SCHEMA["schema"],
    }
    return (
        "Choose the single best next investigation action.\n"
        "Return only JSON that matches the provided schema.\n\n"
        f"Planner state:\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}"
    )


def build_critic_prompt(context: dict[str, Any]) -> str:
    """Build a compact prompt for reviewing weak or mixed RCA conclusions."""
    payload = {
        "query": context["query"],
        "incident_window": context["incident_window"],
        "current_assessment": context["current_assessment"],
        "topology_summary": context["topology_summary"],
        "healthy_window_summary": context["healthy_window_summary"],
        "candidate_comparison": context["candidate_comparison"],
        "raw_context": context["raw_context"],
        "output_schema": CRITIC_OUTPUT_SCHEMA["schema"],
    }
    return (
        "Review the weak RCA path and decide whether confidence should be kept, lowered, or left inconclusive.\n"
        "Return only JSON that matches the provided schema.\n\n"
        f"Weak RCA critic state:\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}"
    )


def build_topology_candidate_critic_prompt(context: dict[str, Any]) -> str:
    """Build a compact prompt for one topology candidate-comparison round."""
    payload = {
        "query": context["query"],
        "source_node": context["source_node"],
        "round_depth": context["round_depth"],
        "service_policy": context["service_policy"],
        "scored_best_node_id": context["scored_best_node_id"],
        "candidates": context["candidates"],
        "output_schema": TOPOLOGY_CANDIDATE_CRITIC_OUTPUT_SCHEMA["schema"],
    }
    return (
        "Review this topology candidate round and decide whether the scored best candidate should remain selected.\n"
        "Return only JSON that matches the provided schema.\n\n"
        f"Topology candidate critic state:\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}"
    )


def build_summary_prompt(context: dict[str, object]) -> str:
    """Build the final analyst-summary prompt from compact RCA evidence."""
    compact = {
        "incident_window": context["incident_window"],
        "likely_root_cause": context["likely_root_cause"],
        "classification": context["classification"],
        "confidence": context["confidence"],
        "primary_entities": context["primary_entities"],
        "timeline": context["timeline"],
        "supporting_evidence": context["supporting_evidence"],
        "contradictions": context["contradictions"],
        "unknowns": context["unknowns"],
        "raw_context": context["raw_context"],
    }
    return f"{SUMMARY_PROMPT_PREFIX}\nRCA context JSON:\n{json.dumps(compact, indent=2)}"
