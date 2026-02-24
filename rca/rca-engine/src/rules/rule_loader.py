"""Load service rule sets from YAML files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.rules.models import ConditionNode, RuleCondition, RuleConditionGroup, RuleSet, SignalRule
from src.rules.schema_validator import RuleSchemaValidator


class RuleLoader:
    """Read YAML files, validate schema, and cache parsed rule sets by file mtime."""

    def __init__(self, rules_directory: str) -> None:
        self._rules_directory = Path(rules_directory)
        self._validator = RuleSchemaValidator()
        self._cache: dict[Path, tuple[tuple[tuple[str, int], ...], RuleSet]] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self, service: str, file_name: str) -> RuleSet:
        """Load a rule file for one service, using cache when file is unchanged."""
        path = self._resolve_rule_path(self._rules_directory / file_name)
        dependency_signature = self._dependency_signature(path, visiting=set())

        cached = self._cache.get(path)
        if cached and cached[0] == dependency_signature:
            self._logger.debug("Using cached rules", extra={"service": service, "rule_file": str(path)})
            return cached[1]

        rule_set = self._load_uncached(path, service)
        self._cache[path] = (dependency_signature, rule_set)
        self._logger.info(
            "Rule file loaded",
            extra={
                "service": rule_set.service,
                "rule_file": str(path),
                "rule_count": len(rule_set.rules),
                "from_cache": False,
                "dependency_count": len(dependency_signature),
            },
        )
        return rule_set

    def _load_uncached(self, path: Path, service: str) -> RuleSet:
        """Read and parse rule file from disk."""
        raw_root = self._read_payload(path, service)
        root_service = str(raw_root.get("service", service))
        rules = self._load_rules_recursive(path, root_service, visiting=set())
        self._validate_duplicate_rule_ids(rules, str(path))
        return RuleSet(service=root_service, rules=rules)

    def _load_rules_recursive(
        self,
        path: Path,
        service: str,
        visiting: set[Path],
    ) -> list[SignalRule]:
        """Load rules from one file and all imported files recursively."""
        if path in visiting:
            chain = " -> ".join(str(item) for item in list(visiting) + [path])
            raise ValueError(f"Circular rule imports detected: {chain}")
        visiting.add(path)

        raw = self._read_payload(path, service)

        service_name = str(raw.get("service", service))
        rules: list[SignalRule] = []

        try:
            for item in raw.get("rules", []):
                condition = self._parse_rule_condition(item)
                rules.append(
                    SignalRule(
                        rule_id=item["id"],
                        signal_key=item["signal_key"],
                        level=item["level"],
                        description=item.get("description", item["id"]),
                        condition=condition,
                        tags=item.get("tags", []),
                    )
                )
        except Exception:
            self._logger.exception(
                "Rule parsing failed",
                extra={"service": service_name, "rule_file": str(path)},
            )
            visiting.remove(path)
            raise

        imports = raw.get("imports", [])
        if imports:
            if not isinstance(imports, list) or not all(isinstance(entry, str) for entry in imports):
                visiting.remove(path)
                raise ValueError(f"{path}: imports must be a list of file paths")
            for import_ref in imports:
                import_path = self._resolve_import_path(path, import_ref)
                rules.extend(self._load_rules_recursive(import_path, service_name, visiting))

        visiting.remove(path)
        return rules

    def _read_payload(self, path: Path, service: str) -> dict[str, Any]:
        """Read, parse, and validate one rule YAML payload."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            self._logger.exception("Failed reading rule file", extra={"service": service, "rule_file": str(path)})
            raise

        if not isinstance(raw, dict):
            raise ValueError(f"Rule file must contain mapping: {path}")

        try:
            self._validator.validate(raw, str(path))
        except Exception:
            self._logger.exception(
                "Rule schema validation failed",
                extra={"service": service, "rule_file": str(path)},
            )
            raise
        return raw

    def _dependency_signature(
        self,
        path: Path,
        visiting: set[Path],
    ) -> tuple[tuple[str, int], ...]:
        """Build a deterministic signature of all dependency mtimes."""
        if path in visiting:
            chain = " -> ".join(str(item) for item in list(visiting) + [path])
            raise ValueError(f"Circular rule imports detected: {chain}")
        visiting.add(path)

        raw = self._read_payload(path, "dependency-scan")
        deps: dict[Path, int] = {path: self._get_mtime_ns(path)}

        imports = raw.get("imports", [])
        if imports:
            if not isinstance(imports, list) or not all(isinstance(entry, str) for entry in imports):
                visiting.remove(path)
                raise ValueError(f"{path}: imports must be a list of file paths")
            for import_ref in imports:
                import_path = self._resolve_import_path(path, import_ref)
                child_signature = self._dependency_signature(import_path, visiting)
                for dep_name, dep_mtime in child_signature:
                    deps[Path(dep_name)] = dep_mtime

        visiting.remove(path)
        return tuple(
            sorted(
                (str(dep_path), dep_mtime)
                for dep_path, dep_mtime in deps.items()
            )
        )

    @staticmethod
    def _get_mtime_ns(path: Path) -> int:
        """Return file modification timestamp in nanoseconds."""
        try:
            return path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise ValueError(f"Rule file not found: {path}") from exc

    def _parse_rule_condition(self, rule_raw: dict[str, Any]) -> ConditionNode:
        """Parse nested strict `condition` tree."""
        return self._parse_condition_node(rule_raw["condition"])

    def _resolve_import_path(self, parent_path: Path, import_ref: str) -> Path:
        """Resolve imported file reference relative to parent rule file."""
        resolved = self._resolve_rule_path(parent_path.parent / import_ref)
        if resolved == parent_path:
            raise ValueError(f"{parent_path}: imports must not reference itself")
        return resolved

    def _resolve_rule_path(self, path: Path) -> Path:
        """Resolve path and enforce that it stays inside rules directory."""
        resolved = path.resolve()
        rules_root = self._rules_directory.resolve()
        if not resolved.is_relative_to(rules_root):
            raise ValueError(f"Rule file path escapes rules directory: {path}")
        return resolved

    @staticmethod
    def _validate_duplicate_rule_ids(rules: list[SignalRule], root_path: str) -> None:
        """Fail fast when merged imports produce duplicate rule IDs."""
        seen: set[str] = set()
        duplicates: set[str] = set()
        for rule in rules:
            if rule.rule_id in seen:
                duplicates.add(rule.rule_id)
            seen.add(rule.rule_id)
        if duplicates:
            duplicate_ids = ", ".join(sorted(duplicates))
            raise ValueError(f"{root_path}: duplicate rule id(s) detected: {duplicate_ids}")

    def _parse_condition_node(self, node_raw: dict[str, Any]) -> ConditionNode:
        if "and" in node_raw:
            children = [self._parse_condition_node(child) for child in node_raw["and"]]
            return RuleConditionGroup(op="and", conditions=children)
        if "or" in node_raw:
            children = [self._parse_condition_node(child) for child in node_raw["or"]]
            return RuleConditionGroup(op="or", conditions=children)
        return self._parse_condition_leaf(node_raw)

    @staticmethod
    def _parse_condition_leaf(cond: dict[str, Any]) -> RuleCondition:
        return RuleCondition(
            field=cond["field"],
            op=cond["op"],
            value=cond.get("value"),
            case_sensitive=cond.get("case_sensitive", False),
        )
