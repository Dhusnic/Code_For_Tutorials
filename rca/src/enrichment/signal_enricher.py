"""High-level orchestration for signal enrichment and indexing."""

from __future__ import annotations

import hashlib
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from src.config.settings import AppConfig, ServiceConfig
from src.ingestion.batch_reader import BatchReader
from src.rule_learning.auto_rule_learner import AutoRuleLearner
from src.rules.rule_engine import RuleEngine
from src.rules.rule_loader import RuleLoader
from src.state.checkpoint_store import CheckpointStoreBase
from src.utils.dicts import get_nested
from src.writer.async_bulk_writer import AsyncBulkWriter
from src.writer.bulk_updater import BulkActionFactory


class SignalEnrichmentService:
    """Coordinate reading, rule matching, and writing enriched logs."""

    def __init__(
        self,
        es_client: Elasticsearch,
        config: AppConfig,
        checkpoint_store: CheckpointStoreBase,
    ) -> None:
        self._es_client = es_client
        self._config = config
        self._checkpoint_store = checkpoint_store
        self._rule_loader = RuleLoader(config.rules_directory)
        self._rule_engine = RuleEngine()
        self._rule_learner = AutoRuleLearner(
            config=self._config.rule_learning,
            rules_directory=self._config.rules_directory,
            service_rule_files={svc.name: svc.rule_file for svc in self._config.pipeline.services},
        )
        self._action_factory = BulkActionFactory()
        self._dynamic_eps_by_key: dict[str, float] = {}
        self._logger = logging.getLogger(self.__class__.__name__)
        self._bulk_writer = AsyncBulkWriter(
            flush_fn=self._flush,
            worker_count=max(1, int(self._config.pipeline.bulk_worker_count)),
            queue_size=max(1, int(self._config.pipeline.bulk_queue_size)),
            logger=self._logger,
        )
        self._validate_runtime_config()

    def shutdown(self) -> None:
        """Drain async writer and release state backend resources."""
        self._bulk_writer.close()
        self._checkpoint_store.close()

    def run_cycle(self) -> int:
        """Run one full processing cycle across configured services and indices."""
        cycle_started = time.perf_counter()
        processed = 0
        taken = 0
        max_lag_seconds: float | None = None

        for service in self._config.pipeline.services:
            if not service.enabled:
                continue
            service_processed, service_taken, service_lag = self._process_service(service)
            processed += service_processed
            taken += service_taken
            if service_lag is not None:
                max_lag_seconds = (
                    service_lag
                    if max_lag_seconds is None
                    else max(max_lag_seconds, service_lag)
                )

        self._bulk_writer.drain()
        cycle_seconds = max(time.perf_counter() - cycle_started, 1e-6)
        self._emit_autoscaling_metrics(
            processed_actions=processed,
            taken_events=taken,
            max_lag_seconds=max_lag_seconds,
            cycle_seconds=cycle_seconds,
        )
        self._flush_rule_learning_candidates()
        return processed

    def _process_service(self, service: ServiceConfig) -> tuple[int, int, float | None]:
        try:
            rule_set = self._rule_loader.load(service.name, service.rule_file)
        except Exception:
            self._logger.exception(
                "Failed loading rule file for service",
                extra={"service": service.name, "rule_file": service.rule_file},
            )
            return 0, 0, None

        source_indices = service.source_indices or self._config.pipeline.source_indices
        if not source_indices:
            self._logger.warning("No source indices configured", extra={"service": service.name})
            return 0, 0, None

        owned_indices = [idx for idx in source_indices if self._owns_partition(service.name, idx)]
        if not owned_indices:
            self._logger.debug(
                "Worker has no assigned partitions for service",
                extra={
                    "service": service.name,
                    "worker_id": self._config.pipeline.worker_id,
                    "worker_count": self._config.pipeline.worker_count,
                },
            )
            return 0, 0, None

        processed = 0
        taken = 0
        max_lag: float | None = None

        for index_name in owned_indices:
            try:
                index_processed, index_taken, index_lag = self._process_index(
                    service,
                    rule_set,
                    index_name,
                )
                processed += index_processed
                taken += index_taken
                if index_lag is not None:
                    max_lag = index_lag if max_lag is None else max(max_lag, index_lag)
            except Exception:
                self._logger.exception(
                    "Failed processing service/index",
                    extra={"service": service.name, "index": index_name},
                )
        return processed, taken, max_lag

    def _process_index(
        self,
        service: ServiceConfig,
        rule_set: Any,
        index_name: str,
    ) -> tuple[int, int, float | None]:
        if not (
            self._config.pipeline.write_to_source_index
            or self._config.pipeline.write_to_target_index
        ):
            self._logger.warning(
                "Write targets are disabled for both source and target indices",
                extra={"service": service.name, "source_index": index_name},
            )
            return 0, 0, None

        checkpoint = self._checkpoint_store.get(service.name, index_name)
        start_time = service.start_time or self._config.pipeline.start_time
        effective_batch_size = self._resolve_batch_size(service, index_name)
        self._logger.info(
            "Starting service/index processing",
            extra={
                "service": service.name,
                "source_index": index_name,
                "start_time": start_time,
                "checkpoint_sort": checkpoint,
                "batch_size_used": effective_batch_size,
                "batch_size_mode": self._config.pipeline.batch_size_mode,
            },
        )

        reader = BatchReader(
            client=self._es_client,
            index=index_name,
            batch_size=effective_batch_size,
            timestamp_field=self._config.pipeline.timestamp_field,
            start_time=start_time,
            base_query=service.query,
        )

        actions: list[dict[str, Any]] = []
        processed = 0
        taken_events = 0
        matched_events = 0
        unmatched_events = 0
        latest_sort: list[Any] | None = checkpoint
        latest_event_at: datetime | None = None
        destination_indices_seen: set[str] = set()

        for hit in reader.iter_hits(checkpoint_sort=checkpoint):
            taken_events += 1
            source_doc = hit.get("_source", {})
            event_ts = self._extract_event_timestamp(source_doc)
            if event_ts and (latest_event_at is None or event_ts > latest_event_at):
                latest_event_at = event_ts

            signals = self._rule_engine.evaluate(
                source_doc,
                rule_set,
                max_signals=self._config.pipeline.signal_max_per_event,
                highest_only=self._config.pipeline.signal_select_highest_only,
            )
            selected_signal = signals[0] if signals else None
            matched_rule_ids = [selected_signal["rule_id"]] if selected_signal else []
            source_event_index = hit.get("_index", index_name)
            destination_indices = self._resolve_destination_indices(source_event_index)
            destination_indices_seen.update(destination_indices)
            latest_sort = hit.get("sort", latest_sort)

            if selected_signal:
                matched_events += 1
                self._rule_learner.observe(service.name, source_doc, selected_signal)
                for destination_index in destination_indices:
                    action = self._action_factory.build(
                        source_index=source_event_index,
                        target_index=destination_index,
                        source_id=hit["_id"],
                        source_doc=source_doc,
                        selected_signal=selected_signal,
                        use_source_id=destination_index == source_event_index,
                    )
                    actions.append(action)
                    processed += 1
                self._logger.debug(
                    "Signal added for event",
                    extra={
                        "service": service.name,
                        "source_index": source_event_index,
                        "source_id": hit["_id"],
                        "target_indices": destination_indices,
                        "log": {"level": selected_signal["level"]},
                        "matched_rule_ids": matched_rule_ids,
                        "signal": selected_signal["signal"],
                    },
                )
            elif self._config.logging.log_unmatched_events:
                unmatched_events += 1
                self._logger.debug(
                    "No signals matched for event",
                    extra={
                        "service": service.name,
                        "source_index": source_event_index,
                        "source_id": hit["_id"],
                        "target_indices": destination_indices,
                        "matched_rule_ids": [],
                        "signal_count": 0,
                    },
                )
            else:
                unmatched_events += 1

            if len(actions) >= effective_batch_size:
                self._enqueue_actions(actions)
                actions = []

        if actions:
            self._enqueue_actions(actions)

        if latest_sort:
            self._checkpoint_store.set(service.name, index_name, latest_sort)

        lag_seconds = self._compute_lag_seconds(latest_event_at)
        self._logger.info(
            "Processed service/index",
            extra={
                "service": service.name,
                "source_index": index_name,
                "write_to_source_index": self._config.pipeline.write_to_source_index,
                "write_to_target_index": self._config.pipeline.write_to_target_index,
                "target_index_suffix": self._config.pipeline.target_suffix,
                "target_indices_count": len(destination_indices_seen),
                "target_indices_sample": sorted(list(destination_indices_seen))[:5],
                "batch_size_used": effective_batch_size,
                "total_taken_from_index": taken_events,
                "matched_events": matched_events,
                "unmatched_events": unmatched_events,
                "total_processed": processed,
                "lag_seconds": lag_seconds,
            },
        )
        return processed, taken_events, lag_seconds

    def _flush_rule_learning_candidates(self) -> None:
        """Persist auto-learned rule candidates generated during this cycle."""
        try:
            written_by_service = self._rule_learner.flush()
        except Exception:
            self._logger.exception("Failed flushing auto-learned rule candidates")
            return

        if written_by_service:
            self._logger.info(
                "Auto-learned rules written",
                extra={"written_by_service": written_by_service},
            )

    def _validate_runtime_config(self) -> None:
        worker_count = int(self._config.pipeline.worker_count)
        worker_id = int(self._config.pipeline.worker_id)
        if worker_count < 1:
            raise ValueError("pipeline.worker_count must be >= 1")
        if worker_id < 0 or worker_id >= worker_count:
            raise ValueError("pipeline.worker_id must satisfy 0 <= worker_id < worker_count")

        if (
            self._config.pipeline.write_to_source_index
            and self._config.pipeline.write_to_target_index
        ):
            self._logger.warning(
                "Dual write path is enabled and increases write load",
                extra={
                    "write_to_source_index": True,
                    "write_to_target_index": True,
                },
            )

    def _owns_partition(self, service_name: str, index_name: str) -> bool:
        worker_count = max(1, int(self._config.pipeline.worker_count))
        worker_id = int(self._config.pipeline.worker_id)
        if worker_count == 1:
            return True
        partition = self._partition_for_key(f"{service_name}::{index_name}", worker_count)
        return partition == worker_id

    @staticmethod
    def _partition_for_key(key: str, worker_count: int) -> int:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return value % worker_count

    def _enqueue_actions(self, actions: list[dict[str, Any]]) -> None:
        """Submit actions to async writer queue with backpressure."""
        self._bulk_writer.submit(actions)

    def _resolve_batch_size(self, service: ServiceConfig, index_name: str) -> int:
        """Return effective batch size according to static/dynamic pipeline mode."""
        static_batch = max(1, int(self._config.pipeline.batch_size))
        mode = str(self._config.pipeline.batch_size_mode).strip().lower()
        if mode == "static":
            return static_batch
        if mode == "dynamic":
            return self._estimate_dynamic_batch_size(service, index_name, static_batch)

        self._logger.warning(
            "Unknown batch_size_mode; falling back to static batch size",
            extra={
                "batch_size_mode": self._config.pipeline.batch_size_mode,
                "fallback_batch_size": static_batch,
                "service": service.name,
                "source_index": index_name,
            },
        )
        return static_batch

    def _estimate_dynamic_batch_size(
        self,
        service: ServiceConfig,
        index_name: str,
        static_batch: int,
    ) -> int:
        """Estimate dynamic batch size from recent events/sec in Elasticsearch."""
        lookback_seconds = max(5, int(self._config.pipeline.dynamic_batch_lookback_seconds))
        min_batch = max(1, int(self._config.pipeline.dynamic_batch_min_size))
        max_batch = max(min_batch, int(self._config.pipeline.dynamic_batch_max_size))
        target_window = max(0.1, float(self._config.pipeline.dynamic_batch_target_window_seconds))
        alpha = float(self._config.pipeline.dynamic_batch_smoothing_alpha)
        alpha = min(1.0, max(0.0, alpha))

        try:
            response = self._es_client.count(
                index=index_name,
                body=self._build_recent_count_query(service, lookback_seconds),
            )
        except Exception:
            self._logger.warning(
                "Dynamic batch size count query failed; using static batch size",
                extra={
                    "service": service.name,
                    "source_index": index_name,
                    "fallback_batch_size": static_batch,
                    "lookback_seconds": lookback_seconds,
                },
                exc_info=True,
            )
            return static_batch

        count = int(response.get("count", 0))
        observed_eps = count / lookback_seconds
        cache_key = f"{service.name}::{index_name}"
        previous_eps = self._dynamic_eps_by_key.get(cache_key)
        effective_eps = (
            observed_eps
            if previous_eps is None
            else (alpha * observed_eps) + ((1.0 - alpha) * previous_eps)
        )
        self._dynamic_eps_by_key[cache_key] = effective_eps

        candidate = int(round(effective_eps * target_window))
        batch_size = max(min_batch, min(max_batch, candidate))

        self._logger.debug(
            "Dynamic batch size resolved",
            extra={
                "service": service.name,
                "source_index": index_name,
                "lookback_seconds": lookback_seconds,
                "event_count": count,
                "observed_eps": observed_eps,
                "effective_eps": effective_eps,
                "target_window_seconds": target_window,
                "resolved_batch_size": batch_size,
                "min_batch_size": min_batch,
                "max_batch_size": max_batch,
            },
        )
        return batch_size

    def _build_recent_count_query(
        self,
        service: ServiceConfig,
        lookback_seconds: int,
    ) -> dict[str, Any]:
        """Build query used for dynamic batch-size event rate estimation."""
        bool_filter: list[dict[str, Any]] = [
            {
                "range": {
                    self._config.pipeline.timestamp_field: {
                        "gte": f"now-{lookback_seconds}s",
                    }
                }
            }
        ]
        if service.query:
            bool_filter.append(service.query)
        return {"query": {"bool": {"filter": bool_filter}}}

    def _resolve_destination_indices(self, source_index: str) -> list[str]:
        destinations: list[str] = []

        if self._config.pipeline.write_to_source_index:
            destinations.append(source_index)

        if self._config.pipeline.write_to_target_index:
            target_index = f"{source_index}{self._config.pipeline.target_suffix}"
            if target_index not in destinations:
                destinations.append(target_index)

        return destinations

    def _emit_autoscaling_metrics(
        self,
        *,
        processed_actions: int,
        taken_events: int,
        max_lag_seconds: float | None,
        cycle_seconds: float,
    ) -> None:
        """Emit throughput/lag metrics and scale recommendation to logs."""
        if not self._config.pipeline.autoscaling_enabled:
            return

        worker_count = max(1, int(self._config.pipeline.worker_count))
        min_workers = max(1, int(self._config.pipeline.autoscaling_min_workers))
        max_workers = max(min_workers, int(self._config.pipeline.autoscaling_max_workers))
        target_eps_per_worker = max(
            1.0,
            float(self._config.pipeline.autoscaling_target_events_per_worker_sec),
        )
        lag_scale_up = max(0.0, float(self._config.pipeline.autoscaling_lag_scale_up_seconds))
        lag_scale_down = max(0.0, float(self._config.pipeline.autoscaling_lag_scale_down_seconds))

        worker_output_eps = processed_actions / cycle_seconds
        worker_input_eps = taken_events / cycle_seconds
        cluster_input_eps = worker_input_eps * worker_count

        desired_by_throughput = int(math.ceil(cluster_input_eps / target_eps_per_worker))
        desired_workers = min(max_workers, max(min_workers, desired_by_throughput))

        lag = max_lag_seconds if max_lag_seconds is not None else 0.0
        if lag > lag_scale_up and desired_workers <= worker_count:
            desired_workers = min(max_workers, worker_count + 1)

        if lag < lag_scale_down and desired_workers >= worker_count:
            candidate = max(min_workers, worker_count - 1)
            if candidate >= desired_by_throughput:
                desired_workers = candidate

        recommendation = "steady"
        if desired_workers > worker_count:
            recommendation = "scale_up"
        elif desired_workers < worker_count:
            recommendation = "scale_down"

        self._logger.info(
            "Autoscaling metrics",
            extra={
                "worker_id": self._config.pipeline.worker_id,
                "worker_count": worker_count,
                "cycle_seconds": cycle_seconds,
                "worker_input_events_per_sec": worker_input_eps,
                "worker_output_actions_per_sec": worker_output_eps,
                "estimated_cluster_input_events_per_sec": cluster_input_eps,
                "max_lag_seconds": max_lag_seconds,
                "desired_workers": desired_workers,
                "recommendation": recommendation,
            },
        )

    def _extract_event_timestamp(self, source_doc: dict[str, Any]) -> datetime | None:
        """Extract and parse event timestamp from source document."""
        raw = get_nested(source_doc, self._config.pipeline.timestamp_field)
        if raw is None:
            raw = source_doc.get(self._config.pipeline.timestamp_field)
        if raw is None:
            return None

        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)

        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    @staticmethod
    def _compute_lag_seconds(latest_event_at: datetime | None) -> float | None:
        if latest_event_at is None:
            return None
        lag = (datetime.now(timezone.utc) - latest_event_at).total_seconds()
        return max(0.0, lag)

    def _flush(self, actions: list[dict[str, Any]]) -> None:
        """Bulk write enriched documents with retry and dead-letter fallback."""
        pending_actions = actions
        pending_errors: dict[tuple[str, str], dict[str, Any]] = {}
        attempt = 1
        backoff = self._config.pipeline.retry_initial_backoff_seconds
        max_attempts = self._config.pipeline.retry_max_attempts

        while pending_actions and attempt <= max_attempts:
            success, errors = bulk(self._es_client, pending_actions, raise_on_error=False)
            if not errors:
                self._logger.debug(
                    "Bulk write completed",
                    extra={"success_count": success, "attempt": attempt},
                )
                return

            self._logger.warning(
                "Bulk write attempt returned errors",
                extra={
                    "attempt": attempt,
                    "success_count": success,
                    "error_count": len(errors),
                },
            )
            for error in errors[:3]:
                self._logger.warning(
                    "Bulk write item error sample",
                    extra={"attempt": attempt, "error": error},
                )
            pending_actions, pending_errors = self._extract_failed_actions(pending_actions, errors)
            if pending_actions and attempt < max_attempts:
                time.sleep(backoff)
                backoff *= self._config.pipeline.retry_backoff_multiplier
            attempt += 1

        if pending_actions:
            self._send_to_dead_letter(pending_actions, pending_errors)

    def _extract_failed_actions(
        self,
        sent_actions: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
        """Return action subset that failed in the previous bulk attempt."""
        action_map = {(action["_index"], action["_id"]): action for action in sent_actions}
        failed_actions: list[dict[str, Any]] = []
        failed_errors: dict[tuple[str, str], dict[str, Any]] = {}

        for item in errors:
            _, payload = next(iter(item.items()))
            action_id = payload.get("_id")
            action_index = payload.get("_index")
            if not action_id or not action_index:
                continue
            key = (action_index, action_id)
            if key in action_map:
                failed_actions.append(action_map[key])
                failed_errors[key] = {
                    "error": payload.get("error"),
                    "status": payload.get("status"),
                }

        return failed_actions, failed_errors

    def _send_to_dead_letter(
        self,
        failed_actions: list[dict[str, Any]],
        failed_errors: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        """Persist permanently failed actions into dead-letter indices."""
        dlq_actions: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        for action in failed_actions:
            source_index = action["doc"].get("source_index", "unknown")
            source_id = action["doc"].get("source_id", "unknown")
            target_index = f"{source_index}{self._config.pipeline.dead_letter_suffix}"
            dlq_id = f"{action['_index']}:{action['_id']}:{int(datetime.now(timezone.utc).timestamp())}"
            error_key = (action["_index"], action["_id"])
            dlq_doc = {
                "failed_at": now,
                "reason": "bulk_retry_exhausted",
                "target_index": action["_index"],
                "source_index": source_index,
                "source_id": source_id,
                "error": failed_errors.get(error_key, {}).get("error"),
                "status": failed_errors.get(error_key, {}).get("status"),
                "action": {
                    "op_type": action.get("_op_type"),
                    "id": action.get("_id"),
                    "doc": action.get("doc"),
                },
            }
            dlq_actions.append(
                {
                    "_op_type": "index",
                    "_index": target_index,
                    "_id": dlq_id,
                    "_source": dlq_doc,
                }
            )

        success, errors = bulk(self._es_client, dlq_actions, raise_on_error=False)
        if errors:
            self._logger.error(
                "Dead-letter write returned errors",
                extra={"success_count": success, "error_count": len(errors)},
            )
        else:
            self._logger.error(
                "Moved failed bulk actions to dead-letter index",
                extra={"count": success},
            )
