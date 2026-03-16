"""Entry point for the RCA signal enrichment service."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from src.config.settings import load_app_config
from src.connectors.elasticsearch_client import ElasticClientFactory
from src.enrichment.signal_enricher import SignalEnrichmentService
from src.state.checkpoint_store import create_checkpoint_store
from src.utils.logging import configure_logging


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="RCA enrichment pipeline")
    default_config = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yml"))
    parser.add_argument(
        "--config",
        default=default_config,
        help="Path to configuration YAML file.",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Process one cycle and exit.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the enrichment loop."""
    args = parse_args()

    config = load_app_config(args.config)
    configure_logging(config.logging)
    logger = logging.getLogger(__name__)

    es_client = ElasticClientFactory(config.elasticsearch).create()
    checkpoint_store = create_checkpoint_store(config.checkpoints, es_client=es_client)
    service = SignalEnrichmentService(
        es_client=es_client,
        config=config,
        checkpoint_store=checkpoint_store,
    )

    try:
        while True:
            processed = service.run_cycle()
            logger.info("Processing cycle completed", extra={"processed": processed})
            if args.run_once:
                break
            time.sleep(config.pipeline.poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        return 0
    except Exception:
        logger.exception("Fatal error in enrichment loop")
        return 1
    finally:
        try:
            service.shutdown()
        except Exception:
            logger.exception("Failed during service shutdown")

    return 0


if __name__ == "__main__":
    sys.exit(main())
