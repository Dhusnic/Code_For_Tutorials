package writer

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

var (
	levelAliasMap = map[string]map[string]struct{}{
		"critical": map[string]struct{}{"critical": {}, "crit": {}, "fatal": {}, "panic": {}, "alert": {}, "emerg": {}, "emergency": {}, "severe": {}, "sev": {}},
		"error":    map[string]struct{}{"error": {}, "err": {}, "failure": {}, "failed": {}},
		"warning":  map[string]struct{}{"warning": {}, "warn": {}, "wrn": {}},
		"info":     map[string]struct{}{"info": {}, "inf": {}, "information": {}, "informational": {}, "notice": {}},
		"debug":    map[string]struct{}{"debug": {}, "dbg": {}, "trace": {}, "verbose": {}},
	}
	syslogPriorityMap = map[int]string{
		0: "critical",
		1: "critical",
		2: "critical",
		3: "error",
		4: "warning",
		5: "info",
		6: "info",
		7: "debug",
	}
	levelCompactPattern = regexp.MustCompile(`[\s._-]+`)
)

const defaultRetryOnConflict = 5

// BulkActionFactory builds idempotent Elasticsearch bulk update actions.
type BulkActionFactory struct{}

// BuildSourceUpsert returns an idempotent raw-document upsert for Kafka-origin events.
func (BulkActionFactory) BuildSourceUpsert(
	targetIndex string,
	sourceID string,
	sourceDoc map[string]any,
) map[string]any {
	return buildUpdateAction(targetIndex, sourceID, cloneMap(sourceDoc), true)
}

// BuildSourceUpdate returns an update-only action for an existing source document.
func (BulkActionFactory) BuildSourceUpdate(
	targetIndex string,
	documentID string,
	sourceDoc map[string]any,
) map[string]any {
	return buildUpdateAction(targetIndex, documentID, cloneMap(sourceDoc), false)
}

// BuildMatchedSourceUpdate returns an update-only action for an existing source document with signal fields.
func (BulkActionFactory) BuildMatchedSourceUpdate(
	sourceIndex string,
	targetIndex string,
	documentID string,
	sourceDoc map[string]any,
	selectedSignal map[string]any,
) map[string]any {
	return buildMatchedUpdateAction(sourceIndex, targetIndex, documentID, sourceDoc, selectedSignal, true, false)
}

// Build returns one update action using the source id or a derived target id.
func (BulkActionFactory) Build(
	sourceIndex string,
	targetIndex string,
	sourceID string,
	sourceDoc map[string]any,
	selectedSignal map[string]any,
	useSourceID bool,
) map[string]any {
	return buildMatchedUpdateAction(sourceIndex, targetIndex, sourceID, sourceDoc, selectedSignal, useSourceID, true)
}

func buildUpdateAction(targetIndex string, documentID string, payload map[string]any, docAsUpsert bool) map[string]any {
	return map[string]any{
		"_op_type":          "update",
		"_index":            targetIndex,
		"_id":               documentID,
		"doc":               payload,
		"doc_as_upsert":     docAsUpsert,
		"retry_on_conflict": defaultRetryOnConflict,
	}
}

func buildMatchedUpdateAction(
	sourceIndex string,
	targetIndex string,
	documentID string,
	sourceDoc map[string]any,
	selectedSignal map[string]any,
	useSourceID bool,
	docAsUpsert bool,
) map[string]any {
	targetID := documentID
	if !useSourceID {
		targetID = targetIDFor(sourceIndex, documentID)
	}

	payload := cloneMap(sourceDoc)
	payload["source_index"] = sourceIndex
	payload["source_rca_id"] = firstNonEmptyString(sourceDoc["source_rca_id"], documentID)
	payload["signal"] = selectedSignal["signal"]
	payload["signal_present"] = true
	if matchedAt, ok := selectedSignal["matched_at"]; ok {
		payload["signalized_at"] = matchedAt
	}

	logObject, _ := payload["log"].(map[string]any)
	currentLevel := any(nil)
	if logObject != nil {
		currentLevel = logObject["level"]
	}

	normalizedCurrentLevel := normalizeLevel(currentLevel)
	normalizedRuleLevel := normalizeLevel(selectedSignal["level"])
	if normalizedRuleLevel == "" {
		normalizedRuleLevel = strings.ToLower(strings.TrimSpace(fmt.Sprint(selectedSignal["level"])))
	}

	newLogObject := cloneMap(logObject)
	newLogObject["level"] = normalizedCurrentLevel
	if normalizedCurrentLevel == "" {
		newLogObject["level"] = normalizedRuleLevel
	}
	payload["log"] = newLogObject

	return map[string]any{
		"_op_type":          "update",
		"_index":            targetIndex,
		"_id":               targetID,
		"doc":               payload,
		"doc_as_upsert":     docAsUpsert,
		"retry_on_conflict": defaultRetryOnConflict,
	}
}

func firstNonEmptyString(values ...any) string {
	for _, value := range values {
		text := strings.TrimSpace(fmt.Sprint(value))
		if text != "" && text != "<nil>" {
			return text
		}
	}
	return ""
}

func targetIDFor(sourceIndex string, sourceID string) string {
	sum := sha256.Sum256([]byte(sourceIndex + ":" + sourceID))
	return hex.EncodeToString(sum[:])
}

func normalizeLevel(value any) string {
	if value == nil {
		return ""
	}
	if _, ok := value.(bool); ok {
		return ""
	}

	switch typed := value.(type) {
	case int:
		return syslogPriorityMap[typed]
	case int8:
		return syslogPriorityMap[int(typed)]
	case int16:
		return syslogPriorityMap[int(typed)]
	case int32:
		return syslogPriorityMap[int(typed)]
	case int64:
		return syslogPriorityMap[int(typed)]
	}

	text := strings.ToLower(strings.TrimSpace(fmt.Sprint(value)))
	if text == "" {
		return ""
	}
	if number, err := strconv.Atoi(text); err == nil {
		return syslogPriorityMap[number]
	}

	compact := levelCompactPattern.ReplaceAllString(text, "")
	for canonical, aliases := range levelAliasMap {
		if _, ok := aliases[compact]; ok {
			return canonical
		}
	}
	return ""
}

// NormalizeLogLevel exposes the shared log-level normalization logic.
func NormalizeLogLevel(value any) string {
	return normalizeLevel(value)
}

func cloneMap(source map[string]any) map[string]any {
	if source == nil {
		return map[string]any{}
	}
	cloned := make(map[string]any, len(source))
	for key, value := range source {
		cloned[key] = value
	}
	return cloned
}
