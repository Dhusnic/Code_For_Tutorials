package mongoresults

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
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

const (
	runtimeManagedBy   = "log_rca_engine"
	runtimeSourceKind  = "current"
	runtimeSourceFile  = "log_rca_engine/data/results/rca_results.json"
	resultDocumentKind = "rca_result"
	loadChunkSize      = 500
)

type Store struct {
	cfg    config.MongoSyncConfig
	logger *slog.Logger

	mu           sync.Mutex
	client       *mongo.Client
	ensureIdxMu  sync.Mutex
	indexesReady bool
}

func New(cfg config.MongoSyncConfig, logger *slog.Logger) *Store {
	return &Store{
		cfg:    cfg,
		logger: logger,
	}
}

func (s *Store) Close(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client == nil {
		return nil
	}
	err := s.client.Disconnect(ctx)
	s.client = nil
	return err
}

func (s *Store) Load(context.Context) (models.RCAOutputDocument, error) {
	return models.RCAOutputDocument{}, fmt.Errorf("full RCA result document loads are not supported by the MongoDB store; use incident-scoped loading")
}

func (s *Store) Save(ctx context.Context, document models.RCAOutputDocument) error {
	return s.UpsertRecords(ctx, document.Items)
}

func (s *Store) UpsertRecords(ctx context.Context, records []models.RCARecord) error {
	if len(records) == 0 {
		return nil
	}

	writeCtx, cancel := context.WithTimeout(ctx, s.timeout())
	defer cancel()

	client, err := s.ensureClient(writeCtx)
	if err != nil {
		return err
	}
	collection := client.Database(s.cfg.Database).Collection(s.cfg.ResultsCollection)
	if err := s.ensureIndexes(writeCtx, collection); err != nil {
		return err
	}

	operations := make([]mongo.WriteModel, 0, len(records))
	now := time.Now().UTC()
	for _, record := range records {
		if strings.TrimSpace(record.IncidentID) == "" {
			continue
		}
		document, err := runtimeResultDocument(record)
		if err != nil {
			return fmt.Errorf("build MongoDB RCA result document for incident %s: %w", record.IncidentID, err)
		}
		document["managed_by"] = runtimeManagedBy
		document["document_kind"] = resultDocumentKind
		document["source_kind"] = runtimeSourceKind
		document["source_file"] = runtimeSourceFile
		document["source_file_name"] = "rca_results.json"
		document["last_persisted_at"] = now
		documentID := resultDocumentID(record)

		operations = append(operations, mongo.NewUpdateOneModel().
			SetFilter(bson.M{"_id": documentID}).
			SetUpdate(bson.M{
				"$set": document,
				"$setOnInsert": bson.M{
					"first_persisted_at": now,
				},
			}).
			SetUpsert(true))
	}

	if len(operations) == 0 {
		return nil
	}

	if _, err := collection.BulkWrite(writeCtx, operations, options.BulkWrite().SetOrdered(false)); err != nil {
		return fmt.Errorf("upsert MongoDB RCA results: %w", err)
	}

	if s.logger != nil {
		s.logger.Info("persisted RCA results to MongoDB", "collection", s.cfg.ResultsCollection, "records", len(operations))
	}
	return nil
}

func (s *Store) LoadByIncidentIDs(ctx context.Context, incidentIDs []string) (map[string]models.RCARecord, error) {
	incidentIDs = trimUniqueStrings(incidentIDs)
	if len(incidentIDs) == 0 {
		return map[string]models.RCARecord{}, nil
	}

	readCtx, cancel := context.WithTimeout(ctx, s.timeout())
	defer cancel()

	client, err := s.ensureClient(readCtx)
	if err != nil {
		return nil, err
	}
	collection := client.Database(s.cfg.Database).Collection(s.cfg.ResultsCollection)
	if err := s.ensureIndexes(readCtx, collection); err != nil {
		return nil, err
	}

	recordsByIncident := make(map[string]models.RCARecord, len(incidentIDs))
	for start := 0; start < len(incidentIDs); start += loadChunkSize {
		end := start + loadChunkSize
		if end > len(incidentIDs) {
			end = len(incidentIDs)
		}

		cursor, err := collection.Aggregate(readCtx, latestRecordsPipeline(incidentIDs[start:end]))
		if err != nil {
			return nil, fmt.Errorf("query MongoDB RCA results by incident: %w", err)
		}

		for cursor.Next(readCtx) {
			var document bson.M
			if err := cursor.Decode(&document); err != nil {
				_ = cursor.Close(readCtx)
				return nil, fmt.Errorf("decode MongoDB RCA result document: %w", err)
			}
			record, err := recordFromDocument(document)
			if err != nil {
				_ = cursor.Close(readCtx)
				return nil, fmt.Errorf("convert MongoDB RCA result document: %w", err)
			}
			incidentID := strings.TrimSpace(record.IncidentID)
			if incidentID == "" {
				continue
			}
			recordsByIncident[incidentID] = record
		}
		if err := cursor.Err(); err != nil {
			_ = cursor.Close(readCtx)
			return nil, fmt.Errorf("iterate MongoDB RCA result documents: %w", err)
		}
		if err := cursor.Close(readCtx); err != nil {
			return nil, fmt.Errorf("close MongoDB RCA result cursor: %w", err)
		}
	}

	if s.logger != nil {
		s.logger.Debug("loaded RCA results from MongoDB for incidents", "collection", s.cfg.ResultsCollection, "incident_ids", len(incidentIDs), "records", len(recordsByIncident))
	}
	return recordsByIncident, nil
}

func (s *Store) ensureClient(ctx context.Context) (*mongo.Client, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.client != nil {
		return s.client, nil
	}

	client, err := mongo.Connect(ctx, options.Client().ApplyURI(s.cfg.URI))
	if err != nil {
		return nil, fmt.Errorf("connect MongoDB for RCA results: %w", err)
	}
	if err := client.Ping(ctx, readpref.Primary()); err != nil {
		_ = client.Disconnect(context.Background())
		return nil, fmt.Errorf("ping MongoDB for RCA results: %w", err)
	}
	s.client = client
	return client, nil
}

func (s *Store) ensureIndexes(ctx context.Context, collection *mongo.Collection) error {
	s.ensureIdxMu.Lock()
	defer s.ensureIdxMu.Unlock()
	if s.indexesReady {
		return nil
	}

	models := []mongo.IndexModel{
		{Keys: bson.D{{Key: "managed_by", Value: 1}, {Key: "document_kind", Value: 1}, {Key: "incident_id", Value: 1}, {Key: "updated_at", Value: -1}, {Key: "rca_generated_at", Value: -1}, {Key: "last_persisted_at", Value: -1}}},
		{Keys: bson.D{{Key: "result_signature", Value: 1}}},
		{Keys: bson.D{{Key: "organization_id", Value: 1}, {Key: "topology_id", Value: 1}, {Key: "rule_id", Value: 1}}},
		{Keys: bson.D{{Key: "status", Value: 1}, {Key: "classification", Value: 1}}},
	}
	if _, err := collection.Indexes().CreateMany(ctx, models); err != nil {
		return fmt.Errorf("create MongoDB RCA result indexes: %w", err)
	}
	s.indexesReady = true
	return nil
}

func (s *Store) timeout() time.Duration {
	if s.cfg.Timeout > 0 {
		return s.cfg.Timeout
	}
	return 5 * time.Second
}

func runtimeResultDocument(record models.RCARecord) (bson.M, error) {
	payload, err := json.Marshal(record)
	if err != nil {
		return nil, err
	}

	var document bson.M
	if err := json.Unmarshal(payload, &document); err != nil {
		return nil, err
	}
	document["_id"] = resultDocumentID(record)
	document["incident_id"] = strings.TrimSpace(record.IncidentID)
	document["organization_id"] = strings.TrimSpace(record.OrganizationID)
	document["topology_id"] = strings.TrimSpace(record.TopologyID)
	document["rule_id"] = strings.TrimSpace(record.RuleID)

	resultSignature := strings.TrimSpace(record.ResultSignature)
	if resultSignature == "" {
		document["result_signature"] = nil
	} else {
		document["result_signature"] = resultSignature
	}
	return document, nil
}

func resultDocumentID(record models.RCARecord) string {
	incidentID := strings.TrimSpace(record.IncidentID)
	resultSignature := strings.TrimSpace(record.ResultSignature)
	if resultSignature == "" {
		return runtimeSourceKind + "::rca_results.json::" + incidentID
	}
	return runtimeSourceKind + "::rca_results.json::" + incidentID + "::" + resultSignature
}

func UniqueLatest(records []models.RCARecord) []models.RCARecord {
	if len(records) == 0 {
		return nil
	}

	latestByDocumentID := make(map[string]models.RCARecord, len(records))
	documentIDs := make([]string, 0, len(records))
	for _, record := range records {
		documentID := resultDocumentID(record)
		if _, seen := latestByDocumentID[documentID]; !seen {
			documentIDs = append(documentIDs, documentID)
		}
		latestByDocumentID[documentID] = record
	}

	sort.Strings(documentIDs)
	result := make([]models.RCARecord, 0, len(documentIDs))
	for _, documentID := range documentIDs {
		result = append(result, latestByDocumentID[documentID])
	}
	return result
}

func latestRecordsPipeline(incidentIDs []string) mongo.Pipeline {
	return mongo.Pipeline{
		{{Key: "$match", Value: bson.D{
			{Key: "managed_by", Value: runtimeManagedBy},
			{Key: "document_kind", Value: resultDocumentKind},
			{Key: "incident_id", Value: bson.D{{Key: "$in", Value: incidentIDs}}},
		}}},
		{{Key: "$sort", Value: bson.D{
			{Key: "incident_id", Value: 1},
			{Key: "updated_at", Value: -1},
			{Key: "rca_generated_at", Value: -1},
			{Key: "last_persisted_at", Value: -1},
			{Key: "_id", Value: -1},
		}}},
		{{Key: "$group", Value: bson.D{
			{Key: "_id", Value: "$incident_id"},
			{Key: "document", Value: bson.D{{Key: "$first", Value: "$$ROOT"}}},
		}}},
		{{Key: "$replaceRoot", Value: bson.D{{Key: "newRoot", Value: "$document"}}}},
	}
}

func recordFromDocument(document bson.M) (models.RCARecord, error) {
	payload, err := json.Marshal(document)
	if err != nil {
		return models.RCARecord{}, err
	}

	var record models.RCARecord
	if err := json.Unmarshal(payload, &record); err != nil {
		return models.RCARecord{}, err
	}
	return record, nil
}

func trimUniqueStrings(values []string) []string {
	if len(values) == 0 {
		return nil
	}

	seen := make(map[string]struct{}, len(values))
	trimmed := make([]string, 0, len(values))
	for _, value := range values {
		candidate := strings.TrimSpace(value)
		if candidate == "" {
			continue
		}
		if _, ok := seen[candidate]; ok {
			continue
		}
		seen[candidate] = struct{}{}
		trimmed = append(trimmed, candidate)
	}
	sort.Strings(trimmed)
	return trimmed
}
