package ingest

import (
	"fmt"

	"rca/internal/rca/logging"
)

// SearchClient is the search subset BatchReader needs from Elasticsearch.
type SearchClient interface {
	Search(index string, body map[string]any) (map[string]any, error)
}

// BatchReader iterates one index using search_after pagination.
type BatchReader struct {
	client                    SearchClient
	index                     string
	batchSize                 int
	timestampField            string
	startTime                 string
	baseQuery                 map[string]any
	excludeAlreadySignaled    bool
	logger                    logging.Logger
}

// NewBatchReader constructs a stable index reader.
func NewBatchReader(
	client SearchClient,
	index string,
	batchSize int,
	timestampField string,
	startTime string,
	baseQuery map[string]any,
	excludeAlreadySignaled bool,
) *BatchReader {
	return &BatchReader{
		client:                 client,
		index:                  index,
		batchSize:              batchSize,
		timestampField:         timestampField,
		startTime:              startTime,
		baseQuery:              baseQuery,
		excludeAlreadySignaled: excludeAlreadySignaled,
		logger:                 logging.GetLogger("BatchReader"),
	}
}

// IterHits reads and returns all hits in ascending time order.
func (r *BatchReader) IterHits(checkpointSort []any) ([]map[string]any, error) {
	out := make([]map[string]any, 0)
	if err := r.IterateHits(checkpointSort, func(hit map[string]any) error {
		out = append(out, hit)
		return nil
	}); err != nil {
		return nil, err
	}
	return out, nil
}

// IterateHits streams hits in ascending time order to the provided callback.
func (r *BatchReader) IterateHits(checkpointSort []any, handle func(map[string]any) error) error {
	searchAfter := normalizeSearchAfter(checkpointSort)
	if len(checkpointSort) > 0 && searchAfter == nil {
		r.logger.Warning(
			"Ignoring checkpoint with incompatible sort shape",
			logging.F("index", r.index),
			logging.F("checkpoint_sort", checkpointSort),
		)
	}

	pulledTotal := 0
	batchNumber := 0

	for {
		query := r.buildQuery(searchAfter)
		response, err := r.client.Search(r.index, query)
		if err != nil {
			r.logger.Exception(
				"Search request failed",
				err,
				logging.F("index", r.index),
				logging.F("batch_number", batchNumber+1),
			)
			return err
		}

		hits, _ := anyValue(mapValue(response, "hits"), "hits").([]any)
		if len(hits) == 0 {
			r.logger.Info(
				"Finished reading index batches",
				logging.F("index", r.index),
				logging.F("total_taken_from_index", pulledTotal),
				logging.F("batch_count", batchNumber),
			)
			return nil
		}

		batchNumber++
		pulledTotal += len(hits)
		r.logger.Debug(
			"Batch pulled from index",
			logging.F("index", r.index),
			logging.F("batch_number", batchNumber),
			logging.F("batch_size_taken", len(hits)),
			logging.F("total_taken_from_index", pulledTotal),
		)

		for _, hitRaw := range hits {
			hit, ok := hitRaw.(map[string]any)
			if ok {
				if err := handle(hit); err != nil {
					return err
				}
			}
		}

		lastHit, _ := hits[len(hits)-1].(map[string]any)
		searchAfter = normalizeSearchAfter(sliceValue(lastHit, "sort"))
		if searchAfter == nil {
			return fmt.Errorf("Hit missing compatible sort values for pagination in index=%s", r.index)
		}
	}
}

func (r *BatchReader) buildQuery(searchAfter []any) map[string]any {
	boolFilter := []any{
		map[string]any{
			"range": map[string]any{
				r.timestampField: map[string]any{
					"gte": r.startTime,
				},
			},
		},
	}
	if r.baseQuery != nil {
		boolFilter = append(boolFilter, r.baseQuery)
	}

	mustNot := make([]any, 0)
	if r.excludeAlreadySignaled {
		mustNot = append(mustNot,
			map[string]any{"term": map[string]any{"signal_present": true}},
			map[string]any{"term": map[string]any{"signal_present": "true"}},
		)
	}

	body := map[string]any{
		"size":             r.batchSize,
		"track_total_hits": false,
		"query": map[string]any{
			"bool": map[string]any{
				"filter":   boolFilter,
				"must_not": mustNot,
			},
		},
		"sort": []any{
			map[string]any{r.timestampField: map[string]any{"order": "asc"}},
			map[string]any{"_shard_doc": map[string]any{"order": "asc"}},
		},
	}
	if searchAfter != nil {
		body["search_after"] = searchAfter
	}
	return body
}

func normalizeSearchAfter(value any) []any {
	items, ok := value.([]any)
	if !ok || len(items) != 2 {
		return nil
	}
	return items
}

func mapValue(value any, key string) map[string]any {
	data, ok := value.(map[string]any)
	if !ok {
		return map[string]any{}
	}
	child, ok := data[key].(map[string]any)
	if !ok {
		return map[string]any{}
	}
	return child
}

func anyValue(value map[string]any, key string) any {
	if value == nil {
		return nil
	}
	return value[key]
}

func sliceValue(value map[string]any, key string) []any {
	items, _ := value[key].([]any)
	return items
}
