"""Checkpoint persistence backends for per-service and per-index pagination state."""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from src.config.settings import CheckpointConfig


class CheckpointStoreBase(ABC):
    """Abstract interface for checkpoint read/write backends."""

    @abstractmethod
    def get(self, service: str, index: str) -> list[Any] | None:
        """Load checkpoint sort array for a service/index pair."""

    @abstractmethod
    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        """Save checkpoint sort array for a service/index pair."""

    def close(self) -> None:
        """Release backend resources when needed."""

    @staticmethod
    def key(service: str, index: str) -> str:
        """Return backend key for service/index pair."""
        return f"{service}::{index}"


class CheckpointStore(CheckpointStoreBase):
    """File-backed checkpoint storage with thread-safe read/modify/write."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get(self, service: str, index: str) -> list[Any] | None:
        with self._lock:
            state = self._read()
            value = state.get(self.key(service, index))
            return value if isinstance(value, list) else None

    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        with self._lock:
            state = self._read()
            state[self.key(service, index)] = sort_values
            self._write(state)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ElasticsearchCheckpointStore(CheckpointStoreBase):
    """Checkpoint storage persisted in Elasticsearch index documents."""

    def __init__(self, client: Elasticsearch, index_name: str) -> None:
        self._client = client
        self._index_name = index_name
        self._logger = logging.getLogger(self.__class__.__name__)

    def get(self, service: str, index: str) -> list[Any] | None:
        doc_id = self.key(service, index)
        try:
            response = self._client.get(index=self._index_name, id=doc_id)
        except Exception as exc:
            status = _extract_status_code(exc)
            if status == 404:
                return None
            self._logger.exception(
                "Failed reading checkpoint from Elasticsearch",
                extra={"service": service, "source_index": index, "checkpoint_index": self._index_name},
            )
            raise

        source = response.get("_source", {})
        encoded = source.get("sort_values_json")
        if isinstance(encoded, str):
            try:
                payload = json.loads(encoded)
            except json.JSONDecodeError:
                self._logger.warning(
                    "Invalid sort_values_json payload in checkpoint document",
                    extra={
                        "service": service,
                        "source_index": index,
                        "checkpoint_index": self._index_name,
                    },
                )
                payload = None
            if isinstance(payload, list):
                return payload

        # Backward compatibility for previously persisted array field.
        values = source.get("sort_values")
        return values if isinstance(values, list) else None

    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        doc_id = self.key(service, index)
        document = {
            "service": service,
            "source_index": index,
            # Serialize as string to avoid ES dynamic mapping conflicts for mixed arrays.
            "sort_values_json": json.dumps(sort_values, separators=(",", ":")),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._client.index(index=self._index_name, id=doc_id, document=document, refresh=False)
        except Exception:
            self._logger.exception(
                "Failed writing checkpoint to Elasticsearch",
                extra={"service": service, "source_index": index, "checkpoint_index": self._index_name},
            )
            raise


class RedisCheckpointStore(CheckpointStoreBase):
    """Checkpoint storage persisted in Redis key/value records."""

    def __init__(self, redis_url: str, prefix: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis backend requires 'redis' package") from exc

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix
        self._logger = logging.getLogger(self.__class__.__name__)

    def get(self, service: str, index: str) -> list[Any] | None:
        key = f"{self._prefix}{self.key(service, index)}"
        try:
            raw = self._client.get(key)
        except Exception:
            self._logger.exception(
                "Failed reading checkpoint from Redis",
                extra={"service": service, "source_index": index, "redis_key": key},
            )
            raise
        if raw is None:
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, list) else None

    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        key = f"{self._prefix}{self.key(service, index)}"
        try:
            self._client.set(key, json.dumps(sort_values))
        except Exception:
            self._logger.exception(
                "Failed writing checkpoint to Redis",
                extra={"service": service, "source_index": index, "redis_key": key},
            )
            raise


class PostgresCheckpointStore(CheckpointStoreBase):
    """Checkpoint storage persisted in PostgreSQL table rows."""

    def __init__(self, dsn: str, table: str) -> None:
        try:
            import psycopg
            from psycopg import sql
        except ImportError as exc:
            raise RuntimeError("Postgres backend requires 'psycopg' package") from exc

        self._psycopg = psycopg
        self._sql = sql
        self._table = table
        self._logger = logging.getLogger(self.__class__.__name__)
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._ensure_table()

    def _ensure_table(self) -> None:
        query = self._sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {} (
                ckey TEXT PRIMARY KEY,
                sort_values JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ).format(self._sql.Identifier(self._table))
        with self._conn.cursor() as cur:
            cur.execute(query)

    def get(self, service: str, index: str) -> list[Any] | None:
        key = self.key(service, index)
        query = self._sql.SQL("SELECT sort_values FROM {} WHERE ckey = %s").format(
            self._sql.Identifier(self._table)
        )
        try:
            with self._conn.cursor() as cur:
                cur.execute(query, (key,))
                row = cur.fetchone()
        except Exception:
            self._logger.exception(
                "Failed reading checkpoint from Postgres",
                extra={"service": service, "source_index": index, "table": self._table},
            )
            raise
        if not row:
            return None
        value = row[0]
        return value if isinstance(value, list) else None

    def set(self, service: str, index: str, sort_values: list[Any]) -> None:
        key = self.key(service, index)
        query = self._sql.SQL(
            """
            INSERT INTO {} (ckey, sort_values, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (ckey)
            DO UPDATE SET sort_values = EXCLUDED.sort_values, updated_at = NOW()
            """
        ).format(self._sql.Identifier(self._table))
        try:
            with self._conn.cursor() as cur:
                cur.execute(query, (key, json.dumps(sort_values)))
        except Exception:
            self._logger.exception(
                "Failed writing checkpoint to Postgres",
                extra={"service": service, "source_index": index, "table": self._table},
            )
            raise

    def close(self) -> None:
        self._conn.close()


def create_checkpoint_store(
    config: CheckpointConfig,
    *,
    es_client: Elasticsearch | None = None,
) -> CheckpointStoreBase:
    """Build checkpoint backend from configuration."""
    provider = str(config.provider).strip().lower()

    if provider == "file":
        return CheckpointStore(config.path)

    if provider == "elasticsearch":
        if es_client is None:
            raise ValueError("Elasticsearch checkpoint backend requires Elasticsearch client")
        return ElasticsearchCheckpointStore(es_client, config.elasticsearch_index)

    if provider == "redis":
        if not config.redis_url:
            raise ValueError("Redis checkpoint backend requires checkpoints.redis_url")
        return RedisCheckpointStore(config.redis_url, config.redis_prefix)

    if provider == "postgres":
        if not config.postgres_dsn:
            raise ValueError("Postgres checkpoint backend requires checkpoints.postgres_dsn")
        return PostgresCheckpointStore(config.postgres_dsn, config.postgres_table)

    raise ValueError(f"Unsupported checkpoint provider: {config.provider}")


def _extract_status_code(exc: Exception) -> int | None:
    """Best-effort extraction of HTTP status code from Elasticsearch exceptions."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    meta = getattr(exc, "meta", None)
    meta_status = getattr(meta, "status", None)
    if isinstance(meta_status, int):
        return meta_status
    return None
