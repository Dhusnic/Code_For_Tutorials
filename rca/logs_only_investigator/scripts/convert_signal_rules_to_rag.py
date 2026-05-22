from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


LOGGER = logging.getLogger("convert_signal_rules_to_rag")


DOMAIN_MAP: dict[str, str] = {
    "auth": "security",
    "data_collector": "ingestion",
    "kafka": "messaging",
    "mongodb": "database",
    "network": "network",
    "nginx": "gateway",
    "postgres": "database",
    "rabbitmq": "messaging",
    "redis": "cache",
    "system": "system",
    "arista_eos": "network",
    "aruba_aos": "network",
    "checkpoint": "network",
    "cisco_ios": "network",
    "cisco_nxos": "network",
    "crontab_cron": "system",
    "dell_os10": "network",
    "f5_bigip": "network",
    "fortinet_fortios": "network",
    "huawei_vrp": "network",
    "juniper_junos": "network",
    "mikrotik_ros": "network",
    "paloalto_panos": "network",
}


TOKEN_TITLE_MAP: dict[str, str] = {
    "aaa": "AAA",
    "api": "API",
    "auth": "Auth",
    "bfd": "BFD",
    "bgp": "BGP",
    "cpu": "CPU",
    "db": "DB",
    "dns": "DNS",
    "eos": "EOS",
    "f5": "F5",
    "ha": "HA",
    "http": "HTTP",
    "https": "HTTPS",
    "ike": "IKE",
    "ios": "IOS",
    "ip": "IP",
    "ipsec": "IPsec",
    "junos": "Junos",
    "kafka": "Kafka",
    "mlag": "MLAG",
    "mongodb": "MongoDB",
    "nginx": "NGINX",
    "ospf": "OSPF",
    "pam": "PAM",
    "panos": "PAN-OS",
    "postgres": "Postgres",
    "redis": "Redis",
    "ssh": "SSH",
    "stp": "STP",
    "sudo": "sudo",
    "su": "su",
    "syslog": "Syslog",
    "vrp": "VRP",
    "vpn": "VPN",
}


DEFAULT_LIKELY_ENTITIES = ["service", "host", "ip"]
SERVICE_HINTS: dict[str, list[str]] = {
    "mongodb": ["service", "host", "ip", "replica_set"],
    "postgres": ["service", "host", "ip", "database"],
    "redis": ["service", "host", "ip", "cluster_node"],
    "kafka": ["service", "host", "ip", "broker", "topic"],
    "nginx": ["service", "host", "ip", "upstream"],
    "auth": ["service", "host", "ip", "user"],
    "network": ["service", "host", "ip", "device", "interface"],
}
VENDOR_HINTS: dict[str, list[str]] = {
    "arista_eos": ["host", "ip", "device", "interface"],
    "aruba_aos": ["host", "ip", "device", "interface"],
    "checkpoint": ["host", "ip", "device", "policy"],
    "cisco_ios": ["host", "ip", "device", "interface"],
    "cisco_nxos": ["host", "ip", "device", "interface"],
    "dell_os10": ["host", "ip", "device", "interface"],
    "f5_bigip": ["host", "ip", "device", "virtual_server"],
    "fortinet_fortios": ["host", "ip", "device", "policy"],
    "huawei_vrp": ["host", "ip", "device", "interface"],
    "juniper_junos": ["host", "ip", "device", "interface"],
    "mikrotik_ros": ["host", "ip", "device", "interface"],
    "paloalto_panos": ["host", "ip", "device", "tunnel"],
}


@dataclass
class SourceContext:
    source_file: Path
    output_file: Path
    category: str
    service: str | None
    vendor: str | None
    domain: str


@dataclass
class VectorBuildSummary:
    dbs_total: int = 0
    dbs_written: int = 0
    records_written: int = 0
    db_errors: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert YAML signal rules into RAG-friendly JSON catalogs."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=default_source_root(),
        help="Root folder containing the signal rule YAML files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_output_root(),
        help="Output folder for generated RAG JSON files.",
    )
    parser.add_argument(
        "--signal-source",
        choices=["auto", "signal_key", "id"],
        default="auto",
        help="Choose whether the exported signal value comes from signal_key or the YAML rule id.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with a non-zero status if any file or rule cannot be processed cleanly.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--build-vector-db",
        choices=["ask", "yes", "no"],
        default="ask",
        help="Whether to build separate vector DBs from the generated JSON catalogs.",
    )
    parser.add_argument(
        "--vector-output-root",
        type=Path,
        default=default_vector_output_root(),
        help="Output folder for generated per-catalog vector DBs.",
    )
    parser.add_argument(
        "--embedding-model",
        default="all-MiniLM-L6-v2",
        help="Sentence-Transformers embedding model to use for vector DB generation.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    vector_output_root = args.vector_output_root.resolve()
    if not source_root.exists():
        LOGGER.error("Source root does not exist: %s", source_root)
        return 2

    yaml_files = discover_rule_files(source_root)
    if not yaml_files:
        LOGGER.error("No YAML rule files found under %s", source_root)
        return 2

    summary = {
        "files_total": 0,
        "files_written": 0,
        "records_written": 0,
        "rule_errors": 0,
        "file_errors": 0,
    }

    output_root.mkdir(parents=True, exist_ok=True)

    for yaml_file in yaml_files:
        summary["files_total"] += 1
        try:
            ctx = resolve_source_context(yaml_file, source_root, output_root)
            records, rule_errors = convert_yaml_file(ctx, signal_source=args.signal_source)
            summary["rule_errors"] += rule_errors
            ctx.output_file.parent.mkdir(parents=True, exist_ok=True)
            ctx.output_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
            summary["files_written"] += 1
            summary["records_written"] += len(records)
            LOGGER.info("Wrote %s records -> %s", len(records), ctx.output_file)
        except Exception as exc:  # noqa: BLE001
            summary["file_errors"] += 1
            LOGGER.exception("Failed to convert %s: %s", yaml_file, exc)

    LOGGER.info(
        "Completed conversion: files=%s written=%s records=%s rule_errors=%s file_errors=%s",
        summary["files_total"],
        summary["files_written"],
        summary["records_written"],
        summary["rule_errors"],
        summary["file_errors"],
    )

    if args.strict and (summary["rule_errors"] or summary["file_errors"]):
        return 1

    build_vector_db = should_build_vector_db(args.build_vector_db)
    if build_vector_db:
        try:
            vector_summary = build_vector_databases(
                rag_root=output_root,
                vector_output_root=vector_output_root,
                embedding_model=args.embedding_model,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Vector DB build failed: %s", exc)
            return 1

        LOGGER.info(
            "Completed vector DB build: dbs=%s written=%s records=%s db_errors=%s",
            vector_summary.dbs_total,
            vector_summary.dbs_written,
            vector_summary.records_written,
            vector_summary.db_errors,
        )
        if args.strict and vector_summary.db_errors:
            return 1
    return 0


def default_source_root() -> Path:
    return Path(__file__).resolve().parents[2] / "log_signalizing" / "rules"


def default_output_root() -> Path:
    return Path(__file__).resolve().parents[1] / "rag"


def default_vector_output_root() -> Path:
    return Path(__file__).resolve().parents[1] / "rag_db"


def discover_rule_files(source_root: Path) -> list[Path]:
    services = sorted((source_root / "services").glob("*.yml"))
    vendor_root = source_root / "network" / "vendors"
    vendors = sorted(vendor_root.glob("*.yml")) if vendor_root.exists() else []
    return services + vendors


def discover_rag_json_files(rag_root: Path) -> list[Path]:
    services = sorted((rag_root / "services").glob("*.json"))
    network = sorted((rag_root / "network").glob("*.json"))
    return services + network


def resolve_source_context(source_file: Path, source_root: Path, output_root: Path) -> SourceContext:
    relative = source_file.resolve().relative_to(source_root.resolve())
    parts = [part.lower() for part in relative.parts]
    top_level_service = ""
    vendor: str | None = None
    service: str | None = None
    category = ""

    if "services" in parts:
        category = "services"
        service = source_file.stem.lower()
        top_level_service = service
        output_file = output_root / "services" / f"{source_file.stem.lower()}.json"
    elif "vendors" in parts:
        category = "network"
        vendor = source_file.stem.lower()
        top_level_service = "network"
        service = "network"
        output_file = output_root / "network" / f"{source_file.stem.lower()}.json"
    else:
        raise ValueError(f"Unsupported rule file location: {relative}")

    domain = infer_domain(service=top_level_service or service, vendor=vendor, category=category)
    return SourceContext(
        source_file=source_file,
        output_file=output_file,
        category=category,
        service=service,
        vendor=vendor,
        domain=domain,
    )


def convert_yaml_file(ctx: SourceContext, signal_source: str = "auto") -> tuple[list[dict[str, Any]], int]:
    payload = load_yaml(ctx.source_file)
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"File {ctx.source_file} does not contain a list under 'rules'")

    file_service = normalize_name(payload.get("service")) or ctx.service
    file_vendor = ctx.vendor
    file_domain = infer_domain(service=file_service, vendor=file_vendor, category=ctx.category)

    parsed_rules: list[dict[str, Any]] = []
    rule_errors = 0
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            LOGGER.warning("Skipping non-dict rule in %s at index %s", ctx.source_file, index)
            rule_errors += 1
            continue

        try:
            signal = resolve_signal_name(rule, mode=signal_source)
            description = normalize_text(rule.get("description")) or ""
            tags = normalize_tags(rule.get("tags"))
            parsed_rules.append(
                {
                    "rule": rule,
                    "signal": signal,
                    "description": description,
                    "tags": tags,
                    "service": file_service if ctx.category == "services" else "network",
                    "vendor": file_vendor,
                    "domain": file_domain,
                }
            )
        except Exception as exc:  # noqa: BLE001
            rule_errors += 1
            LOGGER.warning(
                "Skipping malformed rule in %s at index %s: %s",
                ctx.source_file,
                index,
                exc,
            )

    records: list[dict[str, Any]] = []
    for current in parsed_rules:
        related = compute_related_signals(current, parsed_rules)
        query_hints = build_query_hints(current["service"], current["vendor"], current["rule"])
        symptom_keywords = build_symptom_keywords(
            signal=current["signal"],
            description=current["description"],
            tags=current["tags"],
            rule=current["rule"],
        )
        record = {
            "id": f"{build_id_prefix(current['service'], current['vendor'])}::{current['signal']}",
            "service": current["service"],
            "vendor": current["vendor"],
            "domain": current["domain"],
            "rule_file": ctx.source_file.name,
            "signal": current["signal"],
            "title": prettify_signal_title(current["signal"]),
            "summary": current["description"] or prettify_signal_title(current["signal"]),
            "symptom_keywords": symptom_keywords,
            "related_signals": related,
            "query_hints": query_hints,
        }
        records.append(record)

    return records, rule_errors


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read YAML file {path}: {exc}") from exc

    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping in {path}")
    return payload


def resolve_signal_name(rule: dict[str, Any], mode: str = "auto") -> str:
    rule_id = normalize_name(rule.get("id"))
    signal_key = normalize_name(rule.get("signal_key"))

    if mode == "id":
        signal = rule_id
    elif mode == "signal_key":
        signal = signal_key or rule_id
    else:
        signal = signal_key or rule_id

    if not signal:
        raise ValueError("rule is missing both id and signal_key")
    return signal


def build_id_prefix(service: str | None, vendor: str | None) -> str:
    if vendor:
        return vendor
    return service or "unknown"


def infer_domain(service: str | None, vendor: str | None, category: str) -> str:
    if service and service in DOMAIN_MAP:
        return DOMAIN_MAP[service]
    if vendor and vendor in DOMAIN_MAP:
        return DOMAIN_MAP[vendor]
    if category == "network":
        return "network"
    return "application"


def normalize_name(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        text = normalize_name(item)
        if text:
            tags.append(text)
    return tags


def prettify_signal_title(signal: str) -> str:
    parts = [part for part in signal.split("_") if part]
    if not parts:
        return signal
    return " ".join(prettify_token(part) for part in parts)


def prettify_token(token: str) -> str:
    normalized = token.lower()
    if normalized in TOKEN_TITLE_MAP:
        return TOKEN_TITLE_MAP[normalized]
    if normalized.isdigit():
        return normalized
    return normalized.capitalize()


def build_symptom_keywords(
    signal: str,
    description: str,
    tags: list[str],
    rule: dict[str, Any],
) -> list[str]:
    candidates: list[str] = []
    candidates.extend(generate_signal_phrases(signal))
    if description:
        candidates.append(description)
    candidates.extend(tag_to_phrase(tag) for tag in tags)
    candidates.extend(extract_condition_keywords(rule.get("condition")))

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = normalize_keyword(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
        if len(unique) >= 16:
            break
    return unique


def generate_signal_phrases(signal: str) -> list[str]:
    parts = [part for part in signal.split("_") if part]
    phrases = {
        signal.replace("_", " "),
        " ".join(parts[-2:]) if len(parts) >= 2 else signal.replace("_", " "),
    }
    if "mongodb" in parts:
        phrases.add("mongo " + " ".join(part for part in parts if part != "mongodb"))
        phrases.add("mongodb " + " ".join(part for part in parts if part != "mongodb"))
    return [phrase for phrase in phrases if phrase.strip()]


def tag_to_phrase(tag: str) -> str:
    return tag.replace("_", " ").strip()


def extract_condition_keywords(condition: Any) -> list[str]:
    keywords: list[str] = []
    for clause in iter_condition_clauses(condition):
        field = normalize_name(clause.get("field")) or ""
        op = normalize_name(clause.get("op")) or ""
        value = clause.get("value")
        if field == "" or value is None:
            continue

        extracted = extract_values_from_clause(op, value)
        if not extracted:
            continue

        for item in extracted:
            if not item:
                continue
            keywords.append(item)
            if field.endswith("message") or field in {"message", "msg"}:
                simplified = simplify_pattern(item)
                if simplified and simplified != item:
                    keywords.append(simplified)
    return keywords


def iter_condition_clauses(node: Any) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    _walk_condition(node, collected)
    return collected


def _walk_condition(node: Any, collected: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if "field" in node and "op" in node:
            collected.append(node)
            return
        for value in node.values():
            _walk_condition(value, collected)
    elif isinstance(node, list):
        for item in node:
            _walk_condition(item, collected)


def extract_values_from_clause(op: str, value: Any) -> list[str]:
    if isinstance(value, list):
        items = [normalize_text(item) for item in value if normalize_text(item)]
        return items[:4]
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, str):
        text = normalize_text(value)
        if not text:
            return []
        if op == "regex":
            return split_regex_pattern(text)
        return [text]
    return []


def split_regex_pattern(pattern: str) -> list[str]:
    results: list[str] = []
    cleaned = pattern.strip()
    if cleaned:
        results.append(cleaned)
    simplified = simplify_pattern(pattern)
    if simplified and simplified != cleaned:
        results.append(simplified)
    return results


def simplify_pattern(value: str) -> str:
    simplified = value
    replacements = [
        (r"\\b", " "),
        (r"\\.", "."),
        (r"\.\+", " "),
        (r"\.\*", " "),
        (r"\(\?:", "("),
        (r"[\\^$]", " "),
        (r"[\[\]{}]", " "),
        (r"[?+*]", " "),
        (r"\|", " "),
    ]
    for pattern, replacement in replacements:
        simplified = re.sub(pattern, replacement, simplified)

    simplified = simplified.replace("(", " ").replace(")", " ")
    simplified = re.sub(r"\s+", " ", simplified).strip(" '\"")
    return simplified


def normalize_keyword(value: str) -> str:
    cleaned = " ".join(value.replace("_", " ").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return ""
    if len(cleaned) > 120:
        cleaned = cleaned[:117].rstrip() + "..."
    return cleaned


def compute_related_signals(current: dict[str, Any], parsed_rules: list[dict[str, Any]]) -> list[str]:
    current_signal = current["signal"]
    current_tags = set(current["tags"])
    scored: list[tuple[int, str]] = []

    for candidate in parsed_rules:
        other_signal = candidate["signal"]
        if other_signal == current_signal:
            continue
        overlap = len(current_tags & set(candidate["tags"]))
        prefix_bonus = shared_signal_prefix_score(current_signal, other_signal)
        score = overlap * 10 + prefix_bonus
        if score <= 0:
            continue
        scored.append((score, other_signal))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [signal for _, signal in scored[:3]]


def shared_signal_prefix_score(left: str, right: str) -> int:
    left_parts = left.split("_")
    right_parts = right.split("_")
    score = 0
    for l_part, r_part in zip(left_parts, right_parts):
        if l_part != r_part:
            break
        score += 3
    return score


def build_query_hints(service: str | None, vendor: str | None, rule: dict[str, Any]) -> dict[str, Any]:
    likely_entities = list(DEFAULT_LIKELY_ENTITIES)
    if service and service in SERVICE_HINTS:
        likely_entities = SERVICE_HINTS[service]
    if vendor and vendor in VENDOR_HINTS:
        likely_entities = VENDOR_HINTS[vendor]

    fields = {
        normalize_name(clause.get("field")) or ""
        for clause in iter_condition_clauses(rule.get("condition"))
    }
    if any("replica" in field for field in fields) and "replica_set" not in likely_entities:
        likely_entities.append("replica_set")
    if any("interface" in field for field in fields) and "interface" not in likely_entities:
        likely_entities.append("interface")
    if any(field.endswith(".ip") or field == "host.ip" for field in fields) and "ip" not in likely_entities:
        likely_entities.append("ip")

    return {
        "likely_entities": likely_entities,
        "default_time_bias": "same_window",
    }


def should_build_vector_db(mode: str) -> bool:
    normalized = (mode or "ask").strip().lower()
    if normalized == "yes":
        return True
    if normalized == "no":
        LOGGER.info("Skipping vector DB build because --build-vector-db=no was selected.")
        return False

    if not sys.stdin.isatty():
        LOGGER.info(
            "Skipping vector DB build because interactive confirmation is not available. "
            "Use --build-vector-db=yes to force it."
        )
        return False

    while True:
        answer = input("Do you want to build separate vector DBs from the generated RAG JSON files? [y/N]: ")
        normalized_answer = answer.strip().lower()
        if normalized_answer in {"", "n", "no"}:
            LOGGER.info("Skipping vector DB build by user choice.")
            return False
        if normalized_answer in {"y", "yes", "ok"}:
            return True
        print("Please answer yes or no.")


def build_vector_databases(
    rag_root: Path,
    vector_output_root: Path,
    embedding_model: str,
) -> VectorBuildSummary:
    chromadb_module, embedding_function_cls = import_vector_dependencies()
    json_files = discover_rag_json_files(rag_root)
    if not json_files:
        raise ValueError(f"No RAG JSON files found under {rag_root}")

    embedding_function = embedding_function_cls(model_name=embedding_model)
    summary = VectorBuildSummary()
    vector_output_root.mkdir(parents=True, exist_ok=True)

    for json_file in json_files:
        summary.dbs_total += 1
        try:
            relative = json_file.relative_to(rag_root)
            db_dir = vector_output_root / relative.parent / json_file.stem
            db_dir.mkdir(parents=True, exist_ok=True)

            records = load_rag_records(json_file)
            if not records:
                LOGGER.warning("Skipping vector DB build for empty catalog: %s", json_file)
                summary.dbs_written += 1
                continue

            client = chromadb_module.PersistentClient(path=str(db_dir))
            reset_collection(client, "signals")
            collection = client.get_or_create_collection(
                name="signals",
                embedding_function=embedding_function,
                metadata={
                    "source_json": json_file.name,
                    "category": relative.parent.name,
                    "embedding_model": embedding_model,
                },
            )

            documents = [build_embedding_text(record) for record in records]
            ids = [str(record["id"]) for record in records]
            metadatas = [build_chroma_metadata(record) for record in records]
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            write_vector_manifest(db_dir, json_file, embedding_model, records)

            summary.dbs_written += 1
            summary.records_written += len(records)
            LOGGER.info("Built vector DB with %s records -> %s", len(records), db_dir)
        except Exception as exc:  # noqa: BLE001
            summary.db_errors += 1
            LOGGER.exception("Failed to build vector DB for %s: %s", json_file, exc)

    return summary


def import_vector_dependencies() -> tuple[Any, Any]:
    try:
        import chromadb  # type: ignore[import-not-found]
        from chromadb.utils.embedding_functions import (  # type: ignore[import-not-found]
            SentenceTransformerEmbeddingFunction,
        )
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "Vector DB dependencies are not installed. "
            "Install them in logs_only_investigator with "
            "`uv sync --extra rag-build` or add `chromadb` and `sentence-transformers`."
        ) from exc
    return chromadb, SentenceTransformerEmbeddingFunction


def load_rag_records(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read RAG JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError(f"RAG JSON root must be a list in {path}")

    records: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"RAG JSON record at index {index} is not an object in {path}")
        if "id" not in item or "signal" not in item:
            raise ValueError(f"RAG JSON record at index {index} is missing required fields in {path}")
        records.append(item)
    return records


def reset_collection(client: Any, name: str) -> None:
    try:
        client.delete_collection(name=name)
    except Exception:  # noqa: BLE001
        return


def build_embedding_text(record: dict[str, Any]) -> str:
    query_hints = record.get("query_hints") or {}
    likely_entities = ", ".join(query_hints.get("likely_entities") or [])
    related_signals = ", ".join(record.get("related_signals") or [])
    symptom_keywords = ", ".join(record.get("symptom_keywords") or [])
    parts = [
        f"signal: {record.get('signal', '')}",
        f"title: {record.get('title', '')}",
        f"summary: {record.get('summary', '')}",
        f"service: {record.get('service', '')}",
        f"vendor: {record.get('vendor', '')}",
        f"domain: {record.get('domain', '')}",
        f"symptom keywords: {symptom_keywords}",
        f"related signals: {related_signals}",
        f"likely entities: {likely_entities}",
        f"default time bias: {query_hints.get('default_time_bias', '')}",
    ]
    return "\n".join(part for part in parts if part.split(": ", 1)[1].strip())


def build_chroma_metadata(record: dict[str, Any]) -> dict[str, Any]:
    query_hints = record.get("query_hints") or {}
    return {
        "record_id": str(record.get("id", "")),
        "signal": str(record.get("signal", "")),
        "service": record.get("service") or "",
        "vendor": record.get("vendor") or "",
        "domain": record.get("domain") or "",
        "rule_file": record.get("rule_file") or "",
        "title": record.get("title") or "",
        "default_time_bias": query_hints.get("default_time_bias") or "",
        "likely_entities": ",".join(query_hints.get("likely_entities") or []),
        "related_signals": ",".join(record.get("related_signals") or []),
    }


def write_vector_manifest(
    db_dir: Path,
    source_json: Path,
    embedding_model: str,
    records: list[dict[str, Any]],
) -> None:
    sample_record = records[0] if records else {}
    manifest = {
        "source_json": str(source_json),
        "embedding_model": embedding_model,
        "record_count": len(records),
        "service": sample_record.get("service"),
        "vendor": sample_record.get("vendor"),
        "domain": sample_record.get("domain"),
        "collection_name": "signals",
    }
    (db_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
