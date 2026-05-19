package models

import "time"

type EvidenceLog struct {
	ID           string    `json:"id"`
	Severity     string    `json:"severity"`
	SourceIndex  string    `json:"source_index,omitempty"`
	Signal       string    `json:"signal,omitempty"`
	Timestamp    time.Time `json:"timestamp,omitempty"`
	SignalizedAt time.Time `json:"signalized_at,omitempty"`
	ServiceName  string    `json:"service_name,omitempty"`
	HostName     string    `json:"host_name,omitempty"`
	HostIP       string    `json:"host_ip,omitempty"`
	HostIPs      []string  `json:"host_ips,omitempty"`
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

type CorrelationEvent struct {
	SchemaVersion   int               `json:"schema_version,omitempty"`
	LogID           []EvidenceLog     `json:"log_id"`
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
	CorrelatedAt    time.Time         `json:"correlated_at,omitempty"`
	IsProcessed     int               `json:"is_processed"`
	ResultSignature string            `json:"result_signature,omitempty"`
	Audit           *MatchAudit       `json:"audit,omitempty"`
	DocumentID      string            `json:"-"`
	DocumentIndex   string            `json:"-"`
	SortValues      []any             `json:"-"`
}

type CorrelationEventRef struct {
	DocumentID      string
	DocumentIndex   string
	ResultSignature string
}

type SequenceStep struct {
	SignalKey  string         `json:"signal_key,omitempty"`
	SignalKeys []string       `json:"signal_keys,omitempty"`
	AllOf      []SequenceStep `json:"all_of,omitempty"`
	MinCount   int            `json:"min_count"`
	Within     string         `json:"within"`
}

type NegativeStep struct {
	SignalKey string `json:"signal_key"`
}

type Rule struct {
	ID                 string         `json:"id"`
	OrganizationID     string         `json:"organization_id"`
	RuleType           string         `json:"rule_type"`
	Window             string         `json:"window"`
	MaxGapBetweenSteps string         `json:"max_gap_between_steps"`
	GroupBy            []string       `json:"group_by"`
	Priority           int            `json:"priority"`
	TopologyIDs        []string       `json:"topology_ids,omitempty"`
	Sequence           []SequenceStep `json:"sequence"`
	NotSequence        []NegativeStep `json:"not_sequence,omitempty"`
	RecoverySignals    []string       `json:"recovery_signals,omitempty"`
}

type TopologyService struct {
	ServiceName string `json:"service_name,omitempty"`
	DeviceIP    string `json:"device_ip,omitempty"`
	HostName    string `json:"host_name,omitempty"`
}

type TopologyDependency struct {
	From     string  `json:"from"`
	To       string  `json:"to"`
	Relation string  `json:"relation,omitempty"`
	Weight   float64 `json:"weight,omitempty"`
}

type TopologyDeviceService struct {
	ServiceName  string   `json:"service_name"`
	Role         string   `json:"role,omitempty"`
	UpstreamFor  []string `json:"upstream_for,omitempty"`
	ReceivesFrom []string `json:"receives_from,omitempty"`
	DependsOn    []string `json:"depends_on,omitempty"`
}

type TopologyDevice struct {
	DeviceIP string                  `json:"device_ip,omitempty"`
	HostName string                  `json:"host_name,omitempty"`
	Services []TopologyDeviceService `json:"services,omitempty"`
}

type TopologyServiceRelation struct {
	FromService string  `json:"from_service,omitempty"`
	FromIP      string  `json:"from_ip,omitempty"`
	ToService   string  `json:"to_service,omitempty"`
	ToIP        string  `json:"to_ip,omitempty"`
	Relation    string  `json:"relation,omitempty"`
	Weight      float64 `json:"weight,omitempty"`
}

type OrganizationTopology struct {
	TopologyID       string                    `json:"-"`
	Services         []TopologyService         `json:"services"`
	Dependencies     []TopologyDependency      `json:"dependencies"`
	Devices          []TopologyDevice          `json:"devices,omitempty"`
	ServiceRelations []TopologyServiceRelation `json:"service_relations,omitempty"`
}

type TopologyDocument struct {
	SchemaVersion int                                        `json:"schema_version,omitempty"`
	Organizations map[string]map[string]OrganizationTopology `json:"organizations"`
}

type ScoreWeights struct {
	SequenceMatch    float64 `json:"sequence_match"`
	DependencyMatch  float64 `json:"dependency_match"`
	TimeProximity    float64 `json:"time_proximity"`
	SignalSeverity   float64 `json:"signal_severity"`
	RuleCompleteness float64 `json:"rule_completeness"`
}

type ScoreBreakdown struct {
	SequenceMatch          float64 `json:"sequence_match"`
	DependencyMatch        float64 `json:"dependency_match"`
	TimeProximity          float64 `json:"time_proximity"`
	SignalSeverity         float64 `json:"signal_severity"`
	RuleCompleteness       float64 `json:"rule_completeness"`
	TopologyCoverage       float64 `json:"topology_coverage"`
	IdentityConfidence     float64 `json:"identity_confidence"`
	CompletedStepCoverage  float64 `json:"completed_step_coverage"`
	ExpectedSignalSeverity float64 `json:"expected_signal_severity,omitempty"`
	SeverityAlignment      float64 `json:"severity_alignment,omitempty"`
	ContradictionPenalty   float64 `json:"contradiction_penalty"`
	FinalWeighted          float64 `json:"final_weighted"`
}

type ScoreResult struct {
	Classification        string                  `json:"classification"`
	ConfidenceScore       float64                 `json:"confidence_score"`
	Breakdown             ScoreBreakdown          `json:"score_breakdown"`
	BelowThresholdReasons []string                `json:"below_threshold_reasons,omitempty"`
	InvolvedServices      []string                `json:"involved_services,omitempty"`
	MatchedDocIDs         []string                `json:"matched_doc_ids,omitempty"`
	ContradictionEvidence []ContradictionEvidence `json:"contradiction_evidence,omitempty"`
}

type ContradictionEvidence struct {
	Kind        string    `json:"kind"`
	Reason      string    `json:"reason"`
	DocID       string    `json:"doc_id,omitempty"`
	SourceIndex string    `json:"source_index,omitempty"`
	Timestamp   time.Time `json:"timestamp,omitempty"`
	Signal      string    `json:"signal,omitempty"`
	Severity    string    `json:"severity,omitempty"`
	ServiceName string    `json:"service_name,omitempty"`
	HostName    string    `json:"host_name,omitempty"`
	HostIP      string    `json:"host_ip,omitempty"`
	Message     string    `json:"message,omitempty"`
	Relevance   float64   `json:"relevance"`
	Penalty     float64   `json:"penalty"`
}

type LLMExplanation struct {
	Provider               string   `json:"provider,omitempty"`
	Model                  string   `json:"model,omitempty"`
	RootCause              string   `json:"root_cause,omitempty"`
	NaturalLanguageSummary string   `json:"natural_language_summary,omitempty"`
	AffectedServices       []string `json:"affected_services,omitempty"`
	Evidence               []string `json:"evidence,omitempty"`
	NextChecks             []string `json:"next_checks,omitempty"`
	Error                  string   `json:"error,omitempty"`
}

type RCARecord struct {
	SchemaVersion                int                     `json:"schema_version"`
	CorrelationSchemaVersion     int                     `json:"correlation_schema_version,omitempty"`
	IncidentID                   string                  `json:"incident_id"`
	OrganizationID               string                  `json:"organization_id,omitempty"`
	TopologyID                   string                  `json:"topology_id,omitempty"`
	RuleID                       string                  `json:"rule_id,omitempty"`
	Status                       string                  `json:"status,omitempty"`
	Classification               string                  `json:"classification,omitempty"`
	ConfidenceScore              float64                 `json:"confidence_score,omitempty"`
	ScoreBreakdown               ScoreBreakdown          `json:"score_breakdown"`
	BelowThresholdReasons        []string                `json:"below_threshold_reasons,omitempty"`
	InvolvedServices             []string                `json:"involved_services,omitempty"`
	TriggerMatchedDocIDs         []string                `json:"trigger_matched_doc_ids,omitempty"`
	TriggerMatchedLogs           []EvidenceLog           `json:"trigger_matched_logs,omitempty"`
	MatchedDocIDs                []string                `json:"matched_doc_ids,omitempty"`
	MatchedLogs                  []EvidenceLog           `json:"matched_logs,omitempty"`
	ContradictionEvidence        []ContradictionEvidence `json:"contradiction_evidence,omitempty"`
	GroupByValues                map[string]string       `json:"group_by_values,omitempty"`
	FirstMatchedAt               time.Time               `json:"first_matched_at,omitempty"`
	FirstCorrelatedAt            time.Time               `json:"first_correlated_at,omitempty"`
	FirstRCAGeneratedAt          time.Time               `json:"first_rca_generated_at,omitempty"`
	MatchedAt                    time.Time               `json:"matched_at,omitempty"`
	CorrelatedAt                 time.Time               `json:"correlated_at,omitempty"`
	FirstSeen                    *time.Time              `json:"first_seen,omitempty"`
	LastSeen                     *time.Time              `json:"last_seen,omitempty"`
	ResultSignature              string                  `json:"result_signature,omitempty"`
	LastProcessedResultSignature string                  `json:"last_processed_result_signature,omitempty"`
	Audit                        *MatchAudit             `json:"audit,omitempty"`
	LLM                          *LLMExplanation         `json:"llm,omitempty"`
	RCAGeneratedAt               time.Time               `json:"rca_generated_at,omitempty"`
	UpdatedAt                    time.Time               `json:"updated_at,omitempty"`
}

type RCAOutputDocument struct {
	UpdatedAt time.Time   `json:"updated_at,omitempty"`
	Items     []RCARecord `json:"items"`
}

type ReaderCheckpoint struct {
	SearchAfter []any     `json:"search_after,omitempty"`
	UpdatedAt   time.Time `json:"updated_at,omitempty"`
}

type RelatedLog struct {
	Index          string         `json:"index,omitempty"`
	DocID          string         `json:"doc_id,omitempty"`
	Timestamp      time.Time      `json:"timestamp,omitempty"`
	OrganizationID string         `json:"organization_id,omitempty"`
	ServiceName    string         `json:"service_name,omitempty"`
	HostName       string         `json:"host_name,omitempty"`
	HostIP         string         `json:"host_ip,omitempty"`
	HostIPs        []string       `json:"host_ips,omitempty"`
	Severity       string         `json:"severity,omitempty"`
	Signal         string         `json:"signal,omitempty"`
	Message        string         `json:"message,omitempty"`
	Source         map[string]any `json:"source,omitempty"`
}

type ExplanationRequest struct {
	Event       CorrelationEvent      `json:"event"`
	Rule        *Rule                 `json:"rule,omitempty"`
	Score       ScoreResult           `json:"score"`
	Topology    *OrganizationTopology `json:"topology,omitempty"`
	MatchedLogs []RelatedLog          `json:"matched_logs,omitempty"`
	NearbyLogs  []RelatedLog          `json:"nearby_logs,omitempty"`
}
