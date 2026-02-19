"""Learn recurring unclassified critical log patterns and persist rule suggestions."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import RuleLearningConfig
from src.utils.dicts import get_nested


@dataclass(slots=True)
class _PatternBucket:
    """In-memory aggregate for one normalized recurring log pattern."""

    service: str
    signature: str
    count: int = 0
    samples: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _RuleCandidate:
    """Serializable candidate rule generated from one learned pattern."""

    rule_id: str
    signal_key: str
    level: str
    description: str
    tags: list[str]
    condition_field: str
    condition_op: str
    condition_value: str

    def to_rule_dict(self) -> dict[str, Any]:
        """Return rule dictionary compatible with current YAML rule schema."""
        return {
            "id": self.rule_id,
            "signal_key": self.signal_key,
            "level": self.level,
            "description": self.description,
            "tags": self.tags,
            "condition": {
                "field": self.condition_field,
                "op": self.condition_op,
                "value": self.condition_value,
            },
        }


class AutoRuleLearner:
    """Build and persist auto-generated rules for unclassified critical events."""

    _STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "while",
        "this",
        "that",
        "into",
        "after",
        "before",
        "failed",
        "error",
        "critical",
        "panic",
        "alert",
        "warning",
    }
    _MESSAGE_FIELDS = ("message", "error.message", "log.original")

    def __init__(
        self,
        *,
        config: RuleLearningConfig,
        rules_directory: str,
        service_rule_files: dict[str, str],
    ) -> None:
        self._config = config
        self._rules_directory = Path(rules_directory)
        self._output_directory = Path(config.output_directory)
        self._service_rule_files = service_rule_files
        self._pattern_buckets: dict[tuple[str, str], _PatternBucket] = {}
        self._emitted_pattern_keys: set[tuple[str, str]] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def observe(
        self,
        service_name: str,
        source_doc: dict[str, Any],
        selected_signal: dict[str, Any] | None,
    ) -> None:
        """Track one event when it is classified as unclassified critical."""
        if not self._config.enabled:
            return
        if not self._is_unclassified_critical(selected_signal):
            return

        message = self._extract_message(source_doc)
        if not message:
            return

        normalized = self._normalize_message(message)
        if not normalized:
            return
        keywords = self._extract_keywords(normalized)
        min_keywords = max(1, int(self._config.min_keyword_count))
        if len(keywords) < min_keywords:
            return
        signature_tokens = keywords[: max(min_keywords, int(self._config.max_keywords_per_signal))]
        signature = " ".join(signature_tokens)

        key = (service_name, signature)
        bucket = self._pattern_buckets.get(key)
        if bucket is None:
            bucket = _PatternBucket(service=service_name, signature=signature)
            self._pattern_buckets[key] = bucket

        bucket.count += 1
        if len(bucket.samples) < 3:
            bucket.samples.append(message)

    def flush(self) -> dict[str, int]:
        """Persist all eligible learned patterns and return counts by service."""
        if not self._config.enabled:
            return {}

        service_candidates: dict[str, list[tuple[tuple[str, str], _RuleCandidate]]] = {}
        candidates_per_service: dict[str, int] = {}
        sorted_buckets = sorted(
            self._pattern_buckets.items(),
            key=lambda item: item[1].count,
            reverse=True,
        )

        for key, bucket in sorted_buckets:
            if key in self._emitted_pattern_keys:
                continue
            if bucket.count < max(1, int(self._config.min_occurrences)):
                continue

            service = bucket.service
            current_count = candidates_per_service.get(service, 0)
            if current_count >= max(1, int(self._config.max_candidates_per_service)):
                continue

            candidate = self._build_candidate(bucket)
            if candidate is None:
                continue

            service_candidates.setdefault(service, []).append((key, candidate))
            candidates_per_service[service] = current_count + 1

        written_by_service: dict[str, int] = {}
        persisted_services: set[str] = set()
        for service, entries in service_candidates.items():
            rule_file = self._service_rule_files.get(service, f"{service}.yml")
            written = self._persist_candidates(
                service,
                rule_file,
                [candidate for _, candidate in entries],
            )
            if written > 0:
                written_by_service[service] = written
                persisted_services.add(service)

        for service, entries in service_candidates.items():
            if service not in persisted_services:
                continue
            for key, _ in entries:
                self._emitted_pattern_keys.add(key)

        return written_by_service

    def _build_candidate(self, bucket: _PatternBucket) -> _RuleCandidate | None:
        """Generate one deterministic rule candidate from a pattern bucket."""
        signature_hash = hashlib.sha1(
            f"{bucket.service}|{bucket.signature}".encode("utf-8")
        ).hexdigest()
        keywords = self._extract_keywords(bucket.signature)
        min_keywords = max(1, int(self._config.min_keyword_count))
        if len(keywords) < min_keywords:
            return None

        max_keywords = max(min_keywords, int(self._config.max_keywords_per_signal))
        selected_keywords = keywords[:max_keywords]
        keyword_part = "_".join(selected_keywords)
        hash_short = signature_hash[:8]

        signal_key = self._normalize_snake_case(
            f"{bucket.service}_auto_{keyword_part}_{hash_short[:4]}"
        )
        rule_id = self._normalize_rule_id(
            f"{bucket.service.upper()}_AUTO_{'_'.join(kw.upper() for kw in selected_keywords)}_{hash_short.upper()}"
        )

        condition_literal = " ".join(selected_keywords)
        if len(condition_literal.strip()) < 8:
            return None

        description = (
            "Auto-learned from recurring unclassified critical logs: "
            f"{condition_literal}"
        )
        return _RuleCandidate(
            rule_id=rule_id,
            signal_key=signal_key,
            level=str(self._config.level).strip().lower(),
            description=description,
            tags=["auto_generated", "unclassified_learning", bucket.service, "critical"],
            condition_field=str(self._config.condition_field).strip() or "message",
            condition_op=str(self._config.condition_op).strip() or "contains",
            condition_value=condition_literal,
        )

    def _persist_candidates(
        self,
        service: str,
        rule_file: str,
        candidates: list[_RuleCandidate],
    ) -> int:
        """Write non-duplicate candidates to suggestion or main rule file."""
        if not candidates:
            return 0

        mode = str(self._config.mode).strip().lower()
        target_path = (
            self._output_directory / f"{service}.yml"
            if mode == "suggest"
            else self._rules_directory / rule_file
        )

        payload = self._read_rules_payload(target_path, service)
        rules = payload.setdefault("rules", [])
        if not isinstance(rules, list):
            self._logger.warning(
                "Rules payload is not a list; resetting payload",
                extra={"service": service, "path": str(target_path)},
            )
            payload["rules"] = []
            rules = payload["rules"]

        existing_ids, existing_signal_keys, existing_condition_values = self._collect_rule_keys(rules)

        new_rules: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate.rule_id in existing_ids:
                continue
            if candidate.signal_key in existing_signal_keys:
                continue
            normalized_condition = candidate.condition_value.strip().lower()
            if normalized_condition in existing_condition_values:
                continue

            rule_dict = candidate.to_rule_dict()
            rules.append(rule_dict)
            new_rules.append(rule_dict)
            existing_ids.add(candidate.rule_id)
            existing_signal_keys.add(candidate.signal_key)
            existing_condition_values.add(normalized_condition)

        if not new_rules:
            return 0

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )
        except Exception:
            self._logger.exception(
                "Failed writing auto-learned rules",
                extra={"service": service, "path": str(target_path), "mode": mode},
            )
            return 0

        self._logger.info(
            "Auto-learned rule candidates persisted",
            extra={
                "service": service,
                "mode": mode,
                "path": str(target_path),
                "written_count": len(new_rules),
            },
        )
        return len(new_rules)

    @staticmethod
    def _collect_rule_keys(
        rules: list[dict[str, Any]],
    ) -> tuple[set[str], set[str], set[str]]:
        """Collect dedupe keys from existing rule entries."""
        ids: set[str] = set()
        signal_keys: set[str] = set()
        condition_values: set[str] = set()

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("id")
            if isinstance(rule_id, str):
                ids.add(rule_id)

            signal_key = rule.get("signal_key")
            if isinstance(signal_key, str):
                signal_keys.add(signal_key)

            condition = rule.get("condition")
            if isinstance(condition, dict):
                condition_value = condition.get("value")
                if isinstance(condition_value, str):
                    condition_values.add(condition_value.strip().lower())

        return ids, signal_keys, condition_values

    @staticmethod
    def _read_rules_payload(path: Path, service: str) -> dict[str, Any]:
        """Load existing YAML payload or build a default skeleton."""
        if not path.exists():
            return {"service": service, "rules": []}

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return {"service": service, "rules": []}

        if not isinstance(raw, dict):
            return {"service": service, "rules": []}
        if "service" not in raw:
            raw["service"] = service
        if "rules" not in raw:
            raw["rules"] = []
        return raw

    @staticmethod
    def _normalize_message(message: str) -> str:
        """Normalize dynamic values to build stable signatures."""
        text = message.strip().lower()
        text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", " <ip> ", text)
        text = re.sub(r"\b[0-9a-f]{8,}\b", " <hex> ", text)
        text = re.sub(r"\b\d+\b", " <num> ", text)
        text = re.sub(r"[^a-z0-9<>]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_keywords(self, signature: str) -> list[str]:
        """Return stable tokens used for signal and rule generation."""
        ordered: list[str] = []
        seen: set[str] = set()
        for token in signature.split():
            if token in {"<num>", "<ip>", "<hex>"}:
                continue
            if len(token) < 2:
                continue
            if token in self._STOPWORDS:
                continue
            if token not in seen:
                seen.add(token)
                ordered.append(token)
        return ordered

    @classmethod
    def _extract_message(cls, source_doc: dict[str, Any]) -> str | None:
        """Resolve message text from common log fields."""
        for field_name in cls._MESSAGE_FIELDS:
            value = get_nested(source_doc, field_name)
            if value is None and "." not in field_name:
                value = source_doc.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _normalize_snake_case(value: str) -> str:
        """Convert text to schema-compatible snake_case signal key."""
        text = value.strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

    @staticmethod
    def _normalize_rule_id(value: str) -> str:
        """Convert text to uppercase underscore style rule id."""
        text = value.strip().upper()
        text = re.sub(r"[^A-Z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

    @staticmethod
    def _is_unclassified_critical(selected_signal: dict[str, Any] | None) -> bool:
        """Return True for fallback/unclassified critical signals only."""
        if not isinstance(selected_signal, dict):
            return False
        level = str(selected_signal.get("level", "")).strip().lower()
        if level != "critical":
            return False

        signal_key = str(selected_signal.get("signal", "")).strip().lower()
        tags_raw = selected_signal.get("tags", [])
        tags = {str(tag).strip().lower() for tag in tags_raw} if isinstance(tags_raw, list) else set()
        return (
            "unclassified" in tags
            or "fallback" in tags
            or signal_key.endswith("_unclassified_failure")
        )
