from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from elasticsearch import Elasticsearch
from openai import OpenAI
from pymongo import MongoClient

from .config import RuntimeConfig, load_runtime_config, require_openai_api_key
from .graph import InvestigatorAgent, build_graph
from .llm import (
    DisabledCriticGenerator,
    DisabledPlannerGenerator,
    DisabledScopeResolutionGenerator,
    OpenAICriticGenerator,
    OpenAIExplanationGenerator,
    OpenAIPlannerGenerator,
    OpenAIScopeResolutionGenerator,
)
from .observability import configure_logging, log_step
from .rag import CatalogRepository
from .tools.log_store import ElasticsearchLogStore
from .topology_source import MongoTopologySource, TopologySource


@dataclass
class InvestigatorRuntime:
    config: RuntimeConfig
    agent: InvestigatorAgent
    elasticsearch_client: Elasticsearch
    mongo_client: MongoClient
    openai_client: OpenAI
    topology_source: TopologySource


def build_runtime(
    *,
    config_path: Path,
    env_path: Path | None,
    catalog_root: Path,
    max_hops_override: int | None = None,
) -> InvestigatorRuntime:
    """Build the production RCA runtime from config, environment, and catalogs.

    This wires the external backends used by the investigator:
    Elasticsearch for logs, MongoDB for topology, and OpenAI for the final
    analyst-facing explanation.
    """
    runtime_config = load_runtime_config(config_path=config_path, env_path=env_path)
    logger = configure_logging(runtime_config.logging)
    log_step(
        logger,
        20,
        "Runtime initialization started",
        config_path=str(config_path),
        env_path=str(env_path) if env_path else "none",
        catalog_root=str(catalog_root),
    )

    elasticsearch_client = Elasticsearch(**_build_elasticsearch_client_kwargs(runtime_config))
    log_step(
        logger,
        20,
        "Elasticsearch client configured",
        hosts=list(runtime_config.elasticsearch.hosts),
        index=runtime_config.elasticsearch.index,
    )
    mongo_client = MongoClient(
        runtime_config.mongo.uri,
        serverSelectionTimeoutMS=runtime_config.mongo.request_timeout_ms,
    )
    log_step(
        logger,
        20,
        "MongoDB client configured",
        database=runtime_config.mongo.database,
        collection=runtime_config.mongo.collection,
    )
    openai_client = OpenAI(
        api_key=require_openai_api_key(runtime_config.openai),
        timeout=float(runtime_config.openai.timeout_seconds),
    )
    log_step(
        logger,
        20,
        "OpenAI client configured",
        model=runtime_config.openai.model,
        timeout_seconds=runtime_config.openai.timeout_seconds,
    )

    log_store = ElasticsearchLogStore(elasticsearch_client, runtime_config.elasticsearch)
    topology_source = MongoTopologySource(
        mongo_client[runtime_config.mongo.database],
        runtime_config.mongo,
    )
    explanation_generator = OpenAIExplanationGenerator(openai_client, runtime_config.openai)
    scope_resolution_generator = (
        OpenAIScopeResolutionGenerator(openai_client, runtime_config.openai)
        if runtime_config.openai.scope_resolution_enabled
        else DisabledScopeResolutionGenerator()
    )
    planner_generator = (
        OpenAIPlannerGenerator(openai_client, runtime_config.openai)
        if runtime_config.openai.planner_enabled and runtime_config.openai.planner_mode != "deterministic"
        else DisabledPlannerGenerator()
    )
    critic_generator = (
        OpenAICriticGenerator(openai_client, runtime_config.openai)
        if runtime_config.openai.critic_enabled
        else DisabledCriticGenerator()
    )
    vector_root = Path(runtime_config.rag.vector_db_root)
    if not vector_root.is_absolute():
        vector_root = config_path.parent / vector_root
    catalogs = CatalogRepository(
        catalog_root,
        vector_root=vector_root,
        vector_enabled=runtime_config.rag.vector_enabled,
        semantic_top_k=runtime_config.rag.semantic_top_k,
        global_scope_fanout=runtime_config.rag.global_scope_fanout,
    )
    max_hops = max(1, max_hops_override or runtime_config.app.max_hops)

    agent = build_graph(
        log_store=log_store,
        catalogs=catalogs,
        topology_source=topology_source,
        explanation_generator=explanation_generator,
        scope_resolution_generator=scope_resolution_generator,
        planner_generator=planner_generator,
        critic_generator=critic_generator,
        openai_config=runtime_config.openai,
        max_hops=max_hops,
        logger=logger,
        logging_config=runtime_config.logging,
    )
    log_step(logger, 20, "Runtime initialization completed", max_hops=max_hops)
    return InvestigatorRuntime(
        config=runtime_config,
        agent=agent,
        elasticsearch_client=elasticsearch_client,
        mongo_client=mongo_client,
        openai_client=openai_client,
        topology_source=topology_source,
    )


def _build_elasticsearch_client_kwargs(runtime_config: RuntimeConfig) -> dict[str, object]:
    elasticsearch = runtime_config.elasticsearch
    kwargs: dict[str, object] = {
        "hosts": list(elasticsearch.hosts),
        "request_timeout": elasticsearch.request_timeout_seconds,
        "verify_certs": elasticsearch.verify_certs,
    }
    if elasticsearch.ca_certs:
        kwargs["ca_certs"] = elasticsearch.ca_certs
    if elasticsearch.api_key:
        kwargs["api_key"] = elasticsearch.api_key
    elif elasticsearch.username:
        kwargs["basic_auth"] = (
            elasticsearch.username,
            elasticsearch.password or "",
        )
    return kwargs
