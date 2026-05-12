package enrichment

import (
	"context"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strings"
	"time"

	"rca/internal/rca/checkpoints"
	"rca/internal/rca/config"
	"rca/internal/rca/ingest"
	"rca/internal/rca/logging"
	"rca/internal/rca/rulelearning"
	"rca/internal/rca/rules"
	"rca/internal/rca/signalstream"
	"rca/internal/rca/util"
	"rca/internal/rca/writer"
)

var (
	organizationQueryPattern = regexp.MustCompile(`(?:[?&](?:org|organization)=)([A-Za-z0-9_-]+)`)
	ipv4Pattern              = regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`)
)

// CountClient is the count subset needed from Elasticsearch.
type CountClient interface {
	Count(index string, body map[string]any) (map[string]any, error)
}

// IndicesResolver expands wildcard source index patterns.
type IndicesResolver interface {
	IndicesGet(index string) (map[string]any, error)
}

// BulkClient writes bulk actions and returns success/error details.
type BulkClient interface {
	Bulk(actions []map[string]any) (int, []map[string]any, error)
}

// SignalPublisher writes compact signal events for downstream consumers.
type SignalPublisher interface {
	Publish(ctx context.Context, event signalstream.Event) error
	Close() error
}

// SignalEnrichmentService coordinates reading, rule matching, and writing enriched logs.
type SignalEnrichmentService struct {
	esClient        any
	config          config.AppConfig
	checkpointStore checkpoints.Store
	ruleLoader      *rules.RuleLoader
	ruleEngine      *rules.RuleEngine
	ruleLearner     *rulelearning.AutoRuleLearner
	actionFactory   writer.BulkActionFactory
	dynamicEPSByKey map[string]float64
	logger          logging.Logger
	bulkWriter      *writer.AsyncBulkWriter
	streamPublisher SignalPublisher
}

type workUnit struct {
	serviceConfig config.ServiceConfig
	ruleSet       *rules.RuleSet
	indexName     string
}

// NewSignalEnrichmentService constructs the enrichment service.
func NewSignalEnrichmentService(esClient any, cfg config.AppConfig, checkpointStore checkpoints.Store) (*SignalEnrichmentService, error) {
	return NewSignalEnrichmentServiceWithPublisher(esClient, cfg, checkpointStore, nil)
}

// NewSignalEnrichmentServiceWithPublisher constructs the enrichment service with optional compact signal publication.
func NewSignalEnrichmentServiceWithPublisher(
	esClient any,
	cfg config.AppConfig,
	checkpointStore checkpoints.Store,
	streamPublisher SignalPublisher,
) (*SignalEnrichmentService, error) {
	service := &SignalEnrichmentService{
		esClient:        esClient,
		config:          cfg,
		checkpointStore: checkpointStore,
		ruleLoader:      rules.NewRuleLoader(cfg.RulesDirectory),
		ruleEngine:      rules.NewRuleEngine(cfg.Pipeline.VendorAnchorEnforcementEnabled),
		ruleLearner: rulelearning.NewAutoRuleLearner(
			cfg.RuleLearning,
			cfg.RulesDirectory,
			serviceRuleFiles(cfg.Pipeline.Services),
		),
		actionFactory:   writer.BulkActionFactory{},
		dynamicEPSByKey: make(map[string]float64),
		logger:          logging.GetLogger("SignalEnrichmentService"),
		streamPublisher: streamPublisher,
	}

	bulkWriter, err := writer.NewAsyncBulkWriter(
		service.flush,
		maxInt(1, cfg.Pipeline.BulkWorkerCount),
		maxInt(1, cfg.Pipeline.BulkQueueSize),
		service.logger,
		cfg.Pipeline.BulkAutoscalingEnabled,
		maxInt(1, cfg.Pipeline.BulkAutoscalingMinWorkers),
		maxInt(1, cfg.Pipeline.BulkAutoscalingMaxWorkers),
		cfg.Pipeline.BulkAutoscalingScaleUpQueueRatio,
		cfg.Pipeline.BulkAutoscalingScaleDownQueueRatio,
		cfg.Pipeline.BulkAutoscalingCPULimitPercent,
		cfg.Pipeline.BulkAutoscalingMemoryLimitPercent,
		cfg.Pipeline.BulkAutoscalingCheckIntervalSeconds,
		cfg.Pipeline.BulkAutoscalingCooldownSeconds,
		cfg.Pipeline.BulkSpoolEnabled,
		cfg.Pipeline.BulkSpoolDirectory,
		int64(cfg.Pipeline.BulkSpoolMaxBytes),
		cfg.Pipeline.BulkSpoolReplayIntervalSeconds,
		cfg.Pipeline.BulkQueueEnqueueTimeoutSeconds,
	)
	if err != nil {
		return nil, err
	}
	service.bulkWriter = bulkWriter

	if err := service.validateRuntimeConfig(); err != nil {
		_ = service.bulkWriter.Close()
		return nil, err
	}
	return service, nil
}

// Shutdown drains the async writer and closes the checkpoint backend.
func (s *SignalEnrichmentService) Shutdown() error {
	if s.bulkWriter != nil {
		if err := s.bulkWriter.Close(); err != nil {
			return err
		}
	}
	if s.checkpointStore != nil {
		if err := s.checkpointStore.Close(); err != nil {
			return err
		}
	}
	if s.streamPublisher != nil {
		return s.streamPublisher.Close()
	}
	return nil
}

// RunCycle processes one full cycle across configured services and indices.
func (s *SignalEnrichmentService) RunCycle() (int, error) {
	cycleStarted := time.Now()
	processed := 0
	taken := 0
	var maxLagSeconds *float64

	allUnits := s.buildWorkUnits()
	ownedUnits := s.selectOwnedWorkUnits(allUnits)
	s.logWorkUnitOwnership(len(allUnits), ownedUnits)

	for _, unit := range ownedUnits {
		indexProcessed, indexTaken, indexLag, err := s.processIndex(unit.serviceConfig, unit.ruleSet, unit.indexName)
		if err != nil {
			s.logger.Exception(
				"Failed processing service/index",
				err,
				logging.F("service", unit.serviceConfig.Name),
				logging.F("index", unit.indexName),
			)
			continue
		}
		processed += indexProcessed
		taken += indexTaken
		if indexLag != nil {
			if maxLagSeconds == nil || *indexLag > *maxLagSeconds {
				maxLagSeconds = indexLag
			}
		}
	}

	if err := s.bulkWriter.Drain(); err != nil {
		return processed, err
	}

	cycleSeconds := time.Since(cycleStarted).Seconds()
	if cycleSeconds <= 0 {
		cycleSeconds = 0.000001
	}
	s.emitAutoscalingMetrics(processed, taken, maxLagSeconds, cycleSeconds)
	s.flushRuleLearningCandidates()
	return processed, nil
}

func (s *SignalEnrichmentService) buildWorkUnits() []workUnit {
	units := make([]workUnit, 0)
	for _, serviceConfig := range s.config.Pipeline.Services {
		if !serviceConfig.Enabled {
			continue
		}

		ruleSet, err := s.ruleLoader.Load(serviceConfig.Name, serviceConfig.RuleFile)
		if err != nil {
			s.logger.Exception(
				"Failed loading rule file for service",
				err,
				logging.F("service", serviceConfig.Name),
				logging.F("rule_file", serviceConfig.RuleFile),
			)
			continue
		}

		sourceIndices := serviceConfig.SourceIndices
		if len(sourceIndices) == 0 {
			sourceIndices = s.config.Pipeline.SourceIndices
		}
		if len(sourceIndices) == 0 {
			s.logger.Warning("No source indices configured", logging.F("service", serviceConfig.Name))
			continue
		}

		resolvedSourceIndices := s.resolveSourceIndices(serviceConfig.Name, sourceIndices)
		if len(resolvedSourceIndices) == 0 {
			s.logger.Warning(
				"No concrete source indices resolved for service",
				logging.F("service", serviceConfig.Name),
				logging.F("source_indices", sourceIndices),
			)
			continue
		}

		for _, indexName := range resolvedSourceIndices {
			units = append(units, workUnit{
				serviceConfig: serviceConfig,
				ruleSet:       ruleSet,
				indexName:     indexName,
			})
		}
	}
	return units
}

func (s *SignalEnrichmentService) selectOwnedWorkUnits(allUnits []workUnit) []workUnit {
	if len(allUnits) == 0 {
		return nil
	}

	sort.Slice(allUnits, func(left int, right int) bool {
		leftKey := allUnits[left].serviceConfig.Name + "::" + allUnits[left].indexName
		rightKey := allUnits[right].serviceConfig.Name + "::" + allUnits[right].indexName
		return leftKey < rightKey
	})

	workerCount := maxInt(1, s.config.Pipeline.WorkerCount)
	if workerCount == 1 {
		return append([]workUnit{}, allUnits...)
	}

	owned := make([]workUnit, 0, (len(allUnits)+workerCount-1)/workerCount)
	for index, unit := range allUnits {
		if index%workerCount == s.config.Pipeline.WorkerID {
			owned = append(owned, unit)
		}
	}
	return owned
}

func (s *SignalEnrichmentService) logWorkUnitOwnership(totalUnits int, ownedUnits []workUnit) {
	ownedServices := make([]string, 0)
	seen := make(map[string]struct{})
	for _, unit := range ownedUnits {
		serviceName := unit.serviceConfig.Name
		if _, ok := seen[serviceName]; ok {
			continue
		}
		seen[serviceName] = struct{}{}
		ownedServices = append(ownedServices, serviceName)
	}
	sort.Strings(ownedServices)
	s.logger.Info(
		"Worker ownership selected",
		logging.F("worker_id", s.config.Pipeline.WorkerID),
		logging.F("worker_count", s.config.Pipeline.WorkerCount),
		logging.F("total_work_units", totalUnits),
		logging.F("owned_work_units", len(ownedUnits)),
		logging.F("owned_services", ownedServices),
	)
}

func (s *SignalEnrichmentService) processIndex(serviceConfig config.ServiceConfig, ruleSet *rules.RuleSet, indexName string) (int, int, *float64, error) {
	if !s.config.Pipeline.WriteToSourceIndex && !s.config.Pipeline.WriteToTargetIndex {
		s.logger.Warning(
			"Write targets are disabled for both source and target indices",
			logging.F("service", serviceConfig.Name),
			logging.F("source_index", indexName),
		)
		return 0, 0, nil, nil
	}

	checkpoint, err := s.checkpointStore.Get(serviceConfig.Name, indexName)
	if err != nil {
		return 0, 0, nil, err
	}
	startTime := s.config.Pipeline.StartTime
	if serviceConfig.StartTime != nil {
		startTime = *serviceConfig.StartTime
	}
	effectiveBatchSize := s.resolveBatchSize(serviceConfig, indexName)
	s.logger.Info(
		"Starting service/index processing",
		logging.F("service", serviceConfig.Name),
		logging.F("source_index", indexName),
		logging.F("start_time", startTime),
		logging.F("checkpoint_sort", checkpoint),
		logging.F("batch_size_used", effectiveBatchSize),
		logging.F("batch_size_mode", s.config.Pipeline.BatchSizeMode),
	)

	searchClient, ok := s.esClient.(ingest.SearchClient)
	if !ok {
		return 0, 0, nil, fmt.Errorf("Elasticsearch client does not implement search")
	}

	reader := ingest.NewBatchReader(
		searchClient,
		indexName,
		effectiveBatchSize,
		s.config.Pipeline.TimestampField,
		startTime,
		serviceConfig.Query,
		true,
	)

	batcher := writer.NewActionBatcher(effectiveBatchSize, maxInt(1, s.config.Pipeline.BulkMaxBatchBytes))
	processed := 0
	takenEvents := 0
	matchedEvents := 0
	unmatchedEvents := 0
	skippedAlreadySignaledEvents := 0
	latestSort := checkpoint
	var latestEventAt *time.Time
	destinationIndicesSeen := make(map[string]struct{})

	err = reader.IterateHits(checkpoint, func(hit map[string]any) error {
		takenEvents++
		if sortValues, ok := hit["sort"].([]any); ok {
			latestSort = sortValues
		}
		sourceEventIndex := stringValue(hit["_index"], indexName)
		sourceDoc, _ := hit["_source"].(map[string]any)
		if sourceDoc == nil {
			sourceDoc = map[string]any{}
		}
		if isAlreadySignaledDoc(sourceDoc) {
			skippedAlreadySignaledEvents++
			return nil
		}

		eventTS := s.extractEventTimestamp(sourceDoc)
		if eventTS != nil && (latestEventAt == nil || eventTS.After(*latestEventAt)) {
			latestEventAt = eventTS
		}

		signals := s.ruleEngine.Evaluate(
			sourceDoc,
			ruleSet,
			s.config.Pipeline.SignalMaxPerEvent,
			s.config.Pipeline.SignalSelectHighestOnly,
		)
		var selectedSignal map[string]any
		if len(signals) > 0 {
			selectedSignal = signals[0]
		}
		destinationIndices := s.resolveDestinationIndices(sourceEventIndex)
		for _, destinationIndex := range destinationIndices {
			destinationIndicesSeen[destinationIndex] = struct{}{}
		}

		if selectedSignal != nil {
			matchedEvents++
			s.ruleLearner.Observe(serviceConfig.Name, sourceDoc, selectedSignal)
			if s.streamPublisher != nil {
				if event, ok := s.buildSignalStreamEvent(sourceEventIndex, fmt.Sprint(hit["_id"]), sourceDoc, selectedSignal); ok {
					if err := s.streamPublisher.Publish(context.Background(), event); err != nil {
						s.logger.Warning(
							"Failed to publish compact signal event",
							logging.F("service", serviceConfig.Name),
							logging.F("source_index", sourceEventIndex),
							logging.F("source_id", hit["_id"]),
							logging.F("signal", selectedSignal["signal"]),
							logging.F("error", err.Error()),
						)
					}
				}
			}
			for _, destinationIndex := range destinationIndices {
				action := s.actionFactory.Build(
					sourceEventIndex,
					destinationIndex,
					fmt.Sprint(hit["_id"]),
					sourceDoc,
					selectedSignal,
					destinationIndex == sourceEventIndex,
				)
				if flushed := batcher.Add(action); flushed != nil {
					if err := s.enqueueActions(flushed); err != nil {
						return err
					}
				}
				processed++
			}
			s.logger.Debug(
				"Signal added for event",
				logging.F("service", serviceConfig.Name),
				logging.F("source_index", sourceEventIndex),
				logging.F("source_id", hit["_id"]),
				logging.F("target_indices", destinationIndices),
				logging.F("log", map[string]any{"level": selectedSignal["level"]}),
				logging.F("matched_rule_ids", []any{selectedSignal["rule_id"]}),
				logging.F("signal", selectedSignal["signal"]),
			)
		} else if s.config.Logging.LogUnmatchedEvents {
			unmatchedEvents++
			s.logger.Debug(
				"No signals matched for event",
				logging.F("service", serviceConfig.Name),
				logging.F("source_index", sourceEventIndex),
				logging.F("source_id", hit["_id"]),
				logging.F("target_indices", destinationIndices),
				logging.F("matched_rule_ids", []any{}),
				logging.F("signal_count", 0),
			)
		} else {
			unmatchedEvents++
		}
		return nil
	})
	if err != nil {
		return processed, takenEvents, nil, err
	}

	if remaining := batcher.FlushRemaining(); remaining != nil {
		if err := s.enqueueActions(remaining); err != nil {
			return processed, takenEvents, nil, err
		}
	}

	if latestSort != nil {
		if err := s.checkpointStore.Set(serviceConfig.Name, indexName, latestSort); err != nil {
			return processed, takenEvents, nil, err
		}
	}

	lagSeconds := computeLagSeconds(latestEventAt)
	s.logger.Info(
		"Processed service/index",
		logging.F("service", serviceConfig.Name),
		logging.F("source_index", indexName),
		logging.F("write_to_source_index", s.config.Pipeline.WriteToSourceIndex),
		logging.F("write_to_target_index", s.config.Pipeline.WriteToTargetIndex),
		logging.F("target_index_suffix", s.config.Pipeline.TargetSuffix),
		logging.F("target_indices_count", len(destinationIndicesSeen)),
		logging.F("target_indices_sample", mapKeysSample(destinationIndicesSeen, 5)),
		logging.F("batch_size_used", effectiveBatchSize),
		logging.F("bulk_max_batch_bytes", s.config.Pipeline.BulkMaxBatchBytes),
		logging.F("total_taken_from_index", takenEvents),
		logging.F("matched_events", matchedEvents),
		logging.F("unmatched_events", unmatchedEvents),
		logging.F("skipped_already_signaled_events", skippedAlreadySignaledEvents),
		logging.F("total_processed", processed),
		logging.F("lag_seconds", lagSeconds),
	)
	return processed, takenEvents, lagSeconds, nil
}

func (s *SignalEnrichmentService) flushRuleLearningCandidates() {
	writtenByService := s.ruleLearner.Flush()
	if len(writtenByService) > 0 {
		s.logger.Info("Auto-learned rules written", logging.F("written_by_service", writtenByService))
	}
}

func (s *SignalEnrichmentService) validateRuntimeConfig() error {
	workerCount := s.config.Pipeline.WorkerCount
	workerID := s.config.Pipeline.WorkerID
	if workerCount < 1 {
		return fmt.Errorf("pipeline.worker_count must be >= 1")
	}
	if workerID < 0 || workerID >= workerCount {
		return fmt.Errorf("pipeline.worker_id must satisfy 0 <= worker_id < worker_count")
	}

	s.logger.Info(
		"Worker partitioning initialized",
		logging.F("worker_id", workerID),
		logging.F("worker_count", workerCount),
	)
	if s.config.Pipeline.WriteToSourceIndex && s.config.Pipeline.WriteToTargetIndex {
		s.logger.Warning(
			"Dual write path is enabled and increases write load",
			logging.F("write_to_source_index", true),
			logging.F("write_to_target_index", true),
		)
	}
	return nil
}

func (s *SignalEnrichmentService) buildSignalStreamEvent(
	sourceIndex string,
	sourceID string,
	sourceDoc map[string]any,
	selectedSignal map[string]any,
) (signalstream.Event, bool) {
	organizationField := strings.TrimSpace(s.config.SignalStream.OrganizationFieldPath)
	if organizationField == "" {
		organizationField = "event.organization"
	}

	rawOrganization := util.GetNested(sourceDoc, organizationField)
	organizationID := strings.TrimSpace(fmt.Sprint(rawOrganization))
	if rawOrganization == nil || organizationID == "" || organizationID == "<nil>" {
		organizationID = extractOrganizationFromFallbackFields(sourceDoc)
		if organizationID == "" {
			return signalstream.Event{}, false
		}
	}

	eventTime := s.extractEventTimestamp(sourceDoc)
	if eventTime == nil {
		now := time.Now().UTC()
		eventTime = &now
	}

	logLevel := writer.NormalizeLogLevel(util.GetNested(sourceDoc, "log.level"))
	if logLevel == "" {
		logLevel = writer.NormalizeLogLevel(selectedSignal["level"])
	}
	if logLevel == "" {
		logLevel = strings.ToLower(strings.TrimSpace(fmt.Sprint(selectedSignal["level"])))
	}

	return signalstream.Event{
		OrganizationID: organizationID,
		HostIdentity:   resolveSignalStreamHostIdentity(sourceDoc),
		DocID:          sourceID,
		Signal:         strings.TrimSpace(fmt.Sprint(selectedSignal["signal"])),
		LogLevel:       logLevel,
		TimeStamp:      eventTime.UTC(),
		SignalizedAt:   parseSelectedSignalMatchedAt(selectedSignal),
		SourceIndex:    sourceIndex,
		SourceID:       sourceID,
	}, true
}

func parseSelectedSignalMatchedAt(selectedSignal map[string]any) time.Time {
	raw := selectedSignal["matched_at"]
	text := strings.TrimSpace(fmt.Sprint(raw))
	if raw == nil || text == "" || text == "<nil>" {
		return time.Now().UTC()
	}
	if strings.HasSuffix(text, "Z") {
		text = text[:len(text)-1] + "+00:00"
	}
	parsed, err := time.Parse(time.RFC3339Nano, text)
	if err != nil {
		return time.Now().UTC()
	}
	return parsed.UTC()
}

func resolveSignalStreamHostIdentity(sourceDoc map[string]any) string {
	if len(sourceDoc) == 0 {
		return ""
	}

	rawHostIP := util.GetNested(sourceDoc, "host.ip")
	if rawHostIP != nil {
		matches := ipv4Pattern.FindAllString(strings.TrimSpace(fmt.Sprint(rawHostIP)), -1)
		for _, match := range matches {
			trimmed := strings.TrimSpace(match)
			if trimmed != "" {
				return trimmed
			}
		}
	}

	hostName := strings.TrimSpace(fmt.Sprint(util.GetNested(sourceDoc, "host.name")))
	if hostName == "" || hostName == "<nil>" {
		return ""
	}
	return hostName
}

func extractOrganizationFromFallbackFields(sourceDoc map[string]any) string {
	if len(sourceDoc) == 0 {
		return ""
	}

	for _, field := range []string{"url.original", "url.path", "request", "message"} {
		rawValue := util.GetNested(sourceDoc, field)
		candidate := strings.TrimSpace(fmt.Sprint(rawValue))
		if rawValue == nil || candidate == "" || candidate == "<nil>" {
			continue
		}
		match := organizationQueryPattern.FindStringSubmatch(candidate)
		if len(match) > 1 {
			return strings.TrimSpace(match[1])
		}
	}
	return ""
}

func (s *SignalEnrichmentService) resolveSourceIndices(serviceName string, sourceIndices []string) []string {
	resolved := make([]string, 0)
	seen := make(map[string]struct{})
	for _, sourceIndex := range sourceIndices {
		if sourceIndex == "" {
			continue
		}
		concreteIndices := s.expandSourceIndexPattern(serviceName, sourceIndex)
		for _, concreteIndex := range concreteIndices {
			if isSystemIndex(concreteIndex) {
				s.logger.Debug(
					"Skipping system index during source index resolution",
					logging.F("service", serviceName),
					logging.F("source_index", concreteIndex),
				)
				continue
			}
			if _, ok := seen[concreteIndex]; ok {
				continue
			}
			seen[concreteIndex] = struct{}{}
			resolved = append(resolved, concreteIndex)
		}
	}
	return resolved
}

func (s *SignalEnrichmentService) expandSourceIndexPattern(serviceName string, sourceIndex string) []string {
	if !isWildcardIndex(sourceIndex) {
		return []string{sourceIndex}
	}
	resolver, ok := s.esClient.(IndicesResolver)
	if !ok {
		return []string{sourceIndex}
	}

	response, err := resolver.IndicesGet(sourceIndex)
	if err != nil {
		s.logger.Warning(
			"Failed resolving wildcard source index; using pattern as-is",
			logging.F("service", serviceName),
			logging.F("source_index", sourceIndex),
		)
		return []string{sourceIndex}
	}
	if len(response) == 0 {
		s.logger.Debug(
			"Wildcard source index resolved to zero concrete indices",
			logging.F("service", serviceName),
			logging.F("source_index", sourceIndex),
		)
		return []string{}
	}
	concreteIndices := make([]string, 0, len(response))
	for indexName := range response {
		concreteIndices = append(concreteIndices, indexName)
	}
	sort.Strings(concreteIndices)
	return concreteIndices
}

func isWildcardIndex(sourceIndex string) bool {
	return strings.ContainsAny(sourceIndex, "*?[")
}

func isSystemIndex(sourceIndex string) bool {
	return strings.HasPrefix(strings.TrimSpace(sourceIndex), ".")
}

func (s *SignalEnrichmentService) enqueueActions(actions []map[string]any) error {
	return s.bulkWriter.Submit(actions)
}

func (s *SignalEnrichmentService) resolveBatchSize(serviceConfig config.ServiceConfig, indexName string) int {
	staticBatch := maxInt(1, s.config.Pipeline.BatchSize)
	mode := strings.ToLower(strings.TrimSpace(s.config.Pipeline.BatchSizeMode))
	switch mode {
	case "static":
		return staticBatch
	case "dynamic":
		return s.estimateDynamicBatchSize(serviceConfig, indexName, staticBatch)
	default:
		s.logger.Warning(
			"Unknown batch_size_mode; falling back to static batch size",
			logging.F("batch_size_mode", s.config.Pipeline.BatchSizeMode),
			logging.F("fallback_batch_size", staticBatch),
			logging.F("service", serviceConfig.Name),
			logging.F("source_index", indexName),
		)
		return staticBatch
	}
}

func (s *SignalEnrichmentService) estimateDynamicBatchSize(serviceConfig config.ServiceConfig, indexName string, staticBatch int) int {
	lookbackSeconds := maxInt(5, s.config.Pipeline.DynamicBatchLookbackSeconds)
	minBatch := maxInt(1, s.config.Pipeline.DynamicBatchMinSize)
	maxBatch := maxInt(minBatch, s.config.Pipeline.DynamicBatchMaxSize)
	targetWindow := maxFloat(0.1, s.config.Pipeline.DynamicBatchTargetWindowSeconds)
	alpha := clampFloat(s.config.Pipeline.DynamicBatchSmoothingAlpha, 0.0, 1.0)

	counter, ok := s.esClient.(CountClient)
	if !ok {
		return staticBatch
	}
	response, err := counter.Count(indexName, s.buildRecentCountQuery(serviceConfig, lookbackSeconds))
	if err != nil {
		s.logger.Warning(
			"Dynamic batch size count query failed; using static batch size",
			logging.F("service", serviceConfig.Name),
			logging.F("source_index", indexName),
			logging.F("fallback_batch_size", staticBatch),
			logging.F("lookback_seconds", lookbackSeconds),
		)
		return staticBatch
	}

	count := int(numberValue(response["count"]))
	observedEPS := float64(count) / float64(lookbackSeconds)
	cacheKey := serviceConfig.Name + "::" + indexName
	previousEPS, hasPrevious := s.dynamicEPSByKey[cacheKey]
	effectiveEPS := observedEPS
	if hasPrevious {
		effectiveEPS = (alpha * observedEPS) + ((1.0 - alpha) * previousEPS)
	}
	s.dynamicEPSByKey[cacheKey] = effectiveEPS

	candidate := int(math.Round(effectiveEPS * targetWindow))
	batchSize := maxInt(minBatch, minInt(maxBatch, candidate))
	s.logger.Debug(
		"Dynamic batch size resolved",
		logging.F("service", serviceConfig.Name),
		logging.F("source_index", indexName),
		logging.F("lookback_seconds", lookbackSeconds),
		logging.F("event_count", count),
		logging.F("observed_eps", observedEPS),
		logging.F("effective_eps", effectiveEPS),
		logging.F("target_window_seconds", targetWindow),
		logging.F("resolved_batch_size", batchSize),
		logging.F("min_batch_size", minBatch),
		logging.F("max_batch_size", maxBatch),
	)
	return batchSize
}

func (s *SignalEnrichmentService) buildRecentCountQuery(serviceConfig config.ServiceConfig, lookbackSeconds int) map[string]any {
	boolFilter := []any{
		map[string]any{
			"range": map[string]any{
				s.config.Pipeline.TimestampField: map[string]any{
					"gte": fmt.Sprintf("now-%ds", lookbackSeconds),
				},
			},
		},
	}
	if serviceConfig.Query != nil {
		boolFilter = append(boolFilter, serviceConfig.Query)
	}
	return map[string]any{
		"query": map[string]any{
			"bool": map[string]any{
				"filter": boolFilter,
				"must_not": []any{
					map[string]any{"term": map[string]any{"signal_present": true}},
					map[string]any{"term": map[string]any{"signal_present": "true"}},
				},
			},
		},
	}
}

func (s *SignalEnrichmentService) resolveDestinationIndices(sourceIndex string) []string {
	destinations := make([]string, 0, 2)
	if s.config.Pipeline.WriteToSourceIndex {
		destinations = append(destinations, sourceIndex)
	}
	if s.config.Pipeline.WriteToTargetIndex {
		targetIndex := sourceIndex
		suffix := s.config.Pipeline.TargetSuffix
		if !strings.HasSuffix(sourceIndex, suffix) {
			targetIndex = sourceIndex + suffix
		}
		if !containsString(destinations, targetIndex) {
			destinations = append(destinations, targetIndex)
		}
	}
	return destinations
}

func isAlreadySignaledDoc(sourceDoc map[string]any) bool {
	switch value := sourceDoc["signal_present"].(type) {
	case bool:
		return value
	case int:
		return value == 1
	case int64:
		return value == 1
	case float64:
		return value == 1
	case string:
		normalized := strings.ToLower(strings.TrimSpace(value))
		return normalized == "true" || normalized == "1" || normalized == "yes"
	default:
		return false
	}
}

func (s *SignalEnrichmentService) emitAutoscalingMetrics(processedActions int, takenEvents int, maxLagSeconds *float64, cycleSeconds float64) {
	if !s.config.Pipeline.AutoscalingEnabled {
		return
	}

	workerCount := maxInt(1, s.config.Pipeline.WorkerCount)
	minWorkers := maxInt(1, s.config.Pipeline.AutoscalingMinWorkers)
	maxWorkers := maxInt(minWorkers, s.config.Pipeline.AutoscalingMaxWorkers)
	targetEPSPerWorker := maxFloat(1.0, s.config.Pipeline.AutoscalingTargetEventsPerWorkerSec)
	lagScaleUp := maxFloat(0.0, s.config.Pipeline.AutoscalingLagScaleUpSeconds)
	lagScaleDown := maxFloat(0.0, s.config.Pipeline.AutoscalingLagScaleDownSeconds)

	workerOutputEPS := float64(processedActions) / cycleSeconds
	workerInputEPS := float64(takenEvents) / cycleSeconds
	clusterInputEPS := workerInputEPS * float64(workerCount)

	desiredByThroughput := int(math.Ceil(clusterInputEPS / targetEPSPerWorker))
	desiredWorkers := minInt(maxWorkers, maxInt(minWorkers, desiredByThroughput))

	lag := 0.0
	if maxLagSeconds != nil {
		lag = *maxLagSeconds
	}
	if lag > lagScaleUp && desiredWorkers <= workerCount {
		desiredWorkers = minInt(maxWorkers, workerCount+1)
	}
	if lag < lagScaleDown && desiredWorkers >= workerCount {
		candidate := maxInt(minWorkers, workerCount-1)
		if candidate >= desiredByThroughput {
			desiredWorkers = candidate
		}
	}

	recommendation := "steady"
	if desiredWorkers > workerCount {
		recommendation = "scale_up"
	} else if desiredWorkers < workerCount {
		recommendation = "scale_down"
	}

	s.logger.Info(
		"Autoscaling metrics",
		logging.F("worker_id", s.config.Pipeline.WorkerID),
		logging.F("worker_count", workerCount),
		logging.F("cycle_seconds", cycleSeconds),
		logging.F("worker_input_events_per_sec", workerInputEPS),
		logging.F("worker_output_actions_per_sec", workerOutputEPS),
		logging.F("estimated_cluster_input_events_per_sec", clusterInputEPS),
		logging.F("max_lag_seconds", maxLagSeconds),
		logging.F("desired_workers", desiredWorkers),
		logging.F("recommendation", recommendation),
	)
}

func (s *SignalEnrichmentService) extractEventTimestamp(sourceDoc map[string]any) *time.Time {
	raw := util.GetNested(sourceDoc, s.config.Pipeline.TimestampField)
	if raw == nil {
		raw = sourceDoc[s.config.Pipeline.TimestampField]
	}
	if raw == nil {
		return nil
	}

	switch value := raw.(type) {
	case int:
		t := time.Unix(int64(value), 0).UTC()
		return &t
	case int64:
		t := time.Unix(value, 0).UTC()
		return &t
	case float64:
		t := time.Unix(int64(value), 0).UTC()
		return &t
	case string:
		text := strings.TrimSpace(value)
		if text == "" {
			return nil
		}
		if strings.HasSuffix(text, "Z") {
			text = text[:len(text)-1] + "+00:00"
		}
		parsed, err := time.Parse(time.RFC3339Nano, text)
		if err != nil {
			return nil
		}
		t := parsed.UTC()
		return &t
	default:
		return nil
	}
}

func computeLagSeconds(latestEventAt *time.Time) *float64 {
	if latestEventAt == nil {
		return nil
	}
	lag := time.Since(latestEventAt.UTC()).Seconds()
	if lag < 0 {
		lag = 0
	}
	return &lag
}

func (s *SignalEnrichmentService) flush(actions []map[string]any) error {
	bulkClient, ok := s.esClient.(BulkClient)
	if !ok {
		return fmt.Errorf("Elasticsearch client does not implement bulk")
	}

	pendingActions := actions
	pendingErrors := map[string]map[string]any{}
	attempt := 1
	backoff := s.config.Pipeline.RetryInitialBackoffSeconds
	maxAttempts := s.config.Pipeline.RetryMaxAttempts

	for len(pendingActions) > 0 && attempt <= maxAttempts {
		success, errors, err := bulkClient.Bulk(pendingActions)
		if err != nil {
			return err
		}
		if len(errors) == 0 {
			s.logger.Debug("Bulk write completed", logging.F("success_count", success), logging.F("attempt", attempt))
			return nil
		}

		s.logger.Warning(
			"Bulk write attempt returned errors",
			logging.F("attempt", attempt),
			logging.F("success_count", success),
			logging.F("error_count", len(errors)),
		)
		limit := minInt(3, len(errors))
		for idx := 0; idx < limit; idx++ {
			s.logger.Warning("Bulk write item error sample", logging.F("attempt", attempt), logging.F("error", errors[idx]))
		}
		pendingActions, pendingErrors = extractFailedActions(pendingActions, errors)
		if len(pendingActions) > 0 && attempt < maxAttempts {
			time.Sleep(time.Duration(backoff * float64(time.Second)))
			backoff *= s.config.Pipeline.RetryBackoffMultiplier
		}
		attempt++
	}

	if len(pendingActions) > 0 {
		return s.sendToDeadLetter(bulkClient, pendingActions, pendingErrors)
	}
	return nil
}

func extractFailedActions(sentActions []map[string]any, errors []map[string]any) ([]map[string]any, map[string]map[string]any) {
	actionMap := make(map[string]map[string]any)
	for _, action := range sentActions {
		key := fmt.Sprintf("%v||%v", action["_index"], action["_id"])
		actionMap[key] = action
	}

	failedActions := make([]map[string]any, 0)
	failedErrors := make(map[string]map[string]any)
	for _, item := range errors {
		for _, payloadRaw := range item {
			payload, ok := payloadRaw.(map[string]any)
			if !ok {
				continue
			}
			key := fmt.Sprintf("%v||%v", payload["_index"], payload["_id"])
			if action, ok := actionMap[key]; ok {
				failedActions = append(failedActions, action)
				failedErrors[key] = map[string]any{
					"error":  payload["error"],
					"status": payload["status"],
				}
			}
		}
	}
	return failedActions, failedErrors
}

func (s *SignalEnrichmentService) sendToDeadLetter(bulkClient BulkClient, failedActions []map[string]any, failedErrors map[string]map[string]any) error {
	dlqActions := make([]map[string]any, 0, len(failedActions))
	now := time.Now().UTC()
	nowText := now.Format(time.RFC3339Nano)

	for _, action := range failedActions {
		doc, _ := action["doc"].(map[string]any)
		sourceIndex := stringValue(doc["source_index"], "unknown")
		sourceID := stringValue(doc["source_id"], "unknown")
		targetIndex := sourceIndex + s.config.Pipeline.DeadLetterSuffix
		dlqID := fmt.Sprintf("%v:%v:%d", action["_index"], action["_id"], now.Unix())
		errorKey := fmt.Sprintf("%v||%v", action["_index"], action["_id"])
		errorPayload := failedErrors[errorKey]
		dlqDoc := map[string]any{
			"failed_at":    nowText,
			"reason":       "bulk_retry_exhausted",
			"target_index": action["_index"],
			"source_index": sourceIndex,
			"source_id":    sourceID,
			"error":        valueFromMap(errorPayload, "error"),
			"status":       valueFromMap(errorPayload, "status"),
			"action": map[string]any{
				"op_type": action["_op_type"],
				"id":      action["_id"],
				"doc":     action["doc"],
			},
		}
		dlqActions = append(dlqActions, map[string]any{
			"_op_type": "index",
			"_index":   targetIndex,
			"_id":      dlqID,
			"_source":  dlqDoc,
		})
	}

	success, errors, err := bulkClient.Bulk(dlqActions)
	if err != nil {
		return err
	}
	if len(errors) > 0 {
		s.logger.Error(
			"Dead-letter write returned errors",
			logging.F("success_count", success),
			logging.F("error_count", len(errors)),
		)
		return nil
	}
	s.logger.Error("Moved failed bulk actions to dead-letter index", logging.F("count", success))
	return nil
}

func serviceRuleFiles(services []config.ServiceConfig) map[string]string {
	files := make(map[string]string)
	for _, service := range services {
		files[service.Name] = service.RuleFile
	}
	return files
}

func containsString(items []string, target string) bool {
	for _, item := range items {
		if item == target {
			return true
		}
	}
	return false
}

func mapKeysSample(values map[string]struct{}, limit int) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	if len(keys) > limit {
		return keys[:limit]
	}
	return keys
}

func stringValue(value any, fallback string) string {
	if value == nil {
		return fallback
	}
	return fmt.Sprint(value)
}

func numberValue(value any) float64 {
	switch typed := value.(type) {
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case float64:
		return typed
	default:
		return 0
	}
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}

func maxFloat(left float64, right float64) float64 {
	if left > right {
		return left
	}
	return right
}

func clampFloat(value float64, minimum float64, maximum float64) float64 {
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}

func valueFromMap(values map[string]any, key string) any {
	if values == nil {
		return nil
	}
	return values[key]
}
