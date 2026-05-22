from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .observability import log_step
from .runner import (
    InvestigationRequest,
    default_catalog_root,
    default_config_file,
    default_env_file,
    load_runtime_for_request,
    run_investigation,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signal-first logs-only RCA investigator")
    parser.add_argument("--query", required=True, help="Natural-language incident question")
    parser.add_argument("--config", default=str(default_config_file()), help="Runtime YAML configuration file")
    parser.add_argument("--env-file", default=str(default_env_file()), help="Optional .env file containing the OpenAI API key")
    parser.add_argument("--catalog-root", default=str(default_catalog_root()), help="Root folder containing service and network signal catalogs")
    parser.add_argument("--organization-id", default=None, help="Organization or tenant identifier for the investigation scope")
    parser.add_argument("--start-time", default=None, help="Optional ISO8601 lower time bound")
    parser.add_argument("--end-time", default=None, help="Optional ISO8601 upper time bound")
    parser.add_argument("--service", default=None, help="Optional service filter")
    parser.add_argument("--host", default=None, help="Optional host filter")
    parser.add_argument("--ip", default=None, help="Optional IP filter")
    parser.add_argument("--max-hops", default=None, type=int, help="Optional override for the maximum topology hops")
    parser.add_argument("--thread-id", default=None, help="LangGraph thread identifier used for checkpointed chat memory")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    runtime = load_runtime_for_request(
        config_path=Path(args.config),
        env_path=Path(args.env_file) if args.env_file else None,
        catalog_root=Path(args.catalog_root),
        max_hops_override=args.max_hops,
    )
    organization_id = args.organization_id or runtime.config.app.default_organization_id
    thread_id = args.thread_id or runtime.config.app.default_thread_id
    logger = logging.getLogger(runtime.config.logging.logger_name)
    log_step(
        logger,
        logging.INFO,
        "CLI investigation request accepted",
        query=args.query,
        organization_id=organization_id,
        thread_id=thread_id,
    )

    report = run_investigation(
        runtime,
        InvestigationRequest(
            query=args.query,
            organization_id=organization_id,
            thread_id=thread_id,
            start_time=args.start_time,
            end_time=args.end_time,
            service=args.service,
            host=args.host,
            ip=args.ip,
        ),
    )
    log_step(
        logger,
        logging.INFO,
        "CLI investigation request completed",
        classification=report.get("classification"),
        confidence=report.get("confidence"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
