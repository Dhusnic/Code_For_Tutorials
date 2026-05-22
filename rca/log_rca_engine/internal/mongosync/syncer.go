package mongosync

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"log_rca_engine/internal/config"
	"log_rca_engine/internal/models"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.mongodb.org/mongo-driver/mongo/readpref"
)

type Syncer struct {
	cfg          config.MongoSyncConfig
	rulesFile    string
	topologyFile string
	logger       *slog.Logger

	mu        sync.Mutex
	runMu     sync.Mutex
	stateMu   sync.Mutex
	client    *mongo.Client
	lastRev   int64
	revKnown  bool
	forceFull bool
}

func New(cfg config.MongoSyncConfig, rulesFile, topologyFile string, logger *slog.Logger) *Syncer {
	return &Syncer{
		cfg:          cfg,
		rulesFile:    strings.TrimSpace(rulesFile),
		topologyFile: strings.TrimSpace(topologyFile),
		logger:       logger,
	}
}

func (s *Syncer) Close(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client == nil {
		return nil
	}
	err := s.client.Disconnect(ctx)
	s.client = nil
	return err
}

func (s *Syncer) Invalidate() {
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	s.forceFull = true
}

func (s *Syncer) Sync(ctx context.Context) (bool, error) {
	s.runMu.Lock()
	defer s.runMu.Unlock()

	if !s.cfg.Enabled {
		return false, nil
	}
	if strings.TrimSpace(s.rulesFile) == "" {
		return false, fmt.Errorf("rules file path must not be empty")
	}
	if strings.TrimSpace(s.topologyFile) == "" {
		return false, fmt.Errorf("topology file path must not be empty")
	}

	syncCtx, cancel := context.WithTimeout(ctx, s.timeout())
	defer cancel()

	client, err := s.ensureClient(syncCtx)
	if err != nil {
		return false, err
	}

	database := client.Database(s.cfg.Database)
	state, hasState, err := s.loadState(syncCtx, database)
	if err != nil {
		s.resetClient(ctx)
		return false, err
	}
	if !s.needsSync(state, hasState) {
		return false, nil
	}

	if s.cfg.UseSnapshot && hasState {
		rules, topologyDoc, ok, err := s.loadSnapshot(syncCtx, database, state.Revision)
		if err != nil {
			s.resetClient(ctx)
			return false, err
		}
		if ok {
			rulesChanged, err := writeJSONIfChanged(s.rulesFile, rules)
			if err != nil {
				return false, err
			}
			topologyChanged, err := writeJSONIfChanged(s.topologyFile, topologyDoc)
			if err != nil {
				return false, err
			}
			changed := rulesChanged || topologyChanged
			acknowledged, err := s.updateStateSynced(syncCtx, database, state.Revision)
			if err != nil {
				return false, err
			}
			if acknowledged {
				s.markSynced(state.Revision, true)
			}
			if s.logger != nil {
				s.logger.Info(
					"synced RCA rules and topology from MongoDB snapshot",
					"database", s.cfg.Database,
					"snapshot_collection", s.cfg.SnapshotCollection,
					"revision", state.Revision,
					"is_synced", state.IsSynced,
					"state_acknowledged", acknowledged,
					"rules", len(rules),
					"linked_topologies", countTopologies(topologyDoc),
					"changed", changed,
				)
			}
			return changed, nil
		}
	}

	rules, linkedTopologyIDs, err := s.loadEnabledRules(syncCtx, database)
	if err != nil {
		s.resetClient(ctx)
		return false, err
	}
	topologyDoc, err := s.loadLinkedTopologies(syncCtx, database, linkedTopologyIDs)
	if err != nil {
		s.resetClient(ctx)
		return false, err
	}
	if s.cfg.WriteSnapshot && hasState {
		if err := s.writeSnapshot(syncCtx, database, state.Revision, rules, topologyDoc); err != nil {
			s.resetClient(ctx)
			return false, err
		}
	}

	rulesChanged, err := writeJSONIfChanged(s.rulesFile, rules)
	if err != nil {
		return false, err
	}
	topologyChanged, err := writeJSONIfChanged(s.topologyFile, topologyDoc)
	if err != nil {
		return false, err
	}

	changed := rulesChanged || topologyChanged
	if hasState {
		acknowledged, err := s.updateStateSynced(syncCtx, database, state.Revision)
		if err != nil {
			return false, err
		}
		if acknowledged {
			s.markSynced(state.Revision, true)
		}
		if s.logger != nil {
			s.logger.Info(
				"synced RCA rules and topology from MongoDB",
				"database", s.cfg.Database,
				"rules_collection", s.cfg.RulesCollection,
				"topology_collection", s.cfg.TopologyCollection,
				"revision", state.Revision,
				"is_synced", state.IsSynced,
				"state_acknowledged", acknowledged,
				"rules", len(rules),
				"linked_topologies", countTopologies(topologyDoc),
				"changed", changed,
			)
		}
		return changed, nil
	}
	s.markPending(state.Revision)
	if s.logger != nil {
		s.logger.Info(
			"synced RCA rules and topology from MongoDB",
			"database", s.cfg.Database,
			"rules_collection", s.cfg.RulesCollection,
			"topology_collection", s.cfg.TopologyCollection,
			"revision", state.Revision,
			"is_synced", state.IsSynced,
			"state_acknowledged", false,
			"rules", len(rules),
			"linked_topologies", countTopologies(topologyDoc),
			"changed", changed,
		)
	}
	return changed, nil
}

type configState struct {
	Revision int64
	IsSynced bool
}

func (s *Syncer) loadState(ctx context.Context, database *mongo.Database) (configState, bool, error) {
	collection := database.Collection(s.cfg.StateCollection)
	var raw bson.M
	err := collection.FindOne(ctx, bson.M{"name": s.cfg.StateName}).Decode(&raw)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			if s.logger != nil {
				s.logger.Warn("MongoDB config state document not found; falling back to full sync", "collection", s.cfg.StateCollection, "name", s.cfg.StateName)
			}
			return configState{}, false, nil
		}
		return configState{}, false, fmt.Errorf("read MongoDB config state: %w", err)
	}
	doc, err := plainMap(raw)
	if err != nil {
		return configState{}, false, fmt.Errorf("normalize MongoDB config state: %w", err)
	}
	revision := int64Value(firstNonNil(doc["revision"], doc["version"]))
	if revision <= 0 {
		return configState{}, false, fmt.Errorf("MongoDB config state %s/%s must contain a positive revision", s.cfg.StateCollection, s.cfg.StateName)
	}
	return configState{
		Revision: revision,
		IsSynced: boolValue(doc["is_synced"]),
	}, true, nil
}

func (s *Syncer) needsSync(state configState, hasState bool) bool {
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	if s.forceFull {
		s.forceFull = false
		return true
	}
	if !hasState {
		return true
	}
	if state.IsSynced {
		return false
	}
	return !s.revKnown || s.lastRev != state.Revision
}

func (s *Syncer) markSynced(revision int64, hasRevision bool) {
	if !hasRevision {
		return
	}
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	s.lastRev = revision
	s.revKnown = true
}

func (s *Syncer) markPending(revision int64) {
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	s.lastRev = revision
	s.revKnown = true
}

func (s *Syncer) updateStateSynced(ctx context.Context, database *mongo.Database, revision int64) (bool, error) {
	collection := database.Collection(s.cfg.StateCollection)
	now := time.Now().UTC()
	result, err := collection.UpdateOne(
		ctx,
		bson.M{
			"name":     s.cfg.StateName,
			"revision": revision,
			"$or": []bson.M{
				{"is_synced": false},
				{"is_synced": bson.M{"$exists": false}},
			},
		},
		bson.M{"$set": bson.M{
			"is_synced": true,
			"synced_at":  now,
			"updated_at": now,
		}},
	)
	if err != nil {
		return false, fmt.Errorf("mark MongoDB config state synced: %w", err)
	}
	return result.MatchedCount > 0, nil
}

func (s *Syncer) loadSnapshot(ctx context.Context, database *mongo.Database, revision int64) ([]map[string]any, models.TopologyDocument, bool, error) {
	collection := database.Collection(s.cfg.SnapshotCollection)
	var raw bson.M
	err := collection.FindOne(
		ctx,
		bson.M{"name": s.cfg.SnapshotName},
		options.FindOne().SetSort(bson.D{{Key: "revision", Value: -1}}),
	).Decode(&raw)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return nil, models.TopologyDocument{}, false, nil
		}
		return nil, models.TopologyDocument{}, false, fmt.Errorf("read MongoDB config snapshot: %w", err)
	}
	doc, err := plainMap(raw)
	if err != nil {
		return nil, models.TopologyDocument{}, false, fmt.Errorf("normalize MongoDB config snapshot: %w", err)
	}
	snapshotRevision := int64Value(doc["revision"])
	if snapshotRevision < revision {
		return nil, models.TopologyDocument{}, false, nil
	}
	rules, err := ruleSlice(doc["rules"])
	if err != nil {
		return nil, models.TopologyDocument{}, false, fmt.Errorf("decode MongoDB rules snapshot: %w", err)
	}
	var topologyDoc models.TopologyDocument
	if err := decodeViaJSON(doc["topology"], &topologyDoc); err != nil {
		return nil, models.TopologyDocument{}, false, fmt.Errorf("decode MongoDB topology snapshot: %w", err)
	}
	if topologyDoc.Organizations == nil {
		topologyDoc.Organizations = make(map[string]map[string]models.OrganizationTopology)
	}
	return rules, topologyDoc, true, nil
}

func (s *Syncer) writeSnapshot(ctx context.Context, database *mongo.Database, revision int64, rules []map[string]any, topologyDoc models.TopologyDocument) error {
	collection := database.Collection(s.cfg.SnapshotCollection)
	_, err := collection.UpdateOne(
		ctx,
		bson.M{"name": s.cfg.SnapshotName},
		bson.M{"$set": bson.M{
			"name":       s.cfg.SnapshotName,
			"revision":   revision,
			"updated_at": time.Now().UTC(),
			"rules":      rules,
			"topology":   topologyDoc,
		}},
		options.Update().SetUpsert(true),
	)
	if err != nil {
		return fmt.Errorf("write MongoDB config snapshot: %w", err)
	}
	return nil
}

func (s *Syncer) loadEnabledRules(ctx context.Context, database *mongo.Database) ([]map[string]any, map[string]struct{}, error) {
	collection := database.Collection(s.cfg.RulesCollection)
	cursor, err := collection.Find(
		ctx,
		bson.M{"is_enabled": true},
		options.Find().SetSort(bson.D{{Key: "priority", Value: 1}, {Key: "id", Value: 1}}),
	)
	if err != nil {
		return nil, nil, fmt.Errorf("find enabled rules in MongoDB: %w", err)
	}
	defer cursor.Close(ctx)

	rules := make([]map[string]any, 0)
	linkedTopologyIDs := make(map[string]struct{})
	for cursor.Next(ctx) {
		var raw bson.M
		if err := cursor.Decode(&raw); err != nil {
			return nil, nil, fmt.Errorf("decode MongoDB rule document: %w", err)
		}
		doc, err := plainMap(raw)
		if err != nil {
			return nil, nil, fmt.Errorf("normalize MongoDB rule document: %w", err)
		}
		rule := sanitizeRuleDocument(doc)
		if strings.TrimSpace(stringValue(rule["id"])) == "" {
			continue
		}
		rule["is_enabled"] = true
		for _, topologyID := range stringSlice(rule["topology_ids"]) {
			if trimmed := strings.TrimSpace(topologyID); trimmed != "" {
				linkedTopologyIDs[trimmed] = struct{}{}
			}
		}
		rules = append(rules, rule)
	}
	if err := cursor.Err(); err != nil {
		return nil, nil, fmt.Errorf("iterate MongoDB rule documents: %w", err)
	}

	sort.SliceStable(rules, func(i, j int) bool {
		leftPriority := intValue(rules[i]["priority"])
		rightPriority := intValue(rules[j]["priority"])
		if leftPriority != rightPriority {
			return leftPriority < rightPriority
		}
		return stringValue(rules[i]["id"]) < stringValue(rules[j]["id"])
	})
	return rules, linkedTopologyIDs, nil
}

func (s *Syncer) loadLinkedTopologies(ctx context.Context, database *mongo.Database, linkedTopologyIDs map[string]struct{}) (models.TopologyDocument, error) {
	document := models.TopologyDocument{
		SchemaVersion: 1,
		Organizations: make(map[string]map[string]models.OrganizationTopology),
	}
	if len(linkedTopologyIDs) == 0 {
		return document, nil
	}

	topologyIDs := make([]string, 0, len(linkedTopologyIDs))
	for topologyID := range linkedTopologyIDs {
		topologyIDs = append(topologyIDs, topologyID)
	}
	sort.Strings(topologyIDs)

	collection := database.Collection(s.cfg.TopologyCollection)
	cursor, err := collection.Find(
		ctx,
		bson.M{
			"is_enabled":  true,
			"topology_id": bson.M{"$in": topologyIDs},
		},
		options.Find().SetSort(bson.D{{Key: "organization_id", Value: 1}, {Key: "topology_id", Value: 1}}),
	)
	if err != nil {
		return document, fmt.Errorf("find linked topologies in MongoDB: %w", err)
	}
	defer cursor.Close(ctx)

	for cursor.Next(ctx) {
		var raw bson.M
		if err := cursor.Decode(&raw); err != nil {
			return document, fmt.Errorf("decode MongoDB topology document: %w", err)
		}
		doc, err := plainMap(raw)
		if err != nil {
			return document, fmt.Errorf("normalize MongoDB topology document: %w", err)
		}

		organizationID := strings.TrimSpace(stringValue(doc["organization_id"]))
		topologyID := strings.TrimSpace(stringValue(doc["topology_id"]))
		if organizationID == "" || topologyID == "" {
			continue
		}

		topology, err := topologyFromDocument(doc)
		if err != nil {
			return document, fmt.Errorf("decode topology %s/%s: %w", organizationID, topologyID, err)
		}
		if !hasTopologyData(topology) {
			continue
		}

		if document.Organizations[organizationID] == nil {
			document.Organizations[organizationID] = make(map[string]models.OrganizationTopology)
		}
		document.Organizations[organizationID][topologyID] = topology
	}
	if err := cursor.Err(); err != nil {
		return document, fmt.Errorf("iterate MongoDB topology documents: %w", err)
	}
	return document, nil
}

func topologyFromDocument(doc map[string]any) (models.OrganizationTopology, error) {
	if rawTopology, ok := doc["topology"]; ok && rawTopology != nil {
		var topology models.OrganizationTopology
		if err := decodeViaJSON(rawTopology, &topology); err != nil {
			return models.OrganizationTopology{}, err
		}
		return topology, nil
	}

	var topology models.OrganizationTopology
	if rawServices, ok := doc["services"]; ok {
		if err := decodeViaJSON(rawServices, &topology.Services); err != nil {
			return models.OrganizationTopology{}, err
		}
	}
	if rawDependencies, ok := doc["dependencies"]; ok {
		if err := decodeViaJSON(rawDependencies, &topology.Dependencies); err != nil {
			return models.OrganizationTopology{}, err
		}
	}
	if rawDevices, ok := doc["devices"]; ok {
		if err := decodeViaJSON(rawDevices, &topology.Devices); err != nil {
			return models.OrganizationTopology{}, err
		}
	}
	if rawRelations, ok := doc["service_relations"]; ok {
		if err := decodeViaJSON(rawRelations, &topology.ServiceRelations); err != nil {
			return models.OrganizationTopology{}, err
		}
	}
	return topology, nil
}

func (s *Syncer) ensureClient(ctx context.Context) (*mongo.Client, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client != nil {
		return s.client, nil
	}

	client, err := mongo.Connect(ctx, options.Client().ApplyURI(s.cfg.URI))
	if err != nil {
		return nil, fmt.Errorf("connect MongoDB: %w", err)
	}
	if err := client.Ping(ctx, readpref.Primary()); err != nil {
		_ = client.Disconnect(context.Background())
		return nil, fmt.Errorf("ping MongoDB: %w", err)
	}
	s.client = client
	return client, nil
}

func (s *Syncer) resetClient(ctx context.Context) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client == nil {
		return
	}
	_ = s.client.Disconnect(ctx)
	s.client = nil
}

func (s *Syncer) timeout() time.Duration {
	if s.cfg.Timeout > 0 {
		return s.cfg.Timeout
	}
	return 5 * time.Second
}

func sanitizeRuleDocument(input map[string]any) map[string]any {
	result := make(map[string]any, len(input))
	for key, value := range input {
		if isMongoMetadataKey(key) {
			continue
		}
		result[key] = value
	}
	if strings.TrimSpace(stringValue(result["id"])) == "" {
		if ruleID := strings.TrimSpace(stringValue(input["rule_id"])); ruleID != "" {
			result["id"] = ruleID
		}
	}
	return result
}

func isMongoMetadataKey(key string) bool {
	switch strings.TrimSpace(key) {
	case "_id", "managed_by", "imported_at", "source_kind", "source_file", "source_file_name", "document_kind", "rule_id", "original_is_enabled":
		return true
	default:
		return false
	}
}

func writeJSONIfChanged(path string, value any) (bool, error) {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return false, fmt.Errorf("marshal synced JSON: %w", err)
	}
	content = append(content, '\n')

	if existing, err := os.ReadFile(filepath.Clean(path)); err == nil && bytes.Equal(existing, content) {
		return false, nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return false, fmt.Errorf("create synced JSON directory: %w", err)
	}

	tempFile, err := os.CreateTemp(filepath.Dir(path), "mongo-sync-*.tmp")
	if err != nil {
		return false, fmt.Errorf("create synced JSON temp file: %w", err)
	}
	tempPath := tempFile.Name()
	defer func() {
		_ = tempFile.Close()
		_ = os.Remove(tempPath)
	}()

	if _, err := tempFile.Write(content); err != nil {
		return false, fmt.Errorf("write synced JSON temp file: %w", err)
	}
	if err := tempFile.Close(); err != nil {
		return false, fmt.Errorf("close synced JSON temp file: %w", err)
	}
	if err := os.Rename(tempPath, path); err != nil {
		if removeErr := os.Remove(path); removeErr != nil && !os.IsNotExist(removeErr) {
			return false, fmt.Errorf("replace synced JSON file: %w", err)
		}
		if retryErr := os.Rename(tempPath, path); retryErr != nil {
			return false, fmt.Errorf("rename synced JSON temp file: %w", retryErr)
		}
	}
	return true, nil
}

func decodeViaJSON(input any, output any) error {
	payload, err := json.Marshal(input)
	if err != nil {
		return err
	}
	return json.Unmarshal(payload, output)
}

func plainMap(input any) (map[string]any, error) {
	payload, err := bson.MarshalExtJSON(input, false, false)
	if err != nil {
		return nil, err
	}
	var output map[string]any
	if err := json.Unmarshal(payload, &output); err != nil {
		return nil, err
	}
	return output, nil
}

func ruleSlice(value any) ([]map[string]any, error) {
	var rules []map[string]any
	if err := decodeViaJSON(value, &rules); err != nil {
		return nil, err
	}
	normalized := make([]map[string]any, 0, len(rules))
	for _, rule := range rules {
		rule = sanitizeRuleDocument(rule)
		if strings.TrimSpace(stringValue(rule["id"])) == "" {
			continue
		}
		rule["is_enabled"] = true
		normalized = append(normalized, rule)
	}
	sortRules(normalized)
	return normalized, nil
}

func sortRules(rules []map[string]any) {
	sort.SliceStable(rules, func(i, j int) bool {
		leftPriority := intValue(rules[i]["priority"])
		rightPriority := intValue(rules[j]["priority"])
		if leftPriority != rightPriority {
			return leftPriority < rightPriority
		}
		return stringValue(rules[i]["id"]) < stringValue(rules[j]["id"])
	})
}

func firstNonNil(values ...any) any {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
}

func hasTopologyData(topology models.OrganizationTopology) bool {
	return len(topology.Services) > 0 ||
		len(topology.Dependencies) > 0 ||
		len(topology.Devices) > 0 ||
		len(topology.ServiceRelations) > 0
}

func countTopologies(document models.TopologyDocument) int {
	total := 0
	for _, topologies := range document.Organizations {
		total += len(topologies)
	}
	return total
}

func stringSlice(value any) []string {
	switch typed := value.(type) {
	case []string:
		return append([]string(nil), typed...)
	case []any:
		result := make([]string, 0, len(typed))
		for _, item := range typed {
			if text := strings.TrimSpace(stringValue(item)); text != "" {
				result = append(result, text)
			}
		}
		return result
	default:
		var decoded []string
		if err := decodeViaJSON(value, &decoded); err == nil {
			return decoded
		}
		return nil
	}
}

func stringValue(value any) string {
	if value == nil {
		return ""
	}
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed)
	default:
		return strings.TrimSpace(fmt.Sprint(typed))
	}
}

func boolValue(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		switch strings.TrimSpace(strings.ToLower(typed)) {
		case "true", "1", "yes", "on":
			return true
		default:
			return false
		}
	case int:
		return typed != 0
	case int32:
		return typed != 0
	case int64:
		return typed != 0
	case float32:
		return typed != 0
	case float64:
		return typed != 0
	default:
		return false
	}
}

func int64Value(value any) int64 {
	switch typed := value.(type) {
	case int:
		return int64(typed)
	case int32:
		return int64(typed)
	case int64:
		return typed
	case float64:
		return int64(typed)
	case float32:
		return int64(typed)
	default:
		return 0
	}
}

func intValue(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int32:
		return int(typed)
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case float32:
		return int(typed)
	default:
		return 0
	}
}
