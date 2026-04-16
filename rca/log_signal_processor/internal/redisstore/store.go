// Package redisstore provides Redis-based persistence for organization-scoped signal logs
// using hash-based storage with retention and deduplication handled by collector.
package redisstore

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strings"

	goredis "github.com/redis/go-redis/v9"

	"log_signal_processor/internal/config"
	"log_signal_processor/internal/model"
)

// Client wraps the go-redis client with lifecycle management.
//
// Lifecycle:
//   - Created via NewClient with config
//   - Used to create Store and Locker instances
//   - Closed via Close() when shutting down
//
// Thread Safety:
//   - Safe for concurrent use (go-redis client is thread-safe)
//
// Connection Details:
//   - Authentication: Username/Password (Redis 6+) or Password only
//   - Database: Numbered 0-15 (default 0)
//   - Timeouts: Separate dial, read, write timeouts
type Client struct {
	raw *goredis.Client
}

// NewClient creates a Redis client from configuration.
//
// Connection Configuration:
//   - Address: host:port format (e.g., "localhost:6379")
//   - Username: Redis 6+ ACL username (optional)
//   - Password: Auth password (required if auth enabled)
//   - DB: Database number (0-15)
//   - DialTimeout: Connection establishment timeout
//     -ReadTimeout: Read operation timeout
//   - WriteTimeout: Write operation timeout
//
// Parameters:
//   - cfg: RedisConfig with connection parameters
//
// Returns:
//   - *Client: Client wrapper (connection not established until first use)
//
// Note:
//   - go-redis uses lazy connection (first operation may fail if unreachable)
//   - Use PING in startup checks to detect connection issues early
//
// Example:
//
//	cfg := config.RedisConfig{
//	    Address: "localhost:6379",
//	    Password: os.Getenv("REDIS_PASSWORD"),
//	    DialTimeout: 5 * time.Second,
//	    ReadTimeout: 3 * time.Second,
//	    WriteTimeout: 3 * time.Second,
//	}
//	client := NewClient(cfg)
//	defer client.Close()
func NewClient(cfg config.RedisConfig) *Client {
	return &Client{
		raw: goredis.NewClient(&goredis.Options{
			Addr:         cfg.Address,
			Username:     cfg.Username,
			Password:     cfg.Password,
			DB:           cfg.DB,
			DialTimeout:  cfg.DialTimeout,
			ReadTimeout:  cfg.ReadTimeout,
			WriteTimeout: cfg.WriteTimeout,
		}),
	}
}

// Raw exposes the underlying go-redis client for specialized helpers.
//
// Use Case:
//   - Creating Locker with NewLockBackend
//   - Custom Redis operations not exposed by wrapper
//
// Returns:
//   - *goredis.Client: Underlying client (rarely needed)
func (c *Client) Raw() *goredis.Client {
	return c.raw
}

// Close closes the underlying Redis connection.
//
// Behavior:
//   - Idempotent: Safe to call multiple times
//   - Graceful: Waits for pending operations
//   - After close: Client cannot be reused
//
// Returns:
//   - error: Connection close error (rare)
func (c *Client) Close() error {
	if c.raw == nil {
		return nil
	}
	return c.raw.Close()
}

// Store persists and retrieves organization-scoped signal logs from Redis using hash structures.
//
// Storage Model:
//   - Type: Redis HASH
//   - Key: "{KeyPrefix}:{organization}" (e.g., "Rca:acme")
//   - Field: Single field containing JSON array (HashField from config)
//   - Value: JSON array of SignalLog structs (marshaled/unmarshaled by Store)
//
// Organization Scoping:
//   - Each organization has separate Redis key
//   - Data isolated per organization
//   - Concurrent operations on different orgs: fully parallel
//
// Reserved Keys:
//   - Can exclude certain keys from organization enumeration
//   - Typically exclude lock key (e.g., "Rca:collector_lock")
//   - Prevents lock from appearing as data organization
//
// Logging:
//   - Adds component tag to all log messages
//   - Operation errors already context-wrapped
//
// Thread Safety:
//   - Safe for concurrent use (delegated to go-redis client)
type Store struct {
	client       goredis.UniversalClient
	keyPrefix    string
	hashField    string
	orgIndexKey  string
	logger       *slog.Logger
	reservedKeys map[string]struct{}
}

const activeIncidentHashField = "active_incidents"

// NewStore creates a Redis-backed store for organization signal logs.
//
// Parameters:
//   - client: Redis client (UniversalClient works with both Standalone and Cluster)
//   - cfg: RedisConfig with KeyPrefix and HashField
//   - logger: slog.Logger for operational logging
//   - reservedKeys: Keys to exclude from ListOrganizations (e.g., lock key)
//
// Returns:
//   - *Store: Ready-to-use store
//
// Key Normalization:
//   - KeyPrefix: Trailing colon automatically removed if present
//   - Reserved keys: Whitespace trimmed, empty values ignored
//
// Example:
//
//	store := NewStore(
//	    redisClient,
//	    config.RedisConfig{
//	        KeyPrefix: "Rca",
//	        HashField: "signaled_logs",
//	    },
//	    logger,
//	    "Rca:collector_lock",  // Exclude lock from org list
//	)
func NewStore(client goredis.UniversalClient, cfg config.RedisConfig, logger *slog.Logger, reservedKeys ...string) *Store {
	keyPrefix := strings.TrimSuffix(cfg.KeyPrefix, ":")
	keySet := make(map[string]struct{}, len(reservedKeys))
	for _, key := range reservedKeys {
		trimmed := strings.TrimSpace(key)
		if trimmed != "" {
			keySet[trimmed] = struct{}{}
		}
	}

	return &Store{
		client:       client,
		keyPrefix:    keyPrefix,
		hashField:    cfg.HashField,
		orgIndexKey:  fmt.Sprintf("%s:organizations", keyPrefix),
		logger:       logger.With("component", "redis_store"),
		reservedKeys: keySet,
	}
}

// OrganizationKey returns the Redis HASH key for one organization's signal logs.
//
// Key Format:
//   - Pattern: "{KeyPrefix}:{organization}"
//   - Example: "Rca:acme", "Rca:wile"
//
// Parameters:
//   - organization: Organization identifier (e.g., "acme")
//
// Returns:
//   - string: Redis key for this organization's hash
func (s *Store) OrganizationKey(organization string) string {
	return fmt.Sprintf("%s:%s", s.keyPrefix, organization)
}

// ListOrganizations scans Redis for all organization keys managed by signal collector.
// Uses cursor-based scanning to handle large key spaces efficiently.
//
// Scan Process:
//  1. Use SCAN with pattern "{KeyPrefix}:*" to iterate all keys
//  2. Filter out reserved keys (e.g., lock key)
//  3. Validate each key has the hash field (excludes non-data keys)
//  4. Extract organization name from key suffix
//  5. Deduplicate and accumulate results
//  6. Continue until cursor returns to 0
//
// Validation:
//   - WRONGTYPE errors ignored (key is not a hash, skip)
//   - HExists check ensures field is actually stored (not just key exists)
//   - Empty organization names excluded
//
// Performance:
//   - Cursor-based pagination: Non-blocking at Redis server
//   - Scan count 100: Balance between requests and batch size
//   - Typically scans entire keyspace in 1-2 round trips
//
// Parameters:
//   - ctx: Context with deadline for scan operations
//
// Returns:
//   - []string: Organization identifiers from Redis keys (order not guaranteed)
//   - error: Connection, scan, or HExists errors
//
// Errors Returned:
//   - "scan redis keys: ..." - SCAN command failed
//   - "check redis hash field for {key}: ..." - HExists failed
//
// Edge Cases:
//   - No organizations: Returns empty slice []string{} (not nil)
//   - Reserved keys: Silently skipped even if they have data
//   - Wrong type keys: Silently skipped (WRONGTYPE handled)
//   - Empty organization names: Silently skipped
//
// Example:
//
//	orgs, err := store.ListOrganizations(ctx)
//	for _, org := range orgs {
//	    logs, err := store.LoadLogs(ctx, org)
//	}
func (s *Store) ListOrganizations(ctx context.Context) ([]string, error) {
	return s.scanOrganizations(ctx)
}

func (s *Store) scanOrganizations(ctx context.Context) ([]string, error) {
	s.cleanupLegacyOrganizationIndex(ctx)

	var cursor uint64
	pattern := s.keyPrefix + ":*"
	organizations := make([]string, 0)
	seen := make(map[string]struct{})

	for {
		keys, nextCursor, err := s.client.Scan(ctx, cursor, pattern, 100).Result()
		if err != nil {
			return nil, fmt.Errorf("scan redis keys: %w", err)
		}

		for _, key := range keys {
			if _, reserved := s.reservedKeys[key]; reserved {
				continue
			}
			exists, err := s.client.HExists(ctx, key, s.hashField).Result()
			if err != nil {
				if strings.Contains(err.Error(), "WRONGTYPE") {
					continue
				}
				return nil, fmt.Errorf("check redis hash field for %s: %w", key, err)
			}
			if !exists {
				continue
			}

			org := strings.TrimPrefix(key, s.keyPrefix+":")
			if org == "" {
				continue
			}
			if _, ok := seen[org]; ok {
				continue
			}
			seen[org] = struct{}{}
			organizations = append(organizations, org)
		}

		cursor = nextCursor
		if cursor == 0 {
			return organizations, nil
		}
	}
}

func (s *Store) cleanupLegacyOrganizationIndex(ctx context.Context) {
	if strings.TrimSpace(s.orgIndexKey) == "" {
		return
	}
	if err := s.client.Del(ctx, s.orgIndexKey).Err(); err != nil && !errors.Is(err, goredis.Nil) && s.logger != nil {
		s.logger.Warn(
			"failed to remove legacy redis organization index",
			"key", s.orgIndexKey,
			"error", err,
		)
	}
}

// LoadLogs loads one organization's signal log JSON array from Redis.
//
// Loading Process:
//  1. Execute HGet to retrieve hash field value
//  2. If key/field not found: Return empty slice (not error)
//  3. If found: Unmarshal JSON array of SignalLog structs
//
// Storage Format:
//   - Type: Redis HASH field value (string containing JSON)
//   - Encoding: UTF-8 JSON with SignalLog struct marshaling
//   - Structure: ["JSON stringified SignalLog", ...]
//
// Parameters:
//   - ctx: Context with deadline
//   - organization: Organization identifier
//
// Returns:
//   - []model.SignalLog: Signal logs for this organization (empty slice if not found)
//   - error: Connection, JSON parse, or other Redis errors
//
// Errors Returned:
//   - No error if key/field doesn't exist (returns []model.SignalLog{})
//   - "read redis hash for organization {org}: ..." - HGet failed
//   - "decode redis payload for organization {org}: ..." - JSON unmarshal failed
//
// Edge Cases:
//   - Missing key: Returns ([]model.SignalLog{}, nil) - not found treated as empty
//   - Empty JSON array "[]": Returns []model.SignalLog{} (zero-length slice)
//   - Malformed JSON: Returns error with organization context
//
// Example:
//
//	logs, err := store.LoadLogs(ctx, "acme")
//	if err != nil { return err }
//	log.Info("loaded organization signals", "organization", "acme", "count", len(logs))
func (s *Store) LoadLogs(ctx context.Context, organization string) ([]model.SignalLog, error) {
	payload, err := s.client.HGet(ctx, s.OrganizationKey(organization), s.hashField).Result()
	if errors.Is(err, goredis.Nil) {
		return []model.SignalLog{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read redis hash for organization %s: %w", organization, err)
	}

	var logs []model.SignalLog
	if err := json.Unmarshal([]byte(payload), &logs); err != nil {
		return nil, fmt.Errorf("decode redis payload for organization %s: %w", organization, err)
	}
	return logs, nil
}

// SaveLogs writes one organization's complete signal log list to Redis, overwriting previous data.
//
// Save Process:
//  1. Marshal SignalLog array to JSON string
//  2. Execute HSet to update hash field with JSON payload
//  3. Overwrites previous value (no merge, append, or update logic)
//
// Atomicity:
//   - HSet is atomic: Either fully succeeds or fully fails
//   - If already exists: Overwrites with new value
//   - No RDB or multi-step transactions needed
//
// Performance:
//   - Single Redis command: O(N) where N = size of marshaled JSON
//   - JSON marshaling done client-side (CPU bound)
//   - Network: Single round trip
//
// Parameters:
//   - ctx: Context with deadline
//   - organization: Organization identifier
//   - logs: Complete signal log list (merged/deduplicated by collector)
//
// Returns:
//   - error: Connection, JSON marshal, or HSet errors
//
// Errors Returned:
//   - "marshal redis payload for organization {org}: ..." - json.Marshal failed (rare)
//   - "write redis hash for organization {org}: ..." - HSet failed
//
// Data Loss Prevention:
//   - Collector already merges with existing before calling SaveLogs
//   - No need for read-modify-write pattern at storage layer
//   - Always safe to overwrite (collector handles merge logic)
//
// Example:
//
//	merged := service.MergeLogs(existing, incoming, cutoff)
//	if err := store.SaveLogs(ctx, "acme", merged); err != nil {
//	    return fmt.Errorf("save logs: %w", err)
//	}
func (s *Store) SaveLogs(ctx context.Context, organization string, logs []model.SignalLog) error {
	payload, err := json.Marshal(logs)
	if err != nil {
		return fmt.Errorf("marshal redis payload for organization %s: %w", organization, err)
	}
	if err := s.client.HSet(ctx, s.OrganizationKey(organization), s.hashField, payload).Err(); err != nil {
		return fmt.Errorf("write redis hash for organization %s: %w", organization, err)
	}
	return nil
}

// DeleteLogs removes an organization's key entirely when retention trimming results in empty logs.
// Used when merge → retention filtering produces zero logs (safe to delete).
//
// Deletion Rationale:
//   - No data left after retention cutoff: Delete key to free space
//   - Collector handles check: Only calls DeleteLogs if merged result empty
//   - Storage cleanup: Keeps Redis free of stale organization keys
//
// Parameters:
//   - ctx: Context with deadline
//   - organization: Organization identifier
//
// Returns:
//   - error: Connection or DEL command errors
//
// Errors Returned:
//   - "delete redis key for organization {org}: ..." - DEL failed
//
// No-op Behavior:
//   - DEL on non-existent key: Returns success (DEL always succeeds)
//   - Safe to call even if already deleted
//
// Typical Flow:
//
//	merged := service.MergeLogs(existing, incoming, cutoff)
//	if len(merged) == 0 {
//	    err := store.DeleteLogs(ctx, organization)  // ← called here
//	} else {
//	    err := store.SaveLogs(ctx, organization, merged)
//	}
func (s *Store) DeleteLogs(ctx context.Context, organization string) error {
	orgKey := s.OrganizationKey(organization)
	if err := s.client.HDel(ctx, orgKey, s.hashField).Err(); err != nil {
		return fmt.Errorf("delete redis hash field for organization %s: %w", organization, err)
	}
	if err := s.cleanupOrganizationHashIfEmpty(ctx, orgKey); err != nil {
		return fmt.Errorf("cleanup redis key for organization %s: %w", organization, err)
	}
	return nil
}

func (s *Store) cleanupOrganizationHashIfEmpty(ctx context.Context, organizationKey string) error {
	fieldCount, err := s.client.HLen(ctx, organizationKey).Result()
	if err != nil {
		if strings.Contains(strings.ToUpper(err.Error()), "WRONGTYPE") || errors.Is(err, goredis.Nil) {
			return nil
		}
		return err
	}
	if fieldCount == 0 {
		if err := s.client.Del(ctx, organizationKey).Err(); err != nil {
			return err
		}
	}
	return nil
}

func compactStrings(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}
