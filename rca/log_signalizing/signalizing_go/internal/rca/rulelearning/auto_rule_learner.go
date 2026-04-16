package rulelearning

import (
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
	"rca/internal/rca/util"
)

type patternBucket struct {
	Service   string
	Signature string
	Count     int
	Samples   []string
}

type ruleCandidate struct {
	RuleID         string
	SignalKey      string
	Level          string
	Description    string
	Tags           []string
	ConditionField string
	ConditionOp    string
	ConditionValue string
}

var (
	stopwords = map[string]struct{}{
		"the": {}, "and": {}, "for": {}, "with": {}, "from": {}, "while": {}, "this": {}, "that": {}, "into": {}, "after": {}, "before": {}, "failed": {}, "error": {}, "critical": {}, "panic": {}, "alert": {}, "warning": {},
	}
	messageFields = []string{
		"msg",
		"message",
		"error.message",
		"log.message",
		"log.original",
		"event.original",
	}
	embeddedMessagePatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:msg|message|logmsg|description|reason)\s*=\s*"([^"]+)"`),
		regexp.MustCompile(`(?i)\b(?:msg|message|logmsg|description|reason)\s*=\s*'([^']+)'`),
		regexp.MustCompile(`(?i)"(?:msg|message|logmsg|description|reason)"\s*:\s*"([^"]+)"`),
		regexp.MustCompile(`(?i)\b(?:msg|message|logmsg|description|reason)\s*:\s*"([^"]+)"`),
		regexp.MustCompile(`(?i)\b(?:msg|message|logmsg|description|reason)\s*=\s*([^,\s][^,\r\n]*)`),
	}
	ipPattern       = regexp.MustCompile(`\b\d{1,3}(?:\.\d{1,3}){3}\b`)
	hexPattern      = regexp.MustCompile(`\b[0-9a-f]{8,}\b`)
	numberPattern   = regexp.MustCompile(`\b\d+\b`)
	nonWordPattern  = regexp.MustCompile(`[^a-z0-9<>]+`)
	whitespaceRegex = regexp.MustCompile(`\s+`)
	snakeCaseRegex  = regexp.MustCompile(`[^a-z0-9]+`)
	ruleIDRegex     = regexp.MustCompile(`[^A-Z0-9]+`)
)

// AutoRuleLearner learns recurring unclassified critical patterns and persists rule suggestions.
type AutoRuleLearner struct {
	config            config.RuleLearningConfig
	rulesDirectory    string
	outputDirectory   string
	serviceRuleFiles  map[string]string
	patternBuckets    map[string]*patternBucket
	emittedPatternKeys map[string]struct{}
	logger            logging.Logger
}

// NewAutoRuleLearner constructs the learner.
func NewAutoRuleLearner(cfg config.RuleLearningConfig, rulesDirectory string, serviceRuleFiles map[string]string) *AutoRuleLearner {
	return &AutoRuleLearner{
		config:             cfg,
		rulesDirectory:     rulesDirectory,
		outputDirectory:    cfg.OutputDirectory,
		serviceRuleFiles:   serviceRuleFiles,
		patternBuckets:     make(map[string]*patternBucket),
		emittedPatternKeys: make(map[string]struct{}),
		logger:             logging.GetLogger("AutoRuleLearner"),
	}
}

// Observe tracks one event when it is classified as unclassified critical.
func (l *AutoRuleLearner) Observe(serviceName string, sourceDoc map[string]any, selectedSignal map[string]any) {
	if !l.config.Enabled || !isUnclassifiedCritical(selectedSignal) {
		return
	}

	message := extractMessage(sourceDoc)
	if message == "" {
		return
	}

	normalized := normalizeMessage(message)
	if normalized == "" {
		return
	}
	keywords := l.extractKeywords(normalized)
	minKeywords := maxInt(1, l.config.MinKeywordCount)
	if len(keywords) < minKeywords {
		return
	}

	signatureTokens := keywords[:minInt(len(keywords), maxInt(minKeywords, l.config.MaxKeywordsPerSignal))]
	signature := strings.Join(signatureTokens, " ")
	key := serviceName + "||" + signature

	bucket := l.patternBuckets[key]
	if bucket == nil {
		bucket = &patternBucket{Service: serviceName, Signature: signature}
		l.patternBuckets[key] = bucket
	}
	bucket.Count++
	if len(bucket.Samples) < 3 {
		bucket.Samples = append(bucket.Samples, message)
	}
}

// Flush persists eligible learned patterns and returns counts by service.
func (l *AutoRuleLearner) Flush() map[string]int {
	if !l.config.Enabled {
		return map[string]int{}
	}

	type keyedCandidate struct {
		key       string
		candidate *ruleCandidate
	}

	keys := make([]string, 0, len(l.patternBuckets))
	for key := range l.patternBuckets {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		return l.patternBuckets[keys[i]].Count > l.patternBuckets[keys[j]].Count
	})

	serviceCandidates := make(map[string][]keyedCandidate)
	candidatesPerService := make(map[string]int)
	for _, key := range keys {
		if _, emitted := l.emittedPatternKeys[key]; emitted {
			continue
		}

		bucket := l.patternBuckets[key]
		if bucket.Count < maxInt(1, l.config.MinOccurrences) {
			continue
		}
		service := bucket.Service
		if candidatesPerService[service] >= maxInt(1, l.config.MaxCandidatesPerService) {
			continue
		}

		candidate := l.buildCandidate(bucket)
		if candidate == nil {
			continue
		}
		serviceCandidates[service] = append(serviceCandidates[service], keyedCandidate{key: key, candidate: candidate})
		candidatesPerService[service]++
	}

	writtenByService := make(map[string]int)
	persistedServices := make(map[string]struct{})
	for service, entries := range serviceCandidates {
		ruleFile := l.serviceRuleFiles[service]
		if ruleFile == "" {
			ruleFile = service + ".yml"
		}
		candidates := make([]*ruleCandidate, 0, len(entries))
		for _, entry := range entries {
			candidates = append(candidates, entry.candidate)
		}
		written := l.persistCandidates(service, ruleFile, candidates)
		if written > 0 {
			writtenByService[service] = written
			persistedServices[service] = struct{}{}
		}
	}

	for service, entries := range serviceCandidates {
		if _, ok := persistedServices[service]; !ok {
			continue
		}
		for _, entry := range entries {
			l.emittedPatternKeys[entry.key] = struct{}{}
		}
	}

	return writtenByService
}

func (l *AutoRuleLearner) buildCandidate(bucket *patternBucket) *ruleCandidate {
	sum := sha1.Sum([]byte(bucket.Service + "|" + bucket.Signature))
	signatureHash := hex.EncodeToString(sum[:])
	keywords := l.extractKeywords(bucket.Signature)
	minKeywords := maxInt(1, l.config.MinKeywordCount)
	if len(keywords) < minKeywords {
		return nil
	}

	maxKeywords := maxInt(minKeywords, l.config.MaxKeywordsPerSignal)
	selectedKeywords := keywords[:minInt(len(keywords), maxKeywords)]
	keywordPart := strings.Join(selectedKeywords, "_")
	hashShort := signatureHash[:8]

	signalKey := normalizeSnakeCase(fmt.Sprintf("%s_auto_%s_%s", bucket.Service, keywordPart, hashShort[:4]))
	upperKeywords := make([]string, 0, len(selectedKeywords))
	for _, keyword := range selectedKeywords {
		upperKeywords = append(upperKeywords, strings.ToUpper(keyword))
	}
	ruleID := normalizeRuleID(fmt.Sprintf("%s_AUTO_%s_%s", strings.ToUpper(bucket.Service), strings.Join(upperKeywords, "_"), strings.ToUpper(hashShort)))

	conditionLiteral := strings.Join(selectedKeywords, " ")
	if len(strings.TrimSpace(conditionLiteral)) < 8 {
		return nil
	}

	return &ruleCandidate{
		RuleID:         ruleID,
		SignalKey:      signalKey,
		Level:          strings.ToLower(strings.TrimSpace(l.config.Level)),
		Description:    "Auto-learned from recurring unclassified critical logs: " + conditionLiteral,
		Tags:           []string{"auto_generated", "unclassified_learning", bucket.Service, "critical"},
		ConditionField: defaultString(strings.TrimSpace(l.config.ConditionField), "message"),
		ConditionOp:    defaultString(strings.TrimSpace(l.config.ConditionOp), "contains"),
		ConditionValue: conditionLiteral,
	}
}

func (l *AutoRuleLearner) persistCandidates(service string, ruleFile string, candidates []*ruleCandidate) int {
	if len(candidates) == 0 {
		return 0
	}

	mode := strings.ToLower(strings.TrimSpace(l.config.Mode))
	targetPath := filepath.Join(l.rulesDirectory, ruleFile)
	if mode == "suggest" {
		targetPath = filepath.Join(l.outputDirectory, service+".yml")
	}

	root := readRulesPayload(targetPath, service)
	rulesNode := ensureRulesNode(root)
	if rulesNode.Kind != yaml.SequenceNode {
		l.logger.Warning(
			"Rules payload is not a list; resetting payload",
			logging.F("service", service),
			logging.F("path", targetPath),
		)
		rulesNode.Kind = yaml.SequenceNode
		rulesNode.Tag = "!!seq"
		rulesNode.Content = nil
	}

	existingIDs, existingSignalKeys, existingConditionValues := collectRuleKeys(rulesNode)
	newRules := 0
	for _, candidate := range candidates {
		if _, ok := existingIDs[candidate.RuleID]; ok {
			continue
		}
		if _, ok := existingSignalKeys[candidate.SignalKey]; ok {
			continue
		}
		normalizedCondition := strings.ToLower(strings.TrimSpace(candidate.ConditionValue))
		if _, ok := existingConditionValues[normalizedCondition]; ok {
			continue
		}

		rulesNode.Content = append(rulesNode.Content, candidate.toYAMLNode())
		newRules++
		existingIDs[candidate.RuleID] = struct{}{}
		existingSignalKeys[candidate.SignalKey] = struct{}{}
		existingConditionValues[normalizedCondition] = struct{}{}
	}
	if newRules == 0 {
		return 0
	}

	if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
		l.logger.Exception(
			"Failed writing auto-learned rules",
			err,
			logging.F("service", service),
			logging.F("path", targetPath),
			logging.F("mode", mode),
		)
		return 0
	}
	encoded, err := yaml.Marshal(root)
	if err != nil {
		l.logger.Exception(
			"Failed writing auto-learned rules",
			err,
			logging.F("service", service),
			logging.F("path", targetPath),
			logging.F("mode", mode),
		)
		return 0
	}
	if err := os.WriteFile(targetPath, encoded, 0o644); err != nil {
		l.logger.Exception(
			"Failed writing auto-learned rules",
			err,
			logging.F("service", service),
			logging.F("path", targetPath),
			logging.F("mode", mode),
		)
		return 0
	}

	l.logger.Info(
		"Auto-learned rule candidates persisted",
		logging.F("service", service),
		logging.F("mode", mode),
		logging.F("path", targetPath),
		logging.F("written_count", newRules),
	)
	return newRules
}

func collectRuleKeys(rulesNode *yaml.Node) (map[string]struct{}, map[string]struct{}, map[string]struct{}) {
	ids := make(map[string]struct{})
	signalKeys := make(map[string]struct{})
	conditionValues := make(map[string]struct{})

	for _, ruleNode := range rulesNode.Content {
		if ruleNode.Kind != yaml.MappingNode {
			continue
		}
		ruleMap := nodeMap(ruleNode)
		if idNode, ok := ruleMap["id"]; ok {
			ids[strings.TrimSpace(idNode.Value)] = struct{}{}
		}
		if signalNode, ok := ruleMap["signal_key"]; ok {
			signalKeys[strings.TrimSpace(signalNode.Value)] = struct{}{}
		}
		if conditionNode, ok := ruleMap["condition"]; ok && conditionNode.Kind == yaml.MappingNode {
			conditionMap := nodeMap(conditionNode)
			if valueNode, ok := conditionMap["value"]; ok {
				conditionValues[strings.ToLower(strings.TrimSpace(valueNode.Value))] = struct{}{}
			}
		}
	}

	return ids, signalKeys, conditionValues
}

func readRulesPayload(path string, service string) *yaml.Node {
	content, err := os.ReadFile(path)
	if err != nil {
		return newRulesPayload(service)
	}

	var root yaml.Node
	if err := yaml.Unmarshal(content, &root); err != nil {
		return newRulesPayload(service)
	}

	document := documentContent(&root)
	if document == nil || document.Kind != yaml.MappingNode {
		return newRulesPayload(service)
	}

	ensureMappingValue(document, "service", scalarNode(service))
	ensureMappingValue(document, "rules", &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"})
	return document
}

func newRulesPayload(service string) *yaml.Node {
	root := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	root.Content = append(root.Content,
		scalarNode("service"), scalarNode(service),
		scalarNode("rules"), &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"},
	)
	return root
}

func documentContent(root *yaml.Node) *yaml.Node {
	if root == nil {
		return nil
	}
	if root.Kind == yaml.DocumentNode && len(root.Content) > 0 {
		return root.Content[0]
	}
	return root
}

func ensureRulesNode(root *yaml.Node) *yaml.Node {
	rulesNode := getMappingValue(root, "rules")
	if rulesNode == nil {
		rulesNode = &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
		root.Content = append(root.Content, scalarNode("rules"), rulesNode)
	}
	return rulesNode
}

func ensureMappingValue(root *yaml.Node, key string, value *yaml.Node) {
	if getMappingValue(root, key) != nil {
		return
	}
	root.Content = append(root.Content, scalarNode(key), value)
}

func getMappingValue(root *yaml.Node, key string) *yaml.Node {
	if root == nil || root.Kind != yaml.MappingNode {
		return nil
	}
	for idx := 0; idx+1 < len(root.Content); idx += 2 {
		if root.Content[idx].Value == key {
			return root.Content[idx+1]
		}
	}
	return nil
}

func nodeMap(root *yaml.Node) map[string]*yaml.Node {
	values := make(map[string]*yaml.Node)
	if root == nil || root.Kind != yaml.MappingNode {
		return values
	}
	for idx := 0; idx+1 < len(root.Content); idx += 2 {
		values[root.Content[idx].Value] = root.Content[idx+1]
	}
	return values
}

func (c *ruleCandidate) toYAMLNode() *yaml.Node {
	condition := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	condition.Content = append(condition.Content,
		scalarNode("field"), scalarNode(c.ConditionField),
		scalarNode("op"), scalarNode(c.ConditionOp),
		scalarNode("value"), scalarNode(c.ConditionValue),
	)

	tags := &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
	for _, tag := range c.Tags {
		tags.Content = append(tags.Content, scalarNode(tag))
	}

	rule := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	rule.Content = append(rule.Content,
		scalarNode("id"), scalarNode(c.RuleID),
		scalarNode("signal_key"), scalarNode(c.SignalKey),
		scalarNode("level"), scalarNode(c.Level),
		scalarNode("description"), scalarNode(c.Description),
		scalarNode("tags"), tags,
		scalarNode("condition"), condition,
	)
	return rule
}

func scalarNode(value string) *yaml.Node {
	return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: value}
}

func normalizeMessage(message string) string {
	text := strings.TrimSpace(strings.ToLower(message))
	text = ipPattern.ReplaceAllString(text, " <ip> ")
	text = hexPattern.ReplaceAllString(text, " <hex> ")
	text = numberPattern.ReplaceAllString(text, " <num> ")
	text = nonWordPattern.ReplaceAllString(text, " ")
	text = whitespaceRegex.ReplaceAllString(text, " ")
	return strings.TrimSpace(text)
}

func (l *AutoRuleLearner) extractKeywords(signature string) []string {
	ordered := make([]string, 0)
	seen := make(map[string]struct{})
	for _, token := range strings.Fields(signature) {
		if token == "<num>" || token == "<ip>" || token == "<hex>" {
			continue
		}
		if len(token) < 2 {
			continue
		}
		if _, ok := stopwords[token]; ok {
			continue
		}
		if _, ok := seen[token]; ok {
			continue
		}
		seen[token] = struct{}{}
		ordered = append(ordered, token)
	}
	return ordered
}

func extractMessage(sourceDoc map[string]any) string {
	var fallback string
	for _, fieldName := range messageFields {
		value := util.GetNested(sourceDoc, fieldName)
		if value == nil && !strings.Contains(fieldName, ".") {
			value = sourceDoc[fieldName]
		}
		text, ok := value.(string)
		if !ok || strings.TrimSpace(text) == "" {
			continue
		}
		text = strings.TrimSpace(text)
		if fallback == "" {
			fallback = text
		}
		if extracted := extractEmbeddedMessage(text); extracted != "" {
			return extracted
		}
	}
	return fallback
}

func extractEmbeddedMessage(text string) string {
	for _, pattern := range embeddedMessagePatterns {
		match := pattern.FindStringSubmatch(text)
		if len(match) < 2 {
			continue
		}
		captured := strings.TrimSpace(match[1])
		if captured != "" {
			return captured
		}
	}
	return ""
}

func normalizeSnakeCase(value string) string {
	text := strings.TrimSpace(strings.ToLower(value))
	text = snakeCaseRegex.ReplaceAllString(text, "_")
	text = strings.Trim(text, "_")
	text = strings.ReplaceAll(text, "__", "_")
	for strings.Contains(text, "__") {
		text = strings.ReplaceAll(text, "__", "_")
	}
	return text
}

func normalizeRuleID(value string) string {
	text := strings.TrimSpace(strings.ToUpper(value))
	text = ruleIDRegex.ReplaceAllString(text, "_")
	text = strings.Trim(text, "_")
	for strings.Contains(text, "__") {
		text = strings.ReplaceAll(text, "__", "_")
	}
	return text
}

func isUnclassifiedCritical(selectedSignal map[string]any) bool {
	if selectedSignal == nil {
		return false
	}
	level := strings.ToLower(strings.TrimSpace(fmt.Sprint(selectedSignal["level"])))
	if level != "critical" {
		return false
	}
	signalKey := strings.ToLower(strings.TrimSpace(fmt.Sprint(selectedSignal["signal"])))
	tagsRaw, _ := selectedSignal["tags"].([]string)
	tagSet := make(map[string]struct{})
	for _, tag := range tagsRaw {
		tagSet[strings.ToLower(strings.TrimSpace(tag))] = struct{}{}
	}
	if _, ok := tagSet["unclassified"]; ok {
		return true
	}
	if _, ok := tagSet["fallback"]; ok {
		return true
	}
	return strings.HasSuffix(signalKey, "_unclassified_failure")
}

func defaultString(value string, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
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
