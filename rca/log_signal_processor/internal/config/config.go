// Package config provides configuration loading and validation for the signaled logs collector.
// Configuration can be provided via YAML/JSON files or environment variable overrides.
// All configuration is validated before use to ensure safe production operation.
package config

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const (
	docIDSourceDocumentID = "_id"   // Use Elasticsearch document _id as docID
	docIDSourceField      = "field" // Extract docID from specific Elasticsearch field
)

// LoggingConfig controls application log output level and format.
//
// Supported Levels:
//   - "debug" - Detailed diagnostic information
//   - "info" - General informational messages
//   - "warn" / "warning" - Warning-level messages
//   - "error" - Error-level messages
//
// Supported Formats:
//   - "json" - JSON structured logging (recommended for production)
//   - "text" - Human-readable text format
//
// Environment Overrides:
//   - SLP_LOG_LEVEL
//   - SLP_LOG_FORMAT
type LoggingConfig struct {
	Level  string `yaml:"level"`  // Log level threshold
	Format string `yaml:"format"` // Output format (json or text)
}

// SchedulerConfig controls how often the collector runs and operational timeouts.
//
// Fields:
//   - Interval: Time between collection cycles (default: 1 minute)
//   - RunTimeout: Maximum time allowed for single cycle (default: 50 seconds)
//
// The RunTimeout must be less than Interval to allow time between cycles.
// Lock TTL must be >= RunTimeout for proper distributed lock operation.
//
// Environment Overrides:
//   - SLP_SCHEDULER_INTERVAL
//   - SLP_SCHEDULER_RUN_TIMEOUT
type SchedulerConfig struct {
	Interval            time.Duration `yaml:"interval"`             // Cycle frequency
	RunTimeout          time.Duration `yaml:"run_timeout"`          // Max time per cycle
	OrganizationWorkers int           `yaml:"organization_workers"` // Parallel org persistence workers
}

// ElasticsearchConfig stores connection settings, query configuration, and search behavior.
//
// Connection:
//   - Addresses: List of Elasticsearch node URLs
//   - Username/Password: Basic auth (optional)
//   - APIKey: API key auth (optional, preferred over password)
//
// Query Execution:
//   - Index: Elasticsearch index pattern to search
//   - Window: Time window for searching (default: 10 minutes)
//   - PageSize: Documents per request (default: 500)
//   - MaxPages: Maximum pages to fetch (0 = unlimited)
//   - RequestTimeout: Client request timeout (default: 15s)
//   - QueryTimeout: ES query timeout (default: 10s)
//
// Point in Time (PIT):
//   - UsePointInTime: Enable PIT for stable pagination (default: true)
//   - PITKeepAlive: PIT context timeout (default: 2 minutes)
//
// ExtraFilters: Additional Elasticsearch query filters (array of objects)
//
// Environment Overrides:
//   - SLP_ELASTICSEARCH_ADDRESSES (comma/semicolon separated)
//   - SLP_ELASTICSEARCH_USERNAME
//   - SLP_ELASTICSEARCH_PASSWORD
//   - SLP_ELASTICSEARCH_API_KEY
//   - SLP_ELASTICSEARCH_INDEX
//   - SLP_ELASTICSEARCH_PAGE_SIZE
//   - SLP_ELASTICSEARCH_MAX_PAGES
//   - SLP_ELASTICSEARCH_REQUEST_TIMEOUT
//   - SLP_ELASTICSEARCH_QUERY_TIMEOUT
//   - SLP_ELASTICSEARCH_WINDOW
//   - SLP_ELASTICSEARCH_USE_POINT_IN_TIME
//   - SLP_ELASTICSEARCH_PIT_KEEP_ALIVE
type ElasticsearchConfig struct {
	Addresses      []string         `yaml:"addresses"`         // ES node URLs
	Username       string           `yaml:"username"`          // Auth username
	Password       string           `yaml:"password"`          // Auth password
	APIKey         string           `yaml:"api_key"`           //  API key auth
	Index          string           `yaml:"index"`             // Index pattern
	PageSize       int              `yaml:"page_size"`         // Results per page
	MaxPages       int              `yaml:"max_pages"`         // Max pages to fetch
	RequestTimeout time.Duration    `yaml:"request_timeout"`   // Request timeout
	QueryTimeout   time.Duration    `yaml:"query_timeout"`     // Query timeout
	Window         time.Duration    `yaml:"window"`            // Query time window
	UsePointInTime bool             `yaml:"use_point_in_time"` // Enable PIT
	PITKeepAlive   time.Duration    `yaml:"pit_keep_alive"`    // PIT context TTL
	ExtraFilters   []map[string]any `yaml:"extra_filters"`     // Additional filters
}

// RedisConfig stores Redis connection and storage settings.
//
// Connection:
//   - Address: Redis server address (host:port)
//   - Username/Password: Redis auth (optional)
//   - DB: Database number (0-15)
//   - Dial/Read/Write Timeouts: Operation timeouts
//
// Storage:
//   - KeyPrefix: Prefix for all Redis keys (default: "Rca")
//   - HashField: Hash field containing signal logs (default: "signaled_logs")
//   - RetentionWindow: Time to keep signals (default: 30 minutes)
//
// Storage Key Format: "{KeyPrefix}:{organization}"
// Storage Type: Redis HASH with single field containing JSON array
//
// Environment Overrides:
//   - SLP_REDIS_ADDRESS
//   - SLP_REDIS_USERNAME
//   - SLP_REDIS_PASSWORD
//   - SLP_REDIS_DB
//   - SLP_REDIS_DIAL_TIMEOUT
//   - SLP_REDIS_READ_TIMEOUT
//   - SLP_REDIS_WRITE_TIMEOUT
//   - SLP_REDIS_KEY_PREFIX
//   - SLP_REDIS_HASH_FIELD
//   - SLP_REDIS_RETENTION_WINDOW
type RedisConfig struct {
	Address         string        `yaml:"address"`          // Server address
	Username        string        `yaml:"username"`         // Auth username
	Password        string        `yaml:"password"`         // Auth password
	DB              int           `yaml:"db"`               // Database number
	DialTimeout     time.Duration `yaml:"dial_timeout"`     // Dial timeout
	ReadTimeout     time.Duration `yaml:"read_timeout"`     // Read timeout
	WriteTimeout    time.Duration `yaml:"write_timeout"`    // Write timeout
	KeyPrefix       string        `yaml:"key_prefix"`       // Redis key prefix
	HashField       string        `yaml:"hash_field"`       // Hash field name
	RetentionWindow time.Duration `yaml:"retention_window"` // Signal retention
}

// LockConfig stores distributed lock settings for multi-worker deployments.
//
// Distributed Locking:
//   - Enabled: Whether to use locking (default: true)
//   - Key: Redis key for lock (auto-generated if empty)
//   - ShardCount: Number of shard locks for parallel PM2 processing (default: 1)
//   - TTL: Lock lease duration (default: 90 seconds)
//   - AcquireTimeout: Max time to acquire lock (default: 2 seconds)
//
// When ShardCount is 1, the lock ensures only one worker runs collection per cycle.
// When ShardCount is greater than 1, PM2 workers can own different shard locks and
// process disjoint organization subsets in parallel.
// TTL should be > RunTimeout and SafetyMargin to prevent premature lock expiry.
//
// Environment Overrides:
//   - SLP_LOCK_ENABLED
//   - SLP_LOCK_KEY
//   - SLP_LOCK_SHARD_COUNT
//   - SLP_LOCK_TTL
//   - SLP_LOCK_ACQUIRE_TIMEOUT
type LockConfig struct {
	Enabled        bool          `yaml:"enabled"`         // Enable locking
	Key            string        `yaml:"key"`             // Lock key
	ShardCount     int           `yaml:"shard_count"`     // Number of shard locks
	TTL            time.Duration `yaml:"ttl"`             // Lease duration
	AcquireTimeout time.Duration `yaml:"acquire_timeout"` // Acquire timeout
}

// FieldMappings describes where collector reads data from Elasticsearch documents.
//
// Document Fields:
//   - OrganizationField: Field containing organization ID (default: event.organization)
//   - SignalField: Field containing signal type (default: signal)
//   - LogLevelField: Field containing log level (default: log_level)
//   - TimestampField: Field containing log timestamp (default: @timestamp)
//
// DocID Source:
//   - DocIDSource: Where to get document ID (_id or field)
//   - DocIDField: Field name if DocIDSource=field (not needed if _id)
//
// Environment Overrides:
//   - SLP_MAPPING_ORGANIZATION_FIELD
//   - SLP_MAPPING_SIGNAL_FIELD
//   - SLP_MAPPING_LOG_LEVEL_FIELD
//   - SLP_MAPPING_TIMESTAMP_FIELD
//   - SLP_MAPPING_DOC_ID_SOURCE
//   - SLP_MAPPING_DOC_ID_FIELD
type FieldMappings struct {
	OrganizationField string `yaml:"organization_field"` // Organization field
	SignalField       string `yaml:"signal_field"`       // Signal field
	LogLevelField     string `yaml:"log_level_field"`    // Log level field
	TimestampField    string `yaml:"timestamp_field"`    // Timestamp field
	DocIDSource       string `yaml:"doc_id_source"`      // DocID source (_id or field)
	DocIDField        string `yaml:"doc_id_field"`       // DocID field (if source=field)
}

// PM2Config stores PM2-friendly metadata used for documentation and defaults.
//
// Fields:
//   - AppName: Application name for PM2 ecosystem (default: signaled-logs-collector)
//   - Instances: Number of PM2 instances to run (default: 2)
//
// Environment Overrides:
//   - SLP_PM2_APP_NAME
//   - SLP_PM2_INSTANCES
type PM2Config struct {
	AppName   string `yaml:"app_name"`  // App name for PM2
	Instances int    `yaml:"instances"` // Number of instances
}

// Config is the root application configuration combining all subsystems.
//
// All fields are validated before use via the Validate() method.
// Configuration can be overridden by environment variables (SLP_* prefix).
type Config struct {
	ServiceName   string              `yaml:"service_name"`  // Service identifier
	Logging       LoggingConfig       `yaml:"logging"`       // Logging config
	Scheduler     SchedulerConfig     `yaml:"scheduler"`     // Scheduler config
	Elasticsearch ElasticsearchConfig `yaml:"elasticsearch"` // Elasticsearch config
	Redis         RedisConfig         `yaml:"redis"`         // Redis config
	Lock          LockConfig          `yaml:"lock"`          // Distributed lock config
	Mappings      FieldMappings       `yaml:"mappings"`      // Field mappings
	PM2           PM2Config           `yaml:"pm2"`           // PM2 metadata
}

// Load reads configuration from file, applies environment overrides, and validates.
// If no path is provided, uses compiled defaults with environment overrides.
//
// Configuration Loading Sequence:
//  1. Start with compiled defaults
//  2. Overlay values from YAML file (if provided)
//  3. Apply environment variable overrides
//  4. Normalize string fields (trim whitespace, standardize formats)
//  5. Validate all values for production safety
//
// Parameters:
//   - path: File path to configuration (empty string for defaults only)
//
// Returns:
//   - Config: Validated configuration ready for use
//   - error: File I/O, YAML parsing, or validation error
//
// Errors:
//   - File not found: Configuration file doesn't exist
//   - YAML syntax: Invalid YAML structure
//   - Validation failure: Configuration values invalid for production
//
// Example:
//
//	cfg, err := Load("config.yml")
func Load(path string) (Config, error) {
	cfg := defaultConfig()
	if path != "" {
		contents, err := os.ReadFile(filepath.Clean(path))
		if err != nil {
			return Config{}, fmt.Errorf("read config file: %w", err)
		}
		if err := yaml.Unmarshal(contents, &cfg); err != nil {
			return Config{}, fmt.Errorf("parse config file: %w", err)
		}
	}

	applyEnvOverrides(&cfg)
	cfg.normalize()
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

// defaultConfig returns well-tested defaults suitable for production.
// These defaults can be overridden via YAML file or environment variables.
//
// Default Behaviors:
//   - Runs every 1 minute with 50-second cycles
//   - Uses Point-in-Time Elasticsearch searches for stable pagination
//   - Stores signals in Redis with 30-minute retention
//   - Enables distributed locking for multi-worker safety
//   - Uses JSON structured logging at INFO level
//
// Returns:
//   - Config: Fully populated default configuration
func defaultConfig() Config {
	return Config{
		ServiceName: "signaled-logs-collector",
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
		Scheduler: SchedulerConfig{
			Interval:            time.Minute,
			RunTimeout:          50 * time.Second,
			OrganizationWorkers: 4,
		},
		Elasticsearch: ElasticsearchConfig{
			PageSize:       500,
			MaxPages:       0,
			RequestTimeout: 15 * time.Second,
			QueryTimeout:   10 * time.Second,
			Window:         10 * time.Minute,
			UsePointInTime: true,
			PITKeepAlive:   2 * time.Minute,
			ExtraFilters:   []map[string]any{},
		},
		Redis: RedisConfig{
			DB:              0,
			DialTimeout:     5 * time.Second,
			ReadTimeout:     3 * time.Second,
			WriteTimeout:    3 * time.Second,
			KeyPrefix:       "Rca",
			HashField:       "signaled_logs",
			RetentionWindow: 30 * time.Minute,
		},
		Lock: LockConfig{
			Enabled:        true,
			ShardCount:     1,
			TTL:            90 * time.Second,
			AcquireTimeout: 2 * time.Second,
		},
		Mappings: FieldMappings{
			OrganizationField: "event.organization",
			SignalField:       "signal",
			LogLevelField:     "log_level",
			TimestampField:    "@timestamp",
			DocIDSource:       docIDSourceDocumentID,
		},
		PM2: PM2Config{
			AppName:   "signaled-logs-collector",
			Instances: 2,
		},
	}
}

// normalize applies transformations to configuration values for consistency.
// Trims whitespace and StandardIZES formats (lowercase, removes trailing colons).
//
// Operations:
//   - String fields: Trim whitespace
//   - Redis key prefix: Remove trailing colon if present
//   - Elasticsearch addresses: Trim whitespace from each
//   - Lock key: Auto-generate from KeyPrefix if empty
//
// Called automatically by Load() before validation.
func (c *Config) normalize() {
	c.ServiceName = strings.TrimSpace(c.ServiceName)
	c.Logging.Level = strings.TrimSpace(c.Logging.Level)
	c.Logging.Format = strings.ToLower(strings.TrimSpace(c.Logging.Format))
	c.Redis.KeyPrefix = strings.TrimSuffix(strings.TrimSpace(c.Redis.KeyPrefix), ":")
	c.Redis.HashField = strings.TrimSpace(c.Redis.HashField)
	c.Mappings.OrganizationField = strings.TrimSpace(c.Mappings.OrganizationField)
	c.Mappings.SignalField = strings.TrimSpace(c.Mappings.SignalField)
	c.Mappings.LogLevelField = strings.TrimSpace(c.Mappings.LogLevelField)
	c.Mappings.TimestampField = strings.TrimSpace(c.Mappings.TimestampField)
	c.Mappings.DocIDSource = strings.ToLower(strings.TrimSpace(c.Mappings.DocIDSource))
	c.Mappings.DocIDField = strings.TrimSpace(c.Mappings.DocIDField)
	c.Lock.Key = strings.TrimSpace(c.Lock.Key)
	if c.Lock.Key == "" && c.Redis.KeyPrefix != "" {
		c.Lock.Key = c.Redis.KeyPrefix + ":collector_lock"
	}
	c.PM2.AppName = strings.TrimSpace(c.PM2.AppName)
	for idx := range c.Elasticsearch.Addresses {
		c.Elasticsearch.Addresses[idx] = strings.TrimSpace(c.Elasticsearch.Addresses[idx])
	}
}

// Validate comprehensively checks that configuration is valid for production operation.
// Validates all required fields, timings, timeouts, and interdependencies.
//
// Validation Checks:
//   - All service names and identifiers must not be empty
//   - Logging format must be json or text
//   - All timeouts must be positive and reasonable
//   - Elasticsearch must have addresses and valid index
//   - Redis must have valid address and configuration
//   - Distributed lock must have valid TTL if enabled
//   - Field mappings must specify required document fields
//   - Interdependency checks: TTLs > timeouts, etc.
//
// Returns:
//   - error: Description of first validation failure, or nil if valid
//
// Example errors:
//   - "service_name must not be empty"
//   - "scheduler.interval must be greater than zero"
//   - "elasticsearch.addresses must contain at least one host"
//   - "lock.ttl must be greater than or equal to scheduler.run_timeout"
func (c Config) Validate() error {
	if c.ServiceName == "" {
		return errors.New("service_name must not be empty")
	}
	if c.Logging.Format != "json" && c.Logging.Format != "text" {
		return errors.New("logging.format must be either json or text")
	}
	if c.Scheduler.Interval <= 0 {
		return errors.New("scheduler.interval must be greater than zero")
	}
	if c.Scheduler.RunTimeout <= 0 {
		return errors.New("scheduler.run_timeout must be greater than zero")
	}
	if c.Scheduler.OrganizationWorkers <= 0 {
		return errors.New("scheduler.organization_workers must be greater than zero")
	}
	if len(compactStrings(c.Elasticsearch.Addresses)) == 0 {
		return errors.New("elasticsearch.addresses must contain at least one host")
	}
	if strings.TrimSpace(c.Elasticsearch.Index) == "" {
		return errors.New("elasticsearch.index must not be empty")
	}
	if c.Elasticsearch.PageSize <= 0 {
		return errors.New("elasticsearch.page_size must be greater than zero")
	}
	if c.Elasticsearch.MaxPages < 0 {
		return errors.New("elasticsearch.max_pages must be zero or greater")
	}
	if c.Elasticsearch.RequestTimeout <= 0 {
		return errors.New("elasticsearch.request_timeout must be greater than zero")
	}
	if c.Elasticsearch.QueryTimeout <= 0 {
		return errors.New("elasticsearch.query_timeout must be greater than zero")
	}
	if c.Elasticsearch.Window <= 0 {
		return errors.New("elasticsearch.window must be greater than zero")
	}
	if c.Elasticsearch.UsePointInTime {
		if c.Elasticsearch.PITKeepAlive <= 0 {
			return errors.New("elasticsearch.pit_keep_alive must be greater than zero when use_point_in_time is enabled")
		}
		if c.Elasticsearch.PITKeepAlive < c.Elasticsearch.RequestTimeout {
			return errors.New("elasticsearch.pit_keep_alive must be greater than or equal to elasticsearch.request_timeout")
		}
	}
	if strings.TrimSpace(c.Redis.Address) == "" {
		return errors.New("redis.address must not be empty")
	}
	if c.Redis.DialTimeout <= 0 || c.Redis.ReadTimeout <= 0 || c.Redis.WriteTimeout <= 0 {
		return errors.New("redis dial/read/write timeouts must be greater than zero")
	}
	if c.Redis.KeyPrefix == "" {
		return errors.New("redis.key_prefix must not be empty")
	}
	if c.Redis.HashField == "" {
		return errors.New("redis.hash_field must not be empty")
	}
	if c.Redis.RetentionWindow <= 0 {
		return errors.New("redis.retention_window must be greater than zero")
	}
	if c.Lock.Enabled {
		if c.Lock.Key == "" {
			return errors.New("lock.key must not be empty when lock is enabled")
		}
		if c.Lock.ShardCount <= 0 {
			return errors.New("lock.shard_count must be greater than zero when lock is enabled")
		}
		if c.Lock.TTL <= 0 {
			return errors.New("lock.ttl must be greater than zero when lock is enabled")
		}
		if c.Lock.AcquireTimeout <= 0 {
			return errors.New("lock.acquire_timeout must be greater than zero when lock is enabled")
		}
		if c.Lock.TTL < c.Scheduler.RunTimeout {
			return errors.New("lock.ttl must be greater than or equal to scheduler.run_timeout")
		}
	}
	if c.Mappings.OrganizationField == "" {
		return errors.New("mappings.organization_field must not be empty")
	}
	if c.Mappings.SignalField == "" {
		return errors.New("mappings.signal_field must not be empty")
	}
	if c.Mappings.TimestampField == "" {
		return errors.New("mappings.timestamp_field must not be empty")
	}
	switch c.Mappings.DocIDSource {
	case docIDSourceDocumentID:
	case docIDSourceField:
		if c.Mappings.DocIDField == "" {
			return errors.New("mappings.doc_id_field is required when mappings.doc_id_source=field")
		}
	default:
		return errors.New("mappings.doc_id_source must be either _id or field")
	}
	if c.PM2.Instances < 1 {
		return errors.New("pm2.instances must be at least 1")
	}
	return nil
}

// applyEnvOverrides applies environment variable overrides to configuration.
// Environment variables use SLP_ prefix and override YAML file values.
//
// Environment Variable Naming:
//   - SLP_ prefix for all environment variables
//   - Convert config path to uppercase with underscores
//   - Example: elasticsearch.addresses → SLP_ELASTICSEARCH_ADDRESSES
//
// Type Conversions:
//   - String: Direct assignment (trimmed)
//   - StringSlice: Split by comma or semicolon
//   - Int: Parsed with strconv.Atoi
//   - Bool: Parsed with strconv.ParseBool
//   - Duration: Parsed with time.ParseDuration (e.g., "5m", "30s")
//
// Missing or empty environment variables are silently ignored.
//
// Logging: DEBUG level when overrides applied (via service logger)
func applyEnvOverrides(cfg *Config) {
	applyStringEnv(&cfg.ServiceName, "SLP_SERVICE_NAME")
	applyStringEnv(&cfg.Logging.Level, "SLP_LOG_LEVEL")
	applyStringEnv(&cfg.Logging.Format, "SLP_LOG_FORMAT")
	applyDurationEnv(&cfg.Scheduler.Interval, "SLP_SCHEDULER_INTERVAL")
	applyDurationEnv(&cfg.Scheduler.RunTimeout, "SLP_SCHEDULER_RUN_TIMEOUT")
	applyIntEnv(&cfg.Scheduler.OrganizationWorkers, "SLP_SCHEDULER_ORGANIZATION_WORKERS")

	applyStringSliceEnv(&cfg.Elasticsearch.Addresses, "SLP_ELASTICSEARCH_ADDRESSES")
	applyStringEnv(&cfg.Elasticsearch.Username, "SLP_ELASTICSEARCH_USERNAME")
	applyStringEnv(&cfg.Elasticsearch.Password, "SLP_ELASTICSEARCH_PASSWORD")
	applyStringEnv(&cfg.Elasticsearch.APIKey, "SLP_ELASTICSEARCH_API_KEY")
	applyStringEnv(&cfg.Elasticsearch.Index, "SLP_ELASTICSEARCH_INDEX")
	applyIntEnv(&cfg.Elasticsearch.PageSize, "SLP_ELASTICSEARCH_PAGE_SIZE")
	applyIntEnv(&cfg.Elasticsearch.MaxPages, "SLP_ELASTICSEARCH_MAX_PAGES")
	applyDurationEnv(&cfg.Elasticsearch.RequestTimeout, "SLP_ELASTICSEARCH_REQUEST_TIMEOUT")
	applyDurationEnv(&cfg.Elasticsearch.QueryTimeout, "SLP_ELASTICSEARCH_QUERY_TIMEOUT")
	applyDurationEnv(&cfg.Elasticsearch.Window, "SLP_ELASTICSEARCH_WINDOW")
	applyBoolEnv(&cfg.Elasticsearch.UsePointInTime, "SLP_ELASTICSEARCH_USE_POINT_IN_TIME")
	applyDurationEnv(&cfg.Elasticsearch.PITKeepAlive, "SLP_ELASTICSEARCH_PIT_KEEP_ALIVE")

	applyStringEnv(&cfg.Redis.Address, "SLP_REDIS_ADDRESS")
	applyStringEnv(&cfg.Redis.Username, "SLP_REDIS_USERNAME")
	applyStringEnv(&cfg.Redis.Password, "SLP_REDIS_PASSWORD")
	applyIntEnv(&cfg.Redis.DB, "SLP_REDIS_DB")
	applyDurationEnv(&cfg.Redis.DialTimeout, "SLP_REDIS_DIAL_TIMEOUT")
	applyDurationEnv(&cfg.Redis.ReadTimeout, "SLP_REDIS_READ_TIMEOUT")
	applyDurationEnv(&cfg.Redis.WriteTimeout, "SLP_REDIS_WRITE_TIMEOUT")
	applyStringEnv(&cfg.Redis.KeyPrefix, "SLP_REDIS_KEY_PREFIX")
	applyStringEnv(&cfg.Redis.HashField, "SLP_REDIS_HASH_FIELD")
	applyDurationEnv(&cfg.Redis.RetentionWindow, "SLP_REDIS_RETENTION_WINDOW")

	applyBoolEnv(&cfg.Lock.Enabled, "SLP_LOCK_ENABLED")
	applyStringEnv(&cfg.Lock.Key, "SLP_LOCK_KEY")
	applyIntEnv(&cfg.Lock.ShardCount, "SLP_LOCK_SHARD_COUNT")
	applyDurationEnv(&cfg.Lock.TTL, "SLP_LOCK_TTL")
	applyDurationEnv(&cfg.Lock.AcquireTimeout, "SLP_LOCK_ACQUIRE_TIMEOUT")

	applyStringEnv(&cfg.Mappings.OrganizationField, "SLP_MAPPING_ORGANIZATION_FIELD")
	applyStringEnv(&cfg.Mappings.SignalField, "SLP_MAPPING_SIGNAL_FIELD")
	applyStringEnv(&cfg.Mappings.LogLevelField, "SLP_MAPPING_LOG_LEVEL_FIELD")
	applyStringEnv(&cfg.Mappings.TimestampField, "SLP_MAPPING_TIMESTAMP_FIELD")
	applyStringEnv(&cfg.Mappings.DocIDSource, "SLP_MAPPING_DOC_ID_SOURCE")
	applyStringEnv(&cfg.Mappings.DocIDField, "SLP_MAPPING_DOC_ID_FIELD")

	applyStringEnv(&cfg.PM2.AppName, "SLP_PM2_APP_NAME")
	applyIntEnv(&cfg.PM2.Instances, "SLP_PM2_INSTANCES")
}

// applyStringEnv applies a string environment variable override if set.
// Whitespace is trimmed from the value.
//
// Parameters:
//   - target: Pointer to configuration field to override
//   - key: Environment variable name
//
// Behavior:
//   - If env var not set: No change to target
//   - If env var empty: target set to empty string
//   - If env var set: target set to trimmed value
func applyStringEnv(target *string, key string) {
	value, ok := os.LookupEnv(key)
	if ok {
		*target = strings.TrimSpace(value)
	}
}

// applyStringSliceEnv applies a string slice environment variable override.
// Splits by comma or semicolon (e.g., "host1,host2" or "host1;host2").
//
// Parameters:
//   - target: Pointer to string slice field to override
//   - key: Environment variable name
//
// Behavior:
//   - If env var not set: No change to target
//   - If env var empty/whitespace: target set to nil
//   - If env var set: Split and trim each part, filter empty strings
func applyStringSliceEnv(target *[]string, key string) {
	value, ok := os.LookupEnv(key)
	if !ok {
		return
	}
	if strings.TrimSpace(value) == "" {
		*target = nil
		return
	}
	parts := strings.FieldsFunc(value, func(r rune) bool {
		return r == ',' || r == ';'
	})
	*target = compactStrings(parts)
}

// applyIntEnv applies an integer environment variable override.
// Uses strconv.Atoi for parsing.
//
// Parameters:
//   - target: Pointer to int field to override
//   - key: Environment variable name
//
// Behavior:
//   - If env var not set: No change to target
//   - If env var empty: No change to target
//   - If env var not parseable: Silently ignored
//   - If env var valid: target set to parsed value
func applyIntEnv(target *int, key string) {
	value, ok := os.LookupEnv(key)
	if !ok || strings.TrimSpace(value) == "" {
		return
	}
	if parsed, err := strconv.Atoi(strings.TrimSpace(value)); err == nil {
		*target = parsed
	}
}

// applyBoolEnv applies a boolean environment variable override.
// Uses strconv.ParseBool for parsing (accepts: true/false, 1/0, yes/no, on/off).
//
// Parameters:
//   - target: Pointer to bool field to override
//   - key: Environment variable name
//
// Behavior:
//   - If env var not set: No change to target
//   - If env var empty: No change to target
//   - If env var not parseable: Silently ignored
//   - If env var valid: target set to parsed value
func applyBoolEnv(target *bool, key string) {
	value, ok := os.LookupEnv(key)
	if !ok || strings.TrimSpace(value) == "" {
		return
	}
	if parsed, err := strconv.ParseBool(strings.TrimSpace(value)); err == nil {
		*target = parsed
	}
}

// applyDurationEnv applies a duration environment variable override.
// Uses time.ParseDuration for parsing (e.g., "5m", "30s", "1h30m").
//
// Parameters:
//   - target: Pointer to time.Duration field to override
//   - key: Environment variable name
//
// Behavior:
//   - If env var not set: No change to target
//   - If env var empty: No change to target
//   - If env var not parseable: Silently ignored
//   - If env var valid: target set to parsed value
func applyDurationEnv(target *time.Duration, key string) {
	value, ok := os.LookupEnv(key)
	if !ok || strings.TrimSpace(value) == "" {
		return
	}
	if parsed, err := time.ParseDuration(strings.TrimSpace(value)); err == nil {
		*target = parsed
	}
}

// compactStrings filters a string slice to remove empty/whitespace strings.
// Maintains original order.
//
// Parameters:
//   - values: Slice of strings potentially containing empty values
//
// Returns:
//   - Filtered slice containing only non-empty trimmed strings
//
// Example:
//   compactStrings([]string{"host1", " ", "host2", ""}) → []{host1, host2}}

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
