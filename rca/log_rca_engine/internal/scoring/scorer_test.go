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
