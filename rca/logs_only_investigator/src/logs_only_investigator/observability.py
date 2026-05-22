from __future__ import annotations

import json
import logging
import sys
from typing import Any

from .config import LoggingConfig


SENSITIVE_KEYS = {"api_key", "password", "authorization", "token", "secret"}


def configure_logging(config: LoggingConfig) -> logging.Logger:
    logger = logging.getLogger(config.logger_name)
    logger.setLevel(_coerce_level(config.level))
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


def redact_for_logging(value: Any, *, max_chars: int = 1200) -> str:
    sanitized = _sanitize(value)
    try:
        rendered = json.dumps(sanitized, ensure_ascii=True, default=str)
    except TypeError:
        rendered = repr(sanitized)
    if len(rendered) > max_chars:
        return rendered[: max_chars - 3] + "..."
    return rendered


def log_step(logger: logging.Logger, level: int, step: str, **details: Any) -> None:
    if details:
        suffix = " | " + " | ".join(f"{key}={value}" for key, value in details.items())
    else:
        suffix = ""
    logger.log(level, "%s%s", step, suffix)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[str(key)] = "***REDACTED***"
            else:
                sanitized[str(key)] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize(item) for item in value)
    return value


def _coerce_level(value: str) -> int:
    return getattr(logging, value.upper(), logging.INFO)
