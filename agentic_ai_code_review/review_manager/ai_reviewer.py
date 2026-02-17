"""AI review manager built on OpenAI Responses API with resilient error handling."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from comman import CommonUtils

LOGGER = logging.getLogger(__name__)


class AIReviewer(CommonUtils):
    """Encapsulates model calls and token estimation for review workflows."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        max_tokens: int = 2048,
        env_path: str = ".env",
    ) -> None:
        """
        Initialize the AI reviewer service.

        Args:
            model_name: Default OpenAI model to use.
            max_tokens: Maximum output tokens per request.
            env_path: Path to environment file containing `OPENAI_API_KEY`.
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.env_path = env_path

    def estimate_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """
        Estimate token usage for a given text payload.

        Args:
            text: Input text to estimate.
            model: Target model name.

        Returns:
            Estimated token count.
        """
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text or ""))
        except Exception:
            # Fallback heuristic: 1 token ~= 4 chars.
            return max(1, len(text or "") // 4)

    def call_openai(
        self,
        conversation: List[Dict[str, str]],
        model: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: int = 60,
        retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Execute a low-level OpenAI request with retries.

        Args:
            conversation: Chat messages in role/content format.
            model: OpenAI model.
            max_output_tokens: Output token ceiling.
            temperature: Sampling temperature.
            timeout: Request timeout in seconds.
            retries: Retry attempts for transient failures.

        Returns:
            Dictionary with `response` and `tokens_used`.
        """
        api_key = self.get_env_value(self.env_path, "OPENAI_API_KEY", required=True)
        client = OpenAI(api_key=api_key, timeout=timeout)
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                request_tokens = self.estimate_tokens(str(conversation), model=model)
                LOGGER.info(
                    "OpenAI request attempt=%s model=%s request_tokens=%s",
                    attempt,
                    model,
                    request_tokens,
                )

                response = client.responses.create(
                    model=model,
                    input=[self._to_responses_input_item(message) for message in conversation],
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )

                text_output = self._extract_response_text(response)
                usage = self._extract_response_usage(response)
                if usage is not None:
                    prompt_tokens = usage["input_tokens"]
                    response_tokens = usage["output_tokens"]
                    total_tokens = usage["total_tokens"]
                    token_source = "response_usage"
                else:
                    response_tokens = self.estimate_tokens(text_output, model=model)
                    prompt_tokens = request_tokens
                    total_tokens = request_tokens + response_tokens
                    token_source = "estimated"
                LOGGER.info(
                    "OpenAI request completed model=%s source=%s response_tokens=%s total_tokens=%s",
                    model,
                    token_source,
                    response_tokens,
                    total_tokens,
                )
                return {
                    "response": text_output,
                    "tokens_used": total_tokens,
                    "token_source": token_source,
                    "token_usage": {
                        "input_tokens": prompt_tokens,
                        "output_tokens": response_tokens,
                        "total_tokens": total_tokens,
                        "source": token_source,
                    },
                }
            except Exception as exc:
                last_error = exc
                LOGGER.exception(
                    "OpenAI request failed on attempt %s/%s", attempt, retries
                )
                if attempt < retries:
                    time.sleep(attempt * 2)

        raise RuntimeError(f"OpenAI call failed after {retries} attempts: {last_error}")

    def get_ai_response(
        self,
        conversation: List[Dict[str, str]],
        model: str | None = None,
        max_output_tokens: int | None = None,
    ) -> Dict[str, Any]:
        """
        High-level API used by callers to run AI prompts.

        Args:
            conversation: Message history in role/content format.
            model: Optional override model.
            max_output_tokens: Optional override output token limit.

        Returns:
            Dictionary with `response` and `tokens_used`.
        """
        try:
            if not isinstance(conversation, list) or not conversation:
                raise ValueError("Conversation must be a non-empty list")

            for message in conversation:
                if not isinstance(message, dict):
                    raise ValueError("Each conversation item must be an object")
                if "role" not in message or "content" not in message:
                    raise ValueError("Each message must include 'role' and 'content'")

            resolved_model = model or self.model_name
            resolved_max_tokens = max_output_tokens or self.max_tokens
            return self.call_openai(
                conversation=conversation,
                model=resolved_model,
                max_output_tokens=resolved_max_tokens,
            )
        except Exception as exc:
            LOGGER.exception("Failed to generate AI response")
            raise

    def _to_responses_input_item(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert role/content message into Responses API input payload.

        Assistant replay messages must use `output_text`, while other roles use `input_text`.
        """
        role = str(message.get("role", "user") or "user").strip().lower()
        text = str(message.get("content", "") or "")
        if role == "assistant":
            content_type = "output_text"
        else:
            content_type = "input_text"
        return {
            "role": role,
            "content": [{"type": content_type, "text": text}],
        }

    def _extract_response_text(self, response: Any) -> str:
        """
        Normalize output text from OpenAI SDK response object.

        Args:
            response: OpenAI SDK response object.

        Returns:
            Extracted response text.
        """
        try:
            output_text = getattr(response, "output_text", None)
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()

            normalized_parts: List[str] = []
            for item in getattr(response, "output", []) or []:
                item_type = getattr(item, "type", None)
                if item_type != "message":
                    continue
                for content in getattr(item, "content", []) or []:
                    content_type = getattr(content, "type", None)
                    if content_type == "output_text":
                        text_value = getattr(content, "text", "")
                        if text_value:
                            normalized_parts.append(text_value)

            final_text = "\n".join(part for part in normalized_parts if part.strip()).strip()
            if not final_text:
                raise RuntimeError("OpenAI returned an empty output")
            return final_text
        except Exception as exc:
            LOGGER.exception("Unable to extract text from OpenAI response")
            raise RuntimeError("Failed to parse OpenAI response payload") from exc

    def _extract_response_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """
        Extract token usage from OpenAI response payload when available.

        Returns:
            Dictionary with normalized token counters, or `None` if unavailable.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            return None

        def read_usage_int(*keys: str) -> int | None:
            for key in keys:
                raw_value = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
                if raw_value is None:
                    continue
                try:
                    return max(int(raw_value), 0)
                except (TypeError, ValueError):
                    continue
            return None

        input_tokens = read_usage_int("input_tokens", "prompt_tokens")
        output_tokens = read_usage_int("output_tokens", "completion_tokens")
        total_tokens = read_usage_int("total_tokens")

        if total_tokens is None:
            if input_tokens is None and output_tokens is None:
                return None
            total_tokens = max((input_tokens or 0) + (output_tokens or 0), 0)

        if input_tokens is None and output_tokens is not None:
            input_tokens = max(total_tokens - output_tokens, 0)
        if output_tokens is None and input_tokens is not None:
            output_tokens = max(total_tokens - input_tokens, 0)

        return {
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "total_tokens": total_tokens,
        }
