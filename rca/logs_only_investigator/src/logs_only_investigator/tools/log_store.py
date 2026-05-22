from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from ..config import ElasticsearchConfig
from ..models import LogRecord, SearchSummary, TimeWindow, parse_utc, to_utc_string
from ..observability import log_step, redact_for_logging


LOGGER = logging.getLogger("logs_only_investigator")


class LogStore(Protocol):
    def time_bounds(
        self,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
    ) -> tuple[str, str]:
        ...

    def known_hosts(self, organization_id: str | None = None) -> set[str]:
        ...

    def search(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 100,
    ) -> list[LogRecord]:
        ...

    def summarize(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 200,
    ) -> SearchSummary:
        ...

    def aggregate_discovery(
        self,
        *,
        candidate_signals: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        bucket_minutes: int = 5,
    ) -> dict[str, list[dict[str, str | int]]]:
        ...

    def raw_context(
        self,
        *,
        anchor_event_ids: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        ...

    def clear_debug_queries(self) -> None:
        ...

    def consume_debug_queries(self) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class LogSearchRequest:
    organization_id: str | None
    query_terms: tuple[str, ...]
    signals: tuple[str, ...]
    start_time: str | None
    end_time: str | None
    service: str | None
    host: str | None
    ip: str | None
    limit: int
    source_fields: tuple[str, ...]


class ElasticsearchLogStore:
    def __init__(self, client: Elasticsearch, config: ElasticsearchConfig) -> None:
        self._client = client
        self._config = config
        self._debug_local = threading.local()

    def time_bounds(
        self,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
    ) -> tuple[str, str]:
        body = {
            "size": 0,
            "track_total_hits": False,
            "query": _build_filter_query(
                self._config,
                organization_id=organization_id,
                service=service,
                host=host,
                ip=ip,
            ),
            "aggs": {
                "min_ts": {"min": {"field": self._config.timestamp_field}},
                "max_ts": {"max": {"field": self._config.timestamp_field}},
            },
        }
        self._append_debug_query(
            {
                "kind": "time_bounds",
                "index": config_index_list(self._config),
                "body": body,
            }
        )
        response = self._client.search(
            index=_parse_index_names(self._config.index),
            body=body,
            request_timeout=self._config.request_timeout_seconds,
            ignore_unavailable=True,
            allow_partial_search_results=True,
            expand_wildcards=["open"],
        )
        min_value = response["aggregations"]["min_ts"]["value_as_string"]
        max_value = response["aggregations"]["max_ts"]["value_as_string"]
        if not min_value or not max_value:
            raise ValueError("The configured Elasticsearch index did not return any timestamps for the requested organization scope.")
        return _normalize_timestamp(min_value), _normalize_timestamp(max_value)

    def clear_debug_queries(self) -> None:
        self._debug_local.queries = []

    def consume_debug_queries(self) -> list[dict[str, Any]]:
        queries = list(getattr(self._debug_local, "queries", []))
        self._debug_local.queries = []
        return queries

    def known_hosts(self, organization_id: str | None = None) -> set[str]:
        return set()

    def search(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 100,
    ) -> list[LogRecord]:
        request = LogSearchRequest(
            organization_id=organization_id,
            query_terms=tuple(query_terms or ()),
            signals=tuple(signals or ()),
            start_time=start_time,
            end_time=end_time,
            service=service,
            host=host,
            ip=ip,
            limit=limit,
            source_fields=self._config.source_fields,
        )
        return fetch_logs_efficiently(
            self._client,
            self._config,
            request,
            debug_queries=getattr(self._debug_local, "queries", None),
        )

    def summarize(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 200,
    ) -> SearchSummary:
        logs = self.search(
            query_terms=query_terms,
            signals=signals,
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=limit,
        )
        signal_counts = Counter(log.signal for log in logs if log.signal)
        entities = tuple(
            {
                "service": log.service,
                "host": log.host,
                "ip": log.ip,
                "node_id": log.node_id() or "",
            }
            for log in _unique_by_entity(logs)
        )
        return SearchSummary(
            events=tuple(logs),
            signal_counts=dict(signal_counts),
            first_seen=logs[0].timestamp if logs else None,
            last_seen=logs[-1].timestamp if logs else None,
            entities=entities,
        )

    def aggregate_discovery(
        self,
        *,
        candidate_signals: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        bucket_minutes: int = 5,
    ) -> dict[str, list[dict[str, str | int]]]:
        query = _build_filter_query(
            self._config,
            organization_id=organization_id,
            start_time=time_window.start,
            end_time=time_window.end,
            service=service,
            host=host,
            ip=ip,
            signals=candidate_signals,
        )
        body = {
            "size": 0,
            "track_total_hits": False,
            "query": query,
            "aggs": {
                "time_buckets": {
                    "date_histogram": {
                        "field": self._config.timestamp_field,
                        "fixed_interval": f"{bucket_minutes}m",
                        "min_doc_count": 1,
                    }
                },
                "top_services": {"terms": {"field": _aggregation_field(self._config.service_field), "size": 3}},
                "top_hosts": {"terms": {"field": _aggregation_field(self._config.host_field), "size": 3}},
                "top_ips": {"terms": {"field": _aggregation_field(self._config.ip_field), "size": 3}},
                "top_signals": {"terms": {"field": _aggregation_field(self._config.signal_field), "size": 3}},
            },
        }
        try:
            response = self._client.search(
                index=_parse_index_names(self._config.index),
                body=body,
                request_timeout=self._config.request_timeout_seconds,
                ignore_unavailable=True,
                allow_partial_search_results=True,
                expand_wildcards=["open"],
            )
        except Exception as exc:
            log_step(
                LOGGER,
                logging.WARNING,
                "Elasticsearch aggregate discovery fell back to sampled search",
                error=_format_es_exception(exc),
            )
            return self._aggregate_discovery_from_sampled_logs(
                candidate_signals=candidate_signals,
                time_window=time_window,
                organization_id=organization_id,
                service=service,
                host=host,
                ip=ip,
                bucket_minutes=bucket_minutes,
            )
        return {
            "top_time_buckets": [
                {
                    "start": _normalize_timestamp(bucket["key_as_string"]),
                    "end": _normalize_timestamp(to_utc_string(parse_utc(bucket["key_as_string"]) + timedelta(minutes=bucket_minutes))),
                    "count": int(bucket["doc_count"]),
                }
                for bucket in response["aggregations"]["time_buckets"]["buckets"][:3]
            ],
            "top_services": _format_terms_buckets(response["aggregations"]["top_services"]["buckets"], "service"),
            "top_hosts": _format_terms_buckets(response["aggregations"]["top_hosts"]["buckets"], "host"),
            "top_ips": _format_terms_buckets(response["aggregations"]["top_ips"]["buckets"], "ip"),
            "top_signals": _format_terms_buckets(response["aggregations"]["top_signals"]["buckets"], "signal"),
        }

    def _aggregate_discovery_from_sampled_logs(
        self,
        *,
        candidate_signals: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        bucket_minutes: int = 5,
    ) -> dict[str, list[dict[str, str | int]]]:
        logs = self.search(
            signals=candidate_signals,
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=min(1000, self._config.max_records_per_query),
        )
        bucket_counts: Counter[str] = Counter()
        service_counts = Counter(log.service for log in logs if log.service)
        host_counts = Counter(log.host for log in logs if log.host)
        ip_counts = Counter(log.ip for log in logs if log.ip)
        signal_counts = Counter(log.signal for log in logs if log.signal)

        for log in logs:
            bucket_start = _bucket_start(log.timestamp, bucket_minutes)
            bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
            bucket_key = f"{to_utc_string(bucket_start)}|{to_utc_string(bucket_end)}"
            bucket_counts[bucket_key] += 1

        return {
            "top_time_buckets": [
                {"start": start, "end": end, "count": count}
                for start, end, count in _top_bucket_payloads(bucket_counts)
            ],
            "top_services": _top_counts(service_counts, key_name="service"),
            "top_hosts": _top_counts(host_counts, key_name="host"),
            "top_ips": _top_counts(ip_counts, key_name="ip"),
            "top_signals": _top_counts(signal_counts, key_name="signal"),
        }

    def raw_context(
        self,
        *,
        anchor_event_ids: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        logs = self.search(
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=limit,
        )
        by_id = {log.doc_id: log for log in logs}
        anchor_logs = [by_id[event_id] for event_id in anchor_event_ids if event_id in by_id]
        ordered = anchor_logs + [log for log in logs if log.doc_id not in {item.doc_id for item in anchor_logs}]
        return [f"{log.timestamp} {log.service}@{log.host or log.ip}: {log.message}" for log in ordered[:limit]]

    def _append_debug_query(self, payload: dict[str, Any]) -> None:
        queries = getattr(self._debug_local, "queries", None)
        if queries is None:
            queries = []
            self._debug_local.queries = queries
        queries.append(payload)


class FakeLogStore:
    def __init__(self, logs: list[LogRecord]) -> None:
        self._logs = sorted(logs, key=lambda item: item.timestamp)

    @classmethod
    def from_json(cls, path: Path) -> "FakeLogStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        logs = [
            LogRecord(
                doc_id=str(item.get("doc_id", "")),
                timestamp=str(item.get("timestamp", "")),
                service=str(item.get("service", "")),
                host=str(item.get("host", "")),
                severity=str(item.get("severity", "")),
                signal=str(item.get("signal", "")),
                message=str(item.get("message", "")),
                ip=str(item.get("ip", "")),
                vendor=str(item.get("vendor", "")),
                domain=str(item.get("domain", "")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in payload
        ]
        return cls(logs)

    def time_bounds(
        self,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
    ) -> tuple[str, str]:
        if not self._logs:
            raise ValueError("The log store is empty.")
        service_filter = (service or "").strip().lower()
        host_filter = (host or "").strip().lower()
        ip_filter = (ip or "").strip().lower()
        filtered = [
            log
            for log in self._logs
            if (not service_filter or log.service.lower() == service_filter)
            and (not host_filter or log.host.lower() == host_filter)
            and (not ip_filter or log.ip.lower() == ip_filter)
        ]
        if not filtered:
            raise ValueError("The log store did not contain any timestamps for the requested scoped entity.")
        return filtered[0].timestamp, filtered[-1].timestamp

    def known_hosts(self, organization_id: str | None = None) -> set[str]:
        return {log.host.lower() for log in self._logs if log.host}

    def search(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 100,
    ) -> list[LogRecord]:
        normalized_terms = [term.lower() for term in (query_terms or []) if term]
        normalized_signals = {signal.lower() for signal in (signals or []) if signal}
        service_filter = (service or "").strip().lower()
        host_filter = (host or "").strip().lower()
        ip_filter = (ip or "").strip().lower()

        results: list[LogRecord] = []
        for log in self._logs:
            if start_time and log.timestamp < start_time:
                continue
            if end_time and log.timestamp > end_time:
                continue
            if service_filter and log.service.lower() != service_filter:
                continue
            if host_filter and log.host.lower() != host_filter:
                continue
            if ip_filter and log.ip.lower() != ip_filter:
                continue
            if normalized_signals and log.signal.lower() not in normalized_signals:
                continue
            if normalized_terms and not _matches_query(log, normalized_terms):
                continue
            results.append(log)
            if len(results) >= limit:
                break
        return results

    def summarize(
        self,
        *,
        query_terms: list[str] | None = None,
        signals: list[str] | None = None,
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 200,
    ) -> SearchSummary:
        logs = self.search(
            query_terms=query_terms,
            signals=signals,
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=limit,
        )
        signal_counts = Counter(log.signal for log in logs if log.signal)
        entities = tuple(
            {
                "service": log.service,
                "host": log.host,
                "ip": log.ip,
                "node_id": log.node_id() or "",
            }
            for log in _unique_by_entity(logs)
        )
        return SearchSummary(
            events=tuple(logs),
            signal_counts=dict(signal_counts),
            first_seen=logs[0].timestamp if logs else None,
            last_seen=logs[-1].timestamp if logs else None,
            entities=entities,
        )

    def aggregate_discovery(
        self,
        *,
        candidate_signals: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        bucket_minutes: int = 5,
    ) -> dict[str, list[dict[str, str | int]]]:
        logs = self.search(
            signals=candidate_signals,
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=1000,
        )
        bucket_counts: Counter[str] = Counter()
        service_counts = Counter(log.service for log in logs if log.service)
        host_counts = Counter(log.host for log in logs if log.host)
        ip_counts = Counter(log.ip for log in logs if log.ip)
        signal_counts = Counter(log.signal for log in logs if log.signal)

        for log in logs:
            bucket_start = _bucket_start(log.timestamp, bucket_minutes)
            bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
            bucket_key = f"{to_utc_string(bucket_start)}|{to_utc_string(bucket_end)}"
            bucket_counts[bucket_key] += 1

        return {
            "top_time_buckets": [
                {"start": start, "end": end, "count": count}
                for start, end, count in _top_bucket_payloads(bucket_counts)
            ],
            "top_services": _top_counts(service_counts, key_name="service"),
            "top_hosts": _top_counts(host_counts, key_name="host"),
            "top_ips": _top_counts(ip_counts, key_name="ip"),
            "top_signals": _top_counts(signal_counts, key_name="signal"),
        }

    def raw_context(
        self,
        *,
        anchor_event_ids: list[str],
        time_window: TimeWindow,
        organization_id: str | None = None,
        service: str | None = None,
        host: str | None = None,
        ip: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        anchor_set = set(anchor_event_ids)
        primary_logs = [log for log in self._logs if log.doc_id in anchor_set]
        context_logs = self.search(
            start_time=time_window.start,
            end_time=time_window.end,
            organization_id=organization_id,
            service=service,
            host=host,
            ip=ip,
            limit=limit,
        )
        ordered = primary_logs + [log for log in context_logs if log.doc_id not in anchor_set]
        return [f"{log.timestamp} {log.service}@{log.host or log.ip}: {log.message}" for log in ordered[:limit]]

    def clear_debug_queries(self) -> None:
        return None

    def consume_debug_queries(self) -> list[dict[str, Any]]:
        return []


def build_signal_search_query(
    config: ElasticsearchConfig,
    request: LogSearchRequest,
    *,
    page_size: int,
    search_after: list[object] | None = None,
    pit_id: str | None = None,
) -> dict[str, object]:
    """Build the Elasticsearch DSL for one paged RCA log search.

    The query combines hard filters such as organization, time range, service,
    host, IP, and signal families with an optional `simple_query_string`
    clause for free-text query terms. Pagination is stable and forward-only
    using timestamp plus `_shard_doc`, and a point-in-time ID can be attached
    when consistent paging across multiple requests is required.
    """
    query = _build_filter_query(
        config,
        organization_id=request.organization_id,
        start_time=request.start_time,
        end_time=request.end_time,
        service=request.service,
        host=request.host,
        ip=request.ip,
        signals=list(request.signals),
        query_terms=list(request.query_terms),
    )

    body: dict[str, object] = {
        "size": page_size,
        "track_total_hits": False,
        "query": query,
        "_source": list(request.source_fields),
        "sort": [{config.timestamp_field: {"order": "asc", "format": "strict_date_optional_time_nanos"}}, {"_shard_doc": "asc"}],
    }
    if pit_id:
        body["pit"] = {"id": pit_id, "keep_alive": config.point_in_time_keep_alive}
    if search_after:
        body["search_after"] = search_after
    return body


def fetch_logs_efficiently(
    client: Elasticsearch,
    config: ElasticsearchConfig,
    request: LogSearchRequest,
    *,
    debug_queries: list[dict[str, Any]] | None = None,
) -> list[LogRecord]:
    """Fetch RCA logs from Elasticsearch with bounded, consistent pagination.

    This function uses point-in-time search when enabled, paginates with
    `search_after`, respects a global max-record cap, and converts each hit
    into normalized `LogRecord` objects for the rest of the investigator.
    """
    remaining = min(request.limit, config.max_records_per_query)
    page_size = max(1, min(config.search_page_size, remaining))
    pit_id: str | None = None
    results: list[LogRecord] = []
    search_after: list[object] | None = None
    page_number = 0

    log_step(
        LOGGER,
        logging.INFO,
        "Elasticsearch fetch started",
        index=config.index,
        limit=request.limit,
        page_size=page_size,
        filters=redact_for_logging(
            {
                "organization_id": request.organization_id,
                "service": request.service,
                "host": request.host,
                "ip": request.ip,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "signals": list(request.signals),
                "query_terms": list(request.query_terms),
            }
        ),
    )

    try:
        if config.use_point_in_time:
            try:
                pit_response = client.open_point_in_time(
                    index=_parse_index_names(config.index),
                    keep_alive=config.point_in_time_keep_alive,
                    allow_partial_search_results=True,
                    ignore_unavailable=True,
                    expand_wildcards=["open"],
                    error_trace=True,
                )
                pit_id = pit_response["id"]
                log_step(LOGGER, logging.INFO, "Elasticsearch point-in-time opened", keep_alive=config.point_in_time_keep_alive)
            except Exception as exc:
                log_step(
                    LOGGER,
                    logging.WARNING,
                    "Elasticsearch point-in-time open failed, falling back to direct search",
                    error=_format_es_exception(exc),
                )

        while remaining > 0:
            page_number += 1
            body = build_signal_search_query(
                config,
                request,
                page_size=min(page_size, remaining),
                search_after=search_after,
                pit_id=pit_id,
            )
            log_step(
                LOGGER,
                logging.DEBUG,
                "Elasticsearch search page prepared",
                page_number=page_number,
                query=redact_for_logging(body, max_chars=1500),
            )
            try:
                search_kwargs: dict[str, object] = {
                    "index": None if pit_id else _parse_index_names(config.index),
                    "body": body,
                    "request_timeout": config.request_timeout_seconds,
                    "error_trace": True,
                }
                if not pit_id:
                    search_kwargs["ignore_unavailable"] = True
                    search_kwargs["allow_partial_search_results"] = True
                    search_kwargs["expand_wildcards"] = ["open"]
                if debug_queries is not None:
                    debug_queries.append(
                        {
                            "kind": "search",
                            "page_number": page_number,
                            "pit_enabled": bool(pit_id),
                            "index": config_index_list(config) if not pit_id else None,
                            "body": body,
                        }
                    )
                response = client.search(**search_kwargs)
            except Exception as exc:
                log_step(
                    LOGGER,
                    logging.ERROR,
                    "Elasticsearch search request failed",
                    page_number=page_number,
                    pit_enabled=bool(pit_id),
                    error=_format_es_exception(exc),
                    query=redact_for_logging(body, max_chars=1500),
                )
                raise
            hits = response["hits"]["hits"]
            if not hits:
                log_step(LOGGER, logging.INFO, "Elasticsearch search page returned no hits", page_number=page_number)
                break

            for hit in hits:
                results.append(_record_from_hit(config, hit))
            remaining -= len(hits)
            search_after = hits[-1].get("sort")
            log_step(
                LOGGER,
                logging.INFO,
                "Elasticsearch search page completed",
                page_number=page_number,
                page_hits=len(hits),
                accumulated_hits=len(results),
                remaining=remaining,
            )
            if len(hits) < min(page_size, remaining + len(hits)):
                break
    finally:
        if pit_id:
            try:
                client.close_point_in_time(body={"id": pit_id})
                log_step(LOGGER, logging.INFO, "Elasticsearch point-in-time closed")
            except NotFoundError:
                pass

    log_step(LOGGER, logging.INFO, "Elasticsearch fetch completed", result_count=len(results))
    return results


def _build_filter_query(
    config: ElasticsearchConfig,
    *,
    organization_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    service: str | None = None,
    host: str | None = None,
    ip: str | None = None,
    signals: list[str] | None = None,
    query_terms: list[str] | None = None,
) -> dict[str, object]:
    filters: list[dict[str, object]] = []
    must: list[dict[str, object]] = []

    if config.organization_field and organization_id:
        filters.append(_exact_term_filter(config.organization_field, organization_id))
    if start_time or end_time:
        range_filter: dict[str, object] = {}
        if start_time:
            range_filter["gte"] = start_time
        if end_time:
            range_filter["lte"] = end_time
        filters.append({"range": {config.timestamp_field: range_filter}})
    if service:
        filters.append(_exact_term_filter(config.service_field, service))
    if host:
        filters.append(_exact_term_filter(config.host_field, host))
    if ip:
        filters.append(_exact_term_filter(config.ip_field, ip))
    if signals:
        filters.append(_exact_terms_filter(config.signal_field, list(dict.fromkeys(signals))))

    normalized_terms = [term.strip() for term in (query_terms or []) if term and term.strip()]
    if normalized_terms:
        escaped = " ".join(_escape_simple_query_string(term) for term in normalized_terms)
        must.append(
            {
                "simple_query_string": {
                    "query": escaped,
                    "fields": list(config.searchable_fields),
                    "default_operator": "and",
                    "lenient": True,
                }
            }
        )

    body: dict[str, object] = {"bool": {}}
    if filters:
        body["bool"]["filter"] = filters
    if must:
        body["bool"]["must"] = must
    return body


def _record_from_hit(config: ElasticsearchConfig, hit: dict[str, object]) -> LogRecord:
    source = hit.get("_source", {})
    assert isinstance(source, dict)
    metadata = {
        key: value
        for key, value in source.items()
        if key
        not in {
            config.timestamp_field,
            config.service_field,
            config.host_field,
            config.ip_field,
            config.signal_field,
            config.message_field,
            config.severity_field,
            config.vendor_field,
            config.domain_field,
            "doc_id",
        }
    }
    return LogRecord(
        doc_id=str(source.get("doc_id") or hit.get("_id", "")),
        timestamp=_normalize_timestamp(_extract_text_value(source, config.timestamp_field)),
        service=_extract_text_value(source, config.service_field),
        host=_extract_text_value(source, config.host_field),
        severity=_extract_text_value(source, config.severity_field),
        signal=_extract_text_value(source, config.signal_field),
        message=_extract_text_value(source, config.message_field),
        ip=_extract_text_value(source, config.ip_field),
        vendor=_extract_text_value(source, config.vendor_field),
        domain=_extract_text_value(source, config.domain_field),
        metadata=metadata,
    )


def _format_terms_buckets(buckets: list[dict[str, object]], key_name: str) -> list[dict[str, str | int]]:
    return [{key_name: str(bucket["key"]), "count": int(bucket["doc_count"])} for bucket in buckets]


def _normalize_timestamp(value: str) -> str:
    if not value:
        return value
    return to_utc_string(parse_utc(value))


def _escape_simple_query_string(term: str) -> str:
    specials = r'+-=&|><!(){}[]^"~*?:\/'
    escaped = []
    for character in term:
        if character in specials:
            escaped.append(f"\\{character}")
        else:
            escaped.append(character)
    return "".join(escaped)


def _extract_text_value(source: dict[str, object], field_path: str) -> str:
    value = _extract_source_value(source, field_path)
    if value is None:
        return ""
    if isinstance(value, list):
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                return text
        return ""
    if isinstance(value, dict):
        return ""
    return str(value)


def _extract_source_value(source: dict[str, object], field_path: str) -> object | None:
    if not field_path:
        return None

    current: object | None = source
    for segment in field_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
        if current is None:
            return None
    return current


def _bucket_start(timestamp: str, bucket_minutes: int):
    point = parse_utc(timestamp)
    floored_minute = point.minute - (point.minute % bucket_minutes)
    return point.replace(minute=floored_minute, second=0, microsecond=0)


def _unique_by_entity(logs: list[LogRecord]) -> list[LogRecord]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[LogRecord] = []
    for log in logs:
        key = (log.service, log.host, log.ip)
        if key in seen:
            continue
        seen.add(key)
        unique.append(log)
    return unique


def _matches_query(log: LogRecord, query_terms: list[str]) -> bool:
    haystack = log.searchable_text()
    return any(term in haystack for term in query_terms)


def _top_bucket_payloads(counter: Counter[str], limit: int = 3) -> list[tuple[str, str, int]]:
    payloads: list[tuple[str, str, int]] = []
    for key, count in counter.most_common(limit):
        start, end = key.split("|", 1)
        payloads.append((start, end, count))
    return payloads


def _top_counts(counter: Counter[str], *, key_name: str, limit: int = 3) -> list[dict[str, str | int]]:
    return [{key_name: value, "count": count} for value, count in counter.most_common(limit)]


def _parse_index_names(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def config_index_list(config: ElasticsearchConfig) -> list[str]:
    return _parse_index_names(config.index)


def _exact_term_filter(field_name: str, value: str) -> dict[str, object]:
    candidates = _exact_field_candidates(field_name)
    if len(candidates) == 1:
        return {"term": {candidates[0]: value}}
    return {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"term": {candidate: value}} for candidate in candidates],
        }
    }


def _exact_terms_filter(field_name: str, values: list[str]) -> dict[str, object]:
    candidates = _exact_field_candidates(field_name)
    if len(candidates) == 1:
        return {"terms": {candidates[0]: values}}
    return {
        "bool": {
            "minimum_should_match": 1,
            "should": [{"terms": {candidate: values}} for candidate in candidates],
        }
    }


def _exact_field_candidates(field_name: str) -> list[str]:
    lowered = field_name.lower()
    if lowered.endswith(".keyword"):
        return [field_name]
    if "." in field_name:
        return [f"{field_name}.keyword", field_name]
    if lowered == "ip":
        return [field_name]
    return [f"{field_name}.keyword", field_name]


def _aggregation_field(field_name: str) -> str:
    lowered = field_name.lower()
    if lowered.endswith(".keyword"):
        return field_name
    if lowered == "ip":
        return field_name
    if "." in field_name:
        return f"{field_name}.keyword"
    return f"{field_name}.keyword"


def _format_es_exception(exc: Exception) -> str:
    pieces = [str(exc)]
    info = getattr(exc, "info", None)
    body = getattr(exc, "body", None)
    payload = info or body
    if payload:
        try:
            rendered = json.dumps(payload, default=str)
        except TypeError:
            rendered = repr(payload)
        pieces.append(rendered)
    return " | ".join(piece for piece in pieces if piece)
