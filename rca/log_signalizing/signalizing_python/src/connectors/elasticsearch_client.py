"""Elasticsearch client factory and helpers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from elasticsearch import Elasticsearch

from src.config.settings import ElasticsearchConfig


class ElasticClientFactory:
    """Build configured Elasticsearch client instances."""

    def __init__(self, config: ElasticsearchConfig) -> None:
        self._config = config

    def create(self) -> Elasticsearch:
        """Create an Elasticsearch client from application config."""
        kwargs: dict[str, Any] = {
            "hosts": self._config.hosts,
            "verify_certs": self._config.verify_certs,
            "request_timeout": self._config.request_timeout_seconds,
        }
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        elif self._config.username and self._config.password:
            kwargs["basic_auth"] = (self._config.username, self._config.password)

        return Elasticsearch(**kwargs)

    def debug_dict(self) -> dict[str, Any]:
        """Return non-sensitive connection options for debug logs."""
        data = asdict(self._config)
        data.pop("password", None)
        data.pop("api_key", None)
        return data
