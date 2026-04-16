package service

import (
	"context"
	"fmt"
	"log/slog"
	"sort"
	"strings"
	"time"

	"log_rca_engine/internal/models"
	"log_rca_engine/internal/scoring"
	"log_rca_engine/internal/storage"
	"log_rca_engine/internal/utils"
)

type CorrelationEventReader interface {
	ReadCorrelationEvents(ctx context.Context, checkpoint models.ReaderCheckpoint) ([]models.CorrelationEvent, models.ReaderCheckpoint, error)
	FetchMatchedLogs(ctx context.Context, evidence []models.EvidenceLog) ([]models.RelatedLog, error)
	SearchRelatedLogs(ctx context.Context, event models.CorrelationEvent, limit int) ([]models.RelatedLog, error)
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

type CheckpointStore interface {
	Load(ctx context.Context) (models.ReaderCheckpoint, error)
	Save(ctx context.Context, checkpoint models.ReaderCheckpoint) error
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
	Checkpoints          CheckpointStore
	Scorer               Scorer
	Explainer            Explainer
	NeighborhoodLogLimit int
	NearbyLogTrigger     float64
	ProbableCauseMin     float64
	Logger               *slog.Logger
}

type Processor struct {
	reader               CorrelationEventReader
	rules                RulesLoader
	topology             TopologyRepository
	results              ResultStore
	checkpoints          CheckpointStore
	scorer               Scorer
	explainer            Explainer
	neighborhoodLogLimit int
	nearbyLogTrigger     float64
	probableCauseMin     float64
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
		checkpoints:          deps.Checkpoints,
		scorer:               deps.Scorer,
		explainer:            deps.Explainer,
		neighborhoodLogLimit: deps.NeighborhoodLogLimit,
		nearbyLogTrigger:     deps.NearbyLogTrigger,
		probableCauseMin:     deps.ProbableCauseMin,
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
	resultDoc, err := p.results.Load(ctx)
	if err != nil {
		return fmt.Errorf("load result store: %w", err)
	}
	checkpoint, err := p.checkpoints.Load(ctx)
	if err != nil {
		return fmt.Errorf("load checkpoint: %w", err)
	}
	checkpoint.SearchAfter = nil

	recordsByIncident := storage.ByIncident(resultDoc)
	summary := CycleSummary{}
	changed := false
	nextCheckpoint := checkpoint

	for {
		events, pageCheckpoint, err := p.reader.ReadCorrelationEvents(ctx, nextCheckpoint)
		if err != nil {
			return fmt.Errorf("read correlation events: %w", err)
		}
		if len(events) == 0 {
			break
		}

		for _, event := range events {
			if err := ctx.Err(); err != nil {
				return err
			}
			summary.EventsRead++
			incidentID := strings.TrimSpace(event.IncidentID)
			if incidentID == "" {
				summary.EventsSkipped++
				continue
			}

			normalizedStatus := normalizeStatus(event.Status)
			existing, hasExisting := recordsByIncident[incidentID]
			if isDuplicateEvent(existing, normalizedStatus, event.ResultSignature) {
				summary.EventsSkipped++
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

			if normalizedStatus == "closed" {
				if !hasExisting {
					summary.EventsSkipped++
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
				summary.ClosedUpdates++
				summary.ResultWrites++
				changed = true
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
			summary.EventsScored++
			summary.ResultWrites++
			if score.Classification == scoring.ClassificationConfirmed {
				summary.ConfirmedRCAs++
			} else {
				summary.ProbableCauses++
			}
			changed = true
		}

		nextCheckpoint = pageCheckpoint
	}

	if changed {
		if err := p.results.Save(ctx, storage.FromIncidentMap(recordsByIncident)); err != nil {
			return fmt.Errorf("save result store: %w", err)
		}
	}
	nextCheckpoint.SearchAfter = nil
	if err := p.checkpoints.Save(ctx, nextCheckpoint); err != nil {
		return fmt.Errorf("save checkpoint: %w", err)
	}

	if p.logger != nil {
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
		)
	}
	return nil
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

func buildRecord(existing models.RCARecord, hasExisting bool, event models.CorrelationEvent, topologyID string, score models.ScoreResult, now time.Time) models.RCARecord {
	record := models.RCARecord{
		SchemaVersion:                1,
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
		MatchedDocIDs:                append([]string(nil), score.MatchedDocIDs...),
		MatchedLogs:                  cloneEvidenceLogs(event.LogID),
		GroupByValues:                utils.CloneStringMap(event.GroupByValues),
		MatchedAt:                    event.MatchedAt.UTC(),
		FirstSeen:                    cloneTimePtr(event.FirstSeen),
		LastSeen:                     cloneTimePtr(event.LastSeen),
		ResultSignature:              strings.TrimSpace(event.ResultSignature),
		LastProcessedResultSignature: strings.TrimSpace(event.ResultSignature),
		Audit:                        cloneAudit(event.Audit),
		UpdatedAt:                    now,
	}
	if hasExisting && record.FirstSeen == nil {
		record.FirstSeen = cloneTimePtr(existing.FirstSeen)
	}
	return record
}

func updateClosedRecord(existing models.RCARecord, hasExisting bool, event models.CorrelationEvent, topologyID string, now time.Time) models.RCARecord {
	record := existing
	if !hasExisting {
		record = models.RCARecord{
			SchemaVersion:            1,
			IncidentID:               event.IncidentID,
			OrganizationID:           event.OrganizationID,
			TopologyID:               strings.TrimSpace(topologyID),
			RuleID:                   event.RuleID,
			Classification:           scoring.ClassificationProbable,
			BelowThresholdReasons:    []string{"Closed incident arrived before an RCA assessment was stored."},
			CorrelationSchemaVersion: event.SchemaVersion,
		}
	}
	record.Status = "closed"
	record.OrganizationID = event.OrganizationID
	if strings.TrimSpace(record.TopologyID) == "" {
		record.TopologyID = strings.TrimSpace(topologyID)
	}
	record.RuleID = event.RuleID
	record.GroupByValues = utils.CloneStringMap(event.GroupByValues)
	record.MatchedLogs = cloneEvidenceLogs(event.LogID)
	record.MatchedDocIDs = matchedDocIDsFromEvent(event)
	record.ResultSignature = strings.TrimSpace(event.ResultSignature)
	record.LastProcessedResultSignature = strings.TrimSpace(event.ResultSignature)
	record.Audit = cloneAudit(event.Audit)
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

func cloneTimePtr(input *time.Time) *time.Time {
	if input == nil {
		return nil
	}
	value := input.UTC()
	return &value
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
