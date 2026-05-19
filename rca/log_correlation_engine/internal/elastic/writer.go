package elastic

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"strings"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"

	esv8 "github.com/elastic/go-elasticsearch/v8"
)

type WriterInterface interface {
	WriteResults(ctx context.Context, results []*models.CorrelationResult) []error
	Close() error
}

type Writer struct {
	client         *esv8.Client
	index          string
	writeHistory   bool
	currentIndex   string
	requestTimeout time.Duration
	bulkBatchSize  int
	logger         *slog.Logger
}

type bulkEntry struct {
	index  int
	result *models.CorrelationResult
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

type correlationResultDocument struct {
	LogID           []resultLogDocument `json:"log_id"`
	RuleCompletion  float64             `json:"rule_completion"`
	RuleID          string              `json:"rule_id"`
	SequenceMatch   float64             `json:"sequence_match"`
	IncidentID      string              `json:"incident_id,omitempty"`
	Status          string              `json:"status,omitempty"`
	FirstSeen       *time.Time          `json:"first_seen,omitempty"`
	LastSeen        *time.Time          `json:"last_seen,omitempty"`
	OrganizationID  string              `json:"organization_id,omitempty"`
	GroupByValues   map[string]string   `json:"group_by_values,omitempty"`
	MatchedAt       time.Time           `json:"matched_at,omitempty"`
	CorrelatedAt    time.Time           `json:"correlated_at,omitempty"`
	IsProcessed     int                 `json:"is_processed"`
	ResultSignature string              `json:"result_signature,omitempty"`
	Audit           *matchAuditDocument `json:"audit,omitempty"`
}

type resultLogDocument struct {
	ID          string    `json:"id"`
	Severity    string    `json:"severity"`
	SourceIndex string    `json:"source_index,omitempty"`
	Signal      string    `json:"signal,omitempty"`
	Timestamp   time.Time `json:"timestamp,omitempty"`
	ServiceName string    `json:"service_name,omitempty"`
	HostName    string    `json:"host_name,omitempty"`
	HostIP      string    `json:"host_ip,omitempty"`
	HostIPs     []string  `json:"host_ips,omitempty"`
}

type matchAuditDocument struct {
	Window             string                   `json:"window"`
	MaxGapBetweenSteps string                   `json:"max_gap_between_steps,omitempty"`
	NegativeSignals    []string                 `json:"negative_signals,omitempty"`
	Steps              []matchStepAuditDocument `json:"steps,omitempty"`
	MatchedSignals     []string                 `json:"matched_signals,omitempty"`
}

type matchStepAuditDocument struct {
	RequiredCount int      `json:"required_count"`
	MatchedCount  int      `json:"matched_count"`
	Within        string   `json:"within"`
	MatchedLogIDs []string `json:"matched_log_ids,omitempty"`
}

func NewWriter(cfg config.ElasticsearchConfig, logger *slog.Logger) (*Writer, error) {
	client, err := esv8.NewClient(esv8.Config{
		Addresses: cfg.Addresses,
		Username:  cfg.Username,
		Password:  cfg.Password,
		APIKey:    cfg.APIKey,
	})
	if err != nil {
		return nil, fmt.Errorf("create elasticsearch client: %w", err)
	}

	writer := &Writer{
		client:         client,
		index:          cfg.Index,
		writeHistory:   cfg.WriteHistory,
		currentIndex:   cfg.CurrentIndex,
		requestTimeout: cfg.RequestTimeout,
		bulkBatchSize:  cfg.BulkBatchSize,
		logger:         logger,
	}

	pingCtx, cancel := writer.requestContext(context.Background())
	defer cancel()

	response, err := client.Info(client.Info.WithContext(pingCtx))
	if err != nil {
		return nil, fmt.Errorf("connect to elasticsearch: %w", err)
	}
	defer response.Body.Close()

	if response.IsError() {
		body, _ := io.ReadAll(response.Body)
		return nil, fmt.Errorf("elasticsearch info failed with status %s: %s", response.Status(), string(body))
	}

	return writer, nil
}

func (w *Writer) WriteResults(ctx context.Context, results []*models.CorrelationResult) []error {
	errorsByIndex := make([]error, len(results))
	if len(results) == 0 {
		return errorsByIndex
	}

	entries := make([]bulkEntry, 0, len(results))
	for idx, result := range results {
		if result == nil {
			errorsByIndex[idx] = fmt.Errorf("result cannot be nil")
			continue
		}
		result.IsProcessed = 0
		if err := result.EnsureDocumentID(); err != nil {
			errorsByIndex[idx] = fmt.Errorf("ensure result document id: %w", err)
			continue
		}
		entries = append(entries, bulkEntry{
			index:  idx,
			result: result,
		})
	}

	for start := 0; start < len(entries); start += w.bulkBatchSize {
		end := start + w.bulkBatchSize
		if end > len(entries) {
			end = len(entries)
		}

		batchErrors := w.writeBatch(ctx, entries[start:end])
		for idx, err := range batchErrors {
			entry := entries[start+idx]
			errorsByIndex[entry.index] = err
		}
	}

	return errorsByIndex
}

func (w *Writer) writeBatch(ctx context.Context, entries []bulkEntry) []error {
	result := make([]error, len(entries))
	if len(entries) == 0 {
		return result
	}

	if w.writeHistory {
		requestCtx, cancel := w.requestContext(ctx)
		defer cancel()

		var payload bytes.Buffer
		encoder := json.NewEncoder(&payload)
		for _, entry := range entries {
			if err := encoder.Encode(map[string]map[string]string{
				"index": {
					"_id": entry.result.DocumentID,
				},
			}); err != nil {
				return fillBatchErrors(len(entries), fmt.Errorf("encode bulk metadata: %w", err))
			}
			if err := encoder.Encode(compactResultForWrite(entry.result)); err != nil {
				return fillBatchErrors(len(entries), fmt.Errorf("encode bulk document: %w", err))
			}
		}

		response, err := w.client.Bulk(
			bytes.NewReader(payload.Bytes()),
			w.client.Bulk.WithContext(requestCtx),
			w.client.Bulk.WithIndex(w.index),
		)
		if err != nil {
			return fillBatchErrors(len(entries), fmt.Errorf("bulk index correlation results: %w", err))
		}
		defer response.Body.Close()

		body, err := io.ReadAll(response.Body)
		if err != nil {
			return fillBatchErrors(len(entries), fmt.Errorf("read bulk response: %w", err))
		}

		if response.IsError() {
			return fillBatchErrors(len(entries), fmt.Errorf("elasticsearch bulk indexing failed with status %s: %s", response.Status(), string(body)))
		}

		var bulkResult bulkResponse
		if err := json.Unmarshal(body, &bulkResult); err != nil {
			return fillBatchErrors(len(entries), fmt.Errorf("decode bulk response: %w", err))
		}
		if len(bulkResult.Items) != len(entries) {
			return fillBatchErrors(len(entries), fmt.Errorf("bulk response item count mismatch: got %d want %d", len(bulkResult.Items), len(entries)))
		}

		for idx, item := range bulkResult.Items {
			indexResult, ok := item["index"]
			if !ok {
				result[idx] = fmt.Errorf("bulk response missing index item")
				continue
			}
			if len(indexResult.Error) > 0 {
				result[idx] = fmt.Errorf("bulk item failed for document %s with status %d: %s", indexResult.ID, indexResult.Status, string(indexResult.Error))
			}
		}

		if w.logger != nil {
			w.logger.Debug(
				"bulk indexed correlation results",
				"count", len(entries),
				"index", w.index,
				"errors", bulkResult.Errors,
			)
		}
	}

	if strings.TrimSpace(w.currentIndex) != "" && w.currentIndex != w.index {
		successfulEntries := make([]bulkEntry, 0, len(entries))
		successfulIndexes := make([]int, 0, len(entries))
		for idx, entry := range entries {
			if result[idx] != nil {
				continue
			}
			successfulEntries = append(successfulEntries, entry)
			successfulIndexes = append(successfulIndexes, idx)
		}
		currentErrors := w.writeCurrentBatch(ctx, successfulEntries)
		for idx, err := range currentErrors {
			if err == nil {
				continue
			}
			result[successfulIndexes[idx]] = err
		}
	}

	return result
}

func (w *Writer) writeCurrentBatch(ctx context.Context, entries []bulkEntry) []error {
	result := make([]error, len(entries))
	if len(entries) == 0 {
		return result
	}

	requestCtx, cancel := w.requestContext(ctx)
	defer cancel()

	var payload bytes.Buffer
	encoder := json.NewEncoder(&payload)
	for _, entry := range entries {
		incidentID := strings.TrimSpace(entry.result.IncidentID)
		if incidentID == "" {
			return fillBatchErrors(len(entries), fmt.Errorf("incident id is required for current correlation index"))
		}
		if err := encoder.Encode(map[string]map[string]string{
			"index": {
				"_id": incidentID,
			},
		}); err != nil {
			return fillBatchErrors(len(entries), fmt.Errorf("encode current bulk metadata: %w", err))
		}
		if err := encoder.Encode(compactResultForWrite(entry.result)); err != nil {
			return fillBatchErrors(len(entries), fmt.Errorf("encode current bulk document: %w", err))
		}
	}

	response, err := w.client.Bulk(
		bytes.NewReader(payload.Bytes()),
		w.client.Bulk.WithContext(requestCtx),
		w.client.Bulk.WithIndex(w.currentIndex),
	)
	if err != nil {
		return fillBatchErrors(len(entries), fmt.Errorf("bulk index current correlation results: %w", err))
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		return fillBatchErrors(len(entries), fmt.Errorf("read current bulk response: %w", err))
	}
	if response.IsError() {
		return fillBatchErrors(len(entries), fmt.Errorf("current correlation bulk indexing failed with status %s: %s", response.Status(), string(body)))
	}

	var bulkResult bulkResponse
	if err := json.Unmarshal(body, &bulkResult); err != nil {
		return fillBatchErrors(len(entries), fmt.Errorf("decode current bulk response: %w", err))
	}
	if len(bulkResult.Items) != len(entries) {
		return fillBatchErrors(len(entries), fmt.Errorf("current bulk response item count mismatch: got %d want %d", len(bulkResult.Items), len(entries)))
	}

	for idx, item := range bulkResult.Items {
		indexResult, ok := item["index"]
		if !ok {
			result[idx] = fmt.Errorf("current bulk response missing index item")
			continue
		}
		if len(indexResult.Error) > 0 {
			result[idx] = fmt.Errorf("current bulk item failed for incident %s with status %d: %s", indexResult.ID, indexResult.Status, string(indexResult.Error))
		}
	}

	if w.logger != nil {
		w.logger.Debug(
			"bulk indexed current correlation results",
			"count", len(entries),
			"index", w.currentIndex,
			"errors", bulkResult.Errors,
		)
	}

	return result
}

func (w *Writer) Close() error {
	return nil
}

func (w *Writer) requestContext(parent context.Context) (context.Context, context.CancelFunc) {
	if w.requestTimeout <= 0 {
		return context.WithCancel(parent)
	}
	if deadline, ok := parent.Deadline(); ok && time.Until(deadline) <= w.requestTimeout {
		return context.WithCancel(parent)
	}
	return context.WithTimeout(parent, w.requestTimeout)
}

func fillBatchErrors(length int, err error) []error {
	result := make([]error, length)
	for idx := range result {
		result[idx] = err
	}
	return result
}

func compactResultForWrite(result *models.CorrelationResult) correlationResultDocument {
	document := correlationResultDocument{
		LogID:           compactResultLogs(result.LogID),
		RuleCompletion:  result.RuleCompletion,
		RuleID:          result.RuleID,
		SequenceMatch:   result.SequenceMatch,
		IncidentID:      result.IncidentID,
		Status:          result.Status,
		FirstSeen:       cloneTimePtr(result.FirstSeen),
		LastSeen:        cloneTimePtr(result.LastSeen),
		OrganizationID:  result.OrganizationID,
		GroupByValues:   cloneStringMap(result.GroupByValues),
		MatchedAt:       result.MatchedAt,
		CorrelatedAt:    result.CorrelatedAt,
		IsProcessed:     result.IsProcessed,
		ResultSignature: result.ResultSignature,
		Audit:           compactMatchAudit(result.Audit),
	}
	return document
}

func compactResultLogs(logs []models.ResultLog) []resultLogDocument {
	if len(logs) == 0 {
		return nil
	}
	result := make([]resultLogDocument, len(logs))
	for idx, log := range logs {
		result[idx] = resultLogDocument{
			ID:          log.ID,
			Severity:    log.Severity,
			SourceIndex: log.SourceIndex,
			Signal:      log.Signal,
			Timestamp:   log.Timestamp,
			ServiceName: log.ServiceName,
			HostName:    log.HostName,
			HostIP:      log.HostIP,
			HostIPs:     append([]string(nil), log.HostIPs...),
		}
	}
	return result
}

func compactMatchAudit(audit *models.MatchAudit) *matchAuditDocument {
	if audit == nil {
		return nil
	}

	document := &matchAuditDocument{
		Window:             audit.Window,
		MaxGapBetweenSteps: audit.MaxGapBetweenSteps,
		NegativeSignals:    append([]string(nil), audit.NegativeSignals...),
		MatchedSignals:     append([]string(nil), audit.MatchedSignals...),
	}
	if len(audit.Steps) > 0 {
		document.Steps = make([]matchStepAuditDocument, len(audit.Steps))
		for idx, step := range audit.Steps {
			document.Steps[idx] = matchStepAuditDocument{
				RequiredCount: step.RequiredCount,
				MatchedCount:  step.MatchedCount,
				Within:        step.Within,
				MatchedLogIDs: append([]string(nil), step.MatchedLogIDs...),
			}
		}
	}
	return document
}

func cloneTimePtr(value *time.Time) *time.Time {
	if value == nil {
		return nil
	}
	cloned := value.UTC()
	return &cloned
}

func cloneStringMap(input map[string]string) map[string]string {
	if len(input) == 0 {
		return nil
	}
	cloned := make(map[string]string, len(input))
	for key, value := range input {
		cloned[key] = value
	}
	return cloned
}
