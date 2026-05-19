package scoring

import (
	"testing"
	"time"

	"log_rca_engine/internal/models"
)

func defaultWeights() models.ScoreWeights {
	return models.ScoreWeights{
		SequenceMatch:    0.30,
		DependencyMatch:  0.25,
		TimeProximity:    0.15,
		SignalSeverity:   0.15,
		RuleCompleteness: 0.15,
	}
}

func TestScoreStrongDirectDependencyExceedsThreshold(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		GroupByValues:  map[string]string{"service.name": "api"},
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Signal: "s1", Timestamp: now, ServiceName: "api", HostName: "api-1"},
			{ID: "2", Severity: "error", Signal: "s2", Timestamp: now.Add(15 * time.Second), ServiceName: "rabbitmq", HostName: "mq-1"},
			{ID: "3", Severity: "critical", Signal: "s3", Timestamp: now.Add(30 * time.Second), ServiceName: "mongodb", HostName: "db-1"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "s1", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, SignalKey: "s2", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
				{StepIndex: 2, SignalKey: "s3", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"3"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-1",
		MaxGapBetweenSteps: "2m",
		Window:             "10m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "api"},
			{ServiceName: "rabbitmq"},
			{ServiceName: "mongodb"},
		},
		Dependencies: []models.TopologyDependency{
			{From: "api", To: "rabbitmq"},
			{From: "rabbitmq", To: "mongodb"},
		},
	}, nil)

	if result.Classification != ClassificationConfirmed {
		t.Fatalf("expected confirmed RCA, got %#v", result)
	}
	if result.ConfidenceScore <= 7 {
		t.Fatalf("expected score above 7, got %#v", result)
	}
}

func TestScoreDisconnectedEvidenceFallsBelowThreshold(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  0.6,
		RuleCompletion: 0.7,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "warning", Timestamp: now, ServiceName: "api"},
			{ID: "2", Severity: "warning", Timestamp: now.Add(4 * time.Minute), ServiceName: "billing"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "s1", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, SignalKey: "s2", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-1",
		MaxGapBetweenSteps: "2m",
		Window:             "10m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "api"},
			{ServiceName: "billing"},
		},
		Dependencies: []models.TopologyDependency{},
	}, nil)

	if result.Classification != ClassificationProbable {
		t.Fatalf("expected probable cause, got %#v", result)
	}
	if result.ConfidenceScore >= 7 {
		t.Fatalf("expected score below 7, got %#v", result)
	}
	if len(result.BelowThresholdReasons) == 0 {
		t.Fatalf("expected below-threshold reasons")
	}
}

func TestTimeProximityRewardsTighterSequence(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()
	rule := &models.Rule{
		ID:                 "rule-1",
		MaxGapBetweenSteps: "2m",
		Window:             "10m",
	}
	topology := &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "api"}},
	}

	tight := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "error", Timestamp: now, ServiceName: "api"},
			{ID: "2", Severity: "error", Timestamp: now.Add(10 * time.Second), ServiceName: "api"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "s1", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, SignalKey: "s2", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, rule, topology, nil)

	loose := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "error", Timestamp: now, ServiceName: "api"},
			{ID: "2", Severity: "error", Timestamp: now.Add(90 * time.Second), ServiceName: "api"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "s1", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, SignalKey: "s2", MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, rule, topology, nil)

	if tight.Breakdown.TimeProximity <= loose.Breakdown.TimeProximity {
		t.Fatalf("expected tighter sequence to score higher, tight=%#v loose=%#v", tight.Breakdown, loose.Breakdown)
	}
}

func TestSignalSeverityUsesMaxAndAverage(t *testing.T) {
	score := computeSignalSeverityScore([]models.EvidenceLog{
		{Severity: "warning"},
		{Severity: "critical"},
		{Severity: "info"},
	})
	if score <= 0.7 || score >= 1.0 {
		t.Fatalf("expected blended severity score between 0.7 and 1.0, got %f", score)
	}
}

func TestRuleCompletenessDropsWithIncompleteTopologyCoverage(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Timestamp: now, ServiceName: "api"},
			{ID: "2", Severity: "critical", Timestamp: now.Add(10 * time.Second), ServiceName: "billing"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:     "rule-1",
		Window: "10m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "api"}},
	}, nil)

	if result.Breakdown.TopologyCoverage != 0.5 {
		t.Fatalf("expected topology coverage 0.5, got %#v", result.Breakdown)
	}
	if result.Breakdown.RuleCompleteness >= 1 {
		t.Fatalf("expected rule completeness to be reduced, got %#v", result.Breakdown)
	}
}

func TestScoreUsesMatchingDeviceIPFromHostIPCandidates(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{
				ID:          "1",
				Severity:    "critical",
				Timestamp:   now,
				ServiceName: "api",
				HostIP:      "172.16.1.10",
				HostIPs:     []string{"172.16.1.10", "10.0.4.72"},
			},
			{
				ID:          "2",
				Severity:    "critical",
				Timestamp:   now.Add(10 * time.Second),
				ServiceName: "mongodb",
				HostIP:      "192.168.10.20",
				HostIPs:     []string{"192.168.10.20", "10.0.4.73"},
			},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-ip",
		MaxGapBetweenSteps: "2m",
		Window:             "10m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "api", DeviceIP: "10.0.4.72"},
			{ServiceName: "mongodb", DeviceIP: "10.0.4.73"},
		},
		ServiceRelations: []models.TopologyServiceRelation{
			{FromService: "api", FromIP: "10.0.4.72", ToService: "mongodb", ToIP: "10.0.4.73", Relation: "depends_on"},
		},
	}, nil)

	if result.Breakdown.TopologyCoverage != 1 {
		t.Fatalf("expected topology coverage 1, got %#v", result.Breakdown)
	}
	if result.Breakdown.DependencyMatch < 0.8 || result.Breakdown.DependencyMatch >= 1 {
		t.Fatalf("expected strong but direction-aware dependency score using matched device IPs, got %#v", result.Breakdown)
	}
	if len(result.InvolvedServices) != 2 || result.InvolvedServices[0] != "10.0.4.72::api" {
		t.Fatalf("expected involved identities to use topology-matched device IPs, got %#v", result.InvolvedServices)
	}
}

func TestScoreUsesServiceRelationsForServicesOnSameIP(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  0.9,
		RuleCompletion: 0.9,
		LogID: []models.EvidenceLog{
			{
				ID:          "1",
				Severity:    "error",
				Timestamp:   now,
				ServiceName: "nginx",
				HostIP:      "10.0.4.72",
			},
			{
				ID:          "2",
				Severity:    "critical",
				Timestamp:   now.Add(10 * time.Second),
				ServiceName: "api",
				HostIP:      "10.0.4.72",
			},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, MatchedCount: 1, RequiredCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-same-ip",
		MaxGapBetweenSteps: "2m",
		Window:             "10m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "nginx", DeviceIP: "10.0.4.72"},
			{ServiceName: "api", DeviceIP: "10.0.4.72"},
		},
		ServiceRelations: []models.TopologyServiceRelation{
			{FromService: "nginx", FromIP: "10.0.4.72", ToService: "api", ToIP: "10.0.4.72", Relation: "upstream"},
		},
	}, nil)

	if result.Breakdown.TopologyCoverage != 1 {
		t.Fatalf("expected same-IP service topology coverage 1, got %#v", result.Breakdown)
	}
	if result.Breakdown.DependencyMatch != 1 {
		t.Fatalf("expected same-IP service relation to count as direct dependency, got %#v", result.Breakdown)
	}
	if len(result.InvolvedServices) != 2 || result.InvolvedServices[0] != "10.0.4.72::nginx" || result.InvolvedServices[1] != "10.0.4.72::api" {
		t.Fatalf("expected composite same-IP service identities, got %#v", result.InvolvedServices)
	}
}

func TestDependencyScorePrefersDependencyToDependentFailureFlow(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()
	rule := &models.Rule{ID: "rule-flow", Window: "10m", MaxGapBetweenSteps: "2m"}
	topology := &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "api", DeviceIP: "10.0.4.72"},
			{ServiceName: "mongodb", DeviceIP: "10.0.4.73"},
		},
		Dependencies: []models.TopologyDependency{
			{From: "10.0.4.72::api", To: "10.0.4.73::mongodb", Relation: "depends_on"},
		},
	}

	forward := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "error", Timestamp: now, ServiceName: "api", HostIP: "10.0.4.72"},
			{ID: "2", Severity: "critical", Timestamp: now.Add(20 * time.Second), ServiceName: "mongodb", HostIP: "10.0.4.73"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, rule, topology, nil)

	reverse := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.73"},
			{ID: "2", Severity: "error", Timestamp: now.Add(20 * time.Second), ServiceName: "api", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, rule, topology, nil)

	if reverse.Breakdown.DependencyMatch <= forward.Breakdown.DependencyMatch {
		t.Fatalf("expected dependency-to-dependent flow to score higher, forward=%#v reverse=%#v", forward.Breakdown, reverse.Breakdown)
	}
}

func TestScoreAppliesContradictionPenaltyFromNearbyRecoverySignal(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Signal: "mongodb_auth_failed", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "2", Severity: "critical", Signal: "mongodb_host_unreachable", Timestamp: now.Add(20 * time.Second), ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "2m",
			NegativeSignals:    []string{"mongodb_auth_success"},
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_auth_failed", RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, SignalKey: "mongodb_host_unreachable", RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-contradiction",
		Window:             "10m",
		MaxGapBetweenSteps: "2m",
		NotSequence:        []models.NegativeStep{{SignalKey: "mongodb_auth_success"}},
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, []models.RelatedLog{
		{
			DocID:       "nearby-1",
			Timestamp:   now.Add(30 * time.Second),
			ServiceName: "mongodb",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_auth_success",
			Severity:    "info",
			Message:     "authentication recovered successfully",
		},
	})

	if result.Classification != ClassificationProbable {
		t.Fatalf("expected contradiction penalty to block confirmation, got %#v", result)
	}
	if result.Breakdown.ContradictionPenalty >= 1 {
		t.Fatalf("expected contradiction penalty below 1, got %#v", result.Breakdown)
	}
	if len(result.ContradictionEvidence) != 1 {
		t.Fatalf("expected one contradiction evidence item, got %#v", result.ContradictionEvidence)
	}
	if result.ContradictionEvidence[0].Kind != "explicit_not_sequence" {
		t.Fatalf("expected explicit contradiction evidence, got %#v", result.ContradictionEvidence[0])
	}
}

func TestScoreIgnoresGenericSuccessMessageAsRecoveryContradiction(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_user_not_found", RequiredCount: 1, MatchedCount: 1, Within: "5m", MatchedLogIDs: []string{"1"}},
			},
		},
	}, &models.Rule{
		ID:     "rule-generic-success",
		Window: "15m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, []models.RelatedLog{
		{
			DocID:       "systemd-success",
			Timestamp:   now.Add(5 * time.Second),
			ServiceName: "systemd",
			HostIP:      "10.0.4.72",
			Severity:    "info",
			Message:     "Deactivated successfully.",
		},
	})

	if result.Breakdown.ContradictionPenalty != 1 {
		t.Fatalf("expected generic success message to be ignored, got %#v", result.Breakdown)
	}
	if len(result.ContradictionEvidence) != 0 {
		t.Fatalf("expected no contradiction evidence, got %#v", result.ContradictionEvidence)
	}
}

func TestScoreCanConfirmWarningEvidenceWhenOtherSignalsAreStrong(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 4)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "warning", Signal: "mongodb_host_unreachable", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_host_unreachable", RequiredCount: 1, MatchedCount: 1, Within: "5m", MatchedLogIDs: []string{"1"}},
			},
		},
	}, &models.Rule{
		ID:       "rule-critical-expected",
		Window:   "15m",
		Sequence: []models.SequenceStep{{SignalKey: "mongodb_host_unreachable"}},
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, nil)

	if result.ConfidenceScore < 4 {
		t.Fatalf("test expected numeric score above threshold, got %#v", result)
	}
	if result.Classification != ClassificationConfirmed {
		t.Fatalf("expected warning evidence to confirm when topology and timing are strong, got %#v", result)
	}
	if result.Breakdown.ExpectedSignalSeverity != 0.6 {
		t.Fatalf("expected effective severity to come from matched logs, got %#v", result.Breakdown)
	}
	if result.Breakdown.SeverityAlignment != 1 {
		t.Fatalf("expected direct log-severity flow to keep alignment neutral, got %#v", result.Breakdown)
	}
}

func TestScoreConfirmsWarningEvidenceWhenSeveritySupportsIt(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 4)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "2", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now.Add(time.Second), ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "3", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now.Add(2 * time.Second), ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_user_not_found", RequiredCount: 3, MatchedCount: 3, Within: "5m", MatchedLogIDs: []string{"1", "2", "3"}},
			},
		},
	}, &models.Rule{
		ID:       "rule-warning-expected",
		Window:   "15m",
		Sequence: []models.SequenceStep{{SignalKey: "mongodb_user_not_found"}},
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, nil)

	if result.Classification != ClassificationConfirmed {
		t.Fatalf("expected warning evidence with strong topology and timing to confirm, got %#v", result)
	}
	if result.Breakdown.SignalSeverity != 0.6 || result.Breakdown.ExpectedSignalSeverity != 0.6 || result.Breakdown.SeverityAlignment != 1 {
		t.Fatalf("expected severity breakdown to come directly from matched logs, got %#v", result.Breakdown)
	}
}

func TestScoreConfirmsHighCompletenessDespiteIncompleteFinalMinCount(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 4)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  5.0 / 6.0,
		RuleCompletion: 5.0 / 6.0,
		GroupByValues:  map[string]string{"host.identity": "10.0.4.72"},
		LogID: []models.EvidenceLog{
			{ID: "mongo-1", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "mongo-2", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now.Add(time.Second), ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "mongo-3", Severity: "warning", Signal: "mongodb_user_not_found", Timestamp: now.Add(2 * time.Second), ServiceName: "mongodb", HostIP: "10.0.4.72"},
			{ID: "nginx-1", Severity: "critical", Signal: "nginx_access_502_bad_gateway", Timestamp: now.Add(10 * time.Second), ServiceName: "nginx", HostIP: "10.0.4.72"},
			{ID: "nginx-2", Severity: "critical", Signal: "nginx_access_502_bad_gateway", Timestamp: now.Add(10 * time.Second), ServiceName: "nginx", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_user_not_found", RequiredCount: 3, MatchedCount: 3, Within: "3m", MatchedLogIDs: []string{"mongo-1", "mongo-2", "mongo-3"}},
				{StepIndex: 1, SignalKey: "nginx_access_502_bad_gateway", RequiredCount: 3, MatchedCount: 2, Within: "3m", MatchedLogIDs: []string{"nginx-1", "nginx-2"}},
			},
		},
	}, &models.Rule{
		ID:     "mongo-to-nginx",
		Window: "10m",
		Sequence: []models.SequenceStep{
			{SignalKey: "mongodb_user_not_found", MinCount: 3, Within: "3m"},
			{SignalKey: "nginx_access_502_bad_gateway", MinCount: 3, Within: "3m"},
		},
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{
			{ServiceName: "mongodb", DeviceIP: "10.0.4.72"},
			{ServiceName: "nginx", DeviceIP: "10.0.4.72"},
		},
		Dependencies: []models.TopologyDependency{
			{From: "10.0.4.72::mongodb", To: "10.0.4.72::nginx"},
		},
	}, nil)

	if result.Classification != ClassificationConfirmed {
		t.Fatalf("expected high-completeness partial min_count evidence to confirm, got %#v", result)
	}
	if result.Breakdown.CompletedStepCoverage != 0.5 {
		t.Fatalf("expected completed step coverage to remain audit-only at 0.5, got %#v", result.Breakdown)
	}
	if result.Breakdown.RuleCompleteness < 0.8 {
		t.Fatalf("expected high rule completeness, got %#v", result.Breakdown)
	}
}

func TestScoreCapsRepeatedRecoveryPenaltyPerService(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Signal: "mongodb_auth_failed", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_auth_failed", RequiredCount: 1, MatchedCount: 1, Within: "5m", MatchedLogIDs: []string{"1"}},
			},
		},
	}, &models.Rule{
		ID:              "rule-recovery-cap",
		Window:          "15m",
		RecoverySignals: []string{"mongodb_login_ok"},
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, []models.RelatedLog{
		{
			DocID:       "recovery-1",
			Timestamp:   now.Add(5 * time.Second),
			ServiceName: "mongodb",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_login_ok",
			Severity:    "info",
		},
		{
			DocID:       "recovery-2",
			Timestamp:   now.Add(6 * time.Second),
			ServiceName: "mongodb",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_login_ok",
			Severity:    "info",
		},
	})

	if result.Breakdown.ContradictionPenalty != 0.8 {
		t.Fatalf("expected repeated same-service recovery to cap at 0.8 multiplier, got %#v", result.Breakdown)
	}
	if len(result.ContradictionEvidence) != 1 {
		t.Fatalf("expected only the capped recovery evidence to be retained, got %#v", result.ContradictionEvidence)
	}
	if result.ContradictionEvidence[0].Kind != "same_service_recovery" {
		t.Fatalf("expected recovery evidence, got %#v", result.ContradictionEvidence[0])
	}
}

func TestScoreUsesUnambiguousSignalizedRecovery(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "critical", Signal: "mongodb_host_unreachable", Timestamp: now, ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
		Audit: &models.MatchAudit{
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, SignalKey: "mongodb_host_unreachable", RequiredCount: 1, MatchedCount: 1, Within: "5m", MatchedLogIDs: []string{"1"}},
			},
		},
	}, &models.Rule{
		ID:     "rule-signalized-recovery",
		Window: "15m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "mongodb", DeviceIP: "10.0.4.72"}},
	}, []models.RelatedLog{
		{
			DocID:       "recovered",
			Timestamp:   now.Add(5 * time.Second),
			ServiceName: "mongodb",
			HostIP:      "10.0.4.72",
			Signal:      "mongodb_primary_recovered",
			Severity:    "info",
		},
	})

	if result.Breakdown.ContradictionPenalty != 0.8 {
		t.Fatalf("expected signalized recovery to reduce multiplier to 0.8, got %#v", result.Breakdown)
	}
}

func TestTimeProximityDoesNotPerfectScoreSparseSingleLogSteps(t *testing.T) {
	scorer := NewScorer(defaultWeights(), 7)
	now := time.Now().UTC()

	result := scorer.Score(models.CorrelationEvent{
		SequenceMatch:  1,
		RuleCompletion: 1,
		LogID: []models.EvidenceLog{
			{ID: "1", Severity: "error", Timestamp: now, ServiceName: "api"},
			{ID: "2", Severity: "error", Timestamp: now.Add(10 * time.Second), ServiceName: "api"},
		},
		Audit: &models.MatchAudit{
			MaxGapBetweenSteps: "1m",
			Steps: []models.MatchStepAudit{
				{StepIndex: 0, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"1"}},
				{StepIndex: 1, RequiredCount: 1, MatchedCount: 1, Within: "1m", MatchedLogIDs: []string{"2"}},
			},
		},
	}, &models.Rule{
		ID:                 "rule-sparse-time",
		Window:             "5m",
		MaxGapBetweenSteps: "1m",
	}, &models.OrganizationTopology{
		Services: []models.TopologyService{{ServiceName: "api"}},
	}, nil)

	if result.Breakdown.TimeProximity >= 1 {
		t.Fatalf("expected sparse timing evidence to stay below a perfect score, got %#v", result.Breakdown)
	}
}
