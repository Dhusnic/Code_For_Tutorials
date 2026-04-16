package service

import (
	"context"
	"errors"
	"testing"
	"time"

	"log_rca_engine/internal/models"
	"log_rca_engine/internal/scoring"
)

func testWeights() models.ScoreWeights {
	return models.ScoreWeights{
		SequenceMatch:    0.30,
		DependencyMatch:  0.25,
		TimeProximity:    0.15,
		SignalSeverity:   0.15,
		RuleCompleteness: 0.15,
	}
}

type stubReader struct {
	pages              [][]models.CorrelationEvent
	index              int
	seenCheckpoints    []models.ReaderCheckpoint
	returnedCheckpoint models.ReaderCheckpoint
	matchedLogs        []models.RelatedLog
	relatedLogs        []models.RelatedLog
	relatedCalls       int
}

func (r *stubReader) ReadCorrelationEvents(_ context.Context, checkpoint models.ReaderCheckpoint) ([]models.CorrelationEvent, models.ReaderCheckpoint, error) {
	r.seenCheckpoints = append(r.seenCheckpoints, checkpoint)
	if r.index >= len(r.pages) {
		return nil, models.ReaderCheckpoint{}, nil
	}
	events := r.pages[r.index]
	r.index++
	next := r.returnedCheckpoint
	if len(next.SearchAfter) == 0 {
		next.SearchAfter = []any{r.index}
	}
	return events, next, nil
}

func (r *stubReader) FetchMatchedLogs(_ context.Context, evidence []models.EvidenceLog) ([]models.RelatedLog, error) {
	if len(r.matchedLogs) > 0 {
		return append([]models.RelatedLog(nil), r.matchedLogs...), nil
	}
	result := make([]models.RelatedLog, 0, len(evidence))
	for _, log := range evidence {
		result = append(result, models.RelatedLog{DocID: log.ID, Index: log.SourceIndex})
	}
	return result, nil
}

func (r *stubReader) SearchRelatedLogs(context.Context, models.CorrelationEvent, int) ([]models.RelatedLog, error) {
	r.relatedCalls++
	if len(r.relatedLogs) > 0 {
		return append([]models.RelatedLog(nil), r.relatedLogs...), nil
	}
	return []models.RelatedLog{{DocID: "nearby-1", Index: "logs"}}, nil
}

type stubRules struct {
	rules map[string]models.Rule
}

func (s *stubRules) Load(context.Context) (map[string]models.Rule, error) {
	return s.rules, nil
}

type stubTopology struct {
	document models.TopologyDocument
	err      error
}

func (s *stubTopology) Load(context.Context) (models.TopologyDocument, error) {
	return s.document, s.err
}

type stubResults struct {
	document  models.RCAOutputDocument
	saved     models.RCAOutputDocument
	saveCalls int
}

func (s *stubResults) Load(context.Context) (models.RCAOutputDocument, error) {
	return s.document, nil
}

func (s *stubResults) Save(_ context.Context, document models.RCAOutputDocument) error {
	s.saved = document
	s.document = document
	s.saveCalls++
	return nil
}

type stubCheckpoint struct {
	value     models.ReaderCheckpoint
	saveCalls int
}

func (s *stubCheckpoint) Load(context.Context) (models.ReaderCheckpoint, error) {
	return s.value, nil
}

func (s *stubCheckpoint) Save(_ context.Context, checkpoint models.ReaderCheckpoint) error {
	s.value = checkpoint
	s.saveCalls++
	return nil
}

type stubScorer struct {
	result      models.ScoreResult
	results     []models.ScoreResult
	byTopology  map[string]models.ScoreResult
	calls       int
	events      []models.CorrelationEvent
	topologyIDs []string
}

func (s *stubScorer) Score(event models.CorrelationEvent, _ *models.Rule, topology *models.OrganizationTopology, _ []models.RelatedLog) models.ScoreResult {
	s.calls++
	s.events = append(s.events, event)
	if topology != nil {
		s.topologyIDs = append(s.topologyIDs, topology.TopologyID)
		if len(s.byTopology) > 0 {
			if candidate, ok := s.byTopology[topology.TopologyID]; ok {
				return candidate
			}
		}
	}
	if len(s.results) >= s.calls {
		return s.results[s.calls-1]
	}
	return s.result
}

type stubExplainer struct {
	enabled bool
	calls   int
	err     error
}

func (s *stubExplainer) Enabled() bool {
	return s.enabled
}

func (s *stubExplainer) Explain(context.Context, models.ExplanationRequest) (*models.LLMExplanation, error) {
	s.calls++
	if s.err != nil {
		return nil, s.err
	}
	return &models.LLMExplanation{
		Provider:               "openai",
		Model:                  "test-model",
		RootCause:              "queue dependency failure",
		NaturalLanguageSummary: "API calls failed because the queue dependency stalled.",
		AffectedServices:       []string{"api", "rabbitmq"},
		Evidence:               []string{"Matched logs 1 and 2"},
		NextChecks:             []string{"Check queue depth"},
	}, nil
}

func baseEvent(signature string, status string) models.CorrelationEvent {
	now := time.Now().UTC()
	return models.CorrelationEvent{
		SchemaVersion:   2,
		IncidentID:      "incident-1",
		OrganizationID:  "org-1",
		RuleID:          "rule-1",
		Status:          status,
		ResultSignature: signature,
		MatchedAt:       now,
		FirstSeen:       &now,
		LastSeen:        &now,
		LogID: []models.EvidenceLog{
			{ID: "doc-1", Severity: "critical", Timestamp: now, ServiceName: "api", SourceIndex: "logs-a"},
			{ID: "doc-2", Severity: "error", Timestamp: now.Add(10 * time.Second), ServiceName: "rabbitmq", SourceIndex: "logs-a"},
		},
	}
}

func TestProcessorStoresProbableCauseWhenScoreIsBelowThreshold(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-1", "open")}}}
	results := &stubResults{}
	checkpoints := &stubCheckpoint{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:        scoring.ClassificationProbable,
			ConfidenceScore:       4.4,
			Breakdown:             models.ScoreBreakdown{DependencyMatch: 0.1},
			BelowThresholdReasons: []string{"Low dependency confidence."},
			InvolvedServices:      []string{"api", "rabbitmq"},
			MatchedDocIDs:         []string{"doc-1", "doc-2"},
		},
	}
	explainer := &stubExplainer{enabled: true}

	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		Checkpoints:          checkpoints,
		Scorer:               scorerStub,
		Explainer:            explainer,
		NeighborhoodLogLimit: 10,
		NearbyLogTrigger:     10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if explainer.calls != 0 {
		t.Fatalf("expected no LLM call, got %d", explainer.calls)
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected one saved item, got %#v", results.saved)
	}
	if results.saved.Items[0].Classification != scoring.ClassificationProbable {
		t.Fatalf("unexpected saved record: %#v", results.saved.Items[0])
	}
}

func TestProcessorSkipsNearbyLogSearchForWeakBaseScore(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-weak", "open")}}}
	results := &stubResults{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationProbable,
			ConfidenceScore:  4.9,
			Breakdown:        models.ScoreBreakdown{},
			InvolvedServices: []string{"api"},
			MatchedDocIDs:    []string{"doc-1"},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader:           reader,
		Rules:            &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:         &stubTopology{document: models.TopologyDocument{}},
		Results:          results,
		Checkpoints:      &stubCheckpoint{},
		Scorer:           scorerStub,
		Explainer:        &stubExplainer{},
		NearbyLogTrigger: 5.5,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if reader.relatedCalls != 0 {
		t.Fatalf("expected no nearby-log search for weak score, got %d", reader.relatedCalls)
	}
	if scorerStub.calls != 1 {
		t.Fatalf("expected one scoring pass, got %d", scorerStub.calls)
	}
}

func TestProcessorRescoresWithNearbyLogsWhenBaseScoreIsNearThreshold(t *testing.T) {
	reader := &stubReader{
		pages:       [][]models.CorrelationEvent{{baseEvent("sig-near", "open")}},
		relatedLogs: []models.RelatedLog{{DocID: "nearby-1", Index: "logs", Signal: "recovered"}},
	}
	results := &stubResults{}
	scorerStub := &stubScorer{
		results: []models.ScoreResult{
			{
				Classification:   scoring.ClassificationProbable,
				ConfidenceScore:  6.1,
				Breakdown:        models.ScoreBreakdown{},
				InvolvedServices: []string{"api"},
				MatchedDocIDs:    []string{"doc-1"},
			},
			{
				Classification:   scoring.ClassificationConfirmed,
				ConfidenceScore:  7.3,
				Breakdown:        models.ScoreBreakdown{ContradictionPenalty: 0.9},
				InvolvedServices: []string{"api"},
				MatchedDocIDs:    []string{"doc-1"},
			},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		Checkpoints:          &stubCheckpoint{},
		Scorer:               scorerStub,
		Explainer:            &stubExplainer{},
		NeighborhoodLogLimit: 10,
		NearbyLogTrigger:     5.5,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if reader.relatedCalls != 1 {
		t.Fatalf("expected one nearby-log search, got %d", reader.relatedCalls)
	}
	if scorerStub.calls != 2 {
		t.Fatalf("expected two scoring passes, got %d", scorerStub.calls)
	}
	if len(results.saved.Items) != 1 || results.saved.Items[0].Classification != scoring.ClassificationConfirmed {
		t.Fatalf("expected final confirmed RCA record, got %#v", results.saved.Items)
	}
}

func TestProcessorDedupesSameSignatureAndCallsLLMOnce(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-1", "open")}}}
	results := &stubResults{}
	checkpoints := &stubCheckpoint{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationConfirmed,
			ConfidenceScore:  8.6,
			Breakdown:        models.ScoreBreakdown{DependencyMatch: 1},
			InvolvedServices: []string{"api", "rabbitmq"},
			MatchedDocIDs:    []string{"doc-1", "doc-2"},
		},
	}
	explainer := &stubExplainer{enabled: true}
	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		Checkpoints:          checkpoints,
		Scorer:               scorerStub,
		Explainer:            explainer,
		NeighborhoodLogLimit: 10,
		NearbyLogTrigger:     10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("first RunCycle returned error: %v", err)
	}
	reader.pages = [][]models.CorrelationEvent{{baseEvent("sig-1", "open")}}
	reader.index = 0
	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("second RunCycle returned error: %v", err)
	}
	if explainer.calls != 1 {
		t.Fatalf("expected one LLM call after dedupe, got %d", explainer.calls)
	}
	if scorerStub.calls != 1 {
		t.Fatalf("expected one score call after dedupe, got %d", scorerStub.calls)
	}
}

func TestProcessorClosesExistingIncidentWithoutRescoring(t *testing.T) {
	now := time.Now().UTC()
	existing := models.RCARecord{
		SchemaVersion:                1,
		IncidentID:                   "incident-1",
		OrganizationID:               "org-1",
		RuleID:                       "rule-1",
		Status:                       "open",
		Classification:               scoring.ClassificationConfirmed,
		ConfidenceScore:              8.2,
		LastProcessedResultSignature: "sig-open",
		LLM:                          &models.LLMExplanation{RootCause: "original summary"},
		FirstSeen:                    &now,
		LastSeen:                     &now,
	}
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-closed", "closed")}}}
	results := &stubResults{document: models.RCAOutputDocument{Items: []models.RCARecord{existing}}}
	scorerStub := &stubScorer{}
	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		Checkpoints:          &stubCheckpoint{},
		Scorer:               scorerStub,
		Explainer:            &stubExplainer{enabled: true},
		NeighborhoodLogLimit: 10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 0 {
		t.Fatalf("expected no score call for close update, got %d", scorerStub.calls)
	}
	if len(results.saved.Items) != 1 || results.saved.Items[0].Status != "closed" {
		t.Fatalf("expected closed saved record, got %#v", results.saved.Items)
	}
	if results.saved.Items[0].LLM == nil || results.saved.Items[0].LLM.RootCause != "original summary" {
		t.Fatalf("expected existing summary to remain, got %#v", results.saved.Items[0].LLM)
	}
}

func TestProcessorSkipsClosedIncidentWithoutExistingRecord(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-closed-only", "closed")}}}
	results := &stubResults{}
	scorerStub := &stubScorer{}

	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		Checkpoints:          &stubCheckpoint{},
		Scorer:               scorerStub,
		Explainer:            &stubExplainer{enabled: true},
		NeighborhoodLogLimit: 10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 0 {
		t.Fatalf("expected no score call for closed-only event, got %d", scorerStub.calls)
	}
	if results.saveCalls != 0 {
		t.Fatalf("expected no result writes for closed-only event without prior RCA, got %d", results.saveCalls)
	}
}

func TestProcessorHandlesOldSchemaEventWithoutFailing(t *testing.T) {
	now := time.Now().UTC()
	oldEvent := models.CorrelationEvent{
		IncidentID:      "legacy-1",
		OrganizationID:  "org-1",
		RuleID:          "rule-1",
		ResultSignature: "legacy-sig",
		MatchedAt:       now,
		LogID: []models.EvidenceLog{
			{ID: "doc-1", Severity: "warning"},
		},
	}
	reader := &stubReader{pages: [][]models.CorrelationEvent{{oldEvent}}}
	results := &stubResults{}
	processor := NewProcessor(Dependencies{
		Reader:      reader,
		Rules:       &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1", Window: "10m"}}},
		Topology:    &stubTopology{document: models.TopologyDocument{}},
		Results:     results,
		Checkpoints: &stubCheckpoint{},
		Scorer:      scoring.NewScorer(testWeights(), 7),
		Explainer:   &stubExplainer{enabled: true, err: errors.New("should not run")},
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected one saved record, got %#v", results.saved)
	}
	if results.saved.Items[0].Classification != scoring.ClassificationProbable {
		t.Fatalf("expected probable cause fallback, got %#v", results.saved.Items[0])
	}
}

func TestProcessorStoresLLMErrorWithoutFailingCycle(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-2", "open")}}}
	results := &stubResults{}
	explainer := &stubExplainer{enabled: true, err: errors.New("openai timeout")}
	processor := NewProcessor(Dependencies{
		Reader:      reader,
		Rules:       &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:    &stubTopology{document: models.TopologyDocument{}},
		Results:     results,
		Checkpoints: &stubCheckpoint{},
		Scorer: &stubScorer{
			result: models.ScoreResult{
				Classification:   scoring.ClassificationConfirmed,
				ConfidenceScore:  8.8,
				Breakdown:        models.ScoreBreakdown{DependencyMatch: 1},
				InvolvedServices: []string{"api", "rabbitmq"},
				MatchedDocIDs:    []string{"doc-1", "doc-2"},
			},
		},
		Explainer:            explainer,
		NeighborhoodLogLimit: 10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected saved record, got %#v", results.saved)
	}
	if results.saved.Items[0].LLM == nil || results.saved.Items[0].LLM.Error == "" {
		t.Fatalf("expected saved LLM error payload, got %#v", results.saved.Items[0].LLM)
	}
}

func TestProcessorEnrichesMissingHostIPsFromMatchedLogsBeforeScoring(t *testing.T) {
	event := baseEvent("sig-ip", "open")
	event.LogID = []models.EvidenceLog{
		{
			ID:          "doc-1",
			Severity:    "critical",
			SourceIndex: "logs-a",
			ServiceName: "api",
		},
	}

	reader := &stubReader{
		pages: [][]models.CorrelationEvent{{event}},
		matchedLogs: []models.RelatedLog{
			{
				DocID:       "doc-1",
				Index:       "logs-a",
				ServiceName: "api",
				HostName:    "host-1",
				HostIP:      "10.0.4.72",
				HostIPs:     []string{"10.0.4.72", "172.16.1.10"},
			},
		},
	}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationProbable,
			ConfidenceScore:  5.5,
			Breakdown:        models.ScoreBreakdown{},
			InvolvedServices: []string{"10.0.4.72"},
			MatchedDocIDs:    []string{"doc-1"},
		},
	}
	processor := NewProcessor(Dependencies{
		Reader:           reader,
		Rules:            &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:         &stubTopology{document: models.TopologyDocument{}},
		Results:          &stubResults{},
		Checkpoints:      &stubCheckpoint{},
		Scorer:           scorerStub,
		Explainer:        &stubExplainer{},
		NearbyLogTrigger: 10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if len(scorerStub.events) != 1 {
		t.Fatalf("expected scorer to receive one event, got %d", len(scorerStub.events))
	}
	if scorerStub.events[0].LogID[0].HostIP != "10.0.4.72" {
		t.Fatalf("expected host IP enrichment before scoring, got %#v", scorerStub.events[0].LogID[0])
	}
	if len(scorerStub.events[0].LogID[0].HostIPs) != 2 {
		t.Fatalf("expected host IP candidates before scoring, got %#v", scorerStub.events[0].LogID[0])
	}
}

func TestProcessorReplaysFromCheckpointWatermarkWithoutPersistingSearchAfter(t *testing.T) {
	now := time.Date(2026, time.April, 10, 12, 8, 0, 0, time.UTC)
	reader := &stubReader{
		pages: [][]models.CorrelationEvent{{baseEvent("sig-replay", "open")}},
		returnedCheckpoint: models.ReaderCheckpoint{
			UpdatedAt:   now.Add(-time.Minute),
			SearchAfter: []any{"2026-04-10T12:01:54.379Z", "2026-04-10T11:27:25.870Z", "incident-1", "sig-open"},
		},
	}
	checkpoints := &stubCheckpoint{
		value: models.ReaderCheckpoint{
			UpdatedAt:   now.Add(-2 * time.Minute),
			SearchAfter: []any{"legacy-cursor"},
		},
	}
	results := &stubResults{}
	processor := NewProcessor(Dependencies{
		Reader:      reader,
		Rules:       &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:    &stubTopology{document: models.TopologyDocument{}},
		Results:     results,
		Checkpoints: checkpoints,
		Scorer: &stubScorer{
			result: models.ScoreResult{
				Classification:   scoring.ClassificationProbable,
				ConfidenceScore:  5.0,
				Breakdown:        models.ScoreBreakdown{},
				InvolvedServices: []string{"api"},
				MatchedDocIDs:    []string{"doc-1"},
			},
		},
		Explainer: &stubExplainer{},
	})
	processor.now = func() time.Time { return now }

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if len(reader.seenCheckpoints) == 0 {
		t.Fatal("expected reader to observe a checkpoint")
	}
	if len(reader.seenCheckpoints[0].SearchAfter) != 0 {
		t.Fatalf("expected persisted search_after to be cleared before replay, got %#v", reader.seenCheckpoints[0].SearchAfter)
	}
	if !reader.seenCheckpoints[0].UpdatedAt.Equal(now.Add(-2 * time.Minute)) {
		t.Fatalf("expected replay to preserve updated_at watermark, got %s", reader.seenCheckpoints[0].UpdatedAt)
	}
	if len(checkpoints.value.SearchAfter) != 0 {
		t.Fatalf("expected saved checkpoint search_after to remain empty, got %#v", checkpoints.value.SearchAfter)
	}
	if checkpoints.saveCalls != 1 {
		t.Fatalf("expected one checkpoint save, got %d", checkpoints.saveCalls)
	}
}

func TestProcessorSelectsBestOrganizationTopologyAndStoresTopologyID(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-topology", "open")}}}
	results := &stubResults{}
	scorerStub := &stubScorer{
		byTopology: map[string]models.ScoreResult{
			"topo-a": {
				Classification:   scoring.ClassificationProbable,
				ConfidenceScore:  4.5,
				Breakdown:        models.ScoreBreakdown{TopologyCoverage: 0.4, IdentityConfidence: 0.5},
				InvolvedServices: []string{"api"},
				MatchedDocIDs:    []string{"doc-1"},
			},
			"topo-b": {
				Classification:   scoring.ClassificationConfirmed,
				ConfidenceScore:  8.1,
				Breakdown:        models.ScoreBreakdown{TopologyCoverage: 1.0, IdentityConfidence: 0.95},
				InvolvedServices: []string{"10.0.4.72::api", "10.0.4.72::rabbitmq"},
				MatchedDocIDs:    []string{"doc-1", "doc-2"},
			},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader: reader,
		Rules: &stubRules{rules: map[string]models.Rule{
			"rule-1": {ID: "rule-1"},
		}},
		Topology: &stubTopology{
			document: models.TopologyDocument{
				Organizations: map[string]map[string]models.OrganizationTopology{
					"org-1": {
						"topo-a": {
							Services: []models.TopologyService{
								{ServiceName: "api", DeviceIP: "10.0.9.10"},
							},
						},
						"topo-b": {
							Services: []models.TopologyService{
								{ServiceName: "api", DeviceIP: "10.0.4.72"},
								{ServiceName: "rabbitmq", DeviceIP: "10.0.4.72"},
							},
							ServiceRelations: []models.TopologyServiceRelation{
								{FromService: "api", FromIP: "10.0.4.72", ToService: "rabbitmq", ToIP: "10.0.4.72", Relation: "depends_on"},
							},
						},
					},
				},
			},
		},
		Results:     results,
		Checkpoints: &stubCheckpoint{},
		Scorer:      scorerStub,
		Explainer:   &stubExplainer{},
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected one saved record, got %#v", results.saved.Items)
	}
	if results.saved.Items[0].TopologyID != "topo-b" {
		t.Fatalf("expected topology_id topo-b, got %#v", results.saved.Items[0].TopologyID)
	}
}

func TestProcessorSkipsEventWhenRuleTopologyScopeDoesNotMatch(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-topology-skip", "open")}}}
	results := &stubResults{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationConfirmed,
			ConfidenceScore:  8.0,
			Breakdown:        models.ScoreBreakdown{TopologyCoverage: 1},
			InvolvedServices: []string{"api"},
			MatchedDocIDs:    []string{"doc-1"},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader: reader,
		Rules: &stubRules{rules: map[string]models.Rule{
			"rule-1": {ID: "rule-1", TopologyIDs: []string{"topo-only"}},
		}},
		Topology: &stubTopology{
			document: models.TopologyDocument{
				Organizations: map[string]map[string]models.OrganizationTopology{
					"org-1": {
						"topo-other": {
							Services: []models.TopologyService{
								{ServiceName: "api", DeviceIP: "10.0.4.72"},
							},
						},
					},
				},
			},
		},
		Results:     results,
		Checkpoints: &stubCheckpoint{},
		Scorer:      scorerStub,
		Explainer:   &stubExplainer{},
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 0 {
		t.Fatalf("expected scorer not to run for scoped-out topology, got %d calls", scorerStub.calls)
	}
	if results.saveCalls != 0 {
		t.Fatalf("expected no result writes for scoped-out topology, got %d", results.saveCalls)
	}
}

func TestProcessorSkipsProbableCauseBelowMinimumThreshold(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-low-probable", "open")}}}
	results := &stubResults{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationProbable,
			ConfidenceScore:  1.9,
			Breakdown:        models.ScoreBreakdown{DependencyMatch: 0.2},
			InvolvedServices: []string{"api"},
			MatchedDocIDs:    []string{"doc-1"},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader:           reader,
		Rules:            &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:         &stubTopology{document: models.TopologyDocument{}},
		Results:          results,
		Checkpoints:      &stubCheckpoint{},
		Scorer:           scorerStub,
		Explainer:        &stubExplainer{enabled: true},
		ProbableCauseMin: 2.0,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 1 {
		t.Fatalf("expected scorer to run once, got %d", scorerStub.calls)
	}
	if results.saveCalls != 0 {
		t.Fatalf("expected no saved results for weak probable cause, got %d", results.saveCalls)
	}
}

func TestSingleRuleTopologyID(t *testing.T) {
	testCases := []struct {
		name string
		rule *models.Rule
		want string
		ok   bool
	}{
		{name: "nil rule", rule: nil, want: "", ok: false},
		{name: "no topology ids", rule: &models.Rule{}, want: "", ok: false},
		{name: "single topology id", rule: &models.Rule{TopologyIDs: []string{"topo-a"}}, want: "topo-a", ok: true},
		{name: "single topology id with spaces", rule: &models.Rule{TopologyIDs: []string{"  topo-a  ", "  "}}, want: "topo-a", ok: true},
		{name: "duplicate topology ids", rule: &models.Rule{TopologyIDs: []string{"topo-a", "topo-a"}}, want: "topo-a", ok: true},
		{name: "multiple topology ids", rule: &models.Rule{TopologyIDs: []string{"topo-a", "topo-b"}}, want: "", ok: false},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := singleRuleTopologyID(tc.rule)
			if ok != tc.ok {
				t.Fatalf("expected ok=%v, got %v", tc.ok, ok)
			}
			if got != tc.want {
				t.Fatalf("expected topology id %q, got %q", tc.want, got)
			}
		})
	}
}

func TestResolveOrganizationTopologyByID(t *testing.T) {
	document := models.TopologyDocument{
		Organizations: map[string]map[string]models.OrganizationTopology{
			"org-1": {
				" topo-a ": {
					Services: []models.TopologyService{
						{ServiceName: "api", DeviceIP: "10.0.4.72"},
					},
				},
				"topo-empty": {},
			},
		},
	}

	topology, found := resolveOrganizationTopologyByID("org-1", "topo-a", document)
	if !found {
		t.Fatal("expected topology lookup to resolve trimmed key")
	}
	if len(topology.Services) != 1 || topology.Services[0].DeviceIP != "10.0.4.72" {
		t.Fatalf("unexpected topology payload: %#v", topology)
	}

	if _, found := resolveOrganizationTopologyByID("org-1", "topo-empty", document); found {
		t.Fatal("expected topology lookup to reject empty topology data")
	}
	if _, found := resolveOrganizationTopologyByID("org-1", "missing", document); found {
		t.Fatal("expected missing topology lookup to fail")
	}
}
