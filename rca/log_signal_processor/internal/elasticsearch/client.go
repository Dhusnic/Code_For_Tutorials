// Package elasticsearch provides typed client wrapper for Elasticsearch v8 operations.
// Handles search requests, Point-in-Time pagination, timeout management, and error wrapping.
//
// Key Responsibilities:
//   - Wrap elasticsearch-go/v8 client for clean API boundaries
//   - Manage request contexts with configurable timeouts
//   - Support Point-in-Time (PIT) for stable pagination
//   - Format durations in Elasticsearch-compatible syntax
//   - Decode JSON responses into Go structs
//
// Logging Integration:
//   - Client is stateless wrapper (logging delegated to caller)
//   - ERROR errors include response status and body content
//   - Recommend DEBUG-level logging at call sites for search operations
//   - All timeouts and context management observable via calling code
//
// Thread Safety:
//   - Safe for concurrent use (underlying *esv8.Client is thread-safe)
package elasticsearch

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	esv8 "github.com/elastic/go-elasticsearch/v8"
	"github.com/elastic/go-elasticsearch/v8/esapi"

	"log_signal_processor/internal/config"
)

// Client wraps the official Elasticsearch Go client (esv8.Client) with timeout management.
//
// Responsibilities:
//   - Encapsulate esv8.Client for cleaner dependency injection
//   - Manage per-request context timeouts
//   - Decode JSON responses into provided Go types
//   - Enable Point-in-Time pagination for stable slicing
//
// Timeout Behavior:
//   - requestTimeout from config applied to each Elasticsearch request
//   - Respects parent context deadline if closer than requestTimeout
//   - Defaults to unlimited timeout if requestTimeout ≤ 0
//
// Thread Safety:
//   - Safe for concurrent use (delegated to underlying esv8.Client)
type Client struct {
	raw            *esv8.Client
	requestTimeout time.Duration
}

// NewClient builds an Elasticsearch client from configuration.
//
// Configuration Usage:
//   - Addresses: Required list of Elasticsearch node URLs (e.g., ["https://localhost:9200"])
//   - Username/Password: Basic auth (optional, omit if using APIKey)
//   - APIKey: API key auth (optional, preferred over password)
//   - RequestTimeout: Per-request timeout for all operations
//
// Parameters:
//   - cfg: ElasticsearchConfig with connection and timeout settings
//
// Returns:
//   - *Client: Ready-to-use client with configured timeout
//   - error: Connection setup error or invalid configuration
//
// Errors:
//   - esv8 client initialization errors (invalid URLs, connection issues)
//
// Example:
//
//	cfg := config.ElasticsearchConfig{
//	    Addresses: []string{"https://es:9200"},
//	    Username: "elastic",
//	    Password: os.Getenv("ES_PASSWORD"),
//	    RequestTimeout: 15 * time.Second,
//	}
//	client, err := NewClient(cfg)
//	if err != nil {
//	    log.Fatal(err)
//	}
func NewClient(cfg config.ElasticsearchConfig) (*Client, error) {
	raw, err := esv8.NewClient(esv8.Config{
		Addresses: cfg.Addresses,
		Username:  cfg.Username,
		Password:  cfg.Password,
		APIKey:    cfg.APIKey,
	})
	if err != nil {
		return nil, fmt.Errorf("create elasticsearch client: %w", err)
	}
	return &Client{
		raw:            raw,
		requestTimeout: cfg.RequestTimeout,
	}, nil
}

// Search executes a search request and decodes the JSON response into a provided destination struct.
//
// Search Process:
//  1. Create request context with configured timeout (or parent deadline, if sooner)
//  2. Marshal search body to JSON
//  3. Execute search with index and body
//  4. Check HTTP status for errors
//  5. Decode JSON response body into destination
//
// Parameters:
//   - ctx: Parent context (timeout/cancellation propagated with requestTimeout applied)
//   - index: Index pattern (e.g., "logs-*", "events") - empty index allowed
//   - body: Search query body as map[string]any (e.g., {"query": {...}, "size": 100})
//   - destination: Pointer to struct for JSON response (typically SearchResponse)
//
// Returns:
//   - error: Connection, timeout, HTTP error, marshal, or decode error
//
// Errors Returned:
//   - "execute elasticsearch search: ..." - Network or client error
//   - "elasticsearch search failed with status NNN: ..." - HTTP error with response body
//   - "decode elasticsearch response: ..." - JSON parsing error
//   - "marshal elasticsearch search body: ..." - Request body serialization error
//
// Behavior:
//   - Automatically adds index and context to request options
//   - Reads and consumes response body (caller doesn't need to close)
//   - Wraps detailed error messages with operation context
//
// Logging Recommendations:
//   - DEBUG: Log index, query size, timeout before calling
//   - DEBUG: Log response size and hit count after success
//   - WARN: Log when non-signal documents encountered
//   - ERROR: Search failures already context-wrapped here
//
// Example:
//
//	searchBody := map[string]any{
//	    "query": map[string]any{
//	        "bool": map[string]any{
//	            "must": []map[string]any{
//	                {"match": map[string]any{"signal": map[string]any{}}},
//	            },
//	        },
//	    },
//	    "size": 500,
//	}
//	var resp elasticsearch.SearchResponse
//	if err := client.Search(ctx, "logs-app-*", searchBody, &resp); err != nil {
//	    return fmt.Errorf("search failed: %w", err)
//	}
func (c *Client) Search(ctx context.Context, index string, body map[string]any, destination any) error {
	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal elasticsearch search body: %w", err)
	}

	options := []func(*esapi.SearchRequest){
		c.raw.Search.WithContext(requestCtx),
		c.raw.Search.WithBody(bytes.NewReader(payload)),
	}
	if strings.TrimSpace(index) != "" {
		options = append(options, c.raw.Search.WithIndex(index))
	}

	response, err := c.raw.Search(options...)
	if err != nil {
		return fmt.Errorf("execute elasticsearch search: %w", err)
	}
	defer response.Body.Close()

	if response.IsError() {
		content, _ := io.ReadAll(response.Body)
		return fmt.Errorf("elasticsearch search failed with status %s: %s", response.Status(), string(content))
	}
	if err := json.NewDecoder(response.Body).Decode(destination); err != nil {
		return fmt.Errorf("decode elasticsearch response: %w", err)
	}
	return nil
}

// OpenPointInTime opens a Point-in-Time context for stable pagination across multiple search requests.
//
// Point-in-Time (PIT) Usage:
//   - A "snapshot" of the index at a specific point in time
//   - Enables stable pagination without relying on sort order
//   - Prevents document shifts during pagination (insertions/deletions between requests)
//   - Must be closed manually to free resources
//
// Workflow:
//  1. Call OpenPointInTime to get PIT ID
//  2. Execute search requests with PIT ID and search_after token
//  3. Call ClosePointInTime to release resources
//
// Parameters:
//   - ctx: Parent context (requestTimeout applied)
//   - index: Index pattern (e.g., "logs-*", "events")
//   - keepAlive: Time to keep PIT alive between requests (e.g., 2m)
//   - Typical value: request timeout + buffer (e.g., 15s request + 15s buffer = 30s)
//   - Too short: Requests fail with "PIT expired" errors
//   - Too long: Wastes server resources
//
// Returns:
//   - string: PIT ID for use in subsequent search requests
//   - error: Elasticsearch connection, timeout, or HTTP error
//
// Errors Returned:
//   - "open point in time: ..." - Network or client error
//   - "open point in time failed with status NNN: ..." - HTTP error
//   - "decode point in time response: ..." - Response parsing error
//   - "open point in time returned an empty id" - Elasticsearch server error
//
// Logging Recommendations:
//   - DEBUG: Log PIT ID when opened (for correlation)
//   - DEBUG: Log keepAlive duration
//   - Errors already wrapped with context here
//
// Example:
//
//	pitID, err := client.OpenPointInTime(ctx, "logs-*", 2*time.Minute)
//	if err != nil {
//	    return fmt.Errorf("open PIT: %w", err)
//	}
//	defer client.ClosePointInTime(context.Background(), pitID)  // Close even on error
func (c *Client) OpenPointInTime(ctx context.Context, index string, keepAlive time.Duration) (string, error) {
	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	response, err := c.raw.OpenPointInTime(
		[]string{index},
		formatDurationForElasticsearch(keepAlive),
		c.raw.OpenPointInTime.WithContext(requestCtx),
	)
	if err != nil {
		return "", fmt.Errorf("open point in time: %w", err)
	}
	defer response.Body.Close()

	if response.IsError() {
		content, _ := io.ReadAll(response.Body)
		return "", fmt.Errorf("open point in time failed with status %s: %s", response.Status(), string(content))
	}

	var payload struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return "", fmt.Errorf("decode point in time response: %w", err)
	}
	if strings.TrimSpace(payload.ID) == "" {
		return "", fmt.Errorf("open point in time returned an empty id")
	}
	return payload.ID, nil
}

// ClosePointInTime closes a previously opened Point-in-Time context.
// Frees server-side resources. Safe to call multiple times (idempotent behavior expected).
//
// When to Call:
//   - After search pagination completes successfully
//   - In defer() to ensure cleanup on error paths
//   - Even if search requests returned partial results
//
// Parameters:
//   - ctx: Context for closure operation (typically short deadline or background context)
//   - pitID: PIT ID returned by OpenPointInTime
//
// Returns:
//   - error: Connection, HTTP, timeout, or response parsing error
//
// Errors Returned:
//   - "close point in time: ..." - Network or client error
//   - "close point in time failed with status NNN: ..." - HTTP error
//   - "marshal point in time close body: ..." - JSON error (unlikely)
//
// Behavior:
//   - Idempotent: Safe to call multiple times with same PIT ID
//   - Returns error if PIT already expired
//   - Response body consumed automatically
//
// Logging Recommendations:
//   - WARN: Log errors (PIT may have expired naturally)
//   - DEBUG: Log PIT closure (optional, for troubleshooting)
//
// Best Practice:
//
//	pitID, err := client.OpenPointInTime(ctx, "logs-*", 2*time.Minute)
//	if err != nil { return err }
//	defer client.ClosePointInTime(context.Background(), pitID)  // Use background ctx
func (c *Client) ClosePointInTime(ctx context.Context, pitID string) error {
	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	body, err := json.Marshal(map[string]string{"id": pitID})
	if err != nil {
		return fmt.Errorf("marshal point in time close body: %w", err)
	}

	response, err := c.raw.ClosePointInTime(
		c.raw.ClosePointInTime.WithContext(requestCtx),
		c.raw.ClosePointInTime.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return fmt.Errorf("close point in time: %w", err)
	}
	defer response.Body.Close()

	if response.IsError() {
		content, _ := io.ReadAll(response.Body)
		return fmt.Errorf("close point in time failed with status %s: %s", response.Status(), string(content))
	}
	return nil
}

// requestContext creates a context for Elasticsearch operations with appropriate timeout.
//
// Timeout Strategy:
//   - Respects parent context deadline if it's earlier than requestTimeout
//   - Uses requestTimeout as fallback if parent has no deadline
//   - Returns unlimited context if requestTimeout ≤ 0 (no timeout enforcement)
//
// Rationale:
//   - Caller's deadline (e.g., from scheduler) takes precedence
//   - Prevents timeout-within-timeout nested deadlines
//   - Allows flexible configuration per-operation
//
// Parameters:
//   - parent: Parent context (typically from scheduler or caller)
//
// Returns:
//   - context.Context: New context with appropriate timeout
//   - context.CancelFunc: Cancel function (caller should defer call)
//
// Example:
//
//	requestCtx, cancel := c.requestContext(parentCtx)
//	defer cancel()
//	response, err := c.raw.Search(..., c.raw.Search.WithContext(requestCtx))
func (c *Client) requestContext(parent context.Context) (context.Context, context.CancelFunc) {
	if c.requestTimeout <= 0 {
		return context.WithCancel(parent)
	}
	if deadline, ok := parent.Deadline(); ok && time.Until(deadline) <= c.requestTimeout {
		return context.WithCancel(parent)
	}
	return context.WithTimeout(parent, c.requestTimeout)
}

// formatDurationForElasticsearch converts a Go time.Duration to Elasticsearch-compatible string format.
//
// Elasticsearch Formats:
//   - Hours: "1h", "2h" (for durations ≥ 1 hour)
//   - Minutes: "30m", "2m" (for durations ≥ 1 minute without seconds)
//   - Seconds: "45s", "10s" (for durations ≥ 1 second without milliseconds)
//   - Milliseconds: "500ms", "100ms" (default for sub-second durations)
//
// Edge Cases:
//   - ≤ 0: Returns "1ms" (Elasticsearch minimum)
//   - Fractional units: Rounded up (e.g., 1.5s → 1500ms, 90s → 1m30s behavior varies)
//   - Very small: Capped at 1ms minimum
//
// Parameters:
//   - value: Duration to format
//
// Returns:
//   - string: Elasticsearch-compatible duration string
//
// Examples:
//
//	formatDurationForElasticsearch(2 * time.Hour) → "2h"
//	formatDurationForElasticsearch(30 * time.Second) → "30s"
//	formatDurationForElasticsearch(500 * time.Millisecond) → "500ms"
//	formatDurationForElasticsearch(-1 * time.Second) → "1ms"
func formatDurationForElasticsearch(value time.Duration) string {
	switch {
	case value <= 0:
		return "1ms"
	case value%time.Hour == 0:
		return fmt.Sprintf("%dh", value/time.Hour)
	case value%time.Minute == 0:
		return fmt.Sprintf("%dm", value/time.Minute)
	case value%time.Second == 0:
		return fmt.Sprintf("%ds", value/time.Second)
	default:
		milliseconds := value / time.Millisecond
		if value%time.Millisecond != 0 {
			milliseconds++
		}
		if milliseconds < 1 {
			milliseconds = 1
		}
		return fmt.Sprintf("%dms", milliseconds)
	}
}
