"""Read source logs from Elasticsearch in stable batches."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from elasticsearch import Elasticsearch


class BatchReader:
    """Iterate through index documents using search_after pagination."""

    def __init__(
        self,
        client: Elasticsearch,
        index: str,
        batch_size: int,
        timestamp_field: str,
        start_time: str,
        base_query: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._index = index
        self._batch_size = batch_size
        self._timestamp_field = timestamp_field
        self._start_time = start_time
        self._base_query = base_query
        self._logger = logging.getLogger(self.__class__.__name__)

    def iter_hits(self, checkpoint_sort: list[Any] | None = None) -> Iterator[dict[str, Any]]:
        """Yield documents from Elasticsearch in ascending time order."""
        search_after = checkpoint_sort
        pulled_total = 0
        batch_number = 0

        while True:
            query = self._build_query(search_after)
            response = self._client.search(index="*", body=query)
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                self._logger.info(
                    "Finished reading index batches",
                    extra={
                        "index": self._index,
                        "total_taken_from_index": pulled_total,
                        "batch_count": batch_number,
                    },
                )
                return

            batch_number += 1
            pulled_total += len(hits)
            self._logger.info(
                "Batch pulled from index",
                extra={
                    "index": self._index,
                    "batch_number": batch_number,
                    "batch_size_taken": len(hits),
                    "total_taken_from_index": pulled_total,
                },
            )

            for hit in hits:
                yield hit

            search_after = hits[-1].get("sort")

    def _build_query(self, search_after: list[Any] | None) -> dict[str, Any]:
        bool_filter: list[dict[str, Any]] = [
            {"range": {self._timestamp_field: {"gte": self._start_time}}}
        ]
        if self._base_query:
            bool_filter.append(self._base_query)

        body: dict[str, Any] = {
            "size": self._batch_size,
            "query": {"bool": {"filter": bool_filter}},
            "sort": [
                {self._timestamp_field: {"order": "asc"}},
            ],
        }
        if search_after:
            body["search_after"] = search_after

        return body
