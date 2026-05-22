from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from .config import OpenAIConfig
from .observability import log_step, redact_for_logging
from .prompts import (
    CRITIC_OUTPUT_SCHEMA,
    CRITIC_SYSTEM_PROMPT,
    PLANNER_OUTPUT_SCHEMA,
    PLANNER_SYSTEM_PROMPT,
    SCOPE_RESOLUTION_OUTPUT_SCHEMA,
    SCOPE_RESOLUTION_SYSTEM_PROMPT,
    TOPOLOGY_CANDIDATE_CRITIC_OUTPUT_SCHEMA,
    TOPOLOGY_CANDIDATE_CRITIC_SYSTEM_PROMPT,
    build_critic_prompt,
    build_planner_prompt,
    build_scope_resolution_prompt,
    build_summary_prompt,
    build_topology_candidate_critic_prompt,
)


LOGGER = logging.getLogger("logs_only_investigator")


class ExplanationGenerator(Protocol):
    def generate_summary(self, context: dict[str, object]) -> dict[str, object]:
        ...


class ScopeResolutionGenerator(Protocol):
    def resolve_scope(self, context: dict[str, object]) -> dict[str, object]:
        ...


class PlannerGenerator(Protocol):
    def choose_next_action(self, context: dict[str, object]) -> dict[str, object]:
        ...


class CriticGenerator(Protocol):
    def review_weak_rca(self, context: dict[str, object]) -> dict[str, object]:
        ...

    def review_topology_candidates(self, context: dict[str, object]) -> dict[str, object]:
        ...


@dataclass
class DeterministicExplanationGenerator:
    def generate_summary(self, context: dict[str, object]) -> dict[str, object]:
        return {
            "analyst_summary": str(context["fallback_summary"]),
            "summary_source": "fallback",
            "requested_model": None,
            "llm_model": None,
            "usage": None,
        }


class OpenAIExplanationGenerator:
    def __init__(self, client: OpenAI, config: OpenAIConfig) -> None:
        self._client = client
        self._config = config

    def generate_summary(self, context: dict[str, object]) -> dict[str, object]:
        prompt = build_summary_prompt(context)
        request: dict[str, object] = {
            "model": self._config.model,
            "input": prompt,
            "max_output_tokens": self._config.max_output_tokens,
        }
        if _supports_reasoning_controls(self._config.model):
            request["reasoning"] = {"effort": self._config.reasoning_effort}
        if _supports_text_controls(self._config.model):
            request["text"] = {"verbosity": self._config.text_verbosity}
        if self._config.instructions.strip():
            request["instructions"] = self._config.instructions

        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI summary generation started",
            model=self._config.model,
            request=redact_for_logging(request, max_chars=1500),
        )
        try:
            response = self._client.responses.create(**request)
        except Exception as exc:
            log_step(
                LOGGER,
                logging.ERROR,
                "OpenAI summary generation failed",
                model=self._config.model,
                error=str(exc),
            )
            return {
                "analyst_summary": str(context["fallback_summary"]),
                "summary_source": "fallback",
                "requested_model": self._config.model,
                "llm_model": None,
                "usage": None,
                "error": f"OpenAI summary generation failed: {exc}",
            }
        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI summary generation completed",
            model=response.model,
            usage=redact_for_logging(_usage_to_dict(getattr(response, "usage", None))),
        )
        return {
            "analyst_summary": (response.output_text or "").strip() or str(context["fallback_summary"]),
            "summary_source": "llm" if (response.output_text or "").strip() else "fallback",
            "requested_model": self._config.model,
            "llm_model": response.model,
            "usage": _usage_to_dict(getattr(response, "usage", None)),
        }


@dataclass
class DisabledScopeResolutionGenerator:
    def resolve_scope(self, context: dict[str, object]) -> dict[str, object]:
        return {
            "selected_node_id": None,
            "service": None,
            "host": None,
            "ip": None,
            "confidence": 0.0,
            "reason": "LLM scope resolution is disabled.",
            "requested_model": None,
            "llm_model": None,
            "usage": None,
            "error": None,
        }


@dataclass
class DisabledPlannerGenerator:
    def choose_next_action(self, context: dict[str, object]) -> dict[str, object]:
        return {
            "thought": "LLM planning is disabled.",
            "action": "tool_call",
            "tool_name": None,
            "tool_args": None,
            "stop_reason": None,
            "confidence_note": "Deterministic planner fallback is required.",
            "requested_model": None,
            "llm_model": None,
            "usage": None,
            "request": None,
            "raw_output_text": None,
            "error": None,
        }


@dataclass
class DisabledCriticGenerator:
    def review_weak_rca(self, context: dict[str, object]) -> dict[str, object]:
        return {
            "verdict": "inconclusive",
            "recommended_classification": None,
            "confidence_delta": 0.0,
            "reasoning": "LLM critic is disabled.",
            "alternate_focus": [],
            "key_risks": [],
            "requested_model": None,
            "llm_model": None,
            "usage": None,
            "request": None,
            "raw_output_text": None,
            "error": None,
        }

    def review_topology_candidates(self, context: dict[str, object]) -> dict[str, object]:
        return {
            "verdict": "inconclusive",
            "selected_node_id": None,
            "score_adjustment": 0.0,
            "reasoning": "Topology candidate critic is disabled.",
            "risk_note": None,
            "requested_model": None,
            "llm_model": None,
            "usage": None,
            "request": None,
            "raw_output_text": None,
            "error": None,
        }


class OpenAIScopeResolutionGenerator:
    def __init__(self, client: OpenAI, config: OpenAIConfig) -> None:
        self._client = client
        self._config = config

    def resolve_scope(self, context: dict[str, object]) -> dict[str, object]:
        prompt = build_scope_resolution_prompt(context)
        request_preview: dict[str, object] = {
            "model": self._config.model,
            "max_output_tokens": self._config.scope_resolution_max_output_tokens,
            "system_prompt": SCOPE_RESOLUTION_SYSTEM_PROMPT,
            "prompt": prompt,
            "candidate_payload": context,
        }
        request: dict[str, object] = {
            "model": self._config.model,
            "input": prompt,
            "max_output_tokens": self._config.scope_resolution_max_output_tokens,
            "instructions": SCOPE_RESOLUTION_SYSTEM_PROMPT,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": str(SCOPE_RESOLUTION_OUTPUT_SCHEMA["name"]),
                    "strict": True,
                    "schema": dict(SCOPE_RESOLUTION_OUTPUT_SCHEMA["schema"]),
                }
            },
        }
        if _supports_reasoning_controls(self._config.model):
            request["reasoning"] = {"effort": self._config.reasoning_effort}

        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI scope resolution started",
            model=self._config.model,
            request=redact_for_logging(request, max_chars=1600),
        )
        try:
            response = self._client.responses.create(**request)
        except Exception as exc:
            log_step(
                LOGGER,
                logging.ERROR,
                "OpenAI scope resolution failed",
                model=self._config.model,
                error=str(exc),
            )
            return {
                "selected_node_id": None,
                "service": None,
                "host": None,
                "ip": None,
                "confidence": 0.0,
                "reason": "The OpenAI scope resolver failed before returning a structured result.",
                "requested_model": self._config.model,
                "llm_model": None,
                "usage": None,
                "request": request_preview,
                "raw_output_text": None,
                "error": f"OpenAI scope resolution failed: {exc}",
            }

        usage = _usage_to_dict(getattr(response, "usage", None))
        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI scope resolution completed",
            model=response.model,
            usage=redact_for_logging(usage),
        )
        raw_text = (response.output_text or "").strip()
        if not raw_text:
            return {
                "selected_node_id": None,
                "service": None,
                "host": None,
                "ip": None,
                "confidence": 0.0,
                "reason": "The OpenAI scope resolver returned an empty structured payload.",
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": "The OpenAI scope resolver returned empty output.",
            }
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return {
                "selected_node_id": None,
                "service": None,
                "host": None,
                "ip": None,
                "confidence": 0.0,
                "reason": "The OpenAI scope resolver returned malformed JSON.",
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": f"Could not parse scope resolver output: {exc}",
            }
        payload["requested_model"] = self._config.model
        payload["llm_model"] = response.model
        payload["usage"] = usage
        payload["request"] = request_preview
        payload["raw_output_text"] = raw_text
        payload["error"] = None
        return payload


class OpenAIPlannerGenerator:
    def __init__(self, client: OpenAI, config: OpenAIConfig) -> None:
        self._client = client
        self._config = config

    def choose_next_action(self, context: dict[str, object]) -> dict[str, object]:
        prompt = build_planner_prompt(context)
        request_preview: dict[str, object] = {
            "model": self._config.model,
            "max_output_tokens": self._config.planner_max_output_tokens,
            "system_prompt": PLANNER_SYSTEM_PROMPT,
            "prompt": prompt,
            "planner_context": context,
        }
        request: dict[str, object] = {
            "model": self._config.model,
            "input": prompt,
            "max_output_tokens": self._config.planner_max_output_tokens,
            "instructions": PLANNER_SYSTEM_PROMPT,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": str(PLANNER_OUTPUT_SCHEMA["name"]),
                    "strict": True,
                    "schema": dict(PLANNER_OUTPUT_SCHEMA["schema"]),
                }
            },
        }
        if _supports_reasoning_controls(self._config.model):
            request["reasoning"] = {"effort": self._config.reasoning_effort}

        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI planner generation started",
            model=self._config.model,
            request=redact_for_logging(request, max_chars=1600),
        )
        try:
            response = self._client.responses.create(**request)
        except Exception as exc:
            log_step(
                LOGGER,
                logging.ERROR,
                "OpenAI planner generation failed",
                model=self._config.model,
                error=str(exc),
            )
            return {
                "thought": "The OpenAI planner failed before returning a structured result.",
                "action": "tool_call",
                "tool_name": None,
                "tool_args": None,
                "stop_reason": None,
                "confidence_note": "Deterministic planner fallback is required.",
                "requested_model": self._config.model,
                "llm_model": None,
                "usage": None,
                "request": request_preview,
                "raw_output_text": None,
                "error": f"OpenAI planner generation failed: {exc}",
            }

        usage = _usage_to_dict(getattr(response, "usage", None))
        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI planner generation completed",
            model=response.model,
            usage=redact_for_logging(usage),
        )
        raw_text = (response.output_text or "").strip()
        if not raw_text:
            return {
                "thought": "The OpenAI planner returned an empty structured payload.",
                "action": "tool_call",
                "tool_name": None,
                "tool_args": None,
                "stop_reason": None,
                "confidence_note": "Deterministic planner fallback is required.",
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": "The OpenAI planner returned empty output.",
            }
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return {
                "thought": "The OpenAI planner returned malformed JSON.",
                "action": "tool_call",
                "tool_name": None,
                "tool_args": None,
                "stop_reason": None,
                "confidence_note": "Deterministic planner fallback is required.",
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": f"Could not parse planner output: {exc}",
            }
        payload["requested_model"] = self._config.model
        payload["llm_model"] = response.model
        payload["usage"] = usage
        payload["request"] = request_preview
        payload["raw_output_text"] = raw_text
        payload["error"] = None
        return payload


class OpenAICriticGenerator:
    def __init__(self, client: OpenAI, config: OpenAIConfig) -> None:
        self._client = client
        self._config = config

    def review_weak_rca(self, context: dict[str, object]) -> dict[str, object]:
        prompt = build_critic_prompt(context)
        request_preview: dict[str, object] = {
            "model": self._config.model,
            "max_output_tokens": self._config.critic_max_output_tokens,
            "system_prompt": CRITIC_SYSTEM_PROMPT,
            "prompt": prompt,
            "critic_context": context,
        }
        request: dict[str, object] = {
            "model": self._config.model,
            "input": prompt,
            "max_output_tokens": self._config.critic_max_output_tokens,
            "instructions": CRITIC_SYSTEM_PROMPT,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": str(CRITIC_OUTPUT_SCHEMA["name"]),
                    "strict": True,
                    "schema": dict(CRITIC_OUTPUT_SCHEMA["schema"]),
                }
            },
        }
        if _supports_reasoning_controls(self._config.model):
            request["reasoning"] = {"effort": self._config.reasoning_effort}

        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI critic generation started",
            model=self._config.model,
            request=redact_for_logging(request, max_chars=1600),
        )
        try:
            response = self._client.responses.create(**request)
        except Exception as exc:
            log_step(
                LOGGER,
                logging.ERROR,
                "OpenAI critic generation failed",
                model=self._config.model,
                error=str(exc),
            )
            return {
                "verdict": "inconclusive",
                "recommended_classification": None,
                "confidence_delta": 0.0,
                "reasoning": "The OpenAI critic failed before returning a structured result.",
                "alternate_focus": [],
                "key_risks": [],
                "requested_model": self._config.model,
                "llm_model": None,
                "usage": None,
                "request": request_preview,
                "raw_output_text": None,
                "error": f"OpenAI critic generation failed: {exc}",
            }
        usage = _usage_to_dict(getattr(response, "usage", None))
        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI critic generation completed",
            model=response.model,
            usage=redact_for_logging(usage),
        )
        raw_text = (response.output_text or "").strip()
        if not raw_text:
            return {
                "verdict": "inconclusive",
                "recommended_classification": None,
                "confidence_delta": 0.0,
                "reasoning": "The OpenAI critic returned an empty structured payload.",
                "alternate_focus": [],
                "key_risks": [],
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": "The OpenAI critic returned empty output.",
            }
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return {
                "verdict": "inconclusive",
                "recommended_classification": None,
                "confidence_delta": 0.0,
                "reasoning": "The OpenAI critic returned malformed JSON.",
                "alternate_focus": [],
                "key_risks": [],
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": f"Could not parse critic output: {exc}",
            }
        payload["requested_model"] = self._config.model
        payload["llm_model"] = response.model
        payload["usage"] = usage
        payload["request"] = request_preview
        payload["raw_output_text"] = raw_text
        payload["error"] = None
        return payload

    def review_topology_candidates(self, context: dict[str, object]) -> dict[str, object]:
        prompt = build_topology_candidate_critic_prompt(context)
        request_preview: dict[str, object] = {
            "model": self._config.model,
            "max_output_tokens": self._config.critic_max_output_tokens,
            "system_prompt": TOPOLOGY_CANDIDATE_CRITIC_SYSTEM_PROMPT,
            "prompt": prompt,
            "topology_candidate_context": context,
        }
        request: dict[str, object] = {
            "model": self._config.model,
            "input": prompt,
            "max_output_tokens": self._config.critic_max_output_tokens,
            "instructions": TOPOLOGY_CANDIDATE_CRITIC_SYSTEM_PROMPT,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": str(TOPOLOGY_CANDIDATE_CRITIC_OUTPUT_SCHEMA["name"]),
                    "strict": True,
                    "schema": dict(TOPOLOGY_CANDIDATE_CRITIC_OUTPUT_SCHEMA["schema"]),
                }
            },
        }
        if _supports_reasoning_controls(self._config.model):
            request["reasoning"] = {"effort": self._config.reasoning_effort}

        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI topology candidate critic started",
            model=self._config.model,
            request=redact_for_logging(request, max_chars=1600),
        )
        try:
            response = self._client.responses.create(**request)
        except Exception as exc:
            log_step(
                LOGGER,
                logging.ERROR,
                "OpenAI topology candidate critic failed",
                model=self._config.model,
                error=str(exc),
            )
            return {
                "verdict": "inconclusive",
                "selected_node_id": None,
                "score_adjustment": 0.0,
                "reasoning": "The OpenAI topology candidate critic failed before returning a structured result.",
                "risk_note": None,
                "requested_model": self._config.model,
                "llm_model": None,
                "usage": None,
                "request": request_preview,
                "raw_output_text": None,
                "error": f"OpenAI topology candidate critic failed: {exc}",
            }
        usage = _usage_to_dict(getattr(response, "usage", None))
        log_step(
            LOGGER,
            logging.INFO,
            "OpenAI topology candidate critic completed",
            model=response.model,
            usage=redact_for_logging(usage),
        )
        raw_text = (response.output_text or "").strip()
        if not raw_text:
            return {
                "verdict": "inconclusive",
                "selected_node_id": None,
                "score_adjustment": 0.0,
                "reasoning": "The OpenAI topology candidate critic returned an empty structured payload.",
                "risk_note": None,
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": "The OpenAI topology candidate critic returned empty output.",
            }
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return {
                "verdict": "inconclusive",
                "selected_node_id": None,
                "score_adjustment": 0.0,
                "reasoning": "The OpenAI topology candidate critic returned malformed JSON.",
                "risk_note": None,
                "requested_model": self._config.model,
                "llm_model": response.model,
                "usage": usage,
                "request": request_preview,
                "raw_output_text": raw_text,
                "error": f"Could not parse topology candidate critic output: {exc}",
            }
        payload["requested_model"] = self._config.model
        payload["llm_model"] = response.model
        payload["usage"] = usage
        payload["request"] = request_preview
        payload["raw_output_text"] = raw_text
        payload["error"] = None
        return payload


def _usage_to_dict(usage: object | None) -> dict[str, object] | None:
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _supports_reasoning_controls(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("gpt-5") or normalized.startswith("o1") or normalized.startswith("o3") or normalized.startswith("o4")


def _supports_text_controls(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("gpt-5")
