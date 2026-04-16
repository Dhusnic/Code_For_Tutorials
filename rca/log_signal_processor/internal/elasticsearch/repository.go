// Package elasticsearch provides document fetching from Elasticsearch with field mapping and multi-page pagination.
package elasticsearch

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"log_signal_processor/internal/config"
)

// DocumentHit represents a minimal Elasticsearch document shape needed by the collector service.
//
// Fields:
//   - ID: Elasticsearch document _id (required for deduplication)
//   - Source: Nested JSON object (_source) containing mapped fields
//   - Sort: Pagination sort values from Elasticsearch (for search_after continuation)
//
// Usage:
//   - Created by Repository.SearchSignalDocuments
//   - Passed to service.MapDocument for normalization
type DocumentHit struct {
	ID     string
	Source map[string]any
	Sort   []any
}

// Repository reads signal-bearing documents from Elasticsearch with pagination.
//
// Responsibilities:
//   - Query Elasticsearch within configurable time window
//   - Fetch documents containing signal field
//   - Extract required fields and sort/pagination values
//   - Implement multi-page search using search_after pagination
//   - Support Point-in-Time for stable pagination
//   - Manage PIT lifecycle (open → use → close)
//
// Logging:
//   - Adds component and index tags to logger
//   - Logs PIT closure failures as WARN (will auto-expire)
//   - DEBUG logging delegated to underlying Client
//
// Thread Safety:
//   - Safe for concurrent use (stateless wrapper)
type Repository struct {
	client   *Client
	config   config.ElasticsearchConfig
	mappings config.FieldMappings
	logger   *slog.Logger
}

// Internal struct for decoding Elasticsearch response with PIT and pagination.
// Matches exact Elasticsearch response structure for JSON unmarshaling.
type searchResponse struct {
	PITID string `json:"pit_id"`
	Hits  struct {
		Hits []struct {
			ID     string         `json:"_id"`
			Source map[string]any `json:"_source"`
			Sort   []any          `json:"sort"`
		} `json:"hits"`
	} `json:"hits"`
}

// NewRepository creates an Elasticsearch repository with client, configuration, and logging.
//
// Parameters:
//   - client: Elasticsearch client (*Client)
//   - cfg: Elasticsearch configuration (addresses, index, pagination settings)
//   - mappings: Field mapping configuration (organization field, signal field, etc.)
//   - logger: slog.Logger for operational logging
//
// Returns:
//   - *Repository: Ready-to-use repository with component logging context added
//
// Example:
//
//	repo := NewRepository(
//	    esClient,
//	    config.Elasticsearch{Index: "logs-*", PageSize: 500},
//	    config.FieldMappings{...},
//	    logger,
//	)
func NewRepository(client *Client, cfg config.ElasticsearchConfig, mappings config.FieldMappings, logger *slog.Logger) *Repository {
	return &Repository{
		client:   client,
		config:   cfg,
		mappings: mappings,
		logger:   logger.With("component", "elasticsearch_repository", "index", cfg.Index),
	}
}

// SearchSignalDocuments fetches all documents matching signal criteria within a time window.
// Implements multi-page search using search_after pagination with optional Point-in-Time.
//
// Multi-Page Search Workflow:
//  1. If UsePointInTime enabled: Open PIT context (returns PIT ID)
//  2. Loop through pages:
//     - Build query with filters, sorting, optional search_after
//     - Execute search request
//     - Collect results (append to accumulated results)
//     - Check if more pages available (< PageSize results = last page)
//     - Extract sort values for next page's search_after
//     - Stop if MaxPages limit reached
//  3. Close PIT on completion (even on error via defer)
//
// Filters Applied:
//   - Timestamp range: windowStart ≤ @timestamp ≤ windowEnd
//   - Signal field must exist (non-empty, not null)
//   - Extra filters from config.ExtraFilters (if configured)
//
// Pagination Strategy:
//   - Uses search_after with sort order by timestamp, _shard_doc
//   - PageSize from config determines documents per request
//   - MaxPages from config limits total pages (0 = unlimited)
//   - StablePoint-in-Time prevents document shifts during pagination
//
// Parameters:
//   - ctx: Context with deadline (requestTimeout applied by Client)
//   - windowStart: Search window start (inclusive, UTC)
//   - windowEnd: Search window end (inclusive, UTC)
//
// Returns:
//   - []DocumentHit: All matching documents from all pages
//   - error: Elasticsearch connection, query, pagination, or response parse error
//
// Errors Returned:
//   - "open point in time: ..." - PIT initialization failed
//   - "execute elasticsearch search: ..." - Search request failed
//   - "elasticsearch page ended without sort values; ..." - Pagination data corrupted
//   - Any errors from Client.Search or Client.OpenPointInTime
//
// Logging Recommendations:
//   - DEBUG: Log windowStart, windowEnd, pageSize before calling
//   - DEBUG: Log page count and total documents after success
//   - DEBUG: Log first/last sort values for debugging pagination
//
// Example:
//
//	now := time.Now().UTC()
//	windowStart := now.Add(-10 * time.Minute)
//	hits, err := repo.SearchSignalDocuments(ctx, windowStart, now)
//	if err != nil {
//	    return fmt.Errorf("search documents: %w", err)
//	}
//	log.Info("fetched documents", "count", len(hits))
//
// Performance Consideration:
//   - PageSize = 500 typical: 500 docs/request good balance
//   - MaxPages = 0 (unlimited) dangerous with large result sets
//   - Use MaxPages to limit runaway searches (e.g., 100 pages = 50k docs)
func (r *Repository) SearchSignalDocuments(ctx context.Context, windowStart time.Time, windowEnd time.Time) ([]DocumentHit, error) {
	results := make([]DocumentHit, 0, r.config.PageSize)
	var searchAfter []any
	pitID := ""

	if r.config.UsePointInTime {
		var err error
		pitID, err = r.client.OpenPointInTime(ctx, r.config.Index, r.config.PITKeepAlive)
		if err != nil {
			return nil, err
		}
		defer r.closePointInTime(pitID)
	}

	for page := 0; ; page++ {
		if r.config.MaxPages > 0 && page >= r.config.MaxPages {
			return results, nil
		}

		body := r.buildQuery(windowStart, windowEnd, searchAfter, pitID)
		var response searchResponse
		searchIndex := r.config.Index
		if pitID != "" {
			searchIndex = ""
		}
		if err := r.client.Search(ctx, searchIndex, body, &response); err != nil {
			return nil, err
		}
		if response.PITID != "" {
			pitID = response.PITID
		}

		hits := response.Hits.Hits
		for _, hit := range hits {
			results = append(results, DocumentHit{
				ID:     hit.ID,
				Source: hit.Source,
				Sort:   hit.Sort,
			})
		}

		if len(hits) < r.config.PageSize {
			return results, nil
		}
		lastSort := hits[len(hits)-1].Sort
		if len(lastSort) == 0 {
			return nil, fmt.Errorf("elasticsearch page ended without sort values; search_after cannot continue")
		}
		searchAfter = append([]any(nil), lastSort...)
	}
}

// buildQuery constructs the Elasticsearch search query body with filters, sorting, and pagination.
//
// Query Structure:
//   - bool.filter: Time window range + signal field existence + extra filters
//   - sort: Timestamp ascending (primary), optional _shard_doc (with PIT)
//   - search_after: Pagination continuation from previous page
//   - pit: Point-in-Time context (if PIT enabled)
//   - size: PageSize from config
//
// Filter Components:
//  1. Timestamp range: field ≥ windowStart AND field ≤ windowEnd
//  2. Signal field exists: field != null
//  3. Extra filters from config (if configured)
//
// Sort Order:
//   - Primary: Timestamp ascending (enables reproducible ordering)
//   - Secondary (with PIT): _shard_doc ascending (tiebreaker for identical timestamps)
//
// Parameters:
//   - windowStart: Query window start (UTC, formatted as RFC3339Nano)
//   - windowEnd: Query window end (UTC, formatted as RFC3339Nano)
//   - searchAfter: Sort values from previous page (nil for first page)
//   - pitID: Point-in-Time ID (empty string if PIT disabled)
//
// Returns:
//   - map[string]any: Complete Elasticsearch query body
//
// Query Size:
//   - PageSize from config (typically 500)
//   - track_total_hits: false (performance: don't count all matches)
//   - _source includes: Only fields needed for mapping
//
// Timeouts:
//   - QueryTimeout applied if > 0 (Elasticsearch enforces timeout)
//   - RequestTimeout applied separately by Client wrapper
//
// Example Query Structure:
//
//	{
//	    "size": 500,
//	    "track_total_hits": false,
//	    "query": {
//	        "bool": {
//	            "filter": [
//	                {"range": {"@timestamp": {"gte": "2024-01-15T10:00:00Z", "lte": "2024-01-15T10:10:00Z"}}},
//	                {"exists": {"field": "signal"}},
//	            ]
//	        }
//	    },
//	    "sort": [{"@timestamp": {"order": "asc", ...}}, {"_shard_doc": {"order": "asc"}}],
//	    "pit": {"id": "xyz123", "keep_alive": "2m"},
//	    "search_after": [1705317600123, "xyz"],
//	    "_source": {"includes": ["event.organization", "signal", "log_level", "@timestamp"]},
//	    "timeout": "10s"
//	}
func (r *Repository) buildQuery(windowStart time.Time, windowEnd time.Time, searchAfter []any, pitID string) map[string]any {
	filter := []any{
		map[string]any{
			"range": map[string]any{
				r.mappings.TimestampField: map[string]any{
					"gte":    windowStart.UTC().Format(time.RFC3339Nano),
					"lte":    windowEnd.UTC().Format(time.RFC3339Nano),
					"format": "strict_date_optional_time",
				},
			},
		},
		map[string]any{
			"exists": map[string]any{
				"field": r.mappings.SignalField,
			},
		},
	}
	for _, extra := range r.config.ExtraFilters {
		filter = append(filter, extra)
	}

	sortFields := []any{
		map[string]any{
			r.mappings.TimestampField: map[string]any{
				"order":         "asc",
				"format":        "strict_date_optional_time_nanos",
				"numeric_type":  "date_nanos",
				"unmapped_type": "date",
			},
		},
	}
	if pitID != "" {
		sortFields = append(sortFields, map[string]any{
			"_shard_doc": map[string]any{
				"order": "asc",
			},
		})
	}

	body := map[string]any{
		"size":             r.config.PageSize,
		"track_total_hits": false,
		"query": map[string]any{
			"bool": map[string]any{
				"filter": filter,
			},
		},
		"sort": sortFields,
		"_source": map[string]any{
			"includes": requiredSourceFields(r.mappings),
		},
	}

	if r.config.QueryTimeout > 0 {
		body["timeout"] = formatDurationForElasticsearch(r.config.QueryTimeout)
	}
	if pitID != "" {
		body["pit"] = map[string]any{
			"id":         pitID,
			"keep_alive": formatDurationForElasticsearch(r.config.PITKeepAlive),
		}
	}
	if len(searchAfter) > 0 {
		body["search_after"] = searchAfter
	}
	return body
}

// closePointInTime closes a PIT context with logging and timeout handling.
// Never returns error (logs failures as WARN). Always called via defer in SearchSignalDocuments.
//
// Behavior:
//   - Creates short timeout context (10s) for cleanup operation
//   - Applies Client.ClosePointInTime with context
//   - Logs WARN if closure fails (e.g., PIT already expired)
//   - PIT will auto-expire even if not explicitly closed
//
// When Called:
//   - Always: SearchSignalDocuments defers this in finally path
//   - Even on error: Ensures clean resource release on failure paths
//
// Parameters:
//   - pitID: Point-in-Time ID from OpenPointInTime
//
// Logging:
//   - WARN: Logs if closure fails (error and context)
//   - Uses: "failed to close point in time; it will expire automatically"
//
// Example:
//
//	pitID, err := r.client.OpenPointInTime(ctx, r.config.Index, r.config.PITKeepAlive)
//	if err != nil { return nil, err }
//	defer r.closePointInTime(pitID)  // Always called on exit
func (r *Repository) closePointInTime(pitID string) {
	closeCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := r.client.ClosePointInTime(closeCtx, pitID); err != nil {
		r.logger.Warn("failed to close point in time; it will expire automatically", "error", err)
	}
}

// requiredSourceFields extracts the minimum set of Elasticsearch document fields needed for signal collection.
//
// Fields Extracted (from FieldMappings):
//   - OrganizationField: Organization identifier (required)
//   - SignalField: Signal type/indicator (required)
//   - LogLevelField: Log severity level (optional, may be empty)
//   - TimestampField: Event timestamp (required)
//   - DocIDField: Document ID source (if DocIDSource="field")
//
// Optimization:
//   - Only includes fields actually needed
//   - Empty field names excluded
//   - Duplicates removed (if mapping reuses same field)
//   - Reduces network bandwidth and Elasticsearch I/O
//
// Parameters:
//   - mappings: FieldMappings configuration
//
// Returns:
//   - []string: Sorted list of unique field names to request from Elasticsearch
//
// Example:
//
//	mappings: {
//	    OrganizationField: "event.organization",
//	    SignalField: "signal",
//	    LogLevelField: "log_level",
//	    TimestampField: "@timestamp",
//	    DocIDSource: "_id",           // Doesn't add to fields (using _id)
//	}
//	Result: ["event.organization", "signal", "log_level", "@timestamp"]
//
//	Note: If DocIDSource="field", DocIDField is also included
func requiredSourceFields(mappings config.FieldMappings) []string {
	fields := []string{
		mappings.OrganizationField,
		mappings.SignalField,
		mappings.LogLevelField,
		mappings.TimestampField,
	}
	if mappings.DocIDSource == "field" && mappings.DocIDField != "" {
		fields = append(fields, mappings.DocIDField)
	}

	seen := make(map[string]struct{}, len(fields))
	result := make([]string, 0, len(fields))
	for _, field := range fields {
		if field == "" {
			continue
		}
		if _, ok := seen[field]; ok {
			continue
		}
		seen[field] = struct{}{}
		result = append(result, field)
	}
	return result
}
