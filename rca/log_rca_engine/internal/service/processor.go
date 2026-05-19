package service

import (
	"context"
	"fmt"
	"hash/fnv"
	"log/slog"
	"sort"
	"strings"
	"time"

	"log_rca_engine/internal/autoscaling"
	"log_rca_engine/internal/models"
	"log_rca_engine/internal/scoring"
	"log_rca_engine/internal/storage"
	"log_rca_engine/internal/utils"
)

const rcaRecordSchemaVersion = 8

type CorrelationEventReader interface {
	ReadCorrelationEvents(ctx context.Context, checkpoint models.ReaderCheckpoint) ([]models.CorrelationEvent, models.ReaderCheckpoint, error)
	FetchMatchedLogs(ctx context.Context, evidence []models.EvidenceLog) ([]models.RelatedLog, error)
	SearchRelatedLogs(ctx context.Context, event models.CorrelationEvent, limit int) ([]models.RelatedLog, error)
	MarkCorrelationEventsProcessed(ctx context.Context, refs []models.CorrelationEventRef) error
}

type correlationEventReaderTuner interface {
	SetPageSize(size int)
}

type RulesLoader interface {
	Load(ctx context.Context) (map[string]models.Rule, error)
}

type TopologyRepository interface {
	Load(ctx context.Context) (models.TopologyDocument, error)
}

type ResultStore interface {
	Load(ctx context.Context) (models.RCAOutputDocument, error)
	Save(ctx context.Context, document models.RCAOutputDocument) error
}

type IncidentResultStore interface {
	LoadByIncidentIDs(ctx context.Context, incidentIDs []string) (map[string]models.RCARecord, error)
	UpsertRecords(ctx context.Context, records []models.RCARecord) error
}

type CheckpointStore interface {
	Load(ctx context.Context) (models.ReaderCheckpoint, error)
	Save(ctx context.Context, checkpoint models.ReaderCheckpoint) error
}

type ResultPublisher interface {
	UpsertRecords(ctx context.Context, records []models.RCARecord) error
}

type Scorer interface {
	Score(event models.CorrelationEvent, rule *models.Rule, topology *models.OrganizationTopology, nearbyLogs []models.RelatedLog) models.ScoreResult
}

type Explainer interface {
	Enabled() bool
	Explain(ctx context.Context, request models.ExplanationRequest) (*models.LLMExplanation, error)
}

type Dependencies struct {
	Reader               CorrelationEventReader
	Rules                RulesLoader
	Topology             TopologyRepository
	Results              ResultStore
	ResultPublisher      ResultPublisher
	Checkpoints          CheckpointStore
	Scorer               Scorer
	Explainer            Explainer
	NeighborhoodLogLimit int
	NearbyLogTrigger     float64
	ProbableCauseMin     float64
	WorkerIndex          int
	WorkerCount          int
	Autoscaler           *autoscaling.Controller
	Logger               *slog.Logger
}

type Processor struct {
	reader               CorrelationEventReader
	rules                RulesLoader
	topology             TopologyRepository
	results              ResultStore
	resultPublisher      ResultPublisher
	checkpoints          CheckpointStore
	scorer               Scorer
	explainer            Explainer
	neighborhoodLogLimit int
	nearbyLogTrigger     float64
	probableCauseMin     float64
	workerIndex          int
	workerCount          int
	autoscaler           *autoscaling.Controller
	logger               *slog.Logger
	now                  func() time.Time
}

type CycleSummary struct {
	EventsRead     int
	EventsScored   int
	EventsSkipped  int
	ClosedUpdates  int
	ConfirmedRCAs  int
	ProbableCauses int
	LLMCalls       int
	LLMFailures    int
	ResultWrites   int
	PagesRead      int
	WorkloadCapped bool
}

type organizationTopologyCandidate struct {
	TopologyID string
	Topology   models.OrganizationTopology
}

type topologySelection struct {
	TopologyID string
	Topology   *models.OrganizationTopology
	Score      models.ScoreResult
}

func NewProcessor(deps Dependencies) *Processor {
	return &Processor{
		reader:               deps.Reader,
		rules:                deps.Rules,
		topology:             deps.Topology,
		results:              deps.Results,
		resultPublisher:      deps.ResultPublisher,
		checkpoints:          deps.Checkpoints,
		scorer:               deps.Scorer,
		explainer:            deps.Explainer,
		neighborhoodLogLimit: deps.NeighborhoodLogLimit,
		nearbyLogTrigger:     deps.NearbyLogTrigger,
		probableCauseMin:     deps.ProbableCauseMin,
		workerIndex:          deps.WorkerIndex,
		workerCount:          deps.WorkerCount,
		autoscaler:           deps.Autoscaler,
		logger:               deps.Logger,
		now:                  time.Now,
	}
}

func (p *Processor) RunCycle(ctx context.Context) error {
	if p.reader == nil || p.rules == nil || p.topology == nil || p.results == nil || p.checkpoints == nil || p.scorer == nil {
		return fmt.Errorf("processor dependencies are incomplete")
	}

	rulesByID, err := p.rules.Load(ctx)
	if err != nil {
		return fmt.Errorf("load rules: %w", err)
	}
	topologyDoc, err := p.topology.Load(ctx)
	if err != nil {
		return fmt.Errorf("load topology: %w", err)
	}
	checkpoint, err := p.checkpoints.Load(ctx)
	if err != nil {
		return fmt.Errorf("load checkpoint: %w", err)
	}
	checkpoint.SearchAfter = nil

	readerSettings := autoscaling.ReaderSettings{}
	if p.autoscaler != nil && p.autoscaler.Enabled() {
		readerSettings = p.autoscaler.CurrentReaderSettings()
		if tunedReader, ok := p.reader.(correlationEventReaderTuner); ok && readerSettings.PageSize > 0 {
			tunedReader.SetPageSize(readerSettings.PageSize)
		}
	}

	events, nextCheckpoint, pagesRead, workloadCapped, err := p.collectOwnedEvents(ctx, checkpoint, readerSettings.MaxPagesPerCycle)
	if err != nil {
		return fmt.Errorf("read correlation events: %w", err)
	}

	recordsByIncident, optimizedResultStore, err := p.loadResultRecords(ctx, events)
	if err != nil {
		return err
	}

	recordsPendingPublish := make(map[string]models.RCARecord)
	processedEventRefs := make([]models.CorrelationEventRef, 0)
	dirtyIncidentIDs := make(map[string]struct{})
	summary := CycleSummary{
		PagesRead:      pagesRead,
		WorkloadCapped: workloadCapped,
	}
	changed := false
	upgraded, err := p.upgradeStaleRecords(ctx, recordsByIncident, rulesByID, topologyDoc, &summary)
	if err != nil {
		return err
	}
	if upgraded {
		changed = true
		markDirtyIncidents(dirtyIncidentIDs, recordsByIncident)
		queueRecordsForPublish(recordsPendingPublish, storage.FromIncidentMap(recordsByIncident).Items...)
	}
	for _, event := range events {
		if err := ctx.Err(); err != nil {
			return err
		}
		summary.EventsRead++
		incidentID := strings.TrimSpace(event.IncidentID)
		if incidentID == "" {
			summary.EventsSkipped++
			queueSkippedEventForPublish(recordsPendingPublish, models.RCARecord{}, false, event, "", "skipped because incident_id was empty", nil, p.now().UTC())
			processedEventRefs = append(processedEventRefs, processedEventRef(event))
			if p.logger != nil {
				p.logger.Debug(
					"skipping event because incident_id was empty",
					"organization_id", event.OrganizationID,
					"rule_id", event.RuleID,
					"status", event.Status,
					"result_signature", event.ResultSignature,
					"document_id", event.DocumentID,
				)
			}
			continue
		}

		normalizedStatus := normalizeStatus(event.Status)
		existing, hasExisting := recordsByIncident[incidentID]
		if isDuplicateEvent(existing, normalizedStatus, event.ResultSignature) {
			summary.EventsSkipped++
			queueSkippedEventForPublish(recordsPendingPublish, existing, hasExisting, event, existing.TopologyID, "duplicate replayed event", nil, p.now().UTC())
			processedEventRefs = append(processedEventRefs, processedEventRef(event))
			if p.logger != nil {
				p.logger.Debug(
					"skipping duplicate replayed event because incident_id and result_signature were already processed",
					"incident_id", event.IncidentID,
					"organization_id", event.OrganizationID,
					"rule_id", event.RuleID,
					"status", normalizedStatus,
					"result_signature", event.ResultSignature,
					"last_processed_result_signature", existing.LastProcessedResultSignature,
				)
			}
			continue
		}
		enrichedEvent, err := p.enrichEventEvidence(ctx, event)
		if err != nil {
			return fmt.Errorf("enrich matched evidence for incident %s: %w", incidentID, err)
		}
		event = enrichedEvent

		var rule *models.Rule
		if loadedRule, ok := rulesByID[event.RuleID]; ok {
			rule = &loadedRule
		}
		scopedTopologyID, scopedToSingleTopology := singleRuleTopologyID(rule)

		if normalizedStatus == "closed" && (!hasExisting || existing.SchemaVersion >= rcaRecordSchemaVersion) {
			if !hasExisting {
				summary.EventsSkipped++
				queueSkippedEventForPublish(recordsPendingPublish, existing, hasExisting, event, strings.TrimSpace(event.GroupByValues["topology_id"]), "closed event arrived before an RCA record was stored", nil, p.now().UTC())
				processedEventRefs = append(processedEventRefs, processedEventRef(event))
				if p.logger != nil {
					p.logger.Debug(
						"skipping closed event because no prior scored RCA record exists",
						"incident_id", event.IncidentID,
						"organization_id", event.OrganizationID,
						"rule_id", event.RuleID,
					)
				}
				continue
			}
			selectedTopologyID := strings.TrimSpace(existing.TopologyID)
			if selectedTopologyID == "" {
				selectedTopologyID = strings.TrimSpace(event.GroupByValues["topology_id"])
			}
			record := updateClosedRecord(existing, hasExisting, event, selectedTopologyID, p.now().UTC())
			recordsByIncident[incidentID] = record
			markDirtyIncident(dirtyIncidentIDs, incidentID)
			queueRecordsForPublish(recordsPendingPublish, record)
			summary.ClosedUpdates++
			summary.ResultWrites++
			changed = true
			processedEventRefs = append(processedEventRefs, processedEventRef(event))
			continue
		}

		var topologyCandidates []organizationTopologyCandidate
		if !scopedToSingleTopology {
			topologyCandidates = resolveOrganizationTopologies(event.OrganizationID, topologyDoc)
		}
		selection, eligible := p.selectScoringTopology(
			event,
			rule,
			event.OrganizationID,
			topologyDoc,
			scopedTopologyID,
			topologyCandidates,
			nil,
		)
		if !eligible {
			summary.EventsSkipped++
			queueSkippedEventForPublish(recordsPendingPublish, existing, hasExisting, event, scopedTopologyID, "rule topology scope did not match any organization topology", nil, p.now().UTC())
			processedEventRefs = append(processedEventRefs, processedEventRef(event))
			if p.logger != nil {
				p.logger.Debug(
					"skipping event because rule topology scope did not match any organization topology",
					"incident_id", event.IncidentID,
					"organization_id", event.OrganizationID,
					"rule_id", event.RuleID,
					"rule_topology_ids", ruleTopologyIDs(rule),
				)
			}
			continue
		}
		score := selection.Score
		var nearbyLogs []models.RelatedLog
		if p.shouldLoadScoringNearbyLogs(score) {
			nearbyLogs = p.loadScoringNearbyLogs(ctx, event)
			if len(nearbyLogs) > 0 {
				if rescored, ok := p.selectScoringTopology(
					event,
					rule,
					event.OrganizationID,
					topologyDoc,
					scopedTopologyID,
					topologyCandidates,
					nearbyLogs,
				); ok {
					selection = rescored
					score = rescored.Score
				}
			}
		}
		if !p.shouldPersistProbableCause(score) {
			summary.EventsSkipped++
			queueSkippedEventForPublish(recordsPendingPublish, existing, hasExisting, event, selection.TopologyID, "probable cause score was below the minimum threshold", &score, p.now().UTC())
			processedEventRefs = append(processedEventRefs, processedEventRef(event))
			if p.logger != nil {
				p.logger.Debug(
					"skipping probable cause below minimum threshold",
					"incident_id", event.IncidentID,
					"organization_id", event.OrganizationID,
					"rule_id", event.RuleID,
					"confidence_score", score.ConfidenceScore,
					"probable_cause_min_threshold", p.effectiveProbableCauseMin(),
				)
			}
			continue
		}
		record := buildRecord(existing, hasExisting, event, selection.TopologyID, score, p.now().UTC())
		record.Status = normalizedStatus
		record.LLM = nil

		if score.Classification == scoring.ClassificationConfirmed && p.explainer != nil && p.explainer.Enabled() {
			summary.LLMCalls++
			explanation, explainErr := p.explainIncident(ctx, event, rule, selection.Topology, score, nearbyLogs)
			if explainErr != nil {
				summary.LLMFailures++
				record.LLM = &models.LLMExplanation{
					Provider: "openai",
					Error:    explainErr.Error(),
				}
			} else {
				record.LLM = explanation
			}
		}

		recordsByIncident[incidentID] = record
		markDirtyIncident(dirtyIncidentIDs, incidentID)
		queueRecordsForPublish(recordsPendingPublish, record)
		summary.EventsScored++
		summary.ResultWrites++
		if score.Classification == scoring.ClassificationConfirmed {
			summary.ConfirmedRCAs++
		} else {
			summary.ProbableCauses++
		}
		changed = true
		processedEventRefs = append(processedEventRefs, processedEventRef(event))
	}

	if changed {
		if optimizedResultStore != nil {
			if err := optimizedResultStore.UpsertRecords(ctx, recordsForIncidentIDs(recordsByIncident, dirtyIncidentIDs)); err != nil {
				return fmt.Errorf("save result store: %w", err)
			}
		} else {
			if err := p.results.Save(ctx, storage.FromIncidentMap(recordsByIncident)); err != nil {
				return fmt.Errorf("save result store: %w", err)
			}
		}
	}
	if p.resultPublisher != nil && len(recordsPendingPublish) > 0 {
		if err := p.resultPublisher.UpsertRecords(ctx, publishedRecords(recordsPendingPublish)); err != nil {
			return fmt.Errorf("persist RCA results to MongoDB: %w", err)
		}
	}
	if err := p.reader.MarkCorrelationEventsProcessed(ctx, processedEventRefs); err != nil {
		return fmt.Errorf("mark processed correlation events: %w", err)
	}
	nextCheckpoint.SearchAfter = nil
	if err := p.checkpoints.Save(ctx, nextCheckpoint); err != nil {
		return fmt.Errorf("save checkpoint: %w", err)
	}

	if p.logger != nil {
		effectiveReaderSettings := readerSettings
		if effectiveReaderSettings.PageSize <= 0 {
			effectiveReaderSettings.PageSize = 0
		}
		p.logger.Info(
			"log RCA cycle completed",
			"events_read", summary.EventsRead,
			"events_scored", summary.EventsScored,
			"events_skipped", summary.EventsSkipped,
			"closed_updates", summary.ClosedUpdates,
			"confirmed_rca", summary.ConfirmedRCAs,
			"probable_causes", summary.ProbableCauses,
			"llm_calls", summary.LLMCalls,
			"llm_failures", summary.LLMFailures,
			"result_writes", summary.ResultWrites,
			"pages_read", summary.PagesRead,
			"workload_capped", summary.WorkloadCapped,
			"effective_reader_page_size", effectiveReaderSettings.PageSize,
			"effective_max_pages_per_cycle", effectiveReaderSettings.MaxPagesPerCycle,
		)
	}
	if p.autoscaler != nil && p.autoscaler.Enabled() {
		p.autoscaler.ObserveCycle(summary.EventsRead)
		if p.logger != nil {
			schedulerSettings := p.autoscaler.CurrentSchedulerSettings()
			nextReaderSettings := p.autoscaler.CurrentReaderSettings()
			p.logger.Info(
				"autoscaling workload observed",
				"correlation_events", summary.EventsRead,
				"pages_read", summary.PagesRead,
				"workload_capped", summary.WorkloadCapped,
				"next_scheduler_interval", schedulerSettings.Interval.String(),
				"next_scheduler_run_timeout", schedulerSettings.RunTimeout.String(),
				"next_reader_page_size", nextReaderSettings.PageSize,
				"next_max_pages_per_cycle", nextReaderSettings.MaxPagesPerCycle,
			)
		}
	}
	return nil
}

func (p *Processor) collectOwnedEvents(
	ctx context.Context,
	checkpoint models.ReaderCheckpoint,
	maxPagesPerCycle int,
) ([]models.CorrelationEvent, models.ReaderCheckpoint, int, bool, error) {
	nextCheckpoint := checkpoint
	events := make([]models.CorrelationEvent, 0)
	pagesRead := 0
	workloadCapped := false
	for {
		if maxPagesPerCycle > 0 && pagesRead >= maxPagesPerCycle {
			workloadCapped = true
			break
		}
		page, pageCheckpoint, err := p.reader.ReadCorrelationEvents(ctx, nextCheckpoint)
		if err != nil {
			return nil, models.ReaderCheckpoint{}, 0, false, err
		}
		if len(page) == 0 {
			break
		}
		pagesRead++
		for _, event := range page {
			if !p.ownsEvent(event) {
				continue
			}
			events = append(events, event)
		}
		nextCheckpoint = pageCheckpoint
	}
	return events, nextCheckpoint, pagesRead, workloadCapped, nil
}

func (p *Processor) loadResultRecords(
	ctx context.Context,
	events []models.CorrelationEvent,
) (map[string]models.RCARecord, IncidentResultStore, error) {
	if scopedStore, ok := p.results.(IncidentResultStore); ok {
		recordsByIncident, err := scopedStore.LoadByIncidentIDs(ctx, incidentIDsFromEvents(events))
		if err != nil {
			return nil, nil, fmt.Errorf("load result store: %w", err)
		}
		return recordsByIncident, scopedStore, nil
	}

	resultDoc, err := p.results.Load(ctx)
	if err != nil {
		return nil, nil, fmt.Errorf("load result store: %w", err)
	}
	return storage.ByIncident(resultDoc), nil, nil
}

func (p *Processor) ownsEvent(event models.CorrelationEvent) bool {
	if p.workerCount <= 1 {
		return true
	}
	if p.workerIndex < 0 || p.workerIndex >= p.workerCount {
		return false
	}

	key := ownershipKey(event)
	if key == "" {
		return p.workerIndex == 0
	}

	hasher := fnv.New32a()
	_, _ = hasher.Write([]byte(key))
	return int(hasher.Sum32()%uint32(p.workerCount)) == p.workerIndex
}

func ownershipKey(event models.CorrelationEvent) string {
	organizationID := strings.TrimSpace(event.OrganizationID)
	incidentID := strings.TrimSpace(event.IncidentID)
	if organizationID != "" || incidentID != "" {
		return organizationID + "|" + incidentID
	}

	resultSignature := strings.TrimSpace(event.ResultSignature)
	if resultSignature != "" {
		return resultSignature
	}

	documentID := strings.TrimSpace(event.DocumentID)
	if documentID != "" {
		return documentID
	}

	if len(event.LogID) == 0 {
		return strings.TrimSpace(event.RuleID)
	}

	ids := make([]string, 0, len(event.LogID))
	for _, entry := range event.LogID {
		if trimmed := strings.TrimSpace(entry.ID); trimmed != "" {
			ids = append(ids, trimmed)
		}
	}
	sort.Strings(ids)
	if len(ids) == 0 {
		return strings.TrimSpace(event.RuleID)
	}
	return strings.TrimSpace(event.RuleID) + "|" + strings.Join(ids, ",")
}

func (p *Processor) explainIncident(
	ctx context.Context,
	event models.CorrelationEvent,
	rule *models.Rule,
	topology *models.OrganizationTopology,
	score models.ScoreResult,
	nearbyLogs []models.RelatedLog,
) (*models.LLMExplanation, error) {
	matchedLogs, err := p.reader.FetchMatchedLogs(ctx, event.LogID)
	if err != nil {
		return nil, fmt.Errorf("fetch matched logs: %w", err)
	}
	return p.explainer.Explain(ctx, models.ExplanationRequest{
		Event:       event,
		Rule:        rule,
		Score:       score,
		Topology:    topology,
		MatchedLogs: matchedLogs,
		NearbyLogs:  nearbyLogs,
	})
}

func (p *Processor) loadScoringNearbyLogs(ctx context.Context, event models.CorrelationEvent) []models.RelatedLog {
	if p.reader == nil {
		return nil
	}
	limit := p.neighborhoodLogLimit
	if limit <= 0 {
		limit = 20
	}
	if limit > 20 {
		limit = 20
	}
	nearbyLogs, err := p.reader.SearchRelatedLogs(ctx, event, limit)
	if err != nil {
		if p.logger != nil {
			p.logger.Warn("failed to fetch nearby logs for scoring", "incident_id", event.IncidentID, "error", err)
		}
		return nil
	}
	return nearbyLogs
}

func (p *Processor) shouldLoadScoringNearbyLogs(score models.ScoreResult) bool {
	trigger := p.nearbyLogTrigger
	if trigger <= 0 {
		trigger = 5.5
	}
	return score.ConfidenceScore >= trigger
}

func (p *Processor) shouldPersistProbableCause(score models.ScoreResult) bool {
	if score.Classification != scoring.ClassificationProbable {
		return true
	}
	return score.ConfidenceScore >= p.effectiveProbableCauseMin()
}

func (p *Processor) effectiveProbableCauseMin() float64 {
	if p.probableCauseMin <= 0 {
		return 0
	}
	return p.probableCauseMin
}

func (p *Processor) upgradeStaleRecords(
	ctx context.Context,
	recordsByIncident map[string]models.RCARecord,
	rulesByID map[string]models.Rule,
	topologyDoc models.TopologyDocument,
	summary *CycleSummary,
) (bool, error) {
	changed := false
	for incidentID, existing := range recordsByIncident {
		if existing.SchemaVersion >= rcaRecordSchemaVersion || strings.TrimSpace(existing.IncidentID) == "" {
			continue
		}

		event := correlationEventFromRecord(existing)
		if len(event.LogID) == 0 {
			continue
		}

		var rule *models.Rule
		if loadedRule, ok := rulesByID[event.RuleID]; ok {
			rule = &loadedRule
		}
		scopedTopologyID, scopedToSingleTopology := singleRuleTopologyID(rule)
		var topologyCandidates []organizationTopologyCandidate
		if !scopedToSingleTopology {
			topologyCandidates = resolveOrganizationTopologies(event.OrganizationID, topologyDoc)
		}

		selection, eligible := p.selectScoringTopology(
			event,
			rule,
			event.OrganizationID,
			topologyDoc,
			scopedTopologyID,
			topologyCandidates,
			nil,
		)
		if !eligible {
			continue
		}

		score := selection.Score
		var nearbyLogs []models.RelatedLog
		if p.shouldLoadScoringNearbyLogs(score) {
			nearbyLogs = p.loadScoringNearbyLogs(ctx, event)
			if len(nearbyLogs) > 0 {
				if rescored, ok := p.selectScoringTopology(
					event,
					rule,
					event.OrganizationID,
					topologyDoc,
					scopedTopologyID,
					topologyCandidates,
					nearbyLogs,
				); ok {
					selection = rescored
					score = rescored.Score
				}
			}
		}
		if !p.shouldPersistProbableCause(score) {
			continue
		}

		record := buildRecord(existing, true, event, selection.TopologyID, score, p.now().UTC())
		record.Status = normalizeStatus(existing.Status)
		record.LLM = existing.LLM
		if score.Classification == scoring.ClassificationConfirmed && p.explainer != nil && p.explainer.Enabled() && record.LLM == nil {
			summary.LLMCalls++
			explanation, explainErr := p.explainIncident(ctx, event, rule, selection.Topology, score, nearbyLogs)
			if explainErr != nil {
				summary.LLMFailures++
				record.LLM = &models.LLMExplanation{
					Provider: "openai",
					Error:    explainErr.Error(),
				}
			} else {
				record.LLM = explanation
			}
		}

		recordsByIncident[incidentID] = record
		summary.EventsScored++
		if score.Classification == scoring.ClassificationConfirmed {
			summary.ConfirmedRCAs++
		} else {
			summary.ProbableCauses++
		}
		summary.ResultWrites++
		changed = true
	}
	return changed, nil
}

func (p *Processor) selectScoringTopology(
	event models.CorrelationEvent,
	rule *models.Rule,
	organizationID string,
	document models.TopologyDocument,
	scopedTopologyID string,
	candidates []organizationTopologyCandidate,
	nearbyLogs []models.RelatedLog,
) (topologySelection, bool) {
	if scopedTopologyID != "" {
		topology, found := resolveOrganizationTopologyByID(organizationID, scopedTopologyID, document)
		if !found {
			return topologySelection{}, false
		}

		topologyCopy := topology
		topologyCopy.TopologyID = scopedTopologyID
		return topologySelection{
			TopologyID: scopedTopologyID,
			Topology:   &topologyCopy,
			Score:      p.scorer.Score(event, rule, &topologyCopy, nearbyLogs),
		}, true
	}

	allowed := allowedTopologyIDSet(ruleTopologyIDs(rule))
	if len(candidates) == 0 {
		if len(allowed) > 0 {
			return topologySelection{}, false
		}
		return topologySelection{
			TopologyID: "",
			Topology:   nil,
			Score:      p.scorer.Score(event, rule, nil, nearbyLogs),
		}, true
	}

	var best topologySelection
	found := false
	for _, candidate := range candidates {
		if len(allowed) > 0 {
			if _, ok := allowed[candidate.TopologyID]; !ok {
				continue
			}
		}

		topologyCopy := candidate.Topology
		topologyCopy.TopologyID = candidate.TopologyID
		selection := topologySelection{
			TopologyID: candidate.TopologyID,
			Topology:   &topologyCopy,
			Score:      p.scorer.Score(event, rule, &topologyCopy, nearbyLogs),
		}
		if !found || betterTopologySelection(selection, best) {
			best = selection
			found = true
		}
	}
	return best, found
}

func betterTopologySelection(left, right topologySelection) bool {
	leftBreakdown := left.Score.Breakdown
	rightBreakdown := right.Score.Breakdown

	if leftBreakdown.TopologyCoverage != rightBreakdown.TopologyCoverage {
		return leftBreakdown.TopologyCoverage > rightBreakdown.TopologyCoverage
	}
	if leftBreakdown.IdentityConfidence != rightBreakdown.IdentityConfidence {
		return leftBreakdown.IdentityConfidence > rightBreakdown.IdentityConfidence
	}
	if leftBreakdown.DependencyMatch != rightBreakdown.DependencyMatch {
		return leftBreakdown.DependencyMatch > rightBreakdown.DependencyMatch
	}
	if leftBreakdown.RuleCompleteness != rightBreakdown.RuleCompleteness {
		return leftBreakdown.RuleCompleteness > rightBreakdown.RuleCompleteness
	}
	if left.Score.ConfidenceScore != right.Score.ConfidenceScore {
		return left.Score.ConfidenceScore > right.Score.ConfidenceScore
	}
	return strings.TrimSpace(left.TopologyID) < strings.TrimSpace(right.TopologyID)
}

func ruleTopologyIDs(rule *models.Rule) []string {
	if rule == nil {
		return nil
	}
	return append([]string(nil), rule.TopologyIDs...)
}

func singleRuleTopologyID(rule *models.Rule) (string, bool) {
	if rule == nil {
		return "", false
	}

	var selected string
	for _, raw := range rule.TopologyIDs {
		topologyID := strings.TrimSpace(raw)
		if topologyID == "" {
			continue
		}
		if selected == "" {
			selected = topologyID
			continue
		}
		if selected != topologyID {
			return "", false
		}
	}
	if selected == "" {
		return "", false
	}
	return selected, true
}

func allowedTopologyIDSet(raw []string) map[string]struct{} {
	if len(raw) == 0 {
		return nil
	}
	allowed := make(map[string]struct{}, len(raw))
	for _, item := range raw {
		trimmed := strings.TrimSpace(item)
		if trimmed == "" {
			continue
		}
		allowed[trimmed] = struct{}{}
	}
	if len(allowed) == 0 {
		return nil
	}
	return allowed
}

func resolveOrganizationTopologyByID(
	organizationID string,
	topologyID string,
	document models.TopologyDocument,
) (models.OrganizationTopology, bool) {
	trimmedTopologyID := strings.TrimSpace(topologyID)
	if trimmedTopologyID == "" {
		return models.OrganizationTopology{}, false
	}

	orgTopologies, ok := document.Organizations[organizationID]
	if !ok || len(orgTopologies) == 0 {
		return models.OrganizationTopology{}, false
	}

	if topology, found := orgTopologies[trimmedTopologyID]; found {
		if !hasTopologyData(topology) {
			return models.OrganizationTopology{}, false
		}
		return topology, true
	}

	for key, topology := range orgTopologies {
		if strings.TrimSpace(key) != trimmedTopologyID {
			continue
		}
		if !hasTopologyData(topology) {
			return models.OrganizationTopology{}, false
		}
		return topology, true
	}

	return models.OrganizationTopology{}, false
}

func resolveOrganizationTopologies(organizationID string, document models.TopologyDocument) []organizationTopologyCandidate {
	orgTopologies, ok := document.Organizations[organizationID]
	if !ok || len(orgTopologies) == 0 {
		return nil
	}

	topologyIDs := make([]string, 0, len(orgTopologies))
	for topologyID := range orgTopologies {
		topologyIDs = append(topologyIDs, topologyID)
	}
	sort.Strings(topologyIDs)

	candidates := make([]organizationTopologyCandidate, 0, len(topologyIDs))
	for idx, topologyID := range topologyIDs {
		topology := orgTopologies[topologyID]
		if !hasTopologyData(topology) {
			continue
		}

		resolvedTopologyID := firstNonEmpty(strings.TrimSpace(topologyID), fmt.Sprintf("%s::topology_%d", organizationID, idx+1))
		topologyCopy := topology
		topologyCopy.TopologyID = resolvedTopologyID
		candidates = append(candidates, organizationTopologyCandidate{
			TopologyID: resolvedTopologyID,
			Topology:   topologyCopy,
		})
	}
	return candidates
}

func hasTopologyData(topology models.OrganizationTopology) bool {
	return len(topology.Services) > 0 ||
		len(topology.Dependencies) > 0 ||
		len(topology.Devices) > 0 ||
		len(topology.ServiceRelations) > 0
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			return trimmed
		}
	}
	return ""
}

func correlationEventFromRecord(record models.RCARecord) models.CorrelationEvent {
	return models.CorrelationEvent{
		SchemaVersion:   record.CorrelationSchemaVersion,
		LogID:           cloneEvidenceLogs(record.MatchedLogs),
		RuleCompletion:  estimatedRuleCompletion(record.ScoreBreakdown),
		RuleID:          record.RuleID,
		SequenceMatch:   record.ScoreBreakdown.SequenceMatch,
		IncidentID:      record.IncidentID,
		Status:          normalizeStatus(record.Status),
		FirstSeen:       cloneTimePtr(record.FirstSeen),
		LastSeen:        cloneTimePtr(record.LastSeen),
		OrganizationID:  record.OrganizationID,
		GroupByValues:   utils.CloneStringMap(record.GroupByValues),
		MatchedAt:       record.MatchedAt,
		CorrelatedAt:    record.CorrelatedAt,
		ResultSignature: strings.TrimSpace(record.ResultSignature),
		Audit:           cloneAudit(record.Audit),
	}
}

func estimatedRuleCompletion(breakdown models.ScoreBreakdown) float64 {
	denominator := breakdown.TopologyCoverage * breakdown.IdentityConfidence
	if denominator > 0 {
		return clampUnit(breakdown.RuleCompleteness / denominator)
	}
	return clampUnit(breakdown.RuleCompleteness)
}

func clampUnit(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return value
}

func buildRecord(existing models.RCARecord, hasExisting bool, event models.CorrelationEvent, topologyID string, score models.ScoreResult, now time.Time) models.RCARecord {
	matchedLogs := evidenceLogsForPersistence(existing.MatchedLogs, event.LogID)
	correlatedAt := correlationTimeForPersistence(existing.CorrelatedAt, event.CorrelatedAt)

	record := models.RCARecord{
		SchemaVersion:                rcaRecordSchemaVersion,
		CorrelationSchemaVersion:     event.SchemaVersion,
		IncidentID:                   event.IncidentID,
		OrganizationID:               event.OrganizationID,
		TopologyID:                   strings.TrimSpace(topologyID),
		RuleID:                       event.RuleID,
		Status:                       normalizeStatus(event.Status),
		Classification:               score.Classification,
		ConfidenceScore:              score.ConfidenceScore,
		ScoreBreakdown:               score.Breakdown,
		BelowThresholdReasons:        append([]string(nil), score.BelowThresholdReasons...),
		InvolvedServices:             append([]string(nil), score.InvolvedServices...),
		TriggerMatchedDocIDs:         triggerMatchedDocIDsForPersistence(existing, event),
		TriggerMatchedLogs:           triggerEvidenceLogsForPersistence(existing, event.LogID),
		MatchedDocIDs:                append([]string(nil), score.MatchedDocIDs...),
		MatchedLogs:                  matchedLogs,
		ContradictionEvidence:        cloneContradictionEvidence(score.ContradictionEvidence),
		GroupByValues:                utils.CloneStringMap(event.GroupByValues),
		FirstMatchedAt:               firstMatchedAtForPersistence(existing, event),
		FirstCorrelatedAt:            firstCorrelatedAtForPersistence(existing, event),
		FirstRCAGeneratedAt:          firstRCAGeneratedAtForPersistence(existing, now),
		MatchedAt:                    event.MatchedAt.UTC(),
		CorrelatedAt:                 correlatedAt,
		FirstSeen:                    cloneTimePtr(event.FirstSeen),
		LastSeen:                     cloneTimePtr(event.LastSeen),
		ResultSignature:              strings.TrimSpace(event.ResultSignature),
		LastProcessedResultSignature: strings.TrimSpace(event.ResultSignature),
		Audit:                        cloneAudit(event.Audit),
		RCAGeneratedAt:               now,
		UpdatedAt:                    now,
	}
	if hasExisting && record.FirstSeen == nil {
		record.FirstSeen = cloneTimePtr(existing.FirstSeen)
	}
	return record
}

func buildSkippedPublishRecord(existing models.RCARecord, hasExisting bool, event models.CorrelationEvent, topologyID, reason string, score *models.ScoreResult, now time.Time) models.RCARecord {
	record := existing
	if score != nil {
		record = buildRecord(existing, hasExisting, event, topologyID, *score, now)
	} else {
		if !hasExisting {
			record = models.RCARecord{
				SchemaVersion:            rcaRecordSchemaVersion,
				Classification:           scoring.ClassificationProbable,
				CorrelationSchemaVersion: event.SchemaVersion,
			}
		}
		record.SchemaVersion = rcaRecordSchemaVersion
		record.CorrelationSchemaVersion = event.SchemaVersion
		record.IncidentID = publishIncidentID(event)
		record.OrganizationID = event.OrganizationID
		if strings.TrimSpace(record.TopologyID) == "" {
			record.TopologyID = strings.TrimSpace(topologyID)
		}
		record.RuleID = event.RuleID
		record.Status = normalizeStatus(event.Status)
		record.GroupByValues = utils.CloneStringMap(event.GroupByValues)
		record.TriggerMatchedDocIDs = triggerMatchedDocIDsForPersistence(existing, event)
		record.TriggerMatchedLogs = triggerEvidenceLogsForPersistence(existing, event.LogID)
		record.MatchedLogs = evidenceLogsForPersistence(existing.MatchedLogs, event.LogID)
		record.MatchedDocIDs = matchedDocIDsFromEvent(event)
		record.ResultSignature = strings.TrimSpace(event.ResultSignature)
		record.LastProcessedResultSignature = strings.TrimSpace(event.ResultSignature)
		record.Audit = cloneAudit(event.Audit)
		record.FirstMatchedAt = firstMatchedAtForPersistence(existing, event)
		record.FirstCorrelatedAt = firstCorrelatedAtForPersistence(existing, event)
		record.FirstRCAGeneratedAt = firstRCAGeneratedAtForPersistence(existing, now)
		record.CorrelatedAt = correlationTimeForPersistence(existing.CorrelatedAt, event.CorrelatedAt)
		record.RCAGeneratedAt = now
		record.UpdatedAt = now
		if !event.MatchedAt.IsZero() {
			record.MatchedAt = event.MatchedAt.UTC()
		}
		if event.FirstSeen != nil {
			record.FirstSeen = cloneTimePtr(event.FirstSeen)
		} else if hasExisting && record.FirstSeen == nil {
			record.FirstSeen = cloneTimePtr(existing.FirstSeen)
		}
		if event.LastSeen != nil {
			record.LastSeen = cloneTimePtr(event.LastSeen)
		} else if hasExisting && record.LastSeen == nil {
			record.LastSeen = cloneTimePtr(existing.LastSeen)
		}
	}
	if record.IncidentID == "" {
		record.IncidentID = publishIncidentID(event)
	}
	if record.RuleID == "" {
		record.RuleID = event.RuleID
	}
	if record.OrganizationID == "" {
		record.OrganizationID = event.OrganizationID
	}
	if strings.TrimSpace(record.TopologyID) == "" {
		record.TopologyID = strings.TrimSpace(topologyID)
	}
	if strings.TrimSpace(record.Status) == "" {
		record.Status = normalizeStatus(event.Status)
	}
	if reason != "" {
		record.BelowThresholdReasons = appendReason(record.BelowThresholdReasons, reason)
	}
	return record
}

func updateClosedRecord(existing models.RCARecord, hasExisting bool, event models.CorrelationEvent, topologyID string, now time.Time) models.RCARecord {
	record := existing
	if !hasExisting {
		record = models.RCARecord{
			SchemaVersion:            rcaRecordSchemaVersion,
			IncidentID:               event.IncidentID,
			OrganizationID:           event.OrganizationID,
			TopologyID:               strings.TrimSpace(topologyID),
			RuleID:                   event.RuleID,
			Classification:           scoring.ClassificationProbable,
			BelowThresholdReasons:    []string{"Closed incident arrived before an RCA assessment was stored."},
			CorrelationSchemaVersion: event.SchemaVersion,
		}
	}
	record.SchemaVersion = rcaRecordSchemaVersion
	record.Status = "closed"
	record.OrganizationID = event.OrganizationID
	if strings.TrimSpace(record.TopologyID) == "" {
		record.TopologyID = strings.TrimSpace(topologyID)
	}
	record.RuleID = event.RuleID
	record.GroupByValues = utils.CloneStringMap(event.GroupByValues)
	record.TriggerMatchedDocIDs = triggerMatchedDocIDsForPersistence(existing, event)
	record.TriggerMatchedLogs = triggerEvidenceLogsForPersistence(existing, event.LogID)
	record.MatchedLogs = evidenceLogsForPersistence(existing.MatchedLogs, event.LogID)
	record.MatchedDocIDs = matchedDocIDsFromEvent(event)
	record.ResultSignature = strings.TrimSpace(event.ResultSignature)
	record.LastProcessedResultSignature = strings.TrimSpace(event.ResultSignature)
	record.Audit = cloneAudit(event.Audit)
	record.FirstMatchedAt = firstMatchedAtForPersistence(existing, event)
	record.FirstCorrelatedAt = firstCorrelatedAtForPersistence(existing, event)
	record.FirstRCAGeneratedAt = firstRCAGeneratedAtForPersistence(existing, now)
	record.CorrelatedAt = correlationTimeForPersistence(existing.CorrelatedAt, event.CorrelatedAt)
	record.RCAGeneratedAt = now
	record.UpdatedAt = now
	record.MatchedAt = event.MatchedAt.UTC()
	if event.FirstSeen != nil {
		record.FirstSeen = cloneTimePtr(event.FirstSeen)
	}
	if event.LastSeen != nil {
		record.LastSeen = cloneTimePtr(event.LastSeen)
	} else {
		closedAt := now.UTC()
		record.LastSeen = &closedAt
	}
	return record
}

func isDuplicateEvent(existing models.RCARecord, normalizedStatus, resultSignature string) bool {
	if strings.TrimSpace(existing.IncidentID) == "" {
		return false
	}
	if existing.SchemaVersion < rcaRecordSchemaVersion {
		return false
	}
	if strings.TrimSpace(resultSignature) == "" {
		return false
	}
	return strings.TrimSpace(existing.LastProcessedResultSignature) == strings.TrimSpace(resultSignature) &&
		normalizeStatus(existing.Status) == normalizedStatus
}

func normalizeStatus(status string) string {
	switch strings.ToLower(strings.TrimSpace(status)) {
	case "updated":
		return "updated"
	case "closed":
		return "closed"
	default:
		return "open"
	}
}

func matchedDocIDsFromEvent(event models.CorrelationEvent) []string {
	ids := make([]string, 0, len(event.LogID))
	for _, log := range event.LogID {
		if strings.TrimSpace(log.ID) != "" {
			ids = append(ids, log.ID)
		}
	}
	return utils.UniqueStrings(ids)
}

func triggerMatchedDocIDsForPersistence(existing models.RCARecord, event models.CorrelationEvent) []string {
	if ids := normalizeDocIDs(existing.TriggerMatchedDocIDs); len(ids) > 0 {
		return ids
	}
	if ids := evidenceDocIDs(existing.TriggerMatchedLogs); len(ids) > 0 {
		return ids
	}
	if ids := normalizeDocIDs(existing.MatchedDocIDs); len(ids) > 0 {
		return ids
	}
	if ids := evidenceDocIDs(existing.MatchedLogs); len(ids) > 0 {
		return ids
	}
	return matchedDocIDsFromEvent(event)
}

func normalizeDocIDs(values []string) []string {
	ids := make([]string, 0, len(values))
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			ids = append(ids, trimmed)
		}
	}
	return utils.UniqueStrings(ids)
}

func evidenceDocIDs(values []models.EvidenceLog) []string {
	ids := make([]string, 0, len(values))
	for _, value := range values {
		if trimmed := strings.TrimSpace(value.ID); trimmed != "" {
			ids = append(ids, trimmed)
		}
	}
	return utils.UniqueStrings(ids)
}

func triggerEvidenceLogsForPersistence(existing models.RCARecord, incoming []models.EvidenceLog) []models.EvidenceLog {
	base := existing.TriggerMatchedLogs
	if len(base) == 0 {
		base = existing.MatchedLogs
	}
	if len(base) == 0 {
		if len(existing.TriggerMatchedDocIDs) > 0 || len(existing.MatchedDocIDs) > 0 {
			return nil
		}
		return evidenceLogsForPersistence(nil, incoming)
	}
	return preserveEvidenceSnapshot(base, incoming)
}

func cloneTimePtr(input *time.Time) *time.Time {
	if input == nil {
		return nil
	}
	value := input.UTC()
	return &value
}

func firstMatchedAtForPersistence(existing models.RCARecord, event models.CorrelationEvent) time.Time {
	return firstNonZeroTime(existing.FirstMatchedAt, existing.MatchedAt, event.MatchedAt)
}

func firstCorrelatedAtForPersistence(existing models.RCARecord, event models.CorrelationEvent) time.Time {
	return firstNonZeroTime(existing.FirstCorrelatedAt, existing.CorrelatedAt, event.CorrelatedAt)
}

func firstRCAGeneratedAtForPersistence(existing models.RCARecord, now time.Time) time.Time {
	return firstNonZeroTime(existing.FirstRCAGeneratedAt, existing.RCAGeneratedAt, existing.UpdatedAt, now)
}

func firstNonZeroTime(values ...time.Time) time.Time {
	for _, value := range values {
		if !value.IsZero() {
			return value.UTC()
		}
	}
	return time.Time{}
}

func cloneAudit(audit *models.MatchAudit) *models.MatchAudit {
	if audit == nil {
		return nil
	}
	cloned := *audit
	cloned.GroupBy = append([]string(nil), audit.GroupBy...)
	cloned.GroupByValues = utils.CloneStringMap(audit.GroupByValues)
	cloned.RequiredMetadata = utils.CloneStringMap(audit.RequiredMetadata)
	cloned.NegativeSignals = append([]string(nil), audit.NegativeSignals...)
	cloned.DeduplicationKey = append([]string(nil), audit.DeduplicationKey...)
	cloned.MatchedLogIDs = append([]string(nil), audit.MatchedLogIDs...)
	cloned.MatchedSignals = append([]string(nil), audit.MatchedSignals...)
	if len(audit.Steps) > 0 {
		cloned.Steps = make([]models.MatchStepAudit, len(audit.Steps))
		for idx, step := range audit.Steps {
			cloned.Steps[idx] = step
			cloned.Steps[idx].MatchedLogIDs = append([]string(nil), step.MatchedLogIDs...)
		}
	}
	return &cloned
}

func cloneEvidenceLogs(input []models.EvidenceLog) []models.EvidenceLog {
	if len(input) == 0 {
		return nil
	}
	cloned := make([]models.EvidenceLog, len(input))
	for idx, entry := range input {
		cloned[idx] = entry
		if len(entry.HostIPs) > 0 {
			cloned[idx].HostIPs = append([]string(nil), entry.HostIPs...)
		}
	}
	return cloned
}

func evidenceLogsForPersistence(existing []models.EvidenceLog, incoming []models.EvidenceLog) []models.EvidenceLog {
	if len(incoming) == 0 {
		return normalizeEvidenceLogs(existing)
	}

	existingByID := make(map[string]models.EvidenceLog, len(existing))
	for _, entry := range existing {
		docID := strings.TrimSpace(entry.ID)
		if docID == "" {
			continue
		}
		existingByID[docID] = normalizeEvidenceLog(entry)
	}

	merged := make([]models.EvidenceLog, len(incoming))
	for idx, entry := range incoming {
		normalized := normalizeEvidenceLog(entry)
		docID := strings.TrimSpace(normalized.ID)
		if docID != "" {
			if prior, ok := existingByID[docID]; ok {
				if normalized.Timestamp.IsZero() {
					normalized.Timestamp = prior.Timestamp.UTC()
				}
				if normalized.SignalizedAt.IsZero() {
					normalized.SignalizedAt = prior.SignalizedAt.UTC()
				}
			}
		}
		merged[idx] = normalized
	}
	return merged
}

func preserveEvidenceSnapshot(existing []models.EvidenceLog, incoming []models.EvidenceLog) []models.EvidenceLog {
	if len(existing) == 0 {
		return evidenceLogsForPersistence(nil, incoming)
	}
	if len(incoming) == 0 {
		return normalizeEvidenceLogs(existing)
	}

	incomingByID := make(map[string]models.EvidenceLog, len(incoming))
	for _, entry := range incoming {
		normalized := normalizeEvidenceLog(entry)
		docID := strings.TrimSpace(normalized.ID)
		if docID == "" {
			continue
		}
		incomingByID[docID] = normalized
	}

	result := make([]models.EvidenceLog, len(existing))
	for idx, entry := range existing {
		normalized := normalizeEvidenceLog(entry)
		docID := strings.TrimSpace(normalized.ID)
		if incomingEntry, ok := incomingByID[docID]; ok {
			normalized = fillMissingEvidenceFields(normalized, incomingEntry)
		}
		result[idx] = normalized
	}
	return result
}

func normalizeEvidenceLogs(input []models.EvidenceLog) []models.EvidenceLog {
	cloned := cloneEvidenceLogs(input)
	for idx := range cloned {
		cloned[idx] = normalizeEvidenceLog(cloned[idx])
	}
	return cloned
}

func fillMissingEvidenceFields(current models.EvidenceLog, incoming models.EvidenceLog) models.EvidenceLog {
	filled := current
	if filled.Severity == "" {
		filled.Severity = incoming.Severity
	}
	if filled.SourceIndex == "" {
		filled.SourceIndex = incoming.SourceIndex
	}
	if filled.Signal == "" {
		filled.Signal = incoming.Signal
	}
	if filled.Timestamp.IsZero() && !incoming.Timestamp.IsZero() {
		filled.Timestamp = incoming.Timestamp.UTC()
	}
	if filled.SignalizedAt.IsZero() && !incoming.SignalizedAt.IsZero() {
		filled.SignalizedAt = incoming.SignalizedAt.UTC()
	}
	if filled.ServiceName == "" {
		filled.ServiceName = incoming.ServiceName
	}
	if filled.HostName == "" {
		filled.HostName = incoming.HostName
	}
	if filled.HostIP == "" {
		filled.HostIP = incoming.HostIP
	}
	if len(filled.HostIPs) == 0 && len(incoming.HostIPs) > 0 {
		filled.HostIPs = append([]string(nil), incoming.HostIPs...)
	}
	return filled
}

func normalizeEvidenceLog(entry models.EvidenceLog) models.EvidenceLog {
	normalized := entry
	if !normalized.Timestamp.IsZero() {
		normalized.Timestamp = normalized.Timestamp.UTC()
	}
	if !normalized.SignalizedAt.IsZero() {
		normalized.SignalizedAt = normalized.SignalizedAt.UTC()
	}
	return normalized
}

func correlationTimeForPersistence(existing time.Time, incoming time.Time) time.Time {
	if !incoming.IsZero() {
		return incoming.UTC()
	}
	if !existing.IsZero() {
		return existing.UTC()
	}
	return time.Time{}
}

func cloneContradictionEvidence(input []models.ContradictionEvidence) []models.ContradictionEvidence {
	if len(input) == 0 {
		return nil
	}
	cloned := make([]models.ContradictionEvidence, len(input))
	copy(cloned, input)
	return cloned
}

func (p *Processor) enrichEventEvidence(ctx context.Context, event models.CorrelationEvent) (models.CorrelationEvent, error) {
	if !evidenceNeedsMatchedLogEnrichment(event.LogID) || p.reader == nil {
		return event, nil
	}

	matchedLogs, err := p.reader.FetchMatchedLogs(ctx, event.LogID)
	if err != nil {
		return event, err
	}
	if len(matchedLogs) == 0 {
		return event, nil
	}

	enriched := event
	enriched.LogID = cloneEvidenceLogs(event.LogID)

	byExactKey := make(map[string]models.RelatedLog, len(matchedLogs))
	byDocID := make(map[string]models.RelatedLog, len(matchedLogs))
	for _, matched := range matchedLogs {
		docID := strings.TrimSpace(matched.DocID)
		if docID == "" {
			continue
		}
		byExactKey[evidenceLookupKey(matched.Index, docID)] = matched
		if _, ok := byDocID[docID]; !ok {
			byDocID[docID] = matched
		}
	}

	for idx, entry := range enriched.LogID {
		if !evidenceEntryNeedsEnrichment(entry) {
			continue
		}
		docID := strings.TrimSpace(entry.ID)
		if docID == "" {
			continue
		}
		matched, ok := byExactKey[evidenceLookupKey(entry.SourceIndex, docID)]
		if !ok {
			matched, ok = byDocID[docID]
		}
		if !ok {
			continue
		}
		enriched.LogID[idx] = mergeEvidenceEntry(entry, matched)
	}
	return enriched, nil
}

func evidenceNeedsMatchedLogEnrichment(entries []models.EvidenceLog) bool {
	for _, entry := range entries {
		if evidenceEntryNeedsEnrichment(entry) {
			return true
		}
	}
	return false
}

func evidenceEntryNeedsEnrichment(entry models.EvidenceLog) bool {
	return strings.TrimSpace(entry.HostIP) == "" && len(entry.HostIPs) == 0
}

func evidenceLookupKey(index, docID string) string {
	return strings.TrimSpace(index) + "|" + strings.TrimSpace(docID)
}

func mergeEvidenceEntry(entry models.EvidenceLog, matched models.RelatedLog) models.EvidenceLog {
	merged := entry
	if merged.SourceIndex == "" {
		merged.SourceIndex = matched.Index
	}
	if merged.ServiceName == "" {
		merged.ServiceName = matched.ServiceName
	}
	if merged.HostName == "" {
		merged.HostName = matched.HostName
	}
	if merged.HostIP == "" {
		merged.HostIP = matched.HostIP
	}
	if len(merged.HostIPs) == 0 && len(matched.HostIPs) > 0 {
		merged.HostIPs = append([]string(nil), matched.HostIPs...)
	}
	return merged
}

func queueRecordsForPublish(destination map[string]models.RCARecord, records ...models.RCARecord) {
	for _, record := range records {
		incidentID := strings.TrimSpace(record.IncidentID)
		if incidentID == "" {
			continue
		}
		destination[resultPublishKey(record)] = record
	}
}

func publishedRecords(recordsByKey map[string]models.RCARecord) []models.RCARecord {
	if len(recordsByKey) == 0 {
		return nil
	}

	keys := make([]string, 0, len(recordsByKey))
	for key := range recordsByKey {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	records := make([]models.RCARecord, 0, len(keys))
	for _, key := range keys {
		records = append(records, recordsByKey[key])
	}
	return records
}

func resultPublishKey(record models.RCARecord) string {
	incidentID := strings.TrimSpace(record.IncidentID)
	resultSignature := strings.TrimSpace(record.ResultSignature)
	if resultSignature == "" {
		return incidentID
	}
	return incidentID + "|" + resultSignature
}

func queueSkippedEventForPublish(
	destination map[string]models.RCARecord,
	existing models.RCARecord,
	hasExisting bool,
	event models.CorrelationEvent,
	topologyID, reason string,
	score *models.ScoreResult,
	now time.Time,
) {
	if destination == nil {
		return
	}
	record := buildSkippedPublishRecord(existing, hasExisting, event, topologyID, reason, score, now)
	if strings.TrimSpace(record.IncidentID) == "" {
		return
	}
	queueRecordsForPublish(destination, record)
}

func publishIncidentID(event models.CorrelationEvent) string {
	if trimmed := strings.TrimSpace(event.IncidentID); trimmed != "" {
		return trimmed
	}
	if trimmed := strings.TrimSpace(event.DocumentID); trimmed != "" {
		return trimmed
	}
	return strings.TrimSpace(event.ResultSignature)
}

func processedEventRef(event models.CorrelationEvent) models.CorrelationEventRef {
	return models.CorrelationEventRef{
		DocumentID:      strings.TrimSpace(event.DocumentID),
		DocumentIndex:   strings.TrimSpace(event.DocumentIndex),
		ResultSignature: strings.TrimSpace(event.ResultSignature),
	}
}

func appendReason(reasons []string, reason string) []string {
	trimmed := strings.TrimSpace(reason)
	if trimmed == "" {
		return reasons
	}
	for _, existing := range reasons {
		if strings.EqualFold(strings.TrimSpace(existing), trimmed) {
			return reasons
		}
	}
	return append(reasons, trimmed)
}

func incidentIDsFromEvents(events []models.CorrelationEvent) []string {
	if len(events) == 0 {
		return nil
	}

	seen := make(map[string]struct{}, len(events))
	incidentIDs := make([]string, 0, len(events))
	for _, event := range events {
		incidentID := strings.TrimSpace(event.IncidentID)
		if incidentID == "" {
			continue
		}
		if _, ok := seen[incidentID]; ok {
			continue
		}
		seen[incidentID] = struct{}{}
		incidentIDs = append(incidentIDs, incidentID)
	}
	sort.Strings(incidentIDs)
	return incidentIDs
}

func markDirtyIncident(destination map[string]struct{}, incidentID string) {
	if destination == nil {
		return
	}
	trimmed := strings.TrimSpace(incidentID)
	if trimmed == "" {
		return
	}
	destination[trimmed] = struct{}{}
}

func markDirtyIncidents(destination map[string]struct{}, records map[string]models.RCARecord) {
	for incidentID := range records {
		markDirtyIncident(destination, incidentID)
	}
}

func recordsForIncidentIDs(recordsByIncident map[string]models.RCARecord, incidentIDs map[string]struct{}) []models.RCARecord {
	if len(recordsByIncident) == 0 || len(incidentIDs) == 0 {
		return nil
	}

	keys := make([]string, 0, len(incidentIDs))
	for incidentID := range incidentIDs {
		if _, ok := recordsByIncident[incidentID]; ok {
			keys = append(keys, incidentID)
		}
	}
	sort.Strings(keys)

	records := make([]models.RCARecord, 0, len(keys))
	for _, incidentID := range keys {
		records = append(records, recordsByIncident[incidentID])
	}
	return records
}
