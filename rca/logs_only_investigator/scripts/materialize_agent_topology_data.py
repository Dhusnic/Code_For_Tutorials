from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from logs_only_investigator.config import load_runtime_config  # noqa: E402
from logs_only_investigator.topology_converter import build_agent_topology_documents  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize simplified agent topology documents from RCA topology_data.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yml"), help="Runtime YAML configuration file")
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"), help="Optional env file path")
    parser.add_argument("--source-collection", default="topology_data", help="Source MongoDB topology collection")
    parser.add_argument("--target-collection", default="agent_topology_data", help="Target MongoDB collection")
    parser.add_argument("--organization-id", default=None, help="Optional single organization to rebuild")
    parser.add_argument("--drop-target", action="store_true", help="Drop the target collection before writing")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runtime_config = load_runtime_config(Path(args.config), Path(args.env_file) if args.env_file else None)

    client = MongoClient(
        runtime_config.mongo.uri,
        serverSelectionTimeoutMS=runtime_config.mongo.request_timeout_ms,
    )
    database = client[runtime_config.mongo.database]
    source_collection = database[args.source_collection]
    target_collection = database[args.target_collection]

    query = {}
    if args.organization_id:
        query[runtime_config.mongo.organization_field] = args.organization_id

    source_documents = list(source_collection.find(query))
    transformed = build_agent_topology_documents(source_documents)

    if args.drop_target:
        target_collection.drop()

    upserted = 0
    for document in transformed:
        target_collection.replace_one(
            {"_id": document["_id"]},
            document,
            upsert=True,
        )
        upserted += 1

    print(
        f"Materialized {upserted} versioned topology documents into "
        f"{runtime_config.mongo.database}.{args.target_collection}"
    )


if __name__ == "__main__":
    main()
