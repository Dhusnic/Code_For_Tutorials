package models

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

type SignalLog struct {
	Signal    string
	LogLevel  string
	DocID     string
	TimeStamp time.Time
}

type signalLogPayload struct {
	Signal    string `json:"signal"`
	LogLevel  string `json:"log_level"`
	DocID     string `json:"doc_id"`
	TimeStamp string `json:"time_stamp"`
}

func (s SignalLog) MarshalJSON() ([]byte, error) {
	return json.Marshal(signalLogPayload{
		Signal:    s.Signal,
		LogLevel:  s.LogLevel,
		DocID:     s.DocID,
		TimeStamp: s.TimeStamp.UTC().Format(time.RFC3339Nano),
	})
}

func (s *SignalLog) UnmarshalJSON(data []byte) error {
	var payload signalLogPayload
	if err := json.Unmarshal(data, &payload); err != nil {
		return fmt.Errorf("parse JSON payload: %w", err)
	}

	parsed, err := time.Parse(time.RFC3339Nano, payload.TimeStamp)
	if err != nil {
		return fmt.Errorf("parse time_stamp %q: %w", payload.TimeStamp, err)
	}

	s.Signal = payload.Signal
	s.LogLevel = payload.LogLevel
	s.DocID = payload.DocID
	s.TimeStamp = parsed.UTC()
	return nil
}

func DecodeSignalLogsPayload(payload []byte) ([]SignalLog, error) {
	if len(payload) == 0 {
		return []SignalLog{}, nil
	}

	var logs []SignalLog
	if err := json.Unmarshal(payload, &logs); err != nil {
		return nil, fmt.Errorf("decode signal logs payload: %w", err)
	}
	return logs, nil
}

func MarshalSignalLogsPayload(logs []SignalLog) ([]byte, error) {
	payload, err := json.Marshal(logs)
	if err != nil {
		return nil, fmt.Errorf("marshal signal logs payload: %w", err)
	}
	return payload, nil
}

type SignalizedLog = SignalLog

type SignalStreamEvent struct {
	OrganizationID string    `json:"organization_id"`
	DocID          string    `json:"doc_id"`
	Signal         string    `json:"signal"`
	LogLevel       string    `json:"log_level"`
	TimeStamp      time.Time `json:"time_stamp"`
	SourceIndex    string    `json:"source_index,omitempty"`
	SourceID       string    `json:"source_id,omitempty"`
}

type FullLog struct {
	DocID     string         `json:"doc_id"`
	Timestamp time.Time      `json:"timestamp"`
	Signal    string         `json:"signal"`
	LogLevel  string         `json:"log_level"`
	Metadata  map[string]any `json:"metadata"`
}

type Rule struct {
	IsEnabled          bool              `json:"is_enabled"`
	ID                 string            `json:"id"`
	OrganizationID     string            `json:"organization_id"`
	RuleType           string            `json:"rule_type"`
	Window             string            `json:"window"`
	MaxGapBetweenSteps string            `json:"max_gap_between_steps"`
	GroupBy            []string          `json:"group_by"`
	Priority           int               `json:"priority"`
	TopologyIDs        []string          `json:"topology_ids,omitempty"`
	RequiredMetadata   map[string]string `json:"required_metadata,omitempty"`
	ShadowMode         bool              `json:"shadow_mode,omitempty"`
	Sequence           []SequenceStep    `json:"sequence"`
	NotSequence        []NegativeStep    `json:"not_sequence"`
	Deduplication      Deduplication     `json:"deduplication"`
}

func (r *Rule) UnmarshalJSON(data []byte) error {
	type ruleAlias Rule
	type ruleEnvelope struct {
		ruleAlias
		IsEnabled *bool `json:"is_enabled"`
	}

	var payload ruleEnvelope
	if err := json.Unmarshal(data, &payload); err != nil {
		return err
	}

	*r = Rule(payload.ruleAlias)
	if payload.IsEnabled == nil {
		r.IsEnabled = true
	} else {
		r.IsEnabled = *payload.IsEnabled
	}
	return nil
}

type SequenceStep struct {
	SignalKey  string           `json:"signal_key,omitempty"`
	SignalKeys []string         `json:"signal_keys,omitempty"`
	AnyOf      []SignalSelector `json:"any_of,omitempty"`
	AllOf      []SignalSelector `json:"all_of,omitempty"`
	MinCount   int              `json:"min_count"`
	Within     string           `json:"within"`
}

type SignalSelector struct {
	SignalKey  string   `json:"signal_key,omitempty"`
	SignalKeys []string `json:"signal_keys,omitempty"`
}

type NegativeStep struct {
	SignalKey string `json:"signal_key"`
}

type Deduplication struct {
	Key    []string `json:"key"`
	Window string   `json:"window"`
}

type ResultLog struct {
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

type MatchStepAudit struct {
	StepIndex     int      `json:"step_index"`
	SignalKey     string   `json:"signal_key"`
	RequiredCount int      `json:"required_count"`
	MatchedCount  int      `json:"matched_count"`
	Within        string   `json:"within"`
	MatchedLogIDs []string `json:"matched_log_ids,omitempty"`
}

type MatchAudit struct {
	RuleType            string            `json:"rule_type"`
	Window              string            `json:"window"`
	MaxGapBetweenSteps  string            `json:"max_gap_between_steps,omitempty"`
	GroupBy             []string          `json:"group_by,omitempty"`
	GroupByValues       map[string]string `json:"group_by_values,omitempty"`
	RequiredMetadata    map[string]string `json:"required_metadata,omitempty"`
	NegativeSignals     []string          `json:"negative_signals,omitempty"`
	DeduplicationKey    []string          `json:"deduplication_key,omitempty"`
	DeduplicationWindow string            `json:"deduplication_window,omitempty"`
	Steps               []MatchStepAudit  `json:"steps,omitempty"`
	MatchedLogIDs       []string          `json:"matched_log_ids,omitempty"`
	MatchedSignals      []string          `json:"matched_signals,omitempty"`
}

type CorrelationResult struct {
	SchemaVersion   int               `json:"schema_version,omitempty"`
	LogID           []ResultLog       `json:"log_id"`
	RuleCompletion  float64           `json:"rule_completion"`
	RuleID          string            `json:"rule_id"`
	SequenceMatch   float64           `json:"sequence_match"`
	IncidentID      string            `json:"incident_id,omitempty"`
	Status          string            `json:"status,omitempty"`
	FirstSeen       *time.Time        `json:"first_seen,omitempty"`
	LastSeen        *time.Time        `json:"last_seen,omitempty"`
	OrganizationID  string            `json:"organization_id,omitempty"`
	GroupByValues   map[string]string `json:"group_by_values,omitempty"`
	MatchedAt       time.Time         `json:"matched_at,omitempty"`
	ResultSignature string            `json:"result_signature,omitempty"`
	Audit           *MatchAudit       `json:"audit,omitempty"`

	Priority   int    `json:"-"`
	DocumentID string `json:"-"`
}

type ProcessingMetrics struct {
	TotalLogsProcessed int64
	TotalRulesMatched  int64
	ProcessingTimeMS   int64
}

type ProcessingCheckpoint struct {
	Checkpoint             time.Time
	CheckpointDocID        string
	SignalPayloadSignature string
	SignalCount            int
	StreamID               string
	RulesSignature         string
}

type IncidentState struct {
	IncidentID          string            `json:"incident_id"`
	OrganizationID      string            `json:"organization_id"`
	RuleID              string            `json:"rule_id"`
	Status              string            `json:"status"`
	FirstSeen           time.Time         `json:"first_seen"`
	LastSeen            time.Time         `json:"last_seen"`
	LastResultSignature string            `json:"last_result_signature"`
	GroupByValues       map[string]string `json:"group_by_values,omitempty"`
	Snapshot            IncidentSnapshot  `json:"snapshot"`
}

type IncidentSnapshot struct {
	SchemaVersion  int         `json:"schema_version,omitempty"`
	LogID          []ResultLog `json:"log_id,omitempty"`
	RuleCompletion float64     `json:"rule_completion,omitempty"`
	SequenceMatch  float64     `json:"sequence_match,omitempty"`
	MatchedAt      time.Time   `json:"matched_at,omitempty"`
	Audit          *MatchAudit `json:"audit,omitempty"`
}

type correlationResultIdentity struct {
	OrganizationID string   `json:"organization_id"`
	RuleID         string   `json:"rule_id"`
	LogIDs         []string `json:"log_ids"`
}

type correlationEventIdentity struct {
	OrganizationID string `json:"organization_id"`
	IncidentID     string `json:"incident_id"`
	Status         string `json:"status"`
	Signature      string `json:"signature"`
}

type incidentEpisodeIdentity struct {
	IncidentKey      string    `json:"incident_key"`
	EpisodeStartedAt time.Time `json:"episode_started_at"`
}

func (r *CorrelationResult) EnsureDocumentID() error {
	if r == nil {
		return fmt.Errorf("correlation result is nil")
	}
	if r.DocumentID != "" {
		return nil
	}
	if r.IncidentID != "" {
		r.DocumentID = r.IncidentID
		return nil
	}
	if r.OrganizationID == "" {
		return fmt.Errorf("organization id must not be empty")
	}
	if r.RuleID == "" {
		return fmt.Errorf("rule id must not be empty")
	}

	logIDs := make([]string, 0, len(r.LogID))
	for _, entry := range r.LogID {
		if entry.ID == "" {
			return fmt.Errorf("result log id must not be empty")
		}
		logIDs = append(logIDs, entry.ID)
	}
	sort.Strings(logIDs)

	payload, err := json.Marshal(correlationResultIdentity{
		OrganizationID: r.OrganizationID,
		RuleID:         r.RuleID,
		LogIDs:         logIDs,
	})
	if err != nil {
		return fmt.Errorf("marshal correlation result identity: %w", err)
	}

	sum := sha256.Sum256(payload)
	r.DocumentID = hex.EncodeToString(sum[:])
	return nil
}

func (r *CorrelationResult) EnsureResultSignature() error {
	if r == nil {
		return fmt.Errorf("correlation result is nil")
	}
	if r.ResultSignature != "" {
		return nil
	}

	logIDs := make([]string, 0, len(r.LogID))
	for _, entry := range r.LogID {
		if entry.ID == "" {
			return fmt.Errorf("result log id must not be empty")
		}
		logIDs = append(logIDs, entry.ID)
	}
	sort.Strings(logIDs)

	payload, err := json.Marshal(struct {
		RuleID         string   `json:"rule_id"`
		LogIDs         []string `json:"log_ids"`
		RuleCompletion float64  `json:"rule_completion"`
		SequenceMatch  float64  `json:"sequence_match"`
	}{
		RuleID:         r.RuleID,
		LogIDs:         logIDs,
		RuleCompletion: r.RuleCompletion,
		SequenceMatch:  r.SequenceMatch,
	})
	if err != nil {
		return fmt.Errorf("marshal correlation result signature: %w", err)
	}

	sum := sha256.Sum256(payload)
	r.ResultSignature = hex.EncodeToString(sum[:])
	return nil
}

func BuildIncidentID(organizationID, ruleID string, groupByValues map[string]string) (string, error) {
	if organizationID == "" {
		return "", fmt.Errorf("organization id must not be empty")
	}
	if ruleID == "" {
		return "", fmt.Errorf("rule id must not be empty")
	}

	normalized := make(map[string]string, len(groupByValues))
	for key, value := range groupByValues {
		normalized[key] = value
	}

	payload, err := json.Marshal(struct {
		OrganizationID string            `json:"organization_id"`
		RuleID         string            `json:"rule_id"`
		GroupByValues  map[string]string `json:"group_by_values"`
	}{
		OrganizationID: organizationID,
		RuleID:         ruleID,
		GroupByValues:  normalized,
	})
	if err != nil {
		return "", fmt.Errorf("marshal incident identity: %w", err)
	}

	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func BuildIncidentEpisodeID(incidentKey string, episodeStartedAt time.Time) (string, error) {
	trimmedKey := strings.TrimSpace(incidentKey)
	if trimmedKey == "" {
		return "", fmt.Errorf("incident key must not be empty")
	}
	if episodeStartedAt.IsZero() {
		return "", fmt.Errorf("episode_started_at must not be zero")
	}

	payload, err := json.Marshal(incidentEpisodeIdentity{
		IncidentKey:      trimmedKey,
		EpisodeStartedAt: episodeStartedAt.UTC(),
	})
	if err != nil {
		return "", fmt.Errorf("marshal incident episode identity: %w", err)
	}

	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func BuildCorrelationEventDocumentID(organizationID, incidentID, status, signature string) (string, error) {
	if organizationID == "" {
		return "", fmt.Errorf("organization id must not be empty")
	}
	if incidentID == "" {
		return "", fmt.Errorf("incident id must not be empty")
	}
	if status == "" {
		return "", fmt.Errorf("status must not be empty")
	}
	if signature == "" {
		return "", fmt.Errorf("signature must not be empty")
	}

	payload, err := json.Marshal(correlationEventIdentity{
		OrganizationID: organizationID,
		IncidentID:     incidentID,
		Status:         status,
		Signature:      signature,
	})
	if err != nil {
		return "", fmt.Errorf("marshal correlation event identity: %w", err)
	}

	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func NormalizeCorrelationResults(results []CorrelationResult) ([]CorrelationResult, int) {
	if len(results) < 2 {
		normalized := append([]CorrelationResult(nil), results...)
		sortCorrelationResults(normalized)
		return normalized, 0
	}

	candidates := append([]CorrelationResult(nil), results...)
	sort.Slice(candidates, func(i, j int) bool {
		return strongerConflictResult(candidates[i], candidates[j])
	})

	resolved := make([]CorrelationResult, 0, len(candidates))
	suppressed := 0
	for _, candidate := range candidates {
		if isContainedByAccepted(candidate, resolved) {
			suppressed++
			continue
		}
		resolved = append(resolved, candidate)
	}

	sortCorrelationResults(resolved)
	return resolved, suppressed
}

func sortCorrelationResults(results []CorrelationResult) {
	sort.Slice(results, func(i, j int) bool {
		if results[i].Priority != results[j].Priority {
			return results[i].Priority < results[j].Priority
		}
		if results[i].RuleCompletion != results[j].RuleCompletion {
			return results[i].RuleCompletion > results[j].RuleCompletion
		}
		if results[i].SequenceMatch != results[j].SequenceMatch {
			return results[i].SequenceMatch > results[j].SequenceMatch
		}
		return results[i].RuleID < results[j].RuleID
	})
}

func strongerConflictResult(left, right CorrelationResult) bool {
	if left.RuleCompletion != right.RuleCompletion {
		return left.RuleCompletion > right.RuleCompletion
	}
	if left.SequenceMatch != right.SequenceMatch {
		return left.SequenceMatch > right.SequenceMatch
	}
	if len(left.LogID) != len(right.LogID) {
		return len(left.LogID) > len(right.LogID)
	}
	if left.Priority != right.Priority {
		return left.Priority < right.Priority
	}
	return left.RuleID < right.RuleID
}

func isContainedByAccepted(candidate CorrelationResult, accepted []CorrelationResult) bool {
	if len(candidate.LogID) == 0 {
		return false
	}
	for _, current := range accepted {
		if sameOrganization(candidate, current) && resultLogSubset(candidate.LogID, current.LogID) {
			return true
		}
	}
	return false
}

func sameOrganization(left, right CorrelationResult) bool {
	if left.OrganizationID == "" || right.OrganizationID == "" {
		return true
	}
	return left.OrganizationID == right.OrganizationID
}

func resultLogSubset(candidate, accepted []ResultLog) bool {
	acceptedIDs := make(map[string]struct{}, len(accepted))
	for _, entry := range accepted {
		acceptedIDs[entry.ID] = struct{}{}
	}
	for _, entry := range candidate {
		if _, ok := acceptedIDs[entry.ID]; !ok {
			return false
		}
	}
	return true
}
