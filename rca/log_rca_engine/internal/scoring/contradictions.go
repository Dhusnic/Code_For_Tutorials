package scoring

import (
	"strings"
	"unicode"

	"log_rca_engine/internal/models"
)

const maxContradictionEvidenceMessageLength = 500

func computeContradictionPenalty(event models.CorrelationEvent, rule *models.Rule, topology *models.OrganizationTopology, nearbyLogs []models.RelatedLog) (float64, []string, []models.ContradictionEvidence) {
	if len(nearbyLogs) == 0 {
		return 1, nil, nil
	}

	known := knownTopologyNodes(topology)
	graph := buildDirectedGraph(topology)
	involved := identitiesFromResolved(orderedTopologyMatchesFromEvent(event, topology))
	involvedSet := trimmedSet(involved)
	negativeSignals := negativeSignalSet(event, rule)
	recoverySignals := recoverySignalSet(rule)
	matchedSignals := matchedSignalSet(event)

	incidentServices := make(map[string]struct{}, len(event.LogID))
	incidentHosts := make(map[string]struct{}, len(event.LogID))
	incidentIPs := make(map[string]struct{}, len(event.LogID))
	for _, log := range event.LogID {
		if service := strings.ToLower(strings.TrimSpace(log.ServiceName)); service != "" {
			incidentServices[service] = struct{}{}
		}
		if host := strings.ToLower(strings.TrimSpace(log.HostName)); host != "" {
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
	recoveryPenaltyByScope := make(map[string]float64)
	evidence := make([]models.ContradictionEvidence, 0, len(nearbyLogs))

	for _, log := range nearbyLogs {
		signal := strings.ToLower(strings.TrimSpace(log.Signal))
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
				appliedPenalty := explicitContradictionPenalty * relevance
				penalty += appliedPenalty
				evidence = append(evidence, contradictionEvidence(
					"explicit_not_sequence",
					"signal matched a rule exclusion/not_sequence entry",
					log,
					relevance,
					appliedPenalty,
				))
				continue
			}
		}

		if recoverySignal, reason := classifyRecoverySignal(signal, recoverySignals); recoverySignal {
			scopeKey, ok := recoveryScopeKey(log, signal, identity, involvedSet, incidentServices, incidentHosts, incidentIPs)
			if !ok {
				continue
			}
			appliedPenalty := recoveryContradictionPenalty * relevance
			remainingPenalty := recoveryContradictionPenalty - recoveryPenaltyByScope[scopeKey]
			if remainingPenalty <= 0 {
				continue
			}
			if appliedPenalty > remainingPenalty {
				appliedPenalty = remainingPenalty
			}
			recoveryPenaltyByScope[scopeKey] += appliedPenalty
			recoveryFound = true
			penalty += appliedPenalty
			evidence = append(evidence, contradictionEvidence(
				"same_service_recovery",
				reason,
				log,
				relevance,
				appliedPenalty,
			))
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
		appliedPenalty := competingSignalPenalty * relevance
		penalty += appliedPenalty
		evidence = append(evidence, contradictionEvidence(
			"competing_high_severity",
			"high-severity signal appeared on a weakly connected topology identity",
			log,
			relevance,
			appliedPenalty,
		))
	}

	penalty = minFloat(penalty, maxContradictionPenalty)
	reasons := make([]string, 0, 3)
	if explicitFound {
		reasons = append(reasons, "Nearby rule exclusion signals contradicted the expected incident sequence.")
	}
	if recoveryFound {
		reasons = append(reasons, "Nearby same-service recovery signals reduced confidence in an active RCA.")
	}
	if competingFound {
		reasons = append(reasons, "Competing high-severity signals appeared on weakly related services nearby.")
	}
	if !explicitFound && !recoveryFound && !competingFound {
		return 1, nil, nil
	}
	return clamp01(1 - penalty), reasons, evidence
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

func recoverySignalSet(rule *models.Rule) map[string]struct{} {
	result := make(map[string]struct{})
	if rule == nil {
		return result
	}
	for _, signal := range rule.RecoverySignals {
		if trimmed := strings.ToLower(strings.TrimSpace(signal)); trimmed != "" {
			result[trimmed] = struct{}{}
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
	if _, ok := incidentServices[strings.ToLower(strings.TrimSpace(log.ServiceName))]; ok {
		score = 1.00
	}
	if _, ok := incidentHosts[strings.ToLower(strings.TrimSpace(log.HostName))]; ok && score < 0.90 {
		score = 0.90
	}
	for _, ip := range relatedLogIPCandidates(log) {
		if _, ok := incidentIPs[ip]; ok {
			return 1.00
		}
	}
	return score
}

func classifyRecoverySignal(signal string, recoverySignals map[string]struct{}) (bool, string) {
	if signal == "" {
		return false, ""
	}
	if _, ok := recoverySignals[signal]; ok {
		return true, "signal matched the rule recovery_signals list"
	}
	if looksLikeRecoverySignalName(signal) {
		return true, "signal name is an unambiguous service recovery indicator"
	}
	return false, ""
}

func looksLikeRecoverySignalName(signal string) bool {
	tokens := signalNameTokens(signal)
	if len(tokens) == 0 {
		return false
	}
	for _, token := range tokens {
		switch token {
		case "abnormal", "conflict", "corrupt", "degraded", "error", "failed", "failure", "recovering", "unhealthy", "unstable":
			return false
		}
	}
	for _, token := range tokens {
		switch token {
		case "cleared", "healthy", "normal", "recovered", "resolved", "restored", "stabilized", "stable":
			return true
		}
	}
	return false
}

func signalNameTokens(signal string) []string {
	return strings.FieldsFunc(strings.ToLower(strings.TrimSpace(signal)), func(r rune) bool {
		return r == '_' || r == '-' || r == '.' || r == ':' || unicode.IsSpace(r)
	})
}

func recoveryScopeKey(log models.RelatedLog, signal, identity string, involved map[string]struct{}, incidentServices, incidentHosts, incidentIPs map[string]struct{}) (string, bool) {
	service := strings.ToLower(strings.TrimSpace(log.ServiceName))
	if service != "" {
		if _, ok := incidentServices[service]; ok {
			return "service|" + service, true
		}
	}
	if identity != "" {
		if _, ok := involved[strings.TrimSpace(identity)]; ok {
			return "identity|" + strings.TrimSpace(identity), true
		}
	}
	if matchedService := serviceFromSignal(signal, incidentServices); matchedService != "" && sharesIncidentHostOrIP(log, incidentHosts, incidentIPs) {
		return "service|" + matchedService, true
	}
	return "", false
}

func serviceFromSignal(signal string, incidentServices map[string]struct{}) string {
	signal = strings.ToLower(strings.TrimSpace(signal))
	if signal == "" {
		return ""
	}
	for service := range incidentServices {
		if signal == service || strings.HasPrefix(signal, service+"_") || strings.HasPrefix(signal, service+"-") {
			return service
		}
	}
	return ""
}

func sharesIncidentHostOrIP(log models.RelatedLog, incidentHosts, incidentIPs map[string]struct{}) bool {
	if _, ok := incidentHosts[strings.ToLower(strings.TrimSpace(log.HostName))]; ok {
		return true
	}
	for _, ip := range relatedLogIPCandidates(log) {
		if _, ok := incidentIPs[ip]; ok {
			return true
		}
	}
	return false
}

func contradictionEvidence(kind, reason string, log models.RelatedLog, relevance, penalty float64) models.ContradictionEvidence {
	return models.ContradictionEvidence{
		Kind:        kind,
		Reason:      reason,
		DocID:       log.DocID,
		SourceIndex: log.Index,
		Timestamp:   log.Timestamp,
		Signal:      log.Signal,
		Severity:    log.Severity,
		ServiceName: log.ServiceName,
		HostName:    log.HostName,
		HostIP:      log.HostIP,
		Message:     trimEvidenceMessage(log.Message),
		Relevance:   round(relevance),
		Penalty:     round(penalty),
	}
}

func trimEvidenceMessage(message string) string {
	message = strings.TrimSpace(message)
	if len(message) <= maxContradictionEvidenceMessageLength {
		return message
	}
	return message[:maxContradictionEvidenceMessageLength]
}

func trimmedSet(values []string) map[string]struct{} {
	result := make(map[string]struct{}, len(values))
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			result[trimmed] = struct{}{}
		}
	}
	return result
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
