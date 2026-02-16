"""High-level orchestration for signal enrichment and indexing."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from src.config.settings import AppConfig, ServiceConfig
from src.ingestion.batch_reader import BatchReader
from src.rules.rule_engine import RuleEngine
from src.rules.rule_loader import RuleLoader
from src.state.checkpoint_store import CheckpointStore
from src.writer.bulk_updater import BulkActionFactory


class SignalEnrichmentService:
    """Coordinate reading, rule matching, and writing enriched logs."""

    def __init__(
        self,
        es_client: Elasticsearch,
        config: AppConfig,
        checkpoint_store: CheckpointStore,
    ) -> None:
        self._es_client = es_client
        self._config = config
        self._checkpoint_store = checkpoint_store
        self._rule_loader = RuleLoader(config.rules_directory)
        self._rule_engine = RuleEngine()
        self._action_factory = BulkActionFactory()
        self._logger = logging.getLogger(self.__class__.__name__)

    def run_cycle(self) -> int:
        """Run one full processing cycle across configured services and indices."""
        processed = 0
        for service in self._config.pipeline.services:
            if not service.enabled:
                continue
            processed += self._process_service(service)
        return processed

    def _process_service(self, service: ServiceConfig) -> int:
        rule_set = self._rule_loader.load(service.name, service.rule_file)
        source_indices = service.source_indices or self._config.pipeline.source_indices
        if not source_indices:
            self._logger.warning("No source indices configured", extra={"service": service.name})
            return 0

        processed = 0
        for index_name in source_indices:
            try:
                processed += self._process_index(service, rule_set, index_name)
            except Exception:
                self._logger.exception(
                    "Failed processing service/index",
                    extra={"service": service.name, "index": index_name},
                )
        return processed

    def _process_index(self, service: ServiceConfig, rule_set: Any, index_name: str) -> int:
        checkpoint = self._checkpoint_store.get(service.name, index_name)
        start_time = service.start_time or self._config.pipeline.start_time
        self._logger.info(
            "Starting service/index processing",
            extra={
                "service": service.name,
                "source_index": index_name,
                "start_time": start_time,
                "checkpoint_sort": checkpoint,
            },
        )

        reader = BatchReader(
            client=self._es_client,
            index=index_name,
            batch_size=self._config.pipeline.batch_size,
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
        target_indices: set[str] = set()

        for hit in reader.iter_hits(checkpoint_sort=checkpoint):
            taken_events += 1
            source_doc = hit.get("_source", {})
            signals = self._rule_engine.evaluate(
                source_doc,
                rule_set,
                max_signals=self._config.pipeline.signal_max_per_event,
                highest_only=self._config.pipeline.signal_select_highest_only,
            )
            selected_signal = signals[0] if signals else None
            matched_rule_ids = [selected_signal["rule_id"]] if selected_signal else []
            source_event_index = hit.get("_index", index_name)
            target_index = f"{source_event_index}{self._config.pipeline.target_suffix}"
            target_indices.add(target_index)

            # Old behavior (kept for easy rollback): write every event including unmatched.
            # action = self._action_factory.build(
            #     source_index=source_event_index,
            #     target_index=target_index,
            #     source_id=hit["_id"],
            #     source_doc=source_doc,
            #     signals=signals,
            # )
            # actions.append(action)
            # processed += 1
            latest_sort = hit.get("sort", latest_sort)

            if selected_signal:
                matched_events += 1
                action = self._action_factory.build(
                    source_index=source_event_index,
                    target_index=target_index,
                    source_id=hit["_id"],
                    source_doc=source_doc,
                    selected_signal=selected_signal,
                )
                actions.append(action)
                processed += 1
                self._logger.info(
                    "Signal added for event",
                    extra={
                        "service": service.name,
                        "source_index": source_event_index,
                        "source_id": hit["_id"],
                        "target_index": target_index,
                        "log": {"level": selected_signal["level"]},
                        "matched_rule_ids": matched_rule_ids,
                        "signal": selected_signal["signal"],
                        # "signal_rule_id": selected_signal["rule_id"],
                    },
                )
            elif self._config.logging.log_unmatched_events:
                unmatched_events += 1
                self._logger.info(
                    "No signals matched for event",
                    extra={
                        "service": service.name,
                        "source_index": source_event_index,
                        "source_id": hit["_id"],
                        "target_index": target_index,
                        "matched_rule_ids": [],
                        "signal_count": 0,
                    },
                )

            else:
                unmatched_events += 1

            if len(actions) >= self._config.pipeline.batch_size:
                self._flush(actions)
                actions = []

        if actions:
            self._flush(actions)

        if latest_sort:
            self._checkpoint_store.set(service.name, index_name, latest_sort)

        self._logger.info(
            "Processed service/index",
            extra={
                "service": service.name,
                "source_index": index_name,
                "target_index_suffix": self._config.pipeline.target_suffix,
                "target_indices_count": len(target_indices),
                "target_indices_sample": sorted(list(target_indices))[:5],
                "total_taken_from_index": taken_events,
                "matched_events": matched_events,
                "unmatched_events": unmatched_events,
                "total_processed": processed,
            },
        )
        return processed

    def _flush(self, actions: list[dict[str, Any]]) -> None:
        """Bulk write enriched documents with retry and dead-letter fallback."""
        pending_actions = actions
        pending_errors: dict[str, dict[str, Any]] = {}
        attempt = 1
        backoff = self._config.pipeline.retry_initial_backoff_seconds
        max_attempts = self._config.pipeline.retry_max_attempts

        while pending_actions and attempt <= max_attempts:
            success, errors = bulk(self._es_client, pending_actions, raise_on_error=False)
            if not errors:
                self._logger.info(
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
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Return action subset that failed in the previous bulk attempt."""
        action_map = {action["_id"]: action for action in sent_actions}
        failed_actions: list[dict[str, Any]] = []
        failed_errors: dict[str, dict[str, Any]] = {}
        for item in errors:
            op, payload = next(iter(item.items()))
            _ = op
            action_id = payload.get("_id")
            if action_id and action_id in action_map:
                failed_actions.append(action_map[action_id])
                failed_errors[action_id] = {
                    "error": payload.get("error"),
                    "status": payload.get("status"),
                }
        return failed_actions, failed_errors

    def _send_to_dead_letter(
        self,
        failed_actions: list[dict[str, Any]],
        failed_errors: dict[str, dict[str, Any]],
    ) -> None:
        """Persist permanently failed actions into dead-letter indices."""
        dlq_actions: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        for action in failed_actions:
            source_index = action["doc"].get("source_index", "unknown")
            source_id = action["doc"].get("source_id", "unknown")
            target_index = f"{source_index}{self._config.pipeline.dead_letter_suffix}"
            dlq_id = f"{action['_id']}:{int(datetime.now(timezone.utc).timestamp())}"
            dlq_doc = {
                "failed_at": now,
                "reason": "bulk_retry_exhausted",
                "target_index": action["_index"],
                "source_index": source_index,
                "source_id": source_id,
                "error": failed_errors.get(action["_id"], {}).get("error"),
                "status": failed_errors.get(action["_id"], {}).get("status"),
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
