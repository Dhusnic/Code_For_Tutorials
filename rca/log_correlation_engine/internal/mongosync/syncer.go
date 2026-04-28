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

	"log_correlation_engine/internal/config"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.mongodb.org/mongo-driver/mongo/readpref"
)

type RuleSyncer struct {
	cfg       config.MongoSyncConfig
	rulesFile string
	logger    *slog.Logger

	mu        sync.Mutex
	runMu     sync.Mutex
	stateMu   sync.Mutex
	client    *mongo.Client
	lastRev   int64
	revKnown  bool
	forceFull bool
}

func NewRuleSyncer(cfg config.MongoSyncConfig, rulesFile string, logger *slog.Logger) *RuleSyncer {
	return &RuleSyncer{
		cfg:       cfg,
		rulesFile: strings.TrimSpace(rulesFile),
		logger:    logger,
	}
}

func (s *RuleSyncer) Close(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client == nil {
		return nil
	}
	err := s.client.Disconnect(ctx)
	s.client = nil
	return err
}

func (s *RuleSyncer) Invalidate() {
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	s.forceFull = true
}

func (s *RuleSyncer) Sync(ctx context.Context) (bool, error) {
	s.runMu.Lock()
	defer s.runMu.Unlock()

	if !s.cfg.Enabled {
		return false, nil
	}
	if strings.TrimSpace(s.rulesFile) == "" {
		return false, fmt.Errorf("rules file path must not be empty")
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
	if !s.needsSync(state.Revision, hasState) {
		return false, nil
	}

	if s.cfg.UseSnapshot && hasState {
		rules, ok, err := s.loadRulesSnapshot(syncCtx, database, state.Revision)
		if err != nil {
			s.resetClient(ctx)
			return false, err
		}
		if ok {
			changed, err := writeJSONIfChanged(s.rulesFile, rules)
			if err != nil {
				return false, err
			}
			s.markSynced(state.Revision, true)
			if s.logger != nil {
				s.logger.Info(
					"synced correlation rules from MongoDB snapshot",
					"database", s.cfg.Database,
					"snapshot_collection", s.cfg.SnapshotCollection,
					"revision", state.Revision,
					"rules", len(rules),
					"changed", changed,
				)
			}
			return changed, nil
		}
	}

	rules, err := s.loadEnabledRules(syncCtx, database)
	if err != nil {
		s.resetClient(ctx)
		return false, err
	}
	if s.cfg.WriteSnapshot && hasState {
		if err := s.writeRulesSnapshot(syncCtx, database, state.Revision, rules); err != nil {
			s.resetClient(ctx)
			return false, err
		}
	}

	changed, err := writeJSONIfChanged(s.rulesFile, rules)
	if err != nil {
		return false, err
	}
	if hasState {
		s.markSynced(state.Revision, true)
	}
	if s.logger != nil {
		s.logger.Info(
			"synced correlation rules from MongoDB",
			"database", s.cfg.Database,
			"collection", s.cfg.RulesCollection,
			"revision", state.Revision,
			"revision_tracked", hasState,
			"rules", len(rules),
			"changed", changed,
		)
	}
	return changed, nil
}

type configState struct {
	Revision int64
}

func (s *RuleSyncer) loadState(ctx context.Context, database *mongo.Database) (configState, bool, error) {
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
	return configState{Revision: revision}, true, nil
}

func (s *RuleSyncer) needsSync(revision int64, hasRevision bool) bool {
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	if s.forceFull {
		s.forceFull = false
		return true
	}
	if !hasRevision {
		return true
	}
	return !s.revKnown || s.lastRev != revision
}

func (s *RuleSyncer) markSynced(revision int64, hasRevision bool) {
	if !hasRevision {
		return
	}
	s.stateMu.Lock()
	defer s.stateMu.Unlock()
	s.lastRev = revision
	s.revKnown = true
}

func (s *RuleSyncer) loadRulesSnapshot(ctx context.Context, database *mongo.Database, revision int64) ([]map[string]any, bool, error) {
	collection := database.Collection(s.cfg.SnapshotCollection)
	var raw bson.M
	err := collection.FindOne(
		ctx,
		bson.M{"name": s.cfg.SnapshotName},
		options.FindOne().SetSort(bson.D{{Key: "revision", Value: -1}}),
	).Decode(&raw)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return nil, false, nil
		}
		return nil, false, fmt.Errorf("read MongoDB config snapshot: %w", err)
	}
	doc, err := plainMap(raw)
	if err != nil {
		return nil, false, fmt.Errorf("normalize MongoDB config snapshot: %w", err)
	}
	snapshotRevision := int64Value(doc["revision"])
	if snapshotRevision < revision {
		return nil, false, nil
	}
	rules, err := ruleSlice(doc["rules"])
	if err != nil {
		return nil, false, fmt.Errorf("decode MongoDB rules snapshot: %w", err)
	}
	return rules, true, nil
}

func (s *RuleSyncer) writeRulesSnapshot(ctx context.Context, database *mongo.Database, revision int64, rules []map[string]any) error {
	collection := database.Collection(s.cfg.SnapshotCollection)
	_, err := collection.UpdateOne(
		ctx,
		bson.M{"name": s.cfg.SnapshotName},
		bson.M{"$set": bson.M{
			"name":       s.cfg.SnapshotName,
			"revision":   revision,
			"updated_at": time.Now().UTC(),
			"rules":      rules,
		}},
		options.Update().SetUpsert(true),
	)
	if err != nil {
		return fmt.Errorf("write MongoDB rules snapshot: %w", err)
	}
	return nil
}

func (s *RuleSyncer) loadEnabledRules(ctx context.Context, database *mongo.Database) ([]map[string]any, error) {
	collection := database.Collection(s.cfg.RulesCollection)
	cursor, err := collection.Find(
		ctx,
		bson.M{"is_enabled": true},
		options.Find().SetSort(bson.D{{Key: "priority", Value: 1}, {Key: "id", Value: 1}}),
	)
	if err != nil {
		return nil, fmt.Errorf("find enabled rules in MongoDB: %w", err)
	}
	defer cursor.Close(ctx)

	rules := make([]map[string]any, 0)
	for cursor.Next(ctx) {
		var raw bson.M
		if err := cursor.Decode(&raw); err != nil {
			return nil, fmt.Errorf("decode MongoDB rule document: %w", err)
		}
		doc, err := plainMap(raw)
		if err != nil {
			return nil, fmt.Errorf("normalize MongoDB rule document: %w", err)
		}
		rule := sanitizeRuleDocument(doc)
		if strings.TrimSpace(stringValue(rule["id"])) == "" {
			continue
		}
		rule["is_enabled"] = true
		rules = append(rules, rule)
	}
	if err := cursor.Err(); err != nil {
		return nil, fmt.Errorf("iterate MongoDB rule documents: %w", err)
	}

	sortRules(rules)
	return rules, nil
}

func (s *RuleSyncer) ensureClient(ctx context.Context) (*mongo.Client, error) {
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

func (s *RuleSyncer) resetClient(ctx context.Context) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client == nil {
		return
	}
	_ = s.client.Disconnect(ctx)
	s.client = nil
}

func (s *RuleSyncer) timeout() time.Duration {
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

func decodeViaJSON(input any, output any) error {
	payload, err := json.Marshal(input)
	if err != nil {
		return err
	}
	return json.Unmarshal(payload, output)
}

func firstNonNil(values ...any) any {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
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
