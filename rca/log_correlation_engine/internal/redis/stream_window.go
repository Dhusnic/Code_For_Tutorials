package redis

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"sort"
	"strconv"
	"strings"
	"time"

	"log_correlation_engine/internal/models"

	goredis "github.com/redis/go-redis/v9"
)

func (s *Store) LoadSignalEventsWindow(ctx context.Context, since time.Time) ([]models.FullLog, error) {
	return s.loadSignalEventsWindowFromStreams(ctx, since, []string{s.signalStreamKey})
}

func (s *Store) LoadSignalEventsWindowForSignals(ctx context.Context, since time.Time, signalKeys []string) ([]models.FullLog, error) {
	streamKeys := s.signalStreamKeysForSignals(signalKeys)
	if len(streamKeys) == 0 {
		return s.LoadSignalEventsWindow(ctx, since)
	}
	existing, err := s.client.Exists(ctx, streamKeys...).Result()
	if err != nil && !errors.Is(err, goredis.Nil) {
		return nil, fmt.Errorf("inspect redis signal streams %v: %w", streamKeys, err)
	}
	if existing == 0 {
		return []models.FullLog{}, nil
	}
	return s.loadSignalEventsWindowFromStreams(ctx, since, streamKeys)
}

func (s *Store) CountSignalEventsWindowForSignals(ctx context.Context, since time.Time, signalKeys []string) (map[string]int, error) {
	counts := make(map[string]int, len(signalKeys))
	streamKeys := s.signalStreamKeysForSignals(signalKeys)
	if len(streamKeys) == 0 {
		return counts, nil
	}

	for _, signalKey := range uniqueSortedStrings(signalKeys) {
		streamKey := fmt.Sprintf("%s:signal:%s", s.signalStreamKey, signalKey)
		value, err := s.countSignalEventsForStream(ctx, streamKey, since)
		if err != nil {
			return nil, fmt.Errorf("count redis signal stream %s since %s: %w", streamKey, since.UTC().Format(time.RFC3339Nano), err)
		}
		counts[signalKey] = value
	}

	return counts, nil
}

func (s *Store) countSignalEventsForStream(ctx context.Context, streamKey string, since time.Time) (int, error) {
	if !s.signalStreamEnabled || strings.TrimSpace(streamKey) == "" {
		return 0, nil
	}

	exists, err := s.client.Exists(ctx, streamKey).Result()
	if err != nil && !errors.Is(err, goredis.Nil) {
		return 0, err
	}
	if exists == 0 {
		return 0, nil
	}

	batchSize := int64(s.signalStreamBatchSize)
	if batchSize <= 0 {
		batchSize = 1000
	}

	currentID := signalWindowStartID(since)
	total := 0
	for {
		messages, err := s.client.XRangeN(ctx, streamKey, currentID, "+", batchSize).Result()
		if errors.Is(err, goredis.Nil) || len(messages) == 0 {
			return total, nil
		}
		if err != nil {
			return 0, err
		}

		total += len(messages)
		if int64(len(messages)) < batchSize {
			return total, nil
		}

		nextID, ok := nextStreamID(messages[len(messages)-1].ID)
		if !ok {
			return 0, fmt.Errorf("advance stream cursor from %q", messages[len(messages)-1].ID)
		}
		currentID = nextID
	}
}

func (s *Store) loadSignalEventsWindowFromStreams(ctx context.Context, since time.Time, streamKeys []string) ([]models.FullLog, error) {
	if !s.signalStreamEnabled {
		return nil, nil
	}

	normalizedStreams := uniqueSortedStrings(streamKeys)
	if len(normalizedStreams) == 0 {
		return nil, nil
	}

	count := int64(s.signalStreamBatchSize)
	if count <= 0 {
		count = 1000
	}

	startID := signalWindowStartID(since)
	loaded := make([]models.FullLog, 0, count)
	currentByStream := make(map[string]string, len(normalizedStreams))
	for _, streamKey := range normalizedStreams {
		currentByStream[streamKey] = startID
	}

	for {
		streamArgs := make([]string, 0, len(normalizedStreams)*2)
		streamArgs = append(streamArgs, normalizedStreams...)
		for _, streamKey := range normalizedStreams {
			streamArgs = append(streamArgs, currentByStream[streamKey])
		}

		streams, err := s.client.XRead(ctx, &goredis.XReadArgs{
			Streams: streamArgs,
			Count:   count,
		}).Result()
		if errors.Is(err, goredis.Nil) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read redis signal event window %v since %s: %w", normalizedStreams, since.UTC().Format(time.RFC3339Nano), err)
		}
		if len(streams) == 0 {
			break
		}

		messagesRead := 0
		for _, stream := range streams {
			for _, message := range stream.Messages {
				fullLog, ok, err := decodeSignalWindowMessage(message)
				if err != nil {
					return nil, fmt.Errorf("decode redis signal event %s: %w", message.ID, err)
				}
				currentByStream[stream.Stream] = message.ID
				messagesRead++
				if !ok {
					continue
				}
				loaded = append(loaded, fullLog)
			}
		}
		if messagesRead == 0 || messagesRead < int(count) {
			break
		}
	}

	return deduplicateWindowLogs(loaded), nil
}

func (s *Store) TrimSignalStreams(ctx context.Context, minID string, signalKeys []string) (int64, error) {
	return s.trimSignalStreamKeys(ctx, minID, s.signalStreamKeysForSignals(signalKeys))
}

func (s *Store) signalStreamKeysForSignals(signalKeys []string) []string {
	keys := make([]string, 0, len(signalKeys))
	for _, signalKey := range uniqueSortedStrings(signalKeys) {
		keys = append(keys, fmt.Sprintf("%s:signal:%s", s.signalStreamKey, signalKey))
	}
	return keys
}

func (s *Store) trimSignalStreamKeys(ctx context.Context, minID string, streamKeys []string) (int64, error) {
	if !s.signalStreamEnabled {
		return 0, nil
	}

	trimMinID := strings.TrimSpace(minID)
	if trimMinID == "" {
		return 0, nil
	}

	totalTrimmed := int64(0)
	for _, streamKey := range uniqueSortedStrings(streamKeys) {
		if strings.TrimSpace(streamKey) == "" {
			continue
		}
		trimmed, err := s.client.XTrimMinIDApprox(ctx, streamKey, trimMinID, 0).Result()
		if errors.Is(err, goredis.Nil) {
			continue
		}
		if err != nil {
			return totalTrimmed, fmt.Errorf("trim redis signal stream %s before %s: %w", streamKey, trimMinID, err)
		}
		totalTrimmed += trimmed
	}
	return totalTrimmed, nil
}

func uniqueSortedStrings(values []string) []string {
	seen := make(map[string]struct{}, len(values))
	unique := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		unique = append(unique, trimmed)
	}
	sort.Strings(unique)
	return unique
}

func signalWindowStartID(since time.Time) string {
	if since.IsZero() {
		return "0-0"
	}
	millis := since.UTC().UnixMilli() - 1
	if millis < 0 {
		millis = 0
	}
	return fmt.Sprintf("%d-0", millis)
}

func nextStreamID(current string) (string, bool) {
	parts := strings.SplitN(strings.TrimSpace(current), "-", 2)
	if len(parts) != 2 {
		return "", false
	}

	millis, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return "", false
	}
	sequence, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		return "", false
	}
	return fmt.Sprintf("%d-%d", millis, sequence+1), true
}

func decodeSignalWindowMessage(message goredis.XMessage) (models.FullLog, bool, error) {
	payload, ok := extractSignalWindowPayload(message.Values)
	if !ok {
		return models.FullLog{}, false, nil
	}

	var metadata map[string]any
	if err := json.Unmarshal([]byte(payload), &metadata); err != nil {
		return models.FullLog{}, false, err
	}

	streamTime := streamMessageTimestamp(message.ID)
	timestamp := firstNonZeroTime(
		parseFlexibleTime(extractNestedString(metadata, "@timestamp")),
		parseFlexibleTime(extractNestedString(metadata, "time_stamp")),
		parseFlexibleTime(extractNestedString(metadata, "timestamp")),
		streamTime,
	)
	signalizedAt := firstNonZeroTime(
		parseFlexibleTime(extractNestedString(metadata, "signalized_at")),
		timestamp,
	)

	signal := strings.TrimSpace(extractNestedString(metadata, "signal"))
	if signal == "" {
		return models.FullLog{}, false, nil
	}

	docID := resolveStreamDocID(metadata)
	if docID == "" {
		return models.FullLog{}, false, nil
	}

	if metadata == nil {
		metadata = make(map[string]any)
	}
	normalizeCompactSignalMetadata(metadata)
	metadata["_stream_id"] = message.ID
	if !signalizedAt.IsZero() && extractNestedString(metadata, "signalized_at") == "" {
		metadata["signalized_at"] = signalizedAt.UTC().Format(time.RFC3339Nano)
	}

	return models.FullLog{
		DocID:        docID,
		Timestamp:    timestamp.UTC(),
		Signal:       signal,
		LogLevel:     resolveStreamLogLevel(metadata),
		SignalizedAt: signalizedAt.UTC(),
		Metadata:     metadata,
	}, true, nil
}

func extractSignalWindowPayload(values map[string]any) (string, bool) {
	for _, field := range []string{"payload", "event"} {
		raw, ok := values[field]
		if !ok {
			continue
		}
		payload := strings.TrimSpace(fmt.Sprint(raw))
		if payload == "" || payload == "<nil>" {
			continue
		}
		return payload, true
	}
	return "", false
}

func streamMessageTimestamp(streamID string) time.Time {
	parts := strings.SplitN(strings.TrimSpace(streamID), "-", 2)
	if len(parts) != 2 {
		return time.Time{}
	}
	millis, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return time.Time{}
	}
	return time.UnixMilli(millis).UTC()
}

func parseFlexibleTime(raw string) time.Time {
	text := strings.TrimSpace(raw)
	if text == "" {
		return time.Time{}
	}
	layouts := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999999",
		"2006-01-02 15:04:05",
	}
	for _, layout := range layouts {
		parsed, err := time.Parse(layout, text)
		if err == nil {
			return parsed.UTC()
		}
	}
	return time.Time{}
}

func firstNonZeroTime(values ...time.Time) time.Time {
	for _, value := range values {
		if !value.IsZero() {
			return value.UTC()
		}
	}
	return time.Time{}
}

func resolveStreamLogLevel(metadata map[string]any) string {
	for _, field := range []string{"log.level", "log_level"} {
		if value := strings.TrimSpace(extractNestedString(metadata, field)); value != "" {
			return value
		}
	}
	return ""
}

func resolveStreamDocID(metadata map[string]any) string {
	sourceRCAID := strings.TrimSpace(extractNestedString(metadata, "source_rca_id"))
	if sourceRCAID != "" {
		return sourceRCAID
	}
	docID := strings.TrimSpace(extractNestedString(metadata, "doc_id"))
	if docID != "" {
		return docID
	}
	sourceID := strings.TrimSpace(extractNestedString(metadata, "source_id"))
	if sourceID != "" {
		return sourceID
	}
	return ""
}

func extractNestedString(metadata map[string]any, path string) string {
	if metadata == nil {
		return ""
	}
	if value, ok := metadata[path]; ok {
		return normalizeStringValue(value)
	}

	current := any(metadata)
	for _, part := range strings.Split(path, ".") {
		next, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		value, exists := next[part]
		if !exists {
			return ""
		}
		current = value
	}
	return normalizeStringValue(current)
}

func normalizeCompactSignalMetadata(metadata map[string]any) {
	if metadata == nil {
		return
	}

	organizationID := strings.TrimSpace(extractNestedString(metadata, "organization_id"))
	if organizationID != "" && extractNestedString(metadata, "event.organization") == "" {
		metadata["event"] = ensureNestedMap(metadata, "event")
		eventMap, _ := metadata["event"].(map[string]any)
		eventMap["organization"] = organizationID
	}

	hostIdentity := strings.TrimSpace(extractNestedString(metadata, "host_identity"))
	if hostIdentity != "" {
		metadata["host"] = ensureNestedMap(metadata, "host")
		hostMap, _ := metadata["host"].(map[string]any)
		if net.ParseIP(hostIdentity) != nil {
			if extractNestedString(metadata, "host.ip") == "" {
				hostMap["ip"] = hostIdentity
			}
		} else if extractNestedString(metadata, "host.name") == "" {
			hostMap["name"] = hostIdentity
		}
	}

	logLevel := strings.TrimSpace(extractNestedString(metadata, "log_level"))
	if logLevel != "" && extractNestedString(metadata, "log.level") == "" {
		metadata["log"] = ensureNestedMap(metadata, "log")
		logMap, _ := metadata["log"].(map[string]any)
		logMap["level"] = logLevel
	}

}

func ensureNestedMap(metadata map[string]any, key string) map[string]any {
	existing, ok := metadata[key].(map[string]any)
	if ok && existing != nil {
		return existing
	}
	created := make(map[string]any)
	metadata[key] = created
	return created
}

func normalizeStringValue(value any) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case string:
		return strings.TrimSpace(typed)
	default:
		text := strings.TrimSpace(fmt.Sprint(value))
		if text == "<nil>" {
			return ""
		}
		return text
	}
}

func deduplicateWindowLogs(logs []models.FullLog) []models.FullLog {
	if len(logs) == 0 {
		return nil
	}

	deduped := make(map[string]models.FullLog, len(logs))
	for _, log := range logs {
		current, exists := deduped[log.DocID]
		if !exists || shouldReplaceWindowLog(current, log) {
			deduped[log.DocID] = log
		}
	}

	merged := make([]models.FullLog, 0, len(deduped))
	for _, log := range deduped {
		merged = append(merged, log)
	}
	sort.Slice(merged, func(i, j int) bool {
		if merged[i].Timestamp.Equal(merged[j].Timestamp) {
			return merged[i].DocID < merged[j].DocID
		}
		return merged[i].Timestamp.Before(merged[j].Timestamp)
	})
	return merged
}

func shouldReplaceWindowLog(current models.FullLog, candidate models.FullLog) bool {
	if candidate.Timestamp.After(current.Timestamp) {
		return true
	}
	if candidate.Timestamp.Before(current.Timestamp) {
		return false
	}
	if candidate.SignalizedAt.After(current.SignalizedAt) {
		return true
	}
	if candidate.SignalizedAt.Before(current.SignalizedAt) {
		return false
	}
	return streamLogCompleteness(candidate) >= streamLogCompleteness(current)
}

func streamLogCompleteness(log models.FullLog) int {
	score := 0
	if strings.TrimSpace(log.DocID) != "" {
		score++
	}
	if strings.TrimSpace(log.Signal) != "" {
		score++
	}
	if strings.TrimSpace(log.LogLevel) != "" {
		score++
	}
	if !log.SignalizedAt.IsZero() {
		score++
	}
	if len(log.Metadata) > 0 {
		score++
	}
	return score
}
