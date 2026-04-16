package checkpoints

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"

	"rca/internal/rca/config"
	"rca/internal/rca/logging"
	"rca/internal/rca/util"
)

// Store is the checkpoint persistence interface.
type Store interface {
	Get(service string, index string) ([]any, error)
	Set(service string, index string, sortValues []any) error
	Close() error
}

// ElasticsearchClient is the checkpoint subset needed from Elasticsearch.
type ElasticsearchClient interface {
	GetDocument(index string, id string) (map[string]any, int, error)
	IndexDocument(index string, id string, document map[string]any) error
}

// Key returns the backend key for a service/index pair.
func Key(service string, index string) string {
	return fmt.Sprintf("%s::%s", service, index)
}

// FileStore is the JSON file checkpoint backend.
type FileStore struct {
	path string
	mu   sync.Mutex
}

// NewFileStore creates the file-backed checkpoint store.
func NewFileStore(path string) *FileStore {
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	return &FileStore{path: path}
}

// Get returns the saved sort array when present.
func (s *FileStore) Get(service string, index string) ([]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state := s.read()
	value, ok := state[Key(service, index)].([]any)
	if !ok {
		return nil, nil
	}
	return value, nil
}

// Set saves the sort array for a service/index pair.
func (s *FileStore) Set(service string, index string, sortValues []any) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	state := s.read()
	state[Key(service, index)] = sortValues
	payload, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.path, payload, 0o644)
}

// Close releases backend resources.
func (s *FileStore) Close() error {
	return nil
}

func (s *FileStore) read() map[string]any {
	content, err := os.ReadFile(s.path)
	if err != nil {
		return map[string]any{}
	}
	var state map[string]any
	if err := json.Unmarshal(content, &state); err != nil || state == nil {
		return map[string]any{}
	}
	return state
}

// ElasticsearchStore persists checkpoints in Elasticsearch documents.
type ElasticsearchStore struct {
	client    ElasticsearchClient
	indexName string
	logger    logging.Logger
}

// NewElasticsearchStore creates the Elasticsearch-backed store.
func NewElasticsearchStore(client ElasticsearchClient, indexName string) *ElasticsearchStore {
	return &ElasticsearchStore{
		client:    client,
		indexName: indexName,
		logger:    logging.GetLogger("ElasticsearchCheckpointStore"),
	}
}

// Get returns the saved sort array from Elasticsearch.
func (s *ElasticsearchStore) Get(service string, index string) ([]any, error) {
	response, status, err := s.client.GetDocument(s.indexName, Key(service, index))
	if err != nil {
		if status == 404 {
			return nil, nil
		}
		s.logger.Exception(
			"Failed reading checkpoint from Elasticsearch",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("checkpoint_index", s.indexName),
		)
		return nil, err
	}

	source, _ := response["_source"].(map[string]any)
	if encoded, ok := source["sort_values_json"].(string); ok {
		var payload any
		if err := json.Unmarshal([]byte(encoded), &payload); err != nil {
			s.logger.Warning(
				"Invalid sort_values_json payload in checkpoint document",
				logging.F("service", service),
				logging.F("source_index", index),
				logging.F("checkpoint_index", s.indexName),
			)
			return nil, nil
		}
		if values, ok := payload.([]any); ok {
			return values, nil
		}
	}

	values, _ := source["sort_values"].([]any)
	return values, nil
}

// Set writes the checkpoint document to Elasticsearch.
func (s *ElasticsearchStore) Set(service string, index string, sortValues []any) error {
	encoded, err := json.Marshal(sortValues)
	if err != nil {
		return err
	}
	document := map[string]any{
		"service":          service,
		"source_index":     index,
		"sort_values_json": string(encoded),
		"updated_at":       util.FormatUTCISO(time.Now().UTC()),
	}
	if err := s.client.IndexDocument(s.indexName, Key(service, index), document); err != nil {
		s.logger.Exception(
			"Failed writing checkpoint to Elasticsearch",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("checkpoint_index", s.indexName),
		)
		return err
	}
	return nil
}

// Close releases backend resources.
func (s *ElasticsearchStore) Close() error {
	return nil
}

// RedisStore persists checkpoints in Redis key/value records.
type RedisStore struct {
	client *redis.Client
	prefix string
	logger logging.Logger
}

// NewRedisStore creates the Redis-backed checkpoint store.
func NewRedisStore(redisURL string, prefix string) (*RedisStore, error) {
	options, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, err
	}
	return &RedisStore{
		client: redis.NewClient(options),
		prefix: prefix,
		logger: logging.GetLogger("RedisCheckpointStore"),
	}, nil
}

// Get returns the saved sort array from Redis.
func (s *RedisStore) Get(service string, index string) ([]any, error) {
	ctx := context.Background()
	key := s.prefix + Key(service, index)
	raw, err := s.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		s.logger.Exception(
			"Failed reading checkpoint from Redis",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("redis_key", key),
		)
		return nil, err
	}
	var payload any
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		return nil, err
	}
	values, _ := payload.([]any)
	return values, nil
}

// Set writes the sort array to Redis.
func (s *RedisStore) Set(service string, index string, sortValues []any) error {
	ctx := context.Background()
	key := s.prefix + Key(service, index)
	payload, err := json.Marshal(sortValues)
	if err != nil {
		return err
	}
	if err := s.client.Set(ctx, key, string(payload), 0).Err(); err != nil {
		s.logger.Exception(
			"Failed writing checkpoint to Redis",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("redis_key", key),
		)
		return err
	}
	return nil
}

// Close releases backend resources.
func (s *RedisStore) Close() error {
	return s.client.Close()
}

// PostgresStore persists checkpoints in PostgreSQL rows.
type PostgresStore struct {
	pool   *pgxpool.Pool
	table  string
	logger logging.Logger
}

// NewPostgresStore creates the Postgres-backed checkpoint store.
func NewPostgresStore(dsn string, table string) (*PostgresStore, error) {
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		return nil, err
	}
	store := &PostgresStore{
		pool:   pool,
		table:  table,
		logger: logging.GetLogger("PostgresCheckpointStore"),
	}
	if err := store.ensureTable(); err != nil {
		pool.Close()
		return nil, err
	}
	return store, nil
}

func (s *PostgresStore) ensureTable() error {
	query := fmt.Sprintf(`
		CREATE TABLE IF NOT EXISTS %s (
			ckey TEXT PRIMARY KEY,
			sort_values JSONB NOT NULL,
			updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
		)
	`, s.table)
	_, err := s.pool.Exec(context.Background(), query)
	return err
}

// Get returns the saved sort array from Postgres.
func (s *PostgresStore) Get(service string, index string) ([]any, error) {
	query := fmt.Sprintf("SELECT sort_values FROM %s WHERE ckey = $1", s.table)
	var raw []byte
	err := s.pool.QueryRow(context.Background(), query, Key(service, index)).Scan(&raw)
	if err != nil {
		if strings.Contains(err.Error(), "no rows") {
			return nil, nil
		}
		s.logger.Exception(
			"Failed reading checkpoint from Postgres",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("table", s.table),
		)
		return nil, err
	}
	var payload any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, err
	}
	values, _ := payload.([]any)
	return values, nil
}

// Set writes the sort array to Postgres.
func (s *PostgresStore) Set(service string, index string, sortValues []any) error {
	payload, err := json.Marshal(sortValues)
	if err != nil {
		return err
	}
	query := fmt.Sprintf(`
		INSERT INTO %s (ckey, sort_values, updated_at)
		VALUES ($1, $2::jsonb, NOW())
		ON CONFLICT (ckey)
		DO UPDATE SET sort_values = EXCLUDED.sort_values, updated_at = NOW()
	`, s.table)
	_, err = s.pool.Exec(context.Background(), query, Key(service, index), string(payload))
	if err != nil {
		s.logger.Exception(
			"Failed writing checkpoint to Postgres",
			err,
			logging.F("service", service),
			logging.F("source_index", index),
			logging.F("table", s.table),
		)
		return err
	}
	return nil
}

// Close releases backend resources.
func (s *PostgresStore) Close() error {
	s.pool.Close()
	return nil
}

// CreateStore builds the configured checkpoint backend.
func CreateStore(cfg config.CheckpointConfig, esClient ElasticsearchClient) (Store, error) {
	switch provider := strings.ToLower(strings.TrimSpace(cfg.Provider)); provider {
	case "file":
		return NewFileStore(cfg.Path), nil
	case "elasticsearch":
		if esClient == nil {
			return nil, fmt.Errorf("Elasticsearch checkpoint backend requires Elasticsearch client")
		}
		return NewElasticsearchStore(esClient, cfg.ElasticsearchIndex), nil
	case "redis":
		if cfg.RedisURL == nil {
			return nil, fmt.Errorf("Redis checkpoint backend requires checkpoints.redis_url")
		}
		return NewRedisStore(*cfg.RedisURL, cfg.RedisPrefix)
	case "postgres":
		if cfg.PostgresDSN == nil {
			return nil, fmt.Errorf("Postgres checkpoint backend requires checkpoints.postgres_dsn")
		}
		return NewPostgresStore(*cfg.PostgresDSN, cfg.PostgresTable)
	default:
		return nil, fmt.Errorf("Unsupported checkpoint provider: %s", cfg.Provider)
	}
}
