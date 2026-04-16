package scoring

import (
	"strings"

	"log_rca_engine/internal/models"
)

func computeContradictionPenalty(event models.CorrelationEvent, rule *models.Rule, topology *models.OrganizationTopology, nearbyLogs []models.RelatedLog) (float64, []string) {
	if len(nearbyLogs) == 0 {
		return 1, nil
	}

	known := knownTopologyNodes(topology)
	graph := buildDirectedGraph(topology)
	involved := identitiesFromResolved(orderedTopologyMatchesFromEvent(event, topology))
	negativeSignals := negativeSignalSet(event, rule)
	matchedSignals := matchedSignalSet(event)

	incidentServices := make(map[string]struct{}, len(event.LogID))
	incidentHosts := make(map[string]struct{}, len(event.LogID))
	incidentIPs := make(map[string]struct{}, len(event.LogID))
	for _, log := range event.LogID {
		if service := strings.TrimSpace(log.ServiceName); service != "" {
			incidentServices[service] = struct{}{}
		}
		if host := strings.TrimSpace(log.HostName); host != "" {
			incidentHosts[host] = struct{}{}
		}
		for _, ip := range logIPCandidates(log) {
			incidentIPs[ip] = struct{}{}
		}
	}

	penalty := 0.0
	explicitFound := false
	recoveryFound := false
	competingFound := false
	seen := make(map[string]struct{})

	for _, log := range nearbyLogs {
		signal := strings.ToLower(strings.TrimSpace(log.Signal))
		message := strings.ToLower(strings.TrimSpace(log.Message))
		relevance := relatedLogRelevance(log, incidentServices, incidentHosts, incidentIPs)
		if relevance == 0 {
			continue
		}

		identity := resolveRelatedLogTopologyIdentityDetailed(log, known).Identity
		keyBase := firstNonEmpty(identity, log.ServiceName, log.HostIP, log.HostName, log.DocID)

		if signal != "" {
			if _, ok := negativeSignals[signal]; ok {
				key := "explicit|" + keyBase + "|" + signal
				if _, exists := seen[key]; exists {
					continue
				}
				seen[key] = struct{}{}
				explicitFound = true
				penalty += explicitContradictionPenalty * relevance
				continue
			}
		}

		if looksLikeRecoverySignal(signal, message) {
			key := "recovery|" + keyBase + "|" + signal
			if _, exists := seen[key]; exists {
				continue
			}
			seen[key] = struct{}{}
			recoveryFound = true
			penalty += recoveryContradictionPenalty * relevance
			continue
		}

		if signal == "" || severityWeight(log.Severity) < 0.85 {
			continue
		}
		if _, ok := matchedSignals[signal]; ok {
			continue
		}
		if _, ok := negativeSignals[signal]; ok {
			continue
		}
		if identity == "" || len(involved) == 0 {
			continue
		}
		if maxConnectivityToIncident(graph, identity, involved) > 0.45 {
			continue
		}

		key := "competing|" + keyBase + "|" + signal
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		competingFound = true
		penalty += competingSignalPenalty * relevance
	}

	penalty = minFloat(penalty, maxContradictionPenalty)
	reasons := make([]string, 0, 3)
	if explicitFound {
		reasons = append(reasons, "Nearby exclusion or recovery signals contradicted the expected incident sequence.")
	}
	if recoveryFound {
		reasons = append(reasons, "Nearby recovery or healthy signals reduced confidence in an active RCA.")
	}
	if competingFound {
		reasons = append(reasons, "Competing high-severity signals appeared on weakly related services nearby.")
	}
	if !explicitFound && !recoveryFound && !competingFound {
		return 1, nil
	}
	return clamp01(1 - penalty), reasons
}

func resolveRelatedLogTopologyIdentityDetailed(log models.RelatedLog, known map[string]struct{}) resolvedTopologyIdentity {
	return resolveLogTopologyIdentityDetailed(models.EvidenceLog{
		ServiceName: log.ServiceName,
		HostName:    log.HostName,
		HostIP:      log.HostIP,
		HostIPs:     append([]string(nil), log.HostIPs...),
	}, known)
}

func relatedLogIPCandidates(log models.RelatedLog) []string {
	candidates := make([]string, 0, len(log.HostIPs)+1)
	if value := strings.TrimSpace(log.HostIP); value != "" {
		candidates = append(candidates, value)
	}
	candidates = append(candidates, log.HostIPs...)
	return uniqueNonEmpty(candidates)
}

func negativeSignalSet(event models.CorrelationEvent, rule *models.Rule) map[string]struct{} {
	result := make(map[string]struct{})
	if event.Audit != nil {
		for _, signal := range event.Audit.NegativeSignals {
			if trimmed := strings.ToLower(strings.TrimSpace(signal)); trimmed != "" {
				result[trimmed] = struct{}{}
			}
		}
	}
	if rule != nil {
		for _, step := range rule.NotSequence {
			if trimmed := strings.ToLower(strings.TrimSpace(step.SignalKey)); trimmed != "" {
				result[trimmed] = struct{}{}
			}
		}
	}
	return result
}

func matchedSignalSet(event models.CorrelationEvent) map[string]struct{} {
	result := make(map[string]struct{})
	for _, log := range event.LogID {
		if signal := strings.ToLower(strings.TrimSpace(log.Signal)); signal != "" {
			result[signal] = struct{}{}
		}
	}
	if event.Audit != nil {
		for _, signal := range event.Audit.MatchedSignals {
			if trimmed := strings.ToLower(strings.TrimSpace(signal)); trimmed != "" {
				result[trimmed] = struct{}{}
			}
		}
	}
	return result
}

func relatedLogRelevance(log models.RelatedLog, incidentServices, incidentHosts, incidentIPs map[string]struct{}) float64 {
	score := 0.60
	if _, ok := incidentServices[strings.TrimSpace(log.ServiceName)]; ok {
		score = 1.00
	}
	if _, ok := incidentHosts[strings.TrimSpace(log.HostName)]; ok && score < 0.90 {
		score = 0.90
	}
	for _, ip := range relatedLogIPCandidates(log) {
		if _, ok := incidentIPs[ip]; ok {
			return 1.00
		}
	}
	return score
}

func looksLikeRecoverySignal(signal, message string) bool {
	text := strings.ToLower(strings.TrimSpace(signal + " " + message))
	if text == "" {
		return false
	}
	for _, keyword := range []string{"recover", "healthy", "success", "resolved", "normal", "stabil"} {
		if strings.Contains(text, keyword) {
			return true
		}
	}
	return false
}

func maxConnectivityToIncident(graph map[string][]weightedEdge, identity string, involved []string) float64 {
	best := 0.0
	for _, candidate := range involved {
		score := bestDirectedPathScore(graph, identity, candidate, 4)
		if reverse := bestDirectedPathScore(graph, candidate, identity, 4); reverse > score {
			score = reverse
		}
		if score > best {
			best = score
		}
	}
	return best
}

func uniqueNonEmpty(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(values))
	result := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		result = append(result, trimmed)
	}
	return result
}

func minFloat(left, right float64) float64 {
	if left < right {
		return left
	}
	return right
}
