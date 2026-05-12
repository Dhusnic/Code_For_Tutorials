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

type stubPublisher struct {
	records   [][]models.RCARecord
	saveCalls int
}

func (s *stubPublisher) UpsertRecords(_ context.Context, records []models.RCARecord) error {
	cloned := append([]models.RCARecord(nil), records...)
	s.records = append(s.records, cloned)
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

func TestProcessorPublishesDuplicateEventToMongoPublisher(t *testing.T) {
	event := baseEvent("sig-1", "open")
	reader := &stubReader{pages: [][]models.CorrelationEvent{{event}}}
	results := &stubResults{document: models.RCAOutputDocument{Items: []models.RCARecord{
		{
			SchemaVersion:                rcaRecordSchemaVersion,
			IncidentID:                   event.IncidentID,
			OrganizationID:               event.OrganizationID,
			RuleID:                       event.RuleID,
			Status:                       "open",
			Classification:               scoring.ClassificationConfirmed,
			ConfidenceScore:              8.2,
			LastProcessedResultSignature: "sig-1",
			ResultSignature:              "sig-1",
		},
	}}}
	publisher := &stubPublisher{}

	processor := NewProcessor(Dependencies{
		Reader:          reader,
		Rules:           &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:        &stubTopology{document: models.TopologyDocument{}},
		Results:         results,
		ResultPublisher: publisher,
		Checkpoints:     &stubCheckpoint{},
		Scorer:          &stubScorer{},
		Explainer:       &stubExplainer{},
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if results.saveCalls != 0 {
		t.Fatalf("expected duplicate event not to rewrite local result store, got %d saves", results.saveCalls)
	}
	if publisher.saveCalls != 1 {
		t.Fatalf("expected duplicate event to be published once, got %d publishes", publisher.saveCalls)
	}
	if len(publisher.records) != 1 || len(publisher.records[0]) != 1 {
		t.Fatalf("expected one published record, got %#v", publisher.records)
	}
	record := publisher.records[0][0]
	if record.IncidentID != event.IncidentID || record.ResultSignature != event.ResultSignature {
		t.Fatalf("unexpected published duplicate record: %#v", record)
	}
}

func TestProcessorPublishesBelowThresholdEventToMongoPublisher(t *testing.T) {
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-low", "open")}}}
	results := &stubResults{}
	publisher := &stubPublisher{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:        scoring.ClassificationProbable,
			ConfidenceScore:       1.5,
			Breakdown:             models.ScoreBreakdown{DependencyMatch: 0.1},
			BelowThresholdReasons: []string{"Low dependency confidence."},
			InvolvedServices:      []string{"api"},
			MatchedDocIDs:         []string{"doc-1"},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader:               reader,
		Rules:                &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:             &stubTopology{document: models.TopologyDocument{}},
		Results:              results,
		ResultPublisher:      publisher,
		Checkpoints:          &stubCheckpoint{},
		Scorer:               scorerStub,
		Explainer:            &stubExplainer{},
		ProbableCauseMin:     2.0,
		NeighborhoodLogLimit: 10,
		NearbyLogTrigger:     10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if results.saveCalls != 0 {
		t.Fatalf("expected below-threshold event not to rewrite local result store, got %d saves", results.saveCalls)
	}
	if publisher.saveCalls != 1 {
		t.Fatalf("expected below-threshold event to be published once, got %d publishes", publisher.saveCalls)
	}
	record := publisher.records[0][0]
	if record.ConfidenceScore != 1.5 {
		t.Fatalf("expected published low-score event to keep confidence, got %#v", record)
	}
	if record.IncidentID == "" {
		t.Fatalf("expected published low-score event to have incident id, got %#v", record)
	}
}

func TestProcessorUpgradesStaleRecordWithoutNewCorrelationEvent(t *testing.T) {
	now := time.Now().UTC()
	existing := models.RCARecord{
		SchemaVersion:                rcaRecordSchemaVersion - 1,
		CorrelationSchemaVersion:     2,
		IncidentID:                   "incident-1",
		OrganizationID:               "org-1",
		RuleID:                       "rule-1",
		Status:                       "open",
		Classification:               scoring.ClassificationProbable,
		ScoreBreakdown:               models.ScoreBreakdown{SequenceMatch: 0.8333, RuleCompleteness: 0.8333, TopologyCoverage: 1, IdentityConfidence: 1},
		MatchedLogs:                  []models.EvidenceLog{{ID: "doc-1", Severity: "critical", Timestamp: now, ServiceName: "api"}},
		MatchedAt:                    now,
		FirstSeen:                    &now,
		LastSeen:                     &now,
		ResultSignature:              "sig-1",
		LastProcessedResultSignature: "sig-1",
		Audit: &models.MatchAudit{Steps: []models.MatchStepAudit{
			{StepIndex: 0, SignalKey: "s1", RequiredCount: 3, MatchedCount: 3},
			{StepIndex: 1, SignalKey: "s2", RequiredCount: 3, MatchedCount: 2},
		}},
	}
	reader := &stubReader{}
	results := &stubResults{document: models.RCAOutputDocument{Items: []models.RCARecord{existing}}}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationConfirmed,
			ConfidenceScore:  8.4,
			Breakdown:        models.ScoreBreakdown{SequenceMatch: 0.8333, RuleCompleteness: 0.8333, CompletedStepCoverage: 0.5},
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
		NearbyLogTrigger: 10,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 1 {
		t.Fatalf("expected stale record to be rescored once, got %d", scorerStub.calls)
	}
	if results.saveCalls != 1 {
		t.Fatalf("expected upgraded record to be saved once, got %d", results.saveCalls)
	}
	record := results.saved.Items[0]
	if record.SchemaVersion != rcaRecordSchemaVersion || record.Classification != scoring.ClassificationConfirmed {
		t.Fatalf("expected upgraded confirmed record, got %#v", record)
	}
	if len(record.BelowThresholdReasons) != 0 {
		t.Fatalf("expected no stale below-threshold reasons, got %#v", record.BelowThresholdReasons)
	}
}

func TestProcessorClosesExistingIncidentWithoutRescoring(t *testing.T) {
	now := time.Now().UTC()
	existing := models.RCARecord{
		SchemaVersion:                rcaRecordSchemaVersion,
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

func TestProcessorRescoresClosedIncidentWhenRecordSchemaIsStale(t *testing.T) {
	now := time.Now().UTC()
	existing := models.RCARecord{
		SchemaVersion:                rcaRecordSchemaVersion - 1,
		IncidentID:                   "incident-1",
		OrganizationID:               "org-1",
		RuleID:                       "rule-1",
		Status:                       "open",
		Classification:               scoring.ClassificationConfirmed,
		ConfidenceScore:              8.2,
		LastProcessedResultSignature: "sig-open",
		FirstSeen:                    &now,
		LastSeen:                     &now,
	}
	reader := &stubReader{pages: [][]models.CorrelationEvent{{baseEvent("sig-closed", "closed")}}}
	results := &stubResults{document: models.RCAOutputDocument{Items: []models.RCARecord{existing}}}
	scorerStub := &stubScorer{result: models.ScoreResult{
		Classification:  scoring.ClassificationProbable,
		ConfidenceScore: 6.4,
	}}
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
	if scorerStub.calls == 0 {
		t.Fatal("expected stale closed record to be rescored")
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected saved record, got %#v", results.saved.Items)
	}
	record := results.saved.Items[0]
	if record.Status != "closed" || record.Classification != scoring.ClassificationProbable {
		t.Fatalf("expected rescored closed probable record, got %#v", record)
	}
	if record.SchemaVersion != rcaRecordSchemaVersion {
		t.Fatalf("expected schema version %d, got %d", rcaRecordSchemaVersion, record.SchemaVersion)
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

func TestBuildRecordPersistsContradictionEvidence(t *testing.T) {
	now := time.Now().UTC()
	record := buildRecord(models.RCARecord{}, false, models.CorrelationEvent{
		SchemaVersion:  2,
		IncidentID:     "incident-1",
		OrganizationID: "org-1",
		RuleID:         "rule-1",
		Status:         "open",
		MatchedAt:      now,
		LogID: []models.EvidenceLog{
			{ID: "matched-1", ServiceName: "mongodb", HostIP: "10.0.4.72"},
		},
	}, "topology-1", models.ScoreResult{
		Classification:  "probable_cause",
		ConfidenceScore: 5.5,
		ContradictionEvidence: []models.ContradictionEvidence{
			{
				Kind:        "same_service_recovery",
				DocID:       "nearby-1",
				SourceIndex: "linux_logs-2026.04.20",
				Signal:      "mongodb_primary_recovered",
				ServiceName: "mongodb",
				HostIP:      "10.0.4.72",
				Relevance:   1,
				Penalty:     0.2,
			},
		},
	}, now)

	if len(record.ContradictionEvidence) != 1 {
		t.Fatalf("expected contradiction evidence to be persisted, got %#v", record.ContradictionEvidence)
	}
	if record.ContradictionEvidence[0].DocID != "nearby-1" {
		t.Fatalf("unexpected persisted evidence: %#v", record.ContradictionEvidence[0])
	}
	if record.SchemaVersion != rcaRecordSchemaVersion {
		t.Fatalf("expected schema version %d, got %d", rcaRecordSchemaVersion, record.SchemaVersion)
	}
}

func TestBuildRecordPreservesLatencyFieldsFromExistingRecordWhenEventIsSparse(t *testing.T) {
	now := time.Now().UTC()
	oldLogAt := now.Add(-2 * time.Minute)
	oldSignalizedAt := now.Add(-90 * time.Second)
	oldCorrelatedAt := now.Add(-time.Minute)
	existing := models.RCARecord{
		IncidentID:     "incident-1",
		OrganizationID: "org-1",
		CorrelatedAt:   oldCorrelatedAt,
		MatchedLogs: []models.EvidenceLog{
			{
				ID:           "doc-1",
				Severity:     "critical",
				Timestamp:    oldLogAt,
				SignalizedAt: oldSignalizedAt,
			},
		},
		RCAGeneratedAt: now.Add(-30 * time.Second),
	}

	updatedAt := now.Add(15 * time.Second)
	record := buildRecord(existing, true, models.CorrelationEvent{
		SchemaVersion:  2,
		IncidentID:     "incident-1",
		OrganizationID: "org-1",
		RuleID:         "rule-1",
		Status:         "updated",
		MatchedAt:      now,
		LogID: []models.EvidenceLog{
			{ID: "doc-1", Severity: "critical"},
		},
	}, "topology-1", models.ScoreResult{
		Classification:  "probable_cause",
		ConfidenceScore: 4.5,
	}, updatedAt)

	if len(record.MatchedLogs) != 1 {
		t.Fatalf("expected one matched log, got %#v", record.MatchedLogs)
	}
	if !record.MatchedLogs[0].Timestamp.Equal(oldLogAt) {
		t.Fatalf("expected matched log timestamp %s, got %s", oldLogAt, record.MatchedLogs[0].Timestamp)
	}
	if !record.MatchedLogs[0].SignalizedAt.Equal(oldSignalizedAt) {
		t.Fatalf("expected matched log signalized_at %s, got %s", oldSignalizedAt, record.MatchedLogs[0].SignalizedAt)
	}
	if !record.CorrelatedAt.Equal(oldCorrelatedAt) {
		t.Fatalf("expected correlated_at %s, got %s", oldCorrelatedAt, record.CorrelatedAt)
	}
	if !record.RCAGeneratedAt.Equal(updatedAt) {
		t.Fatalf("expected rca_generated_at %s, got %s", updatedAt, record.RCAGeneratedAt)
	}
}

func TestDuplicateEventReprocessesOlderRecordSchema(t *testing.T) {
	existing := models.RCARecord{
		SchemaVersion:                rcaRecordSchemaVersion - 1,
		IncidentID:                   "incident-1",
		Status:                       "open",
		LastProcessedResultSignature: "sig-1",
	}

	if isDuplicateEvent(existing, "open", "sig-1") {
		t.Fatal("expected older RCA record schema to force reprocessing")
	}

	existing.SchemaVersion = rcaRecordSchemaVersion
	if !isDuplicateEvent(existing, "open", "sig-1") {
		t.Fatal("expected current schema with same signature/status to dedupe")
	}
}

func TestProcessorOnlyProcessesEventsOwnedByWorkerShard(t *testing.T) {
	ownedEvent := baseEvent("sig-owned", "open")
	ownedEvent.IncidentID = "incident-owned"
	unownedEvent := baseEvent("sig-unowned", "open")
	unownedEvent.IncidentID = "incident-unowned"

	var ownerIndex int
	for idx := 0; idx < 2; idx++ {
		processor := NewProcessor(Dependencies{
			Reader:      &stubReader{},
			Rules:       &stubRules{},
			Topology:    &stubTopology{},
			Results:     &stubResults{},
			Checkpoints: &stubCheckpoint{},
			Scorer:      &stubScorer{},
			Explainer:   &stubExplainer{},
			WorkerIndex: idx,
			WorkerCount: 2,
		})
		if processor.ownsEvent(ownedEvent) {
			ownerIndex = idx
			break
		}
	}

	if ownershipKey(ownedEvent) == ownershipKey(unownedEvent) {
		t.Fatal("expected distinct ownership keys for test events")
	}

	if ownerIndex == 0 && NewProcessor(Dependencies{
		Reader:      &stubReader{},
		Rules:       &stubRules{},
		Topology:    &stubTopology{},
		Results:     &stubResults{},
		Checkpoints: &stubCheckpoint{},
		Scorer:      &stubScorer{},
		Explainer:   &stubExplainer{},
		WorkerIndex: 0,
		WorkerCount: 2,
	}).ownsEvent(unownedEvent) {
		ownerIndex = 1
	}

	reader := &stubReader{pages: [][]models.CorrelationEvent{{ownedEvent, unownedEvent}}}
	results := &stubResults{}
	scorerStub := &stubScorer{
		result: models.ScoreResult{
			Classification:   scoring.ClassificationProbable,
			ConfidenceScore:  5.0,
			Breakdown:        models.ScoreBreakdown{},
			InvolvedServices: []string{"api"},
			MatchedDocIDs:    []string{"doc-1"},
		},
	}

	processor := NewProcessor(Dependencies{
		Reader:      reader,
		Rules:       &stubRules{rules: map[string]models.Rule{"rule-1": {ID: "rule-1"}}},
		Topology:    &stubTopology{document: models.TopologyDocument{}},
		Results:     results,
		Checkpoints: &stubCheckpoint{},
		Scorer:      scorerStub,
		Explainer:   &stubExplainer{},
		WorkerIndex: ownerIndex,
		WorkerCount: 2,
	})

	if err := processor.RunCycle(context.Background()); err != nil {
		t.Fatalf("RunCycle returned error: %v", err)
	}
	if scorerStub.calls != 1 {
		t.Fatalf("expected only one owned event to be scored, got %d", scorerStub.calls)
	}
	if len(results.saved.Items) != 1 {
		t.Fatalf("expected only one owned record to be saved, got %#v", results.saved.Items)
	}
	if results.saved.Items[0].IncidentID != ownedEvent.IncidentID {
		t.Fatalf("expected owned incident %q, got %#v", ownedEvent.IncidentID, results.saved.Items[0])
	}
}
