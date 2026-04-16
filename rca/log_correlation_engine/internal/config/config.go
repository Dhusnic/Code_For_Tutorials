package config

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

type SchedulerConfig struct {
	Interval            time.Duration `yaml:"interval"`
	RunTimeout          time.Duration `yaml:"run_timeout"`
	OrganizationWorkers int           `yaml:"organization_workers"`
}

type RedisConfig struct {
	Address                         string        `yaml:"address"`
	Username                        string        `yaml:"username"`
	Password                        string        `yaml:"password"`
	DB                              int           `yaml:"db"`
	DialTimeout                     time.Duration `yaml:"dial_timeout"`
	ReadTimeout                     time.Duration `yaml:"read_timeout"`
	WriteTimeout                    time.Duration `yaml:"write_timeout"`
	KeyPrefix                       string        `yaml:"key_prefix"`
	HashField                       string        `yaml:"hash_field"`
	ResultList                      string        `yaml:"result_list"`
	ResultListMaxLen                int           `yaml:"result_list_max_len"`
	PublishResults                  bool          `yaml:"publish_results"`
	SignalStreamEnabled             bool          `yaml:"signal_stream_enabled"`
	SignalStreamKey                 string        `yaml:"signal_stream_key"`
	SignalStreamBatchSize           int           `yaml:"signal_stream_batch_size"`
	SignalStreamConsumedRetention   time.Duration `yaml:"signal_stream_consumed_retention"`
	SignalStreamUnconsumedRetention time.Duration `yaml:"signal_stream_unconsumed_retention"`
}

type ElasticsearchConfig struct {
	Addresses      []string      `yaml:"addresses"`
	Username       string        `yaml:"username"`
	Password       string        `yaml:"password"`
	APIKey         string        `yaml:"api_key"`
	Index          string        `yaml:"index"`
	CurrentIndex   string        `yaml:"current_index"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
	BulkBatchSize  int           `yaml:"bulk_batch_size"`
}

type EngineConfig struct {
	RulesFile             string        `yaml:"rules_file"`
	HotReloadInterval     time.Duration `yaml:"hot_reload_interval"`
	DefaultWindow         time.Duration `yaml:"default_window"`
	DefaultMaxGap         time.Duration `yaml:"default_max_gap"`
	IncrementalLookback   time.Duration `yaml:"incremental_lookback"`
	IncidentInactivityTTL time.Duration `yaml:"incident_inactivity_ttl"`
	CheckpointDirectory   string        `yaml:"checkpoint_directory"`
}

type FetcherConfig struct {
	Mode           string        `yaml:"mode"`
	Addresses      []string      `yaml:"addresses"`
	Username       string        `yaml:"username"`
	Password       string        `yaml:"password"`
	APIKey         string        `yaml:"api_key"`
	Index          string        `yaml:"index"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
	TimestampField string        `yaml:"timestamp_field"`
	LogLevelField  string        `yaml:"log_level_field"`
}

type Config struct {
	ServiceName   string              `yaml:"service_name"`
	Logging       LoggingConfig       `yaml:"logging"`
	Scheduler     SchedulerConfig     `yaml:"scheduler"`
	Redis         RedisConfig         `yaml:"redis"`
	Elasticsearch ElasticsearchConfig `yaml:"elasticsearch"`
	Engine        EngineConfig        `yaml:"engine"`
	Fetcher       FetcherConfig       `yaml:"fetcher"`
}

func Load(path string) (Config, error) {
	cfg := defaultConfig()
	if strings.TrimSpace(path) != "" {
		contents, err := os.ReadFile(filepath.Clean(path))
		if err != nil {
			return Config{}, fmt.Errorf("read config file: %w", err)
		}
		if err := yaml.Unmarshal(contents, &cfg); err != nil {
			return Config{}, fmt.Errorf("parse config file: %w", err)
		}
	}

	cfg.normalize()
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func defaultConfig() Config {
	return Config{
		ServiceName: "log-correlation-engine",
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
		Scheduler: SchedulerConfig{
			Interval:            time.Minute,
			RunTimeout:          50 * time.Second,
			OrganizationWorkers: 4,
		},
		Redis: RedisConfig{
			DB:                              0,
			DialTimeout:                     5 * time.Second,
			ReadTimeout:                     3 * time.Second,
			WriteTimeout:                    3 * time.Second,
			KeyPrefix:                       "Rca",
			HashField:                       "signaled_logs",
			ResultList:                      "correlated_events",
			ResultListMaxLen:                1000,
			PublishResults:                  false,
			SignalStreamEnabled:             false,
			SignalStreamKey:                 "Rca:signalized_log_events",
			SignalStreamBatchSize:           1000,
			SignalStreamConsumedRetention:   30 * time.Minute,
			SignalStreamUnconsumedRetention: 2 * time.Hour,
		},
		Elasticsearch: ElasticsearchConfig{
			Addresses:      []string{"http://localhost:9200"},
			Index:          "rca_correlated_events",
			CurrentIndex:   "rca_correlated_incidents_current",
			RequestTimeout: 15 * time.Second,
			BulkBatchSize:  250,
		},
		Engine: EngineConfig{
			RulesFile:             "rules/rules.json",
			HotReloadInterval:     30 * time.Second,
			DefaultWindow:         30 * time.Minute,
			DefaultMaxGap:         5 * time.Minute,
			IncrementalLookback:   0,
			IncidentInactivityTTL: 30 * time.Minute,
			CheckpointDirectory:   filepath.Join("data", "checkpoints"),
		},
		Fetcher: FetcherConfig{
			Mode:           "mock",
			RequestTimeout: 15 * time.Second,
			TimestampField: "@timestamp",
			LogLevelField:  "log.level",
		},
	}
}

func (c *Config) normalize() {
	c.ServiceName = strings.TrimSpace(c.ServiceName)
	c.Logging.Level = strings.TrimSpace(c.Logging.Level)
	c.Logging.Format = strings.ToLower(strings.TrimSpace(c.Logging.Format))

	c.Redis.Address = strings.TrimSpace(c.Redis.Address)
	c.Redis.Username = strings.TrimSpace(c.Redis.Username)
	c.Redis.KeyPrefix = strings.TrimSuffix(strings.TrimSpace(c.Redis.KeyPrefix), ":")
	c.Redis.HashField = strings.TrimSpace(c.Redis.HashField)
	c.Redis.ResultList = strings.TrimSpace(c.Redis.ResultList)
	c.Redis.SignalStreamKey = strings.TrimSpace(c.Redis.SignalStreamKey)

	c.Elasticsearch.Username = strings.TrimSpace(c.Elasticsearch.Username)
	c.Elasticsearch.Password = strings.TrimSpace(c.Elasticsearch.Password)
	c.Elasticsearch.APIKey = strings.TrimSpace(c.Elasticsearch.APIKey)
	c.Elasticsearch.Index = strings.TrimSpace(c.Elasticsearch.Index)
	c.Elasticsearch.CurrentIndex = strings.TrimSpace(c.Elasticsearch.CurrentIndex)
	for idx := range c.Elasticsearch.Addresses {
		c.Elasticsearch.Addresses[idx] = strings.TrimSpace(c.Elasticsearch.Addresses[idx])
	}
	c.Elasticsearch.Addresses = compactStrings(c.Elasticsearch.Addresses)

	c.Engine.RulesFile = strings.TrimSpace(c.Engine.RulesFile)
	c.Engine.CheckpointDirectory = strings.TrimSpace(c.Engine.CheckpointDirectory)
	c.Fetcher.Mode = strings.ToLower(strings.TrimSpace(c.Fetcher.Mode))
	c.Fetcher.Username = strings.TrimSpace(c.Fetcher.Username)
	c.Fetcher.Password = strings.TrimSpace(c.Fetcher.Password)
	c.Fetcher.APIKey = strings.TrimSpace(c.Fetcher.APIKey)
	c.Fetcher.Index = strings.TrimSpace(c.Fetcher.Index)
	c.Fetcher.TimestampField = strings.TrimSpace(c.Fetcher.TimestampField)
	c.Fetcher.LogLevelField = strings.TrimSpace(c.Fetcher.LogLevelField)
	for idx := range c.Fetcher.Addresses {
		c.Fetcher.Addresses[idx] = strings.TrimSpace(c.Fetcher.Addresses[idx])
	}
	c.Fetcher.Addresses = compactStrings(c.Fetcher.Addresses)
	if c.Fetcher.Mode == "" {
		c.Fetcher.Mode = "mock"
	}
	if c.Fetcher.TimestampField == "" {
		c.Fetcher.TimestampField = "@timestamp"
	}
	if c.Fetcher.LogLevelField == "" {
		c.Fetcher.LogLevelField = "log.level"
	}
	if c.Fetcher.RequestTimeout < 0 {
		c.Fetcher.RequestTimeout = 0
	}
}

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
	if c.Scheduler.RunTimeout > c.Scheduler.Interval {
		return errors.New("scheduler.run_timeout must be less than or equal to scheduler.interval")
	}
	if c.Redis.Address == "" {
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
	if c.Redis.ResultList == "" {
		return errors.New("redis.result_list must not be empty")
	}
	if c.Redis.ResultListMaxLen < 0 {
		return errors.New("redis.result_list_max_len must not be negative")
	}
	if c.Redis.SignalStreamEnabled {
		if c.Redis.SignalStreamKey == "" {
			return errors.New("redis.signal_stream_key must not be empty when redis.signal_stream_enabled is true")
		}
		if c.Redis.SignalStreamBatchSize <= 0 {
			return errors.New("redis.signal_stream_batch_size must be greater than zero when redis.signal_stream_enabled is true")
		}
		if c.Redis.SignalStreamConsumedRetention <= 0 {
			return errors.New("redis.signal_stream_consumed_retention must be greater than zero when redis.signal_stream_enabled is true")
		}
		if c.Redis.SignalStreamUnconsumedRetention <= 0 {
			return errors.New("redis.signal_stream_unconsumed_retention must be greater than zero when redis.signal_stream_enabled is true")
		}
		if c.Redis.SignalStreamUnconsumedRetention < c.Redis.SignalStreamConsumedRetention {
			return errors.New("redis.signal_stream_unconsumed_retention must be greater than or equal to redis.signal_stream_consumed_retention")
		}
	}
	if len(c.Elasticsearch.Addresses) == 0 {
		return errors.New("elasticsearch.addresses must contain at least one host")
	}
	if c.Elasticsearch.Index == "" {
		return errors.New("elasticsearch.index must not be empty")
	}
	if c.Elasticsearch.CurrentIndex == "" {
		return errors.New("elasticsearch.current_index must not be empty")
	}
	if c.Elasticsearch.RequestTimeout <= 0 {
		return errors.New("elasticsearch.request_timeout must be greater than zero")
	}
	if c.Elasticsearch.BulkBatchSize <= 0 {
		return errors.New("elasticsearch.bulk_batch_size must be greater than zero")
	}
	if c.Engine.RulesFile == "" {
		return errors.New("engine.rules_file must not be empty")
	}
	if c.Engine.DefaultWindow <= 0 {
		return errors.New("engine.default_window must be greater than zero")
	}
	if c.Engine.DefaultMaxGap <= 0 {
		return errors.New("engine.default_max_gap must be greater than zero")
	}
	if c.Engine.IncrementalLookback < 0 {
		return errors.New("engine.incremental_lookback must not be negative")
	}
	if c.Engine.IncidentInactivityTTL <= 0 {
		return errors.New("engine.incident_inactivity_ttl must be greater than zero")
	}
	if c.Engine.HotReloadInterval < 0 {
		return errors.New("engine.hot_reload_interval must not be negative")
	}
	if c.Engine.CheckpointDirectory == "" {
		return errors.New("engine.checkpoint_directory must not be empty")
	}
	switch c.Fetcher.Mode {
	case "mock":
	case "elasticsearch":
		if c.Fetcher.Index == "" {
			return errors.New("fetcher.index must not be empty when fetcher.mode is elasticsearch")
		}
		if c.Fetcher.TimestampField == "" {
			return errors.New("fetcher.timestamp_field must not be empty when fetcher.mode is elasticsearch")
		}
		if c.Fetcher.LogLevelField == "" {
			return errors.New("fetcher.log_level_field must not be empty when fetcher.mode is elasticsearch")
		}
	default:
		return fmt.Errorf("fetcher.mode %q is not supported", c.Fetcher.Mode)
	}
	return nil
}

func (c Config) FetcherElasticsearchConfig() ElasticsearchConfig {
	cfg := c.Elasticsearch
	if len(c.Fetcher.Addresses) > 0 {
		cfg.Addresses = append([]string(nil), c.Fetcher.Addresses...)
	}
	if c.Fetcher.Username != "" {
		cfg.Username = c.Fetcher.Username
	}
	if c.Fetcher.Password != "" {
		cfg.Password = c.Fetcher.Password
	}
	if c.Fetcher.APIKey != "" {
		cfg.APIKey = c.Fetcher.APIKey
	}
	if c.Fetcher.Index != "" {
		cfg.Index = c.Fetcher.Index
	}
	if c.Fetcher.RequestTimeout > 0 {
		cfg.RequestTimeout = c.Fetcher.RequestTimeout
	}
	return cfg
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
