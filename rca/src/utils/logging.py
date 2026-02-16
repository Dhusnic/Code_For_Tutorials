"""Logging utilities for consistent structured logs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.config.settings import LoggingConfig


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for ingestion and debugging."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        reserved = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }
        for key, value in record.__dict__.items():
            if key not in reserved:
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(config: LoggingConfig) -> None:
    """Configure root logger using app settings."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if config.json else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
