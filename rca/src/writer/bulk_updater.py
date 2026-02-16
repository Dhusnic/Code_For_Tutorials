"""Build bulk actions that write enriched events into RCA indices."""

from __future__ import annotations

import hashlib
import re
from typing import Any


class BulkActionFactory:
    """Create idempotent upsert actions for Elasticsearch bulk API."""

    _LEVEL_ALIAS_MAP = {
        "critical": {
            "critical",
            "crit",
            "fatal",
            "panic",
            "alert",
            "emerg",
            "emergency",
            "severe",
            "sev",
        },
        "error": {
            "error",
            "err",
            "failure",
            "failed",
        },
        "warning": {
            "warning",
            "warn",
            "wrn",
        },
        "info": {
            "info",
            "inf",
            "information",
            "informational",
            "notice",
        },
        "debug": {
            "debug",
            "dbg",
            "trace",
            "verbose",
        },
    }

    _SYSLOG_PRIORITY_MAP = {
        0: "critical",  # emergency
        1: "critical",  # alert
        2: "critical",  # critical
        3: "error",  # error
        4: "warning",  # warning
        5: "info",  # notice
        6: "info",  # informational
        7: "debug",  # debug
    }

    def build(
        self,
        source_index: str,
        target_index: str,
        source_id: str,
        source_doc: dict[str, Any],
        selected_signal: dict[str, Any],
    ) -> dict[str, Any]:
        """Return one bulk update action with deterministic target id."""
        target_id = self._target_id(source_index, source_id)
        payload = {
            **source_doc,
            "source_index": source_index,
            "source_id": source_id,
            "signal": selected_signal["signal"],
            # "signal_rule_id": selected_signal["rule_id"],
            "signal_present": True,
        }
        log_value = payload.get("log")
        current_level: Any = None
        if isinstance(log_value, dict):
            current_level = log_value.get("level")

        normalized_current_level = self._normalize_level(current_level)
        normalized_rule_level = self._normalize_level(selected_signal.get("level"))
        if normalized_rule_level is None:
            normalized_rule_level = str(selected_signal["level"]).strip().lower()

        log_obj = dict(log_value) if isinstance(log_value, dict) else {}
        # Keep a valid existing level (normalized); fallback to matched rule level only when invalid/missing.
        log_obj["level"] = normalized_current_level or normalized_rule_level
        payload["log"] = log_obj

        return {
            "_op_type": "update",
            "_index": target_index,
            "_id": target_id,
            "doc": payload,
            "doc_as_upsert": True,
        }

    @staticmethod
    def _target_id(source_index: str, source_id: str) -> str:
        raw = f"{source_index}:{source_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _normalize_level(cls, value: Any) -> str | None:
        """Return canonical level name when value is recognized, else None."""
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return cls._SYSLOG_PRIORITY_MAP.get(value)

        text = str(value).strip().lower()
        if not text:
            return None

        if text.isdigit():
            return cls._SYSLOG_PRIORITY_MAP.get(int(text))

        compact = re.sub(r"[\s._-]+", "", text)
        for canonical, aliases in cls._LEVEL_ALIAS_MAP.items():
            if compact in aliases:
                return canonical
        return None
