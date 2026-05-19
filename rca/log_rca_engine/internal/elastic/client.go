package elastic

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"sort"
	"strings"
	"time"

	"log_rca_engine/internal/config"
	"log_rca_engine/internal/models"
	"log_rca_engine/internal/utils"

	esv8 "github.com/elastic/go-elasticsearch/v8"
)

type Client struct {
	client              *esv8.Client
	correlationIndex    string
	sourceIndexFallback string
	requestTimeout      time.Duration
	pageSize            int
	replayWindow        time.Duration
	logger              *slog.Logger
}

type searchHit struct {
	Index  string          `json:"_index"`
	ID     string          `json:"_id"`
	Source json.RawMessage `json:"_source"`
	Sort   []any           `json:"sort"`
}

type searchResponse struct {
	Hits struct {
		Hits []searchHit `json:"hits"`
	} `json:"hits"`
}

type bulkResponse struct {
	Errors bool                        `json:"errors"`
	Items  []map[string]bulkItemResult `json:"items"`
}

type bulkItemResult struct {
	ID     string          `json:"_id"`
	Status int             `json:"status"`
	Error  json.RawMessage `json:"error"`
}

const correlationEventSortFieldCount = 4

func NewClient(cfg config.ElasticsearchConfig, logger *slog.Logger) (*Client, error) {
	client, err := esv8.NewClient(esv8.Config{
		Addresses: cfg.Addresses,
		Username:  cfg.Username,
		Password:  cfg.Password,
		APIKey:    cfg.APIKey,
	})
	if err != nil {
		return nil, fmt.Errorf("create elasticsearch client: %w", err)
	}

	result := &Client{
		client:              client,
		correlationIndex:    cfg.CorrelationIndex,
		sourceIndexFallback: cfg.SourceIndexFallback,
		requestTimeout:      cfg.RequestTimeout,
		pageSize:            cfg.PageSize,
		replayWindow:        cfg.ReplayWindow,
		logger:              logger,
	}

	pingCtx, cancel := result.requestContext(context.Background())
	defer cancel()
	response, err := result.client.Info(result.client.Info.WithContext(pingCtx))
	if err != nil {
		return nil, fmt.Errorf("connect to elasticsearch: %w", err)
	}
	defer response.Body.Close()
	if response.IsError() {
		body, _ := io.ReadAll(response.Body)
		return nil, fmt.Errorf("elasticsearch info failed with status %s: %s", response.Status(), string(body))
	}

	return result, nil
}

func (c *Client) ReadCorrelationEvents(ctx context.Context, checkpoint models.ReaderCheckpoint) ([]models.CorrelationEvent, models.ReaderCheckpoint, error) {
	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	searchAfter := normalizeCorrelationSearchAfter(checkpoint.SearchAfter)
	replayStart := c.replayStart(checkpoint)
	if len(checkpoint.SearchAfter) > 0 && len(searchAfter) == 0 && c.logger != nil {
		c.logger.Warn(
			"ignoring legacy or incompatible RCA checkpoint search_after values",
			"received_values", len(checkpoint.SearchAfter),
			"expected_values", correlationEventSortFieldCount,
		)
	}
	body := buildCorrelationEventSearchBody(c.pageSize, replayStart, searchAfter)

	payload, err := json.Marshal(body)
	if err != nil {
		return nil, checkpoint, fmt.Errorf("marshal correlation event search query: %w", err)
	}

	response, err := c.client.Search(
		c.client.Search.WithContext(requestCtx),
		c.client.Search.WithIndex(c.correlationIndex),
		c.client.Search.WithBody(bytes.NewReader(payload)),
	)
	if err != nil {
		return nil, checkpoint, fmt.Errorf("search correlation events: %w", err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, checkpoint, fmt.Errorf("read correlation event response: %w", err)
	}
	if response.IsError() {
		return nil, checkpoint, fmt.Errorf("correlation event search failed with status %s: %s", response.Status(), string(rawBody))
	}

	var parsed searchResponse
	if err := json.Unmarshal(rawBody, &parsed); err != nil {
		return nil, checkpoint, fmt.Errorf("decode correlation event response: %w", err)
	}

	events := make([]models.CorrelationEvent, 0, len(parsed.Hits.Hits))
	next := checkpoint
	next.SearchAfter = searchAfter
	for _, hit := range parsed.Hits.Hits {
		var event models.CorrelationEvent
		if len(hit.Source) > 0 {
			if err := json.Unmarshal(hit.Source, &event); err != nil {
				if c.logger != nil {
					c.logger.Warn("failed to decode correlation event", "document_id", hit.ID, "error", err)
				}
				continue
			}
		}

		event.DocumentIndex = strings.TrimSpace(hit.Index)
		event.DocumentID = hit.ID
		event.SortValues = append([]any(nil), hit.Sort...)
		if strings.TrimSpace(event.IncidentID) == "" {
			event.IncidentID = hit.ID
		}
		if event.LogID == nil {
			event.LogID = []models.EvidenceLog{}
		}
		events = append(events, event)
		if len(hit.Sort) > 0 {
			next.SearchAfter = append([]any(nil), hit.Sort...)
		}
	}

	return events, next, nil
}

func (c *Client) SetPageSize(size int) {
	if size <= 0 {
		return
	}
	c.pageSize = size
}

func buildCorrelationEventSearchBody(pageSize int, replayStart *time.Time, searchAfter []any) map[string]any {
	filters := []any{unprocessedCorrelationEventFilter()}
	if replayStart != nil {
		replayStartValue := replayStart.UTC().Format(time.RFC3339Nano)
		filters = append(filters, map[string]any{
			"bool": map[string]any{
				"should": []any{
					map[string]any{
						"range": map[string]any{
							"last_seen": map[string]any{
								"gte":    replayStartValue,
								"format": "strict_date_optional_time_nanos",
							},
						},
					},
					map[string]any{
						"range": map[string]any{
							"matched_at": map[string]any{
								"gte":    replayStartValue,
								"format": "strict_date_optional_time_nanos",
							},
						},
					},
				},
				"minimum_should_match": 1,
			},
		})
	}

	body := map[string]any{
		"size": pageSize,
		"query": map[string]any{
			"bool": map[string]any{
				"filter": filters,
			},
		},
		"sort": []map[string]any{
			{
				"last_seen": map[string]any{
					"order":         "asc",
					"format":        "strict_date_optional_time_nanos",
					"missing":       "_last",
					"unmapped_type": "date",
				},
			},
			{
				"matched_at": map[string]any{
					"order":         "asc",
					"format":        "strict_date_optional_time_nanos",
					"missing":       "_last",
					"unmapped_type": "date",
				},
			},
			{
				"incident_id.keyword": map[string]any{
					"order":         "asc",
					"missing":       "_last",
					"unmapped_type": "keyword",
				},
			},
			{
				"result_signature.keyword": map[string]any{
					"order":         "asc",
					"missing":       "_last",
					"unmapped_type": "keyword",
				},
			},
		},
	}
	if len(searchAfter) > 0 {
		body["search_after"] = searchAfter
	}
	return body
}

func unprocessedCorrelationEventFilter() map[string]any {
	return map[string]any{
		"bool": map[string]any{
			"should": []any{
				map[string]any{
					"term": map[string]any{
						"is_processed": 0,
					},
				},
				map[string]any{
					"bool": map[string]any{
						"must_not": []any{
							map[string]any{
								"exists": map[string]any{
									"field": "is_processed",
								},
							},
						},
					},
				},
			},
			"minimum_should_match": 1,
		},
	}
}

func normalizeCorrelationSearchAfter(searchAfter []any) []any {
	if len(searchAfter) != correlationEventSortFieldCount {
		return nil
	}
	return append([]any(nil), searchAfter...)
}

func (c *Client) replayStart(checkpoint models.ReaderCheckpoint) *time.Time {
	if c.replayWindow <= 0 || checkpoint.UpdatedAt.IsZero() {
		return nil
	}
	start := checkpoint.UpdatedAt.UTC().Add(-c.replayWindow)
	return &start
}

func (c *Client) MarkCorrelationEventsProcessed(ctx context.Context, refs []models.CorrelationEventRef) error {
	entries := uniqueCorrelationEventRefs(refs)
	if len(entries) == 0 {
		return nil
	}

	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	var payload bytes.Buffer
	encoder := json.NewEncoder(&payload)
	for _, entry := range entries {
		documentID := strings.TrimSpace(entry.DocumentID)
		documentIndex := strings.TrimSpace(entry.DocumentIndex)
		if documentID == "" || documentIndex == "" {
			continue
		}
		if err := encoder.Encode(map[string]map[string]string{
			"update": {
				"_index": documentIndex,
				"_id":    documentID,
			},
		}); err != nil {
			return fmt.Errorf("encode processed-event bulk metadata: %w", err)
		}
		if err := encoder.Encode(map[string]any{
			"script": map[string]any{
				"lang":   "painless",
				"source": "if (params.result_signature == null || params.result_signature == '') { ctx._source.is_processed = params.is_processed; } else if (ctx._source.result_signature == params.result_signature) { ctx._source.is_processed = params.is_processed; } else { ctx.op = 'none'; }",
				"params": map[string]any{
					"is_processed":     1,
					"result_signature": strings.TrimSpace(entry.ResultSignature),
				},
			},
		}); err != nil {
			return fmt.Errorf("encode processed-event bulk document: %w", err)
		}
	}
	if payload.Len() == 0 {
		return nil
	}

	response, err := c.client.Bulk(
		bytes.NewReader(payload.Bytes()),
		c.client.Bulk.WithContext(requestCtx),
	)
	if err != nil {
		return fmt.Errorf("bulk mark correlation events processed: %w", err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return fmt.Errorf("read processed-event bulk response: %w", err)
	}
	if response.IsError() {
		return fmt.Errorf("processed-event bulk update failed with status %s: %s", response.Status(), string(rawBody))
	}

	var bulkResult bulkResponse
	if err := json.Unmarshal(rawBody, &bulkResult); err != nil {
		return fmt.Errorf("decode processed-event bulk response: %w", err)
	}
	if len(bulkResult.Items) != len(entries) {
		return fmt.Errorf("processed-event bulk response item count mismatch: got %d want %d", len(bulkResult.Items), len(entries))
	}
	for _, item := range bulkResult.Items {
		updateResult, ok := item["update"]
		if !ok {
			return fmt.Errorf("processed-event bulk response missing update item")
		}
		if len(updateResult.Error) > 0 {
			return fmt.Errorf("processed-event bulk item failed for document %s with status %d: %s", updateResult.ID, updateResult.Status, string(updateResult.Error))
		}
	}
	return nil
}

func uniqueCorrelationEventRefs(refs []models.CorrelationEventRef) []models.CorrelationEventRef {
	if len(refs) == 0 {
		return nil
	}

	seen := make(map[string]struct{}, len(refs))
	unique := make([]models.CorrelationEventRef, 0, len(refs))
	for _, ref := range refs {
		documentID := strings.TrimSpace(ref.DocumentID)
		documentIndex := strings.TrimSpace(ref.DocumentIndex)
		if documentID == "" || documentIndex == "" {
			continue
		}
		key := documentIndex + "|" + documentID + "|" + strings.TrimSpace(ref.ResultSignature)
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		unique = append(unique, models.CorrelationEventRef{
			DocumentID:      documentID,
			DocumentIndex:   documentIndex,
			ResultSignature: strings.TrimSpace(ref.ResultSignature),
		})
	}
	return unique
}

func (c *Client) FetchMatchedLogs(ctx context.Context, evidence []models.EvidenceLog) ([]models.RelatedLog, error) {
	grouped := make(map[string][]string)
	order := make([]string, 0, len(evidence))
	for _, log := range evidence {
		docID := strings.TrimSpace(log.ID)
		if docID == "" {
			continue
		}
		index := strings.TrimSpace(log.SourceIndex)
		if index == "" {
			index = c.fallbackIndex()
		}
		key := index + "|" + docID
		order = append(order, key)
		grouped[index] = append(grouped[index], docID)
	}

	resultsByKey := make(map[string]models.RelatedLog)
	for index, ids := range grouped {
		hits, err := c.searchByIDs(ctx, index, utils.UniqueStrings(ids))
		if err != nil {
			return nil, err
		}
		for _, hit := range hits {
			key := index + "|" + hit.DocID
			resultsByKey[key] = hit
		}
	}

	results := make([]models.RelatedLog, 0, len(resultsByKey))
	seen := make(map[string]struct{}, len(resultsByKey))
	for _, key := range order {
		if _, ok := seen[key]; ok {
			continue
		}
		logEntry, ok := resultsByKey[key]
		if !ok {
			continue
		}
		seen[key] = struct{}{}
		results = append(results, logEntry)
	}
	return results, nil
}

func (c *Client) SearchRelatedLogs(ctx context.Context, event models.CorrelationEvent, limit int) ([]models.RelatedLog, error) {
	if limit <= 0 {
		return nil, nil
	}

	windowStart, windowEnd := relatedWindow(event)
	services := make([]string, 0, len(event.LogID))
	hosts := make([]string, 0, len(event.LogID))
	hostIPs := make([]string, 0, len(event.LogID))
	sourceIndices := make([]string, 0, len(event.LogID))
	excludedIDs := make([]string, 0, len(event.LogID))
	for _, log := range event.LogID {
		if log.ServiceName != "" {
			services = append(services, log.ServiceName)
		}
		if log.HostName != "" {
			hosts = append(hosts, log.HostName)
		}
		if log.HostIP != "" {
			hostIPs = append(hostIPs, log.HostIP)
		}
		hostIPs = append(hostIPs, log.HostIPs...)
		if log.SourceIndex != "" {
			sourceIndices = append(sourceIndices, log.SourceIndex)
		}
		if log.ID != "" {
			excludedIDs = append(excludedIDs, log.ID)
		}
	}
	if len(sourceIndices) == 0 {
		sourceIndices = []string{c.fallbackIndex()}
	}

	services = utils.UniqueStrings(services)
	hosts = utils.UniqueStrings(hosts)
	hostIPs = utils.UniqueStrings(hostIPs)
	sourceIndices = utils.UniqueStrings(sourceIndices)
	excludedIDs = utils.UniqueStrings(excludedIDs)

	results := make([]models.RelatedLog, 0, limit)
	seen := make(map[string]struct{})
	for _, index := range sourceIndices {
		if len(results) >= limit {
			break
		}

		remaining := limit - len(results)
		hits, err := c.searchRelated(ctx, index, event.OrganizationID, services, hosts, hostIPs, excludedIDs, windowStart, windowEnd, remaining)
		if err != nil {
			return nil, err
		}
		for _, hit := range hits {
			key := hit.Index + "|" + hit.DocID
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			results = append(results, hit)
		}
	}
	results = rankRelatedLogs(event, results)
	if len(results) > limit {
		results = results[:limit]
	}
	return results, nil
}

func (c *Client) Close() error {
	return nil
}

func (c *Client) searchByIDs(ctx context.Context, index string, ids []string) ([]models.RelatedLog, error) {
	if len(ids) == 0 {
		return nil, nil
	}

	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	body, err := json.Marshal(map[string]any{
		"size":             len(ids),
		"track_total_hits": false,
		"query": map[string]any{
			"ids": map[string]any{
				"values": ids,
			},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("marshal fetch-by-id query: %w", err)
	}

	response, err := c.client.Search(
		c.client.Search.WithContext(requestCtx),
		c.client.Search.WithIndex(index),
		c.client.Search.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("search matched logs in index %s: %w", index, err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read matched log response for index %s: %w", index, err)
	}
	if response.IsError() {
		return nil, fmt.Errorf("matched log search failed for index %s with status %s: %s", index, response.Status(), string(rawBody))
	}

	var parsed searchResponse
	if err := json.Unmarshal(rawBody, &parsed); err != nil {
		return nil, fmt.Errorf("decode matched log response for index %s: %w", index, err)
	}

	result := make([]models.RelatedLog, 0, len(parsed.Hits.Hits))
	for _, hit := range parsed.Hits.Hits {
		entry, err := parseRelatedLog(index, hit)
		if err != nil {
			if c.logger != nil {
				c.logger.Warn("failed to parse matched log", "index", index, "document_id", hit.ID, "error", err)
			}
			continue
		}
		result = append(result, entry)
	}
	return result, nil
}

func (c *Client) searchRelated(
	ctx context.Context,
	index string,
	organizationID string,
	services []string,
	hosts []string,
	hostIPs []string,
	excludedIDs []string,
	windowStart time.Time,
	windowEnd time.Time,
	limit int,
) ([]models.RelatedLog, error) {
	requestCtx, cancel := c.requestContext(ctx)
	defer cancel()

	filters := []any{
		map[string]any{
			"range": map[string]any{
				"@timestamp": map[string]any{
					"gte":    windowStart.UTC().Format(time.RFC3339Nano),
					"lte":    windowEnd.UTC().Format(time.RFC3339Nano),
					"format": "strict_date_optional_time_nanos",
				},
			},
		},
	}
	if strings.TrimSpace(organizationID) != "" {
		filters = append(filters, map[string]any{
			"term": map[string]any{
				"event.organization": organizationID,
			},
		})
	}

	should := make([]any, 0, 3)
	if len(services) > 0 {
		should = append(should,
			map[string]any{"terms": map[string]any{"service.name": services}},
			map[string]any{"terms": map[string]any{"event.module": services}},
		)
	}
	if len(hosts) > 0 {
		should = append(should, map[string]any{"terms": map[string]any{"host.name": hosts}})
	}
	if len(hostIPs) > 0 {
		should = append(should, map[string]any{"terms": map[string]any{"host.ip": hostIPs}})
	}

	boolQuery := map[string]any{"filter": filters}
	if len(should) > 0 {
		boolQuery["should"] = should
		boolQuery["minimum_should_match"] = 1
	}
	if len(excludedIDs) > 0 {
		boolQuery["must_not"] = []any{
			map[string]any{
				"ids": map[string]any{
					"values": excludedIDs,
				},
			},
		}
	}

	requestSize := limit
	if requestSize < limit*4 {
		requestSize = limit * 4
	}
	if requestSize > 200 {
		requestSize = 200
	}

	body, err := json.Marshal(map[string]any{
		"size":             requestSize,
		"track_total_hits": false,
		"query": map[string]any{
			"bool": boolQuery,
		},
		"sort": []map[string]any{
			{
				"@timestamp": map[string]any{
					"order":         "asc",
					"unmapped_type": "date",
				},
			},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("marshal related-log query: %w", err)
	}

	response, err := c.client.Search(
		c.client.Search.WithContext(requestCtx),
		c.client.Search.WithIndex(index),
		c.client.Search.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("search related logs in index %s: %w", index, err)
	}
	defer response.Body.Close()

	rawBody, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read related-log response for index %s: %w", index, err)
	}
	if response.IsError() {
		return nil, fmt.Errorf("related-log search failed for index %s with status %s: %s", index, response.Status(), string(rawBody))
	}

	var parsed searchResponse
	if err := json.Unmarshal(rawBody, &parsed); err != nil {
		return nil, fmt.Errorf("decode related-log response for index %s: %w", index, err)
	}

	result := make([]models.RelatedLog, 0, len(parsed.Hits.Hits))
	for _, hit := range parsed.Hits.Hits {
		entry, err := parseRelatedLog(index, hit)
		if err != nil {
			if c.logger != nil {
				c.logger.Warn("failed to parse related log", "index", index, "document_id", hit.ID, "error", err)
			}
			continue
		}
		result = append(result, entry)
	}
	return result, nil
}

func parseRelatedLog(index string, hit searchHit) (models.RelatedLog, error) {
	var source map[string]any
	if len(hit.Source) > 0 {
		if err := json.Unmarshal(hit.Source, &source); err != nil {
			return models.RelatedLog{}, fmt.Errorf("decode source: %w", err)
		}
	}

	entry := models.RelatedLog{
		Index:          index,
		DocID:          hit.ID,
		OrganizationID: utils.ExtractString(source, "event.organization"),
		ServiceName:    resolveServiceName(source),
		HostName:       utils.ExtractString(source, "host.name"),
		HostIP:         firstIP(utils.ExtractIPAddresses(source, "host.ip")),
		HostIPs:        append([]string(nil), utils.ExtractIPAddresses(source, "host.ip")...),
		Severity:       firstNonEmpty(utils.ExtractString(source, "log.level"), utils.ExtractString(source, "level")),
		Signal:         utils.ExtractString(source, "signal"),
		Message:        firstNonEmpty(utils.ExtractString(source, "message"), utils.ExtractString(source, "msg")),
		Source:         source,
	}
	if timestamp := firstNonEmpty(utils.ExtractString(source, "@timestamp"), utils.ExtractString(source, "timestamp")); timestamp != "" {
		if parsed, err := utils.ParseTime(timestamp); err == nil {
			entry.Timestamp = parsed
		}
	}
	return entry, nil
}

func resolveServiceName(source map[string]any) string {
	for _, field := range []string{"service.name", "event.module", "host.name"} {
		if value := utils.ExtractString(source, field); value != "" {
			return value
		}
	}
	return ""
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func firstIP(values []string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func relatedWindow(event models.CorrelationEvent) (time.Time, time.Time) {
	start := event.MatchedAt
	if event.FirstSeen != nil && !event.FirstSeen.IsZero() {
		start = event.FirstSeen.UTC()
	}
	end := event.MatchedAt
	if event.LastSeen != nil && !event.LastSeen.IsZero() {
		end = event.LastSeen.UTC()
	}
	if start.IsZero() {
		start = time.Now().UTC().Add(-10 * time.Minute)
	}
	if end.IsZero() {
		end = start.Add(10 * time.Minute)
	}
	if end.Before(start) {
		end = start
	}
	buffer := 5 * time.Minute
	if event.Audit != nil {
		if parsed, err := utils.ParseDuration(event.Audit.Window); err == nil && parsed > 0 {
			candidate := parsed / 3
			if candidate < 2*time.Minute {
				candidate = 2 * time.Minute
			}
			if candidate > 15*time.Minute {
				candidate = 15 * time.Minute
			}
			if candidate > buffer {
				buffer = candidate
			}
		}
	}
	return start.Add(-buffer), end.Add(buffer)
}

func (c *Client) fallbackIndex() string {
	if strings.TrimSpace(c.sourceIndexFallback) == "" {
		return "*"
	}
	return c.sourceIndexFallback
}

func (c *Client) requestContext(parent context.Context) (context.Context, context.CancelFunc) {
	if c.requestTimeout <= 0 {
		return context.WithCancel(parent)
	}
	if deadline, ok := parent.Deadline(); ok && time.Until(deadline) <= c.requestTimeout {
		return context.WithCancel(parent)
	}
	return context.WithTimeout(parent, c.requestTimeout)
}

func rankRelatedLogs(event models.CorrelationEvent, logs []models.RelatedLog) []models.RelatedLog {
	if len(logs) <= 1 {
		return logs
	}

	services := make(map[string]struct{}, len(event.LogID))
	hosts := make(map[string]struct{}, len(event.LogID))
	hostIPs := make(map[string]struct{}, len(event.LogID))
	matchedSignals := make(map[string]struct{})
	negativeSignals := make(map[string]struct{})

	for _, log := range event.LogID {
		if service := strings.TrimSpace(log.ServiceName); service != "" {
			services[service] = struct{}{}
		}
		if host := strings.TrimSpace(log.HostName); host != "" {
			hosts[host] = struct{}{}
		}
		if ip := strings.TrimSpace(log.HostIP); ip != "" {
			hostIPs[ip] = struct{}{}
		}
		for _, ip := range log.HostIPs {
			if trimmed := strings.TrimSpace(ip); trimmed != "" {
				hostIPs[trimmed] = struct{}{}
			}
		}
		if signal := strings.ToLower(strings.TrimSpace(log.Signal)); signal != "" {
			matchedSignals[signal] = struct{}{}
		}
	}
	if event.Audit != nil {
		for _, signal := range event.Audit.MatchedSignals {
			if trimmed := strings.ToLower(strings.TrimSpace(signal)); trimmed != "" {
				matchedSignals[trimmed] = struct{}{}
			}
		}
		for _, signal := range event.Audit.NegativeSignals {
			if trimmed := strings.ToLower(strings.TrimSpace(signal)); trimmed != "" {
				negativeSignals[trimmed] = struct{}{}
			}
		}
	}

	referenceTime := event.MatchedAt.UTC()
	if event.LastSeen != nil && !event.LastSeen.IsZero() {
		referenceTime = event.LastSeen.UTC()
	}
	timeWindow := 10 * time.Minute
	if event.Audit != nil {
		if parsed, err := utils.ParseDuration(event.Audit.Window); err == nil && parsed > 0 {
			timeWindow = parsed
		}
	}
	if timeWindow <= 0 {
		timeWindow = 10 * time.Minute
	}

	type rankedLog struct {
		log       models.RelatedLog
		score     float64
		timeDelta time.Duration
	}
	ranked := make([]rankedLog, 0, len(logs))
	for _, log := range logs {
		score := 0.0
		if _, ok := services[strings.TrimSpace(log.ServiceName)]; ok {
			score += 3
		}
		if _, ok := hosts[strings.TrimSpace(log.HostName)]; ok {
			score += 2
		}
		for _, ip := range append([]string{log.HostIP}, log.HostIPs...) {
			if _, ok := hostIPs[strings.TrimSpace(ip)]; ok {
				score += 4
				break
			}
		}

		signal := strings.ToLower(strings.TrimSpace(log.Signal))
		if _, ok := matchedSignals[signal]; ok {
			score += 1.5
		}
		if _, ok := negativeSignals[signal]; ok || looksLikeRecoverySignalName(signal) {
			score += 2.5
		}
		score += relatedSeverityWeight(log.Severity)

		delta := 0 * time.Second
		if !log.Timestamp.IsZero() && !referenceTime.IsZero() {
			delta = log.Timestamp.UTC().Sub(referenceTime)
			if delta < 0 {
				delta = -delta
			}
			score += 2 * clamp01(1-(float64(delta)/float64(timeWindow)))
		}

		ranked = append(ranked, rankedLog{log: log, score: score, timeDelta: delta})
	}

	sort.SliceStable(ranked, func(i, j int) bool {
		if ranked[i].score != ranked[j].score {
			return ranked[i].score > ranked[j].score
		}
		if ranked[i].timeDelta != ranked[j].timeDelta {
			return ranked[i].timeDelta < ranked[j].timeDelta
		}
		if ranked[i].log.Timestamp.Equal(ranked[j].log.Timestamp) {
			return ranked[i].log.DocID < ranked[j].log.DocID
		}
		return ranked[i].log.Timestamp.Before(ranked[j].log.Timestamp)
	})

	result := make([]models.RelatedLog, 0, len(ranked))
	for _, item := range ranked {
		result = append(result, item.log)
	}
	return result
}

func relatedSeverityWeight(raw string) float64 {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "critical", "crit", "fatal", "panic", "alert", "emergency", "emerg":
		return 1.0
	case "error", "err", "failure", "failed":
		return 0.85
	case "warning", "warn":
		return 0.60
	case "info", "notice", "informational":
		return 0.35
	default:
		return 0.20
	}
}

func looksLikeRecoverySignalName(signal string) bool {
	tokens := strings.FieldsFunc(strings.ToLower(strings.TrimSpace(signal)), func(r rune) bool {
		return r == '_' || r == '-' || r == '.' || r == ':' || r == ' ' || r == '\t' || r == '\n'
	})
	if len(tokens) == 0 {
		return false
	}
	for _, token := range tokens {
		switch token {
		case "abnormal", "conflict", "corrupt", "degraded", "error", "failed", "failure", "recovering", "unhealthy", "unstable":
			return false
		}
	}
	for _, token := range tokens {
		switch token {
		case "cleared", "healthy", "normal", "recovered", "resolved", "restored", "stabilized", "stable":
			return true
		}
	}
	return false
}

func clamp01(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return value
}
