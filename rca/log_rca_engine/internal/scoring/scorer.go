package scoring

import (
	"math"
	"sort"
	"strings"
	"time"

	"log_rca_engine/internal/models"
	"log_rca_engine/internal/utils"
)

const (
	ClassificationConfirmed = "confirmed_rca"
	ClassificationProbable  = "probable_cause"
	topologyNodeSeparator   = "::"

	sparseStepTimingScore       = 0.50
	singleLogFallbackTimeScore  = 0.35
	missingTimingWindowScore    = 0.35
	serviceDeviceBridgeStrength = 0.90

	explicitContradictionPenalty = 0.35
	recoveryContradictionPenalty = 0.20
	competingSignalPenalty       = 0.10
	maxContradictionPenalty      = 0.75

	identityConfidenceComposite = 1.00
	identityConfidenceIPOnly    = 0.85
	identityConfidenceService   = 0.65
	identityConfidenceHost      = 0.40
)

type Scorer struct {
	weights   models.ScoreWeights
	threshold float64
}

func NewScorer(weights models.ScoreWeights, threshold float64) *Scorer {
	return &Scorer{
		weights:   weights,
		threshold: threshold,
	}
}

func (s *Scorer) Score(event models.CorrelationEvent, rule *models.Rule, topology *models.OrganizationTopology, nearbyLogs []models.RelatedLog) models.ScoreResult {
	orderedDisplayIdentities := orderedDisplayIdentitiesFromEvent(event)
	resolvedIdentities := orderedTopologyMatchesFromEvent(event, topology)
	topologyIdentities := identitiesFromResolved(resolvedIdentities)
	involvedServices := utils.UniqueStrings(topologyIdentities)
	if len(involvedServices) == 0 {
		involvedServices = utils.UniqueStrings(orderedDisplayIdentities)
	}
	matchedDocIDs := matchedDocIDs(event)
	topologyCoverage := computeTopologyCoverage(topologyIdentities, topology)
	identityConfidence := computeIdentityConfidence(resolvedIdentities, event, topology)

	sequenceScore := clamp01(event.SequenceMatch)
	dependencyScore := computeDependencyScore(topologyIdentities, topology, topologyCoverage, identityConfidence)
	timeScore := computeTimeProximityScore(event, rule)
	severityScore := computeSignalSeverityScore(event.LogID)
	ruleCompletenessScore := clamp01(event.RuleCompletion) * topologyCoverage * identityConfidence
	completedStepCoverage := computeCompletedStepCoverage(event.Audit)
	contradictionPenalty, contradictionReasons := computeContradictionPenalty(event, rule, topology, nearbyLogs)

	weightedSum := (sequenceScore * s.weights.SequenceMatch) +
		(dependencyScore * s.weights.DependencyMatch) +
		(timeScore * s.weights.TimeProximity) +
		(severityScore * s.weights.SignalSeverity) +
		(ruleCompletenessScore * s.weights.RuleCompleteness)
	totalWeight := s.weights.SequenceMatch + s.weights.DependencyMatch + s.weights.TimeProximity + s.weights.SignalSeverity + s.weights.RuleCompleteness
	finalWeighted := 0.0
	if totalWeight > 0 {
		finalWeighted = weightedSum / totalWeight
	}
	finalScore := 10 * finalWeighted * contradictionPenalty

	classification := ClassificationProbable
	if finalScore >= s.threshold && passesConfirmationGates(event, models.ScoreBreakdown{
		SequenceMatch:         sequenceScore,
		DependencyMatch:       dependencyScore,
		TimeProximity:         timeScore,
		SignalSeverity:        severityScore,
		RuleCompleteness:      ruleCompletenessScore,
		TopologyCoverage:      topologyCoverage,
		IdentityConfidence:    identityConfidence,
		CompletedStepCoverage: completedStepCoverage,
		ContradictionPenalty:  contradictionPenalty,
		FinalWeighted:         finalScore / 10,
	}) {
		classification = ClassificationConfirmed
	}

	breakdown := models.ScoreBreakdown{
		SequenceMatch:         round(sequenceScore),
		DependencyMatch:       round(dependencyScore),
		TimeProximity:         round(timeScore),
		SignalSeverity:        round(severityScore),
		RuleCompleteness:      round(ruleCompletenessScore),
		TopologyCoverage:      round(topologyCoverage),
		IdentityConfidence:    round(identityConfidence),
		CompletedStepCoverage: round(completedStepCoverage),
		ContradictionPenalty:  round(contradictionPenalty),
		FinalWeighted:         round(finalScore / 10),
	}

	return models.ScoreResult{
		Classification:        classification,
		ConfidenceScore:       round(finalScore),
		Breakdown:             breakdown,
		BelowThresholdReasons: buildBelowThresholdReasons(classification, finalScore, s.threshold, breakdown, contradictionReasons),
		InvolvedServices:      involvedServices,
		MatchedDocIDs:         matchedDocIDs,
	}
}

func orderedDisplayIdentitiesFromEvent(event models.CorrelationEvent) []string {
	result := make([]string, 0, len(event.LogID)+1)
	for _, log := range event.LogID {
		identity := firstNonEmpty(primaryLogHostIP(log), log.ServiceName, log.HostName)
		if identity == "" {
			continue
		}
		result = append(result, identity)
	}
	if len(result) == 0 {
		if identity := firstNonEmpty(
			event.GroupByValues["topology.identity"],
			event.GroupByValues["host.identity"],
			event.GroupByValues["service.identity"],
			primaryGroupByHostIP(event.GroupByValues),
			event.GroupByValues["service.name"],
			event.GroupByValues["event.module"],
			event.GroupByValues["host.name"],
		); strings.TrimSpace(identity) != "" {
			result = append(result, strings.TrimSpace(identity))
		}
	}
	return result
}

func orderedTopologyIdentitiesFromEvent(event models.CorrelationEvent, topology *models.OrganizationTopology) []string {
	result := make([]string, 0, len(event.LogID)+1)
	known := knownTopologyNodes(topology)
	for _, log := range event.LogID {
		if identity := resolveLogTopologyIdentity(log, known); identity != "" {
			result = append(result, identity)
		}
	}
	if len(result) == 0 {
		if identity := resolveGroupByTopologyIdentity(event.GroupByValues, known); identity != "" {
			result = append(result, identity)
		}
	}
	return result
}

func matchedDocIDs(event models.CorrelationEvent) []string {
	result := make([]string, 0, len(event.LogID))
	for _, log := range event.LogID {
		if strings.TrimSpace(log.ID) != "" {
			result = append(result, log.ID)
		}
	}
	return utils.UniqueStrings(result)
}

func computeTopologyCoverage(identities []string, topology *models.OrganizationTopology) float64 {
	if len(identities) == 0 || topology == nil {
		return 0
	}

	known := topologyKnownNodes(topology)
	if len(known) == 0 {
		return 0
	}

	matched := 0
	for _, identity := range utils.UniqueStrings(identities) {
		if _, ok := known[identity]; ok {
			matched++
		}
	}
	return clamp01(float64(matched) / float64(len(utils.UniqueStrings(identities))))
}

func computeDependencyScore(orderedIdentities []string, topology *models.OrganizationTopology, coverage, identityConfidence float64) float64 {
	identities := compressConsecutiveDuplicates(orderedIdentities)
	if len(identities) == 0 || topology == nil {
		return 0
	}
	if len(identities) == 1 {
		if coverage == 0 {
			return 0
		}
		return round(clamp01(coverage * identityConfidence))
	}

	graph := buildDirectedGraph(topology)
	if len(graph) == 0 {
		return 0
	}

	pairScores := make([]float64, 0, len(identities)-1)
	for idx := 0; idx < len(identities)-1; idx++ {
		left := identities[idx]
		right := identities[idx+1]
		if left == right {
			pairScores = append(pairScores, 1)
			continue
		}
		pairScores = append(pairScores, bestDirectedPathScore(graph, left, right, 4))
	}
	if len(pairScores) == 0 {
		return 0
	}

	total := 0.0
	for _, score := range pairScores {
		total += score
	}
	return clamp01((total / float64(len(pairScores))) * coverage * identityConfidence)
}

func computeTimeProximityScore(event models.CorrelationEvent, rule *models.Rule) float64 {
	logTimes := make(map[string]time.Time, len(event.LogID))
	for _, log := range event.LogID {
		if strings.TrimSpace(log.ID) == "" || log.Timestamp.IsZero() {
			continue
		}
		logTimes[log.ID] = log.Timestamp.UTC()
	}
	if len(logTimes) == 0 {
		return 0
	}

	components := make([]float64, 0)
	if event.Audit != nil && len(event.Audit.Steps) > 0 {
		for _, step := range event.Audit.Steps {
			times := extractStepTimes(step.MatchedLogIDs, logTimes)
			if len(times) == 0 {
				components = append(components, 0)
				continue
			}

			within, err := utils.ParseDuration(step.Within)
			if len(times) == 1 {
				components = append(components, sparseStepTimingScore)
			} else if err != nil || within <= 0 {
				components = append(components, sparseStepTimingScore)
			} else {
				span := times[len(times)-1].Sub(times[0])
				components = append(components, closenessScore(span, within))
			}
		}

		maxGap := parseGapLimit(event, rule)
		for idx := 0; idx < len(event.Audit.Steps)-1; idx++ {
			leftTimes := extractStepTimes(event.Audit.Steps[idx].MatchedLogIDs, logTimes)
			rightTimes := extractStepTimes(event.Audit.Steps[idx+1].MatchedLogIDs, logTimes)
			if len(leftTimes) == 0 || len(rightTimes) == 0 {
				continue
			}
			limit := maxGap
			if limit <= 0 {
				if within, err := utils.ParseDuration(event.Audit.Steps[idx+1].Within); err == nil {
					limit = within
				}
			}
			if limit <= 0 {
				components = append(components, sparseStepTimingScore)
				continue
			}
			gap := rightTimes[0].Sub(leftTimes[len(leftTimes)-1])
			if gap < 0 {
				gap = 0
			}
			components = append(components, closenessScore(gap, limit))
		}
	}

	if len(components) == 0 {
		ordered := make([]time.Time, 0, len(logTimes))
		for _, value := range logTimes {
			ordered = append(ordered, value)
		}
		sort.Slice(ordered, func(i, j int) bool { return ordered[i].Before(ordered[j]) })
		if len(ordered) <= 1 {
			return singleLogFallbackTimeScore
		}
		if rule != nil {
			if window, err := utils.ParseDuration(rule.Window); err == nil && window > 0 {
				return closenessScore(ordered[len(ordered)-1].Sub(ordered[0]), window)
			}
		}
		return missingTimingWindowScore
	}

	total := 0.0
	for _, component := range components {
		total += component
	}
	return clamp01(total / float64(len(components)))
}

func extractStepTimes(ids []string, logTimes map[string]time.Time) []time.Time {
	if len(ids) == 0 {
		return nil
	}
	result := make([]time.Time, 0, len(ids))
	for _, id := range ids {
		if timestamp, ok := logTimes[id]; ok {
			result = append(result, timestamp)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Before(result[j]) })
	return result
}

func parseGapLimit(event models.CorrelationEvent, rule *models.Rule) time.Duration {
	candidates := []string{}
	if event.Audit != nil && strings.TrimSpace(event.Audit.MaxGapBetweenSteps) != "" {
		candidates = append(candidates, event.Audit.MaxGapBetweenSteps)
	}
	if rule != nil && strings.TrimSpace(rule.MaxGapBetweenSteps) != "" {
		candidates = append(candidates, rule.MaxGapBetweenSteps)
	}
	for _, candidate := range candidates {
		if parsed, err := utils.ParseDuration(candidate); err == nil && parsed > 0 {
			return parsed
		}
	}
	return 0
}

func computeSignalSeverityScore(logs []models.EvidenceLog) float64 {
	if len(logs) == 0 {
		return 0
	}

	maxSeverity := 0.0
	total := 0.0
	count := 0.0
	for _, log := range logs {
		score := severityWeight(log.Severity)
		if score > maxSeverity {
			maxSeverity = score
		}
		total += score
		count++
	}
	if count == 0 {
		return 0
	}
	average := total / count
	return clamp01((0.6 * maxSeverity) + (0.4 * average))
}

func severityWeight(raw string) float64 {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "critical", "crit", "fatal", "panic", "alert", "emergency", "emerg":
		return 1.0
	case "error", "err", "failure", "failed":
		return 0.85
	case "warning", "warn":
		return 0.60
	case "info", "notice", "informational":
		return 0.35
	default:
		return 0.20
	}
}

func buildBelowThresholdReasons(classification string, score, threshold float64, breakdown models.ScoreBreakdown, contradictionReasons []string) []string {
	if classification == ClassificationConfirmed {
		return nil
	}

	reasons := make([]string, 0, 8)
	if breakdown.TopologyCoverage < 0.50 {
		reasons = append(reasons, "Topology coverage is too low to confirm the incident confidently.")
	}
	if breakdown.IdentityConfidence < 0.60 {
		reasons = append(reasons, "Log-to-topology identity resolution is not strong enough for a confirmed RCA.")
	}
	if breakdown.DependencyMatch < 0.50 {
		reasons = append(reasons, "Topology relationships do not strongly connect the matched services in the observed order.")
	}
	if breakdown.TimeProximity < 0.50 {
		reasons = append(reasons, "Matched logs were too far apart in time to reinforce the incident sequence.")
	}
	if breakdown.SignalSeverity < 0.70 {
		reasons = append(reasons, "Signal severity stayed too low for a high-confidence RCA.")
	}
	if breakdown.RuleCompleteness < 0.70 {
		reasons = append(reasons, "Rule evidence is only partially complete after topology and identity adjustments.")
	}
	if breakdown.SequenceMatch < 0.70 {
		reasons = append(reasons, "The observed signal sequence only partially matches the expected rule order.")
	}
	if breakdown.CompletedStepCoverage > 0 && breakdown.CompletedStepCoverage < 0.67 {
		reasons = append(reasons, "Too few rule steps were fully completed to confirm a root cause.")
	}
	if breakdown.ContradictionPenalty < 0.80 {
		reasons = append(reasons, "Nearby recovery or competing signals contradicted the RCA evidence.")
	}
	reasons = append(reasons, contradictionReasons...)
	if len(reasons) == 0 {
		if score >= threshold {
			reasons = append(reasons, "The numeric score crossed the threshold, but confirmation safety gates kept the incident as a probable cause.")
		} else {
			reasons = append(reasons, "The combined RCA confidence stayed below the confirmation threshold.")
		}
	}
	return utils.UniqueStrings(reasons)
}

func buildUndirectedGraph(topology *models.OrganizationTopology) map[string][]string {
	graph := make(map[string][]string)
	if topology == nil {
		return graph
	}
	for _, service := range topology.Services {
		name := topologyServiceIdentity(service)
		if name == "" {
			continue
		}
		if _, ok := graph[name]; !ok {
			graph[name] = []string{}
		}
		if deviceIP := strings.TrimSpace(service.DeviceIP); deviceIP != "" {
			if _, ok := graph[deviceIP]; !ok {
				graph[deviceIP] = []string{}
			}
		}
	}
	for _, edge := range topology.Dependencies {
		from := strings.TrimSpace(edge.From)
		to := strings.TrimSpace(edge.To)
		if from == "" || to == "" {
			continue
		}
		graph[from] = appendIfMissing(graph[from], to)
		graph[to] = appendIfMissing(graph[to], from)
	}
	for _, relation := range topology.ServiceRelations {
		from := topologyRelationIdentity(relation.FromIP, relation.FromService)
		to := topologyRelationIdentity(relation.ToIP, relation.ToService)
		if from == "" || to == "" {
			continue
		}
		graph[from] = appendIfMissing(graph[from], to)
		graph[to] = appendIfMissing(graph[to], from)
	}
	return graph
}

func topologyKnownNodes(topology *models.OrganizationTopology) map[string]struct{} {
	known := make(map[string]struct{})
	if topology == nil {
		return known
	}
	for _, service := range topology.Services {
		if identity := topologyServiceIdentity(service); identity != "" {
			known[identity] = struct{}{}
		}
		if deviceIP := strings.TrimSpace(service.DeviceIP); deviceIP != "" {
			known[deviceIP] = struct{}{}
		}
	}
	for _, edge := range topology.Dependencies {
		if from := strings.TrimSpace(edge.From); from != "" {
			known[from] = struct{}{}
		}
		if to := strings.TrimSpace(edge.To); to != "" {
			known[to] = struct{}{}
		}
	}
	for _, relation := range topology.ServiceRelations {
		if from := topologyRelationIdentity(relation.FromIP, relation.FromService); from != "" {
			known[from] = struct{}{}
		}
		if to := topologyRelationIdentity(relation.ToIP, relation.ToService); to != "" {
			known[to] = struct{}{}
		}
		if fromIP := strings.TrimSpace(relation.FromIP); fromIP != "" {
			known[fromIP] = struct{}{}
		}
		if toIP := strings.TrimSpace(relation.ToIP); toIP != "" {
			known[toIP] = struct{}{}
		}
	}
	return known
}

func topologyServiceIdentity(service models.TopologyService) string {
	return topologyRelationIdentity(service.DeviceIP, firstNonEmpty(service.ServiceName, service.HostName))
}

func resolveLogTopologyIdentity(log models.EvidenceLog, known map[string]struct{}) string {
	ipCandidates := logIPCandidates(log)
	serviceCandidates := utils.UniqueStrings([]string{log.ServiceName})
	hostCandidates := utils.UniqueStrings([]string{log.HostName})
	if len(known) > 0 {
		for _, ip := range ipCandidates {
			for _, service := range serviceCandidates {
				candidate := topologyRelationIdentity(ip, service)
				if candidate == "" {
					continue
				}
				if _, ok := known[candidate]; ok {
					return candidate
				}
			}
		}
		for _, candidate := range ipCandidates {
			if _, ok := known[candidate]; ok {
				return candidate
			}
		}
		for _, candidate := range serviceCandidates {
			if candidate == "" {
				continue
			}
			if _, ok := known[candidate]; ok {
				return candidate
			}
		}
		for _, candidate := range hostCandidates {
			if candidate == "" {
				continue
			}
			if _, ok := known[candidate]; ok {
				return candidate
			}
		}
	}
	return firstNonEmpty(firstIP(ipCandidates), log.ServiceName, log.HostName)
}

func resolveGroupByTopologyIdentity(groupByValues map[string]string, known map[string]struct{}) string {
	ipCandidates := utils.ExtractIPAddresses(stringMapToAny(groupByValues), "host.ip")
	serviceCandidates := utils.UniqueStrings([]string{
		groupByValues["service.name"],
		groupByValues["event.module"],
	})
	if len(known) > 0 {
		for _, ip := range ipCandidates {
			for _, service := range serviceCandidates {
				candidate := topologyRelationIdentity(ip, service)
				if candidate == "" {
					continue
				}
				if _, ok := known[candidate]; ok {
					return candidate
				}
			}
		}
		for _, candidate := range ipCandidates {
			if _, ok := known[candidate]; ok {
				return candidate
			}
		}
		for _, candidate := range serviceCandidates {
			if candidate == "" {
				continue
			}
			if _, ok := known[candidate]; ok {
				return candidate
			}
		}
		if host := strings.TrimSpace(groupByValues["host.name"]); host != "" {
			if _, ok := known[host]; ok {
				return host
			}
		}
	}
	return firstNonEmpty(firstIP(ipCandidates), groupByValues["service.name"], groupByValues["event.module"], groupByValues["host.name"])
}

func topologyRelationIdentity(deviceIP, serviceName string) string {
	ip := strings.TrimSpace(deviceIP)
	service := strings.TrimSpace(serviceName)
	switch {
	case ip != "" && service != "":
		return ip + topologyNodeSeparator + service
	case ip != "":
		return ip
	default:
		return service
	}
}

func logIPCandidates(log models.EvidenceLog) []string {
	candidates := make([]string, 0, len(log.HostIPs)+1)
	if value := strings.TrimSpace(log.HostIP); value != "" {
		candidates = append(candidates, value)
	}
	candidates = append(candidates, log.HostIPs...)
	return utils.UniqueStrings(candidates)
}

func primaryLogHostIP(log models.EvidenceLog) string {
	return firstIP(logIPCandidates(log))
}

func primaryGroupByHostIP(groupByValues map[string]string) string {
	return firstIP(utils.ExtractIPAddresses(stringMapToAny(groupByValues), "host.ip"))
}

func stringMapToAny(values map[string]string) map[string]any {
	if len(values) == 0 {
		return nil
	}
	result := make(map[string]any, len(values))
	for key, value := range values {
		result[key] = value
	}
	return result
}

func firstIP(values []string) string {
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			return trimmed
		}
	}
	return ""
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

func appendIfMissing(values []string, candidate string) []string {
	for _, value := range values {
		if value == candidate {
			return values
		}
	}
	return append(values, candidate)
}

func shortestPathLength(graph map[string][]string, start, target string) int {
	if start == target {
		return 0
	}
	if _, ok := graph[start]; !ok {
		return -1
	}
	if _, ok := graph[target]; !ok {
		return -1
	}

	type node struct {
		name  string
		depth int
	}
	queue := []node{{name: start, depth: 0}}
	visited := map[string]struct{}{start: {}}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		for _, next := range graph[current.name] {
			if _, ok := visited[next]; ok {
				continue
			}
			if next == target {
				return current.depth + 1
			}
			visited[next] = struct{}{}
			queue = append(queue, node{name: next, depth: current.depth + 1})
		}
	}
	return -1
}

func compressConsecutiveDuplicates(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	result := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			continue
		}
		if len(result) > 0 && result[len(result)-1] == trimmed {
			continue
		}
		result = append(result, trimmed)
	}
	return result
}

func closenessScore(actual, limit time.Duration) float64 {
	if limit <= 0 {
		return 0
	}
	if actual <= 0 {
		return 1
	}
	if actual >= limit {
		return 0
	}
	return clamp01(1 - (float64(actual) / float64(limit)))
}

func clamp01(value float64) float64 {
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return 0
	}
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return value
}

func round(value float64) float64 {
	return math.Round(value*10000) / 10000
}
