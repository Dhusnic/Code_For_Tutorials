package scoring

import (
	"strings"

	"log_rca_engine/internal/models"
	"log_rca_engine/internal/utils"
)

type resolvedTopologyIdentity struct {
	Identity   string
	Confidence float64
}

type weightedEdge struct {
	To       string
	Strength float64
}

func orderedTopologyMatchesFromEvent(event models.CorrelationEvent, topology *models.OrganizationTopology) []resolvedTopologyIdentity {
	result := make([]resolvedTopologyIdentity, 0, len(event.LogID)+1)
	known := knownTopologyNodes(topology)
	for _, log := range event.LogID {
		if resolved := resolveLogTopologyIdentityDetailed(log, known); resolved.Identity != "" {
			result = append(result, resolved)
		}
	}
	if len(result) == 0 {
		if resolved := resolveGroupByTopologyIdentityDetailed(event.GroupByValues, known); resolved.Identity != "" {
			result = append(result, resolved)
		}
	}
	return result
}

func identitiesFromResolved(resolved []resolvedTopologyIdentity) []string {
	result := make([]string, 0, len(resolved))
	for _, item := range resolved {
		if strings.TrimSpace(item.Identity) != "" {
			result = append(result, strings.TrimSpace(item.Identity))
		}
	}
	return result
}

func computeIdentityConfidence(resolved []resolvedTopologyIdentity, event models.CorrelationEvent, topology *models.OrganizationTopology) float64 {
	if len(resolved) == 0 {
		if fallback := resolveGroupByTopologyIdentityDetailed(event.GroupByValues, knownTopologyNodes(topology)); fallback.Identity != "" {
			return clamp01(fallback.Confidence)
		}
		return 0
	}

	total := 0.0
	for _, item := range resolved {
		total += clamp01(item.Confidence)
	}
	return clamp01(total / float64(len(resolved)))
}

func computeCompletedStepCoverage(audit *models.MatchAudit) float64 {
	if audit == nil || len(audit.Steps) == 0 {
		return 0
	}
	return clamp01(float64(countCompletedSteps(audit)) / float64(len(audit.Steps)))
}

func countCompletedSteps(audit *models.MatchAudit) int {
	if audit == nil || len(audit.Steps) == 0 {
		return 0
	}
	completed := 0
	for _, step := range audit.Steps {
		required := step.RequiredCount
		if required <= 0 {
			required = 1
		}
		if step.MatchedCount >= required {
			completed++
		}
	}
	return completed
}

func passesConfirmationGates(event models.CorrelationEvent, breakdown models.ScoreBreakdown) bool {
	if breakdown.SequenceMatch < 0.55 || breakdown.RuleCompleteness < 0.45 {
		return false
	}
	if breakdown.TopologyCoverage < 0.50 || breakdown.IdentityConfidence < 0.60 {
		return false
	}
	if breakdown.TimeProximity < 0.30 || breakdown.ContradictionPenalty < 0.80 {
		return false
	}
	if breakdown.SeverityAlignment < minimumSeverityAlignment {
		return false
	}
	return true
}

func knownTopologyNodes(topology *models.OrganizationTopology) map[string]struct{} {
	known := make(map[string]struct{})
	if topology == nil {
		return known
	}
	for _, service := range topology.Services {
		if identity := advancedTopologyServiceIdentity(service); identity != "" {
			known[identity] = struct{}{}
		}
		if host := deviceIdentity(service.DeviceIP, service.HostName); host != "" {
			known[host] = struct{}{}
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
		if from := topologyRelationIdentity(firstNonEmpty(relation.FromIP), relation.FromService); from != "" {
			known[from] = struct{}{}
		}
		if to := topologyRelationIdentity(firstNonEmpty(relation.ToIP), relation.ToService); to != "" {
			known[to] = struct{}{}
		}
		if fromIP := strings.TrimSpace(relation.FromIP); fromIP != "" {
			known[fromIP] = struct{}{}
		}
		if toIP := strings.TrimSpace(relation.ToIP); toIP != "" {
			known[toIP] = struct{}{}
		}
	}
	for _, device := range topology.Devices {
		hostIdentity := deviceIdentity(device.DeviceIP, device.HostName)
		if hostIdentity != "" {
			known[hostIdentity] = struct{}{}
		}
		for _, service := range device.Services {
			if identity := topologyRelationIdentity(hostIdentity, service.ServiceName); identity != "" {
				known[identity] = struct{}{}
			}
		}
	}
	return known
}

func advancedTopologyServiceIdentity(service models.TopologyService) string {
	return topologyRelationIdentity(deviceIdentity(service.DeviceIP, service.HostName), firstNonEmpty(service.ServiceName, service.HostName))
}

func deviceIdentity(deviceIP, hostName string) string {
	return firstNonEmpty(deviceIP, hostName)
}

func buildDirectedGraph(topology *models.OrganizationTopology) map[string][]weightedEdge {
	graph := make(map[string][]weightedEdge)
	if topology == nil {
		return graph
	}
	for _, service := range topology.Services {
		serviceIdentity := advancedTopologyServiceIdentity(service)
		if serviceIdentity == "" {
			continue
		}
		if _, ok := graph[serviceIdentity]; !ok {
			graph[serviceIdentity] = []weightedEdge{}
		}
		if host := deviceIdentity(service.DeviceIP, service.HostName); host != "" && host != serviceIdentity {
			addTopologyRelation(graph, serviceIdentity, host, "", serviceDeviceBridgeStrength)
		}
	}
	for _, edge := range topology.Dependencies {
		addTopologyRelation(graph, strings.TrimSpace(edge.From), strings.TrimSpace(edge.To), edge.Relation, edge.Weight)
	}
	for _, relation := range topology.ServiceRelations {
		fromHost := firstNonEmpty(relation.FromIP)
		toHost := firstNonEmpty(relation.ToIP)
		fromNode := topologyRelationIdentity(fromHost, relation.FromService)
		toNode := topologyRelationIdentity(toHost, relation.ToService)
		if fromHost != "" && fromNode != "" {
			addTopologyRelation(graph, fromNode, fromHost, "", serviceDeviceBridgeStrength)
		}
		if toHost != "" && toNode != "" {
			addTopologyRelation(graph, toNode, toHost, "", serviceDeviceBridgeStrength)
		}
		addTopologyRelation(
			graph,
			fromNode,
			toNode,
			relation.Relation,
			relation.Weight,
		)
	}
	for _, device := range topology.Devices {
		addDeviceEdges(graph, device)
	}
	return graph
}

func addDeviceEdges(graph map[string][]weightedEdge, device models.TopologyDevice) {
	hostIdentity := deviceIdentity(device.DeviceIP, device.HostName)
	for _, service := range device.Services {
		serviceIdentity := topologyRelationIdentity(hostIdentity, service.ServiceName)
		if serviceIdentity == "" {
			continue
		}
		if hostIdentity != "" {
			addTopologyRelation(graph, serviceIdentity, hostIdentity, "", serviceDeviceBridgeStrength)
		}
		for _, dependency := range service.DependsOn {
			addTopologyRelation(graph, serviceIdentity, topologyRelationIdentity(hostIdentity, dependency), "depends_on", 1)
		}
		for _, upstream := range service.UpstreamFor {
			addTopologyRelation(graph, serviceIdentity, topologyRelationIdentity(hostIdentity, upstream), "upstream", 1)
		}
		for _, receiver := range service.ReceivesFrom {
			addTopologyRelation(graph, topologyRelationIdentity(hostIdentity, receiver), serviceIdentity, "upstream", 1)
		}
	}
}

func addTopologyRelation(graph map[string][]weightedEdge, from, to, relation string, weight float64) {
	if from == "" || to == "" {
		return
	}
	if _, ok := graph[from]; !ok {
		graph[from] = []weightedEdge{}
	}
	if _, ok := graph[to]; !ok {
		graph[to] = []weightedEdge{}
	}
	baseWeight := normalizeEdgeWeight(weight)
	forwardFactor, reverseFactor := relationDirectionalStrengths(relation)
	graph[from] = appendWeightedEdge(graph[from], weightedEdge{To: to, Strength: clamp01(baseWeight * forwardFactor)})
	graph[to] = appendWeightedEdge(graph[to], weightedEdge{To: from, Strength: clamp01(baseWeight * reverseFactor)})
}

func relationDirectionalStrengths(relation string) (float64, float64) {
	text := strings.ToLower(strings.TrimSpace(relation))
	switch {
	case strings.Contains(text, "upstream"), strings.Contains(text, "calls"):
		return 1.00, 0.85
	case strings.Contains(text, "depends_on"), strings.Contains(text, "dependency"), strings.Contains(text, "uses"),
		strings.Contains(text, "client"), strings.Contains(text, "requires"), strings.Contains(text, "receives_from"):
		return 0.85, 1.00
	case strings.Contains(text, "peer"), strings.Contains(text, "replica"), strings.Contains(text, "sibling"):
		return 0.85, 0.85
	default:
		return 1.00, 1.00
	}
}

func normalizeEdgeWeight(weight float64) float64 {
	if weight <= 0 {
		return 1
	}
	return clamp01(weight)
}

func appendWeightedEdge(values []weightedEdge, candidate weightedEdge) []weightedEdge {
	if candidate.To == "" || candidate.Strength <= 0 {
		return values
	}
	for idx, value := range values {
		if value.To != candidate.To {
			continue
		}
		if candidate.Strength > value.Strength {
			values[idx].Strength = candidate.Strength
		}
		return values
	}
	return append(values, candidate)
}

func resolveLogTopologyIdentityDetailed(log models.EvidenceLog, known map[string]struct{}) resolvedTopologyIdentity {
	ipCandidates := logIPCandidates(log)
	service := strings.TrimSpace(log.ServiceName)
	host := strings.TrimSpace(log.HostName)
	for _, ip := range ipCandidates {
		if service == "" {
			continue
		}
		candidate := topologyRelationIdentity(ip, service)
		if _, ok := known[candidate]; ok {
			return resolvedTopologyIdentity{Identity: candidate, Confidence: identityConfidenceComposite}
		}
	}
	for _, ip := range ipCandidates {
		if _, ok := known[ip]; ok {
			return resolvedTopologyIdentity{Identity: ip, Confidence: identityConfidenceIPOnly}
		}
	}
	if service != "" {
		if _, ok := known[service]; ok {
			return resolvedTopologyIdentity{Identity: service, Confidence: identityConfidenceService}
		}
	}
	if host != "" {
		if _, ok := known[host]; ok {
			return resolvedTopologyIdentity{Identity: host, Confidence: identityConfidenceHost}
		}
	}
	if ip := firstIP(ipCandidates); ip != "" {
		if service != "" {
			return resolvedTopologyIdentity{Identity: topologyRelationIdentity(ip, service), Confidence: 0.95}
		}
		return resolvedTopologyIdentity{Identity: ip, Confidence: identityConfidenceIPOnly}
	}
	if service != "" {
		return resolvedTopologyIdentity{Identity: service, Confidence: identityConfidenceService}
	}
	if host != "" {
		return resolvedTopologyIdentity{Identity: host, Confidence: identityConfidenceHost}
	}
	return resolvedTopologyIdentity{}
}

func resolveGroupByTopologyIdentityDetailed(groupByValues map[string]string, known map[string]struct{}) resolvedTopologyIdentity {
	if identity := strings.TrimSpace(groupByValues["topology.identity"]); identity != "" {
		return resolvedTopologyIdentity{Identity: identity, Confidence: inferIdentityConfidence(identity)}
	}
	service := firstNonEmpty(groupByValues["service.identity"], groupByValues["service.name"], groupByValues["event.module"])
	host := firstNonEmpty(groupByValues["host.identity"], groupByValues["host.name"])
	ipCandidates := utils.ExtractIPAddresses(stringMapToAny(groupByValues), "host.ip")
	if ip := firstIP(ipCandidates); ip != "" {
		if service != "" {
			candidate := topologyRelationIdentity(ip, service)
			if _, ok := known[candidate]; ok || len(known) == 0 {
				return resolvedTopologyIdentity{Identity: candidate, Confidence: 0.95}
			}
		}
		if _, ok := known[ip]; ok || len(known) == 0 {
			return resolvedTopologyIdentity{Identity: ip, Confidence: identityConfidenceIPOnly}
		}
	}
	if service != "" {
		return resolvedTopologyIdentity{Identity: service, Confidence: identityConfidenceService}
	}
	if host != "" {
		return resolvedTopologyIdentity{Identity: host, Confidence: identityConfidenceHost}
	}
	return resolvedTopologyIdentity{}
}

func inferIdentityConfidence(identity string) float64 {
	switch {
	case strings.Contains(identity, topologyNodeSeparator):
		return identityConfidenceComposite
	case strings.Count(identity, ".") == 3:
		return identityConfidenceIPOnly
	default:
		return identityConfidenceService
	}
}

func bestDirectedPathScore(graph map[string][]weightedEdge, start, target string, maxHops int) float64 {
	if start == target && start != "" {
		return 1
	}
	if start == "" || target == "" || maxHops <= 0 {
		return 0
	}
	if _, ok := graph[start]; !ok {
		return 0
	}

	best := 0.0
	visited := map[string]struct{}{start: {}}
	var walk func(node string, hopCount int, total float64)
	walk = func(node string, hopCount int, total float64) {
		if hopCount >= maxHops {
			return
		}
		for _, edge := range graph[node] {
			if _, seen := visited[edge.To]; seen {
				continue
			}
			nextHops := hopCount + 1
			nextTotal := total + edge.Strength
			if edge.To == target {
				score := clamp01((nextTotal / float64(nextHops)) * hopFactor(nextHops))
				if score > best {
					best = score
				}
			}
			visited[edge.To] = struct{}{}
			walk(edge.To, nextHops, nextTotal)
			delete(visited, edge.To)
		}
	}
	walk(start, 0, 0)
	return best
}

func hopFactor(hops int) float64 {
	switch hops {
	case 1:
		return 1.00
	case 2:
		return 0.75
	case 3:
		return 0.50
	case 4:
		return 0.35
	default:
		return 0.20
	}
}
