package loader

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"

	esv8 "github.com/elastic/go-elasticsearch/v8"
)

type LogFetcher interface {
	FetchLog(ctx context.Context, docID string) (*models.FullLog, error)
}

type BatchLogFetcher interface {
	FetchLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error)
}

type MockLogFetcher struct {
	mu     sync.RWMutex
	cache  map[string]*models.FullLog
	logger *slog.Logger
	now    func() time.Time
}

type ElasticsearchLogFetcher struct {
	client         *esv8.Client
	index          string
	requestTimeout time.Duration
	timestampField string
	logLevelField  string
	logger         *slog.Logger
}

type searchResponse struct {
	Hits struct {
		Hits []struct {
			ID     string         `json:"_id"`
			Source map[string]any `json:"_source"`
		} `json:"hits"`
	} `json:"hits"`
}

const elasticsearchGroupedLookupBatchSize = 250

func NewMockLogFetcher(logger *slog.Logger) *MockLogFetcher {
	return &MockLogFetcher{
		cache:  make(map[string]*models.FullLog),
		logger: logger,
		now:    time.Now,
	}
}

func NewElasticsearchLogFetcher(
	cfg config.ElasticsearchConfig,
	timestampField string,
	logLevelField string,
	logger *slog.Logger,
) (*ElasticsearchLogFetcher, error) {
	if len(cfg.Addresses) == 0 {
		return nil, fmt.Errorf("elasticsearch fetcher requires at least one address")
	}
	if strings.TrimSpace(cfg.Index) == "" {
		return nil, fmt.Errorf("elasticsearch fetcher requires a source index")
	}

	client, err := esv8.NewClient(esv8.Config{
		Addresses: cfg.Addresses,
		Username:  cfg.Username,
		Password:  cfg.Password,
		APIKey:    cfg.APIKey,
	})
	if err != nil {
		return nil, fmt.Errorf("create elasticsearch fetcher client: %w", err)
	}

	fetcher := &ElasticsearchLogFetcher{
		client:         client,
		index:          cfg.Index,
		requestTimeout: cfg.RequestTimeout,
		timestampField: strings.TrimSpace(timestampField),
		logLevelField:  strings.TrimSpace(logLevelField),
		logger:         logger,
	}

	pingCtx, cancel := fetcher.requestContext(context.Background())
	defer cancel()

	response, err := client.Info(client.Info.WithContext(pingCtx))
	if err != nil {
		return nil, fmt.Errorf("connect elasticsearch fetcher client: %w", err)
	}
	defer response.Body.Close()

	if response.IsError() {
		body, _ := io.ReadAll(response.Body)
		return nil, fmt.Errorf("elasticsearch fetcher info failed with status %s: %s", response.Status(), string(body))
	}

	return fetcher, nil
}

func (m *MockLogFetcher) FetchLog(ctx context.Context, docID string) (*models.FullLog, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if docID == "" {
		return nil, fmt.Errorf("doc_id cannot be empty")
	}

	m.mu.RLock()
	cached, ok := m.cache[docID]
	m.mu.RUnlock()
	if ok {
		clone := cloneFullLog(cached)
		return &clone, nil
	}

	logEntry := &models.FullLog{
		DocID:     docID,
		Timestamp: m.now().UTC(),
		Signal:    "mock_signal",
		LogLevel:  "info",
		Metadata: map[string]any{
			"event": map[string]any{
				"organization": "135098068173316952064",
			},
			"host": map[string]any{
				"name": "host-1",
			},
			"service": map[string]any{
				"name": "api",
			},
		},
	}

	m.mu.Lock()
	m.cache[docID] = logEntry
	m.mu.Unlock()

	if m.logger != nil {
		m.logger.Debug("generated mock log", "doc_id", docID)
	}

	clone := cloneFullLog(logEntry)
	return &clone, nil
}

func (m *MockLogFetcher) FetchLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	result := make(map[string]*models.FullLog, len(docIDs))
	for _, docID := range uniqueDocIDs(docIDs) {
		logEntry, err := m.FetchLog(ctx, docID)
		if err != nil {
			return nil, err
		}
		result[docID] = logEntry
	}
	return result, nil
}

func (f *ElasticsearchLogFetcher) FetchLog(ctx context.Context, docID string) (*models.FullLog, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if strings.TrimSpace(docID) == "" {
		return nil, fmt.Errorf("doc_id cannot be empty")
	}

	body, err := json.Marshal(f.singleLookupQuery(docID))
	if err != nil {
		return nil, fmt.Errorf("marshal elasticsearch fetch query for doc_id %s: %w", docID, err)
	}

	requestCtx, cancel := f.requestContext(ctx)
	defer cancel()

	response, err := f.client.Search(
		f.client.Search.WithContext(requestCtx),
		f.client.Search.WithIndex(f.index),
		f.client.Search.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("search elasticsearch document %s: %w", docID, err)
	}
	defer response.Body.Close()

	payload, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read elasticsearch document response for %s: %w", docID, err)
	}
	if response.IsError() {
		return nil, fmt.Errorf("elasticsearch document lookup failed for %s with status %s: %s", docID, response.Status(), string(payload))
	}

	var parsed searchResponse
	if err := json.Unmarshal(payload, &parsed); err != nil {
		return nil, fmt.Errorf("decode elasticsearch document response for %s: %w", docID, err)
	}
	if len(parsed.Hits.Hits) == 0 {
		return nil, fmt.Errorf("document %s not found in source index %s", docID, f.index)
	}

	return f.fullLogFromSourceHit(docID, parsed.Hits.Hits[0]), nil
}

func (f *ElasticsearchLogFetcher) FetchLogs(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	uniqueIDs := uniqueDocIDs(docIDs)
	result := make(map[string]*models.FullLog, len(uniqueIDs))
	if len(uniqueIDs) == 0 {
		return result, nil
	}

	for start := 0; start < len(uniqueIDs); start += elasticsearchGroupedLookupBatchSize {
		end := start + elasticsearchGroupedLookupBatchSize
		if end > len(uniqueIDs) {
			end = len(uniqueIDs)
		}

		batchResults, err := f.fetchLogsBatch(ctx, uniqueIDs[start:end])
		if err != nil {
			return nil, err
		}
		for docID, logEntry := range batchResults {
			if logEntry != nil {
				result[docID] = logEntry
			}
		}
	}

	return result, nil
}

func (m *MockLogFetcher) AddMockLog(logEntry *models.FullLog) {
	if logEntry == nil {
		return
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	cloned := cloneFullLog(logEntry)
	m.cache[logEntry.DocID] = &cloned
}

func (m *MockLogFetcher) ClearCache() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.cache = make(map[string]*models.FullLog)
}

func (m *MockLogFetcher) GetCacheSize() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.cache)
}

func cloneFullLog(logEntry *models.FullLog) models.FullLog {
	clone := *logEntry
	if logEntry.Metadata == nil {
		return clone
	}

	clone.Metadata = deepCloneMap(logEntry.Metadata)
	return clone
}

func (f *ElasticsearchLogFetcher) requestContext(parent context.Context) (context.Context, context.CancelFunc) {
	if f.requestTimeout <= 0 {
		return context.WithCancel(parent)
	}
	if deadline, ok := parent.Deadline(); ok && time.Until(deadline) <= f.requestTimeout {
		return context.WithCancel(parent)
	}
	return context.WithTimeout(parent, f.requestTimeout)
}

func (f *ElasticsearchLogFetcher) fetchLogsBatch(ctx context.Context, docIDs []string) (map[string]*models.FullLog, error) {
	requestCtx, cancel := f.requestContext(ctx)
	defer cancel()

	body, err := json.Marshal(f.groupedLookupQuery(docIDs))
	if err != nil {
		return nil, fmt.Errorf("marshal elasticsearch grouped lookup query: %w", err)
	}

	response, err := f.client.Search(
		f.client.Search.WithContext(requestCtx),
		f.client.Search.WithIndex(f.index),
		f.client.Search.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("batch search elasticsearch documents: %w", err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read elasticsearch batch response: %w", err)
	}
	if response.IsError() {
		return nil, fmt.Errorf("elasticsearch batch lookup failed with status %s: %s", response.Status(), string(rawBody))
	}

	var parsed searchResponse
	if err := json.Unmarshal(rawBody, &parsed); err != nil {
		return nil, fmt.Errorf("decode elasticsearch batch response: %w", err)
	}

	results := make(map[string]*models.FullLog, len(docIDs))
	for _, hit := range parsed.Hits.Hits {
		if _, exists := results[hit.ID]; exists {
			continue
		}
		results[hit.ID] = f.fullLogFromSourceHit(hit.ID, hit)
	}

	if f.logger != nil {
		f.logger.Debug(
			"fetched full logs from elasticsearch batch",
			"source_index", f.index,
			"requested_doc_ids", len(docIDs),
			"resolved_logs", len(results),
		)
	}

	return results, nil
}

func (f *ElasticsearchLogFetcher) singleLookupQuery(docID string) map[string]any {
	return map[string]any{
		"size":             1,
		"track_total_hits": false,
		"query": map[string]any{
			"ids": map[string]any{
				"values": []string{docID},
			},
		},
		"sort": []map[string]any{
			{
				f.timestampField: map[string]any{
					"order":         "desc",
					"unmapped_type": "date",
				},
			},
		},
	}
}

func (f *ElasticsearchLogFetcher) groupedLookupQuery(docIDs []string) map[string]any {
	requestSize := len(docIDs)
	if requestSize < 50 {
		requestSize = 50
	}
	return map[string]any{
		"size":             requestSize,
		"track_total_hits": false,
		"query": map[string]any{
			"ids": map[string]any{
				"values": docIDs,
			},
		},
		"sort": []map[string]any{
			{
				f.timestampField: map[string]any{
					"order":         "desc",
					"unmapped_type": "date",
				},
			},
		},
	}
}

func (f *ElasticsearchLogFetcher) fullLogFromSourceHit(docID string, hit struct {
	ID     string         `json:"_id"`
	Source map[string]any `json:"_source"`
}) *models.FullLog {
	source := deepCloneMap(hit.Source)
	fullLog := &models.FullLog{
		DocID:    hit.ID,
		Metadata: source,
	}

	if rawTimestamp, ok := lookupPath(source, f.timestampField); ok {
		if parsedTimestamp, err := parseTimestamp(rawTimestamp); err == nil {
			fullLog.Timestamp = parsedTimestamp
		} else if f.logger != nil {
			f.logger.Debug(
				"failed to parse source timestamp for fetched log",
				"doc_id", docID,
				"field", f.timestampField,
				"error", err,
			)
		}
	}
	if rawLevel, ok := lookupPath(source, f.logLevelField); ok {
		if level, ok := stringValue(rawLevel); ok {
			fullLog.LogLevel = level
		}
	}
	if rawSignal, ok := lookupPath(source, "signal"); ok {
		if signal, ok := stringValue(rawSignal); ok {
			fullLog.Signal = signal
		}
	}

	if f.logger != nil {
		f.logger.Debug(
			"fetched full log from elasticsearch",
			"doc_id", docID,
			"source_index", f.index,
		)
	}

	return fullLog
}

func uniqueDocIDs(docIDs []string) []string {
	seen := make(map[string]struct{}, len(docIDs))
	result := make([]string, 0, len(docIDs))
	for _, docID := range docIDs {
		trimmed := strings.TrimSpace(docID)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		result = append(result, trimmed)
	}
	return result
}

func lookupPath(source map[string]any, fieldPath string) (any, bool) {
	if strings.TrimSpace(fieldPath) == "" {
		return nil, false
	}
	current := any(source)
	for _, part := range strings.Split(fieldPath, ".") {
		next, ok := current.(map[string]any)
		if !ok {
			return nil, false
		}
		value, exists := next[part]
		if !exists {
			return nil, false
		}
		current = value
	}
	return current, true
}

func stringValue(value any) (string, bool) {
	switch typed := value.(type) {
	case nil:
		return "", false
	case string:
		text := strings.TrimSpace(typed)
		return text, text != ""
	case fmt.Stringer:
		text := strings.TrimSpace(typed.String())
		return text, text != ""
	default:
		text := strings.TrimSpace(fmt.Sprint(value))
		return text, text != ""
	}
}

func parseTimestamp(value any) (time.Time, error) {
	switch typed := value.(type) {
	case time.Time:
		return typed.UTC(), nil
	case string:
		text := strings.TrimSpace(typed)
		if text == "" {
			return time.Time{}, errors.New("empty timestamp")
		}
		layouts := []string{
			time.RFC3339Nano,
			time.RFC3339,
			"2006-01-02T15:04:05.999999999",
			"2006-01-02 15:04:05",
		}
		for _, layout := range layouts {
			if parsed, err := time.Parse(layout, text); err == nil {
				return parsed.UTC(), nil
			}
		}
		return time.Time{}, fmt.Errorf("unsupported timestamp format %q", typed)
	default:
		return time.Time{}, fmt.Errorf("unsupported timestamp type %T", value)
	}
}

func deepCloneMap(source map[string]any) map[string]any {
	if source == nil {
		return nil
	}

	cloned := make(map[string]any, len(source))
	for key, value := range source {
		cloned[key] = deepCloneValue(value)
	}
	return cloned
}

func deepCloneValue(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		return deepCloneMap(typed)
	case []any:
		cloned := make([]any, len(typed))
		for idx, item := range typed {
			cloned[idx] = deepCloneValue(item)
		}
		return cloned
	default:
		return typed
	}
}
