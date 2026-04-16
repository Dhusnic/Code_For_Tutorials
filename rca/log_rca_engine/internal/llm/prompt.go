package llm

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"log_rca_engine/internal/models"
)

type RCAPromptBuilder struct{}

type promptPayload struct {
	Incident promptIncident      `json:"incident"`
	Score    models.ScoreResult  `json:"score"`
	Rule     *models.Rule        `json:"rule,omitempty"`
	Topology *promptTopologyView `json:"topology,omitempty"`
	Evidence promptEvidence      `json:"evidence"`
}

type promptIncident struct {
	IncidentID      string            `json:"incident_id,omitempty"`
	OrganizationID  string            `json:"organization_id,omitempty"`
	RuleID          string            `json:"rule_id,omitempty"`
	Status          string            `json:"status,omitempty"`
	MatchedAt       string            `json:"matched_at,omitempty"`
	GroupByValues   map[string]string `json:"group_by_values,omitempty"`
	ResultSignature string            `json:"result_signature,omitempty"`
}

type promptEvidence struct {
	MatchedLogs []promptLog `json:"matched_logs,omitempty"`
	NearbyLogs  []promptLog `json:"nearby_logs,omitempty"`
}

type promptLog struct {
	Timestamp   string `json:"timestamp,omitempty"`
	Signal      string `json:"signal,omitempty"`
	Severity    string `json:"severity,omitempty"`
	ServiceName string `json:"service_name,omitempty"`
	HostName    string `json:"host_name,omitempty"`
	HostIP      string `json:"host_ip,omitempty"`
	Index       string `json:"index,omitempty"`
	DocID       string `json:"doc_id,omitempty"`
	Message     string `json:"message,omitempty"`
}

type promptTopologyView struct {
	Nodes []string             `json:"nodes,omitempty"`
	Edges []promptTopologyEdge `json:"edges,omitempty"`
}

type promptTopologyEdge struct {
	From     string `json:"from,omitempty"`
	To       string `json:"to,omitempty"`
	Relation string `json:"relation,omitempty"`
}

func NewRCAPromptBuilder() *RCAPromptBuilder {
	return &RCAPromptBuilder{}
}

func (b *RCAPromptBuilder) BuildExplanationConversation(model string, maxOutputTokens int, request models.ExplanationRequest) (Conversation, error) {
	payload, err := json.MarshalIndent(buildPromptPayload(request), "", "  ")
	if err != nil {
		return Conversation{}, fmt.Errorf("marshal explanation request: %w", err)
	}

	return Conversation{
		Name:            "rca_summary",
		Model:           strings.TrimSpace(model),
		MaxOutputTokens: maxOutputTokens,
		ResponseSchema:  explanationSchema(),
		Messages: []ConversationMessage{
			{
				Role: "system",
				Content: []ContentPart{
					{
						Type: "input_text",
						Text: rcaSystemPrompt(),
					},
				},
			},
			{
				Role: "user",
				Content: []ContentPart{
					{
						Type: "input_text",
						Text: buildExplanationPrompt(string(payload)),
					},
				},
			},
		},
	}, nil
}

func rcaSystemPrompt() string {
	return strings.TrimSpace(`
You are an RCA assistant for infrastructure and application incidents.
Analyze only the supplied incident payload.
Base every conclusion on the evidence, chronology, topology, and score breakdown that are provided.
Prefer direct evidence over guesswork and mention contradictions when the evidence is mixed.
Do not invent missing facts, hidden systems, or remediation steps that are not supported by the data.
Return only valid JSON matching the provided schema.
Keep the language clear, operational, and concise.
`)
}

func buildExplanationPrompt(payload string) string {
	return strings.TrimSpace(fmt.Sprintf(`
Create a structured RCA explanation for this incident.

Requirements:
- Treat the payload as the single source of truth.
- Explain the most likely root cause in plain language.
- Mention the affected services only if the payload supports them.
- Use concrete evidence from matched logs, nearby logs, topology, and scoring.
- Prefer the matched logs first, then use nearby logs only as supporting or contradicting context.
- Keep "evidence" and "next_checks" actionable and specific.
- Return JSON only.

Incident payload:
%s
`, payload))
}

func buildPromptPayload(request models.ExplanationRequest) promptPayload {
	return promptPayload{
		Incident: promptIncident{
			IncidentID:      request.Event.IncidentID,
			OrganizationID:  request.Event.OrganizationID,
			RuleID:          request.Event.RuleID,
			Status:          request.Event.Status,
			MatchedAt:       formatTime(request.Event.MatchedAt),
			GroupByValues:   request.Event.GroupByValues,
			ResultSignature: request.Event.ResultSignature,
		},
		Score:    request.Score,
		Rule:     request.Rule,
		Topology: buildPromptTopology(request),
		Evidence: promptEvidence{
			MatchedLogs: compactMatchedLogs(request.MatchedLogs),
			NearbyLogs:  compactNearbyLogs(request.NearbyLogs),
		},
	}
}

func buildPromptTopology(request models.ExplanationRequest) *promptTopologyView {
	if request.Topology == nil {
		return nil
	}

	allowedNodes := make(map[string]struct{}, len(request.Score.InvolvedServices))
	for _, node := range request.Score.InvolvedServices {
		trimmed := strings.TrimSpace(node)
		if trimmed != "" {
			allowedNodes[trimmed] = struct{}{}
		}
	}
	if len(allowedNodes) == 0 {
		return nil
	}

	view := &promptTopologyView{
		Nodes: append([]string(nil), request.Score.InvolvedServices...),
	}
	for _, edge := range request.Topology.Dependencies {
		from := strings.TrimSpace(edge.From)
		to := strings.TrimSpace(edge.To)
		if _, ok := allowedNodes[from]; !ok {
			continue
		}
		if _, ok := allowedNodes[to]; !ok {
			continue
		}
		view.Edges = append(view.Edges, promptTopologyEdge{From: from, To: to, Relation: edge.Relation})
	}
	for _, relation := range request.Topology.ServiceRelations {
		from := topologyNode(relation.FromIP, relation.FromService)
		to := topologyNode(relation.ToIP, relation.ToService)
		if _, ok := allowedNodes[from]; !ok {
			continue
		}
		if _, ok := allowedNodes[to]; !ok {
			continue
		}
		view.Edges = append(view.Edges, promptTopologyEdge{From: from, To: to, Relation: relation.Relation})
	}
	if len(view.Nodes) == 0 && len(view.Edges) == 0 {
		return nil
	}
	return view
}

func compactMatchedLogs(logs []models.RelatedLog) []promptLog {
	result := make([]promptLog, 0, len(logs))
	for _, log := range logs {
		result = append(result, compactLog(log))
	}
	return result
}

func compactNearbyLogs(logs []models.RelatedLog) []promptLog {
	if len(logs) > 12 {
		logs = logs[:12]
	}
	result := make([]promptLog, 0, len(logs))
	for _, log := range logs {
		result = append(result, compactLog(log))
	}
	return result
}

func compactLog(log models.RelatedLog) promptLog {
	return promptLog{
		Timestamp:   formatTime(log.Timestamp),
		Signal:      log.Signal,
		Severity:    log.Severity,
		ServiceName: log.ServiceName,
		HostName:    log.HostName,
		HostIP:      log.HostIP,
		Index:       log.Index,
		DocID:       log.DocID,
		Message:     truncateText(log.Message, 240),
	}
}

func formatTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339Nano)
}

func truncateText(value string, limit int) string {
	text := strings.TrimSpace(value)
	if limit <= 0 || len(text) <= limit {
		return text
	}
	return strings.TrimSpace(text[:limit]) + "..."
}

func topologyNode(deviceIP, service string) string {
	device := strings.TrimSpace(deviceIP)
	svc := strings.TrimSpace(service)
	switch {
	case device != "" && svc != "":
		return device + "::" + svc
	case device != "":
		return device
	default:
		return svc
	}
}
