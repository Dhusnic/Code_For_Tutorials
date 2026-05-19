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

type AutoscalingSchedulerConfig struct {
	MinInterval              time.Duration `yaml:"min_interval"`
	MaxInterval              time.Duration `yaml:"max_interval"`
	TimeoutRatio             float64       `yaml:"timeout_ratio"`
	TargetCycleUtilization   float64       `yaml:"target_cycle_utilization"`
	TimeoutScaleUpMultiplier float64       `yaml:"timeout_scale_up_multiplier"`
}

type AutoscalingFetcherConfig struct {
	MinGroupedLookupBatchSize int `yaml:"min_grouped_lookup_batch_size"`
	MaxGroupedLookupBatchSize int `yaml:"max_grouped_lookup_batch_size"`
	MaxBatchesPerCycle        int `yaml:"max_batches_per_cycle"`
}

type AutoscalingConfig struct {
	Enabled                 bool                       `yaml:"enabled"`
	InputBasis              string                     `yaml:"input_basis"`
	InputLowWatermark       int                        `yaml:"input_low_watermark"`
	InputHighWatermark      int                        `yaml:"input_high_watermark"`
	ScaleDownCooldownCycles int                        `yaml:"scale_down_cooldown_cycles"`
	Scheduler               AutoscalingSchedulerConfig `yaml:"scheduler"`
	Fetcher                 AutoscalingFetcherConfig   `yaml:"fetcher"`
}

type DistributedConfig struct {
	Enabled                  bool          `yaml:"enabled"`
	WorkerIDEnv              string        `yaml:"worker_id_env"`
	LeaseTTL                 time.Duration `yaml:"lease_ttl"`
	LeaseHeartbeatInterval   time.Duration `yaml:"lease_heartbeat_interval"`
	ClaimLimitPerCycle       int           `yaml:"claim_limit_per_cycle"`
	StreamConsumerGroup      string        `yaml:"stream_consumer_group"`
	SingleStreamIngestLeader bool          `yaml:"single_stream_ingest_leader"`
	PrefetchFullLogs         bool          `yaml:"prefetch_full_logs"`
	PrefetchTimeout          time.Duration `yaml:"prefetch_timeout"`
	PrefetchMaxDocIDs        int           `yaml:"prefetch_max_doc_ids"`
	FullLogCacheTTL          time.Duration `yaml:"full_log_cache_ttl"`
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
	WriteHistory   bool          `yaml:"write_history_index"`
	CurrentIndex   string        `yaml:"current_index"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
	BulkBatchSize  int           `yaml:"bulk_batch_size"`
}

type ParallelCorrelationConfig struct {
	Enabled                        bool          `yaml:"enabled"`
	MinLogs                        int           `yaml:"min_logs"`
	TargetLogsPerShard             int           `yaml:"target_logs_per_shard"`
	MaxWorkers                     int           `yaml:"max_workers"`
	DistributedTargetShardDuration time.Duration `yaml:"distributed_target_shard_duration"`
	DistributedShardTimeout        time.Duration `yaml:"distributed_shard_timeout"`
	DistributedRunReserve          time.Duration `yaml:"distributed_run_reserve"`
	DistributedMinShardsPerWorker  int           `yaml:"distributed_min_shards_per_worker"`
	DistributedMaxShardsPerWorker  int           `yaml:"distributed_max_shards_per_worker"`
	ShardPollInterval              time.Duration `yaml:"shard_poll_interval"`
}

type EngineConfig struct {
	RulesFile             string                    `yaml:"rules_file"`
	HotReloadInterval     time.Duration             `yaml:"hot_reload_interval"`
	InputMode             string                    `yaml:"input_mode"`
	InputWindow           time.Duration             `yaml:"input_window"`
	GroupByFields         []string                  `yaml:"group_by_fields"`
	DefaultWindow         time.Duration             `yaml:"default_window"`
	DefaultMaxGap         time.Duration             `yaml:"default_max_gap"`
	IncrementalLookback   time.Duration             `yaml:"incremental_lookback"`
	IncidentInactivityTTL time.Duration             `yaml:"incident_inactivity_ttl"`
	CheckpointDirectory   string                    `yaml:"checkpoint_directory"`
	ParallelCorrelation   ParallelCorrelationConfig `yaml:"parallel_correlation"`
}

type MongoSyncConfig struct {
	Enabled            bool              `yaml:"enabled"`
	URI                string            `yaml:"uri"`
	Database           string            `yaml:"database"`
	RulesCollection    string            `yaml:"rules_collection"`
	StateCollection    string            `yaml:"state_collection"`
	StateName          string            `yaml:"state_name"`
	SnapshotCollection string            `yaml:"snapshot_collection"`
	SnapshotName       string            `yaml:"snapshot_name"`
	UseSnapshot        bool              `yaml:"use_snapshot"`
	WriteSnapshot      bool              `yaml:"write_snapshot"`
	RedisNotify        RedisNotifyConfig `yaml:"redis_notify"`
	Timeout            time.Duration     `yaml:"timeout"`
}

type RedisNotifyConfig struct {
	Enabled        bool          `yaml:"enabled"`
	Channel        string        `yaml:"channel"`
	ReconnectDelay time.Duration `yaml:"reconnect_delay"`
}

type FetcherConfig struct {
	Mode                   string        `yaml:"mode"`
	Addresses              []string      `yaml:"addresses"`
	Username               string        `yaml:"username"`
	Password               string        `yaml:"password"`
	APIKey                 string        `yaml:"api_key"`
	Index                  string        `yaml:"index"`
	RequestTimeout         time.Duration `yaml:"request_timeout"`
	GroupedLookupBatchSize int           `yaml:"grouped_lookup_batch_size"`
	TimestampField         string        `yaml:"timestamp_field"`
	LogLevelField          string        `yaml:"log_level_field"`
}

type Config struct {
	ServiceName   string              `yaml:"service_name"`
	Logging       LoggingConfig       `yaml:"logging"`
	Scheduler     SchedulerConfig     `yaml:"scheduler"`
	Autoscaling   AutoscalingConfig   `yaml:"autoscaling"`
	Distributed   DistributedConfig   `yaml:"distributed"`
	Redis         RedisConfig         `yaml:"redis"`
	Elasticsearch ElasticsearchConfig `yaml:"elasticsearch"`
	Engine        EngineConfig        `yaml:"engine"`
	MongoSync     MongoSyncConfig     `yaml:"mongo_sync"`
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
		Autoscaling: AutoscalingConfig{
			Enabled:                 false,
			InputBasis:              "incremental_logs",
			InputLowWatermark:       1000,
			InputHighWatermark:      100000,
			ScaleDownCooldownCycles: 3,
			Scheduler: AutoscalingSchedulerConfig{
				MinInterval:              20 * time.Second,
				MaxInterval:              90 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Fetcher: AutoscalingFetcherConfig{
				MinGroupedLookupBatchSize: 250,
				MaxGroupedLookupBatchSize: 2000,
				MaxBatchesPerCycle:        4,
			},
		},
		Distributed: DistributedConfig{
			Enabled:                  false,
			WorkerIDEnv:              "RCA_WORKER_ID",
			LeaseTTL:                 45 * time.Second,
			LeaseHeartbeatInterval:   15 * time.Second,
			ClaimLimitPerCycle:       32,
			StreamConsumerGroup:      "rca-correlation",
			SingleStreamIngestLeader: true,
			PrefetchFullLogs:         false,
			PrefetchTimeout:          5 * time.Second,
			PrefetchMaxDocIDs:        1000,
			FullLogCacheTTL:          2 * time.Hour,
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
			SignalStreamBatchSize:           250,
			SignalStreamConsumedRetention:   30 * time.Minute,
			SignalStreamUnconsumedRetention: 2 * time.Hour,
		},
		Elasticsearch: ElasticsearchConfig{
			Addresses:      []string{"http://localhost:9200"},
			Index:          "rca_correlated_events",
			WriteHistory:   true,
			CurrentIndex:   "rca_correlated_incidents_current",
			RequestTimeout: 15 * time.Second,
			BulkBatchSize:  250,
		},
		Engine: EngineConfig{
			RulesFile:             "rules/rules.json",
			HotReloadInterval:     30 * time.Second,
			InputMode:             "organization_payload",
			InputWindow:           30 * time.Minute,
			GroupByFields:         nil,
			DefaultWindow:         30 * time.Minute,
			DefaultMaxGap:         5 * time.Minute,
			IncrementalLookback:   0,
			IncidentInactivityTTL: 30 * time.Minute,
			CheckpointDirectory:   filepath.Join("data", "checkpoints"),
			ParallelCorrelation: ParallelCorrelationConfig{
				Enabled:                        false,
				MinLogs:                        5000,
				TargetLogsPerShard:             1500,
				MaxWorkers:                     8,
				DistributedTargetShardDuration: 750 * time.Millisecond,
				DistributedShardTimeout:        5 * time.Second,
				DistributedRunReserve:          3 * time.Second,
				DistributedMinShardsPerWorker:  1,
				DistributedMaxShardsPerWorker:  10,
				ShardPollInterval:              20 * time.Millisecond,
			},
		},
		MongoSync: MongoSyncConfig{
			Database:           "dhusnic_test_db",
			RulesCollection:    "correlation_rules",
			StateCollection:    "rca_config_state",
			StateName:          "prod_rules_topology",
			SnapshotCollection: "rca_config_snapshots",
			SnapshotName:       "prod_rules_topology",
			UseSnapshot:        true,
			RedisNotify: RedisNotifyConfig{
				Channel:        "rca_config_changed",
				ReconnectDelay: 5 * time.Second,
			},
			Timeout: 5 * time.Second,
		},
		Fetcher: FetcherConfig{
			Mode:                   "mock",
			RequestTimeout:         15 * time.Second,
			GroupedLookupBatchSize: 100,
			TimestampField:         "@timestamp",
			LogLevelField:          "log.level",
		},
	}
}

func (c *Config) normalize() {
	c.ServiceName = strings.TrimSpace(c.ServiceName)
	c.Logging.Level = strings.TrimSpace(c.Logging.Level)
	c.Logging.Format = strings.ToLower(strings.TrimSpace(c.Logging.Format))
	c.Autoscaling.InputBasis = strings.ToLower(strings.TrimSpace(c.Autoscaling.InputBasis))
	c.Distributed.WorkerIDEnv = strings.TrimSpace(c.Distributed.WorkerIDEnv)
	c.Distributed.StreamConsumerGroup = strings.TrimSpace(c.Distributed.StreamConsumerGroup)

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
	c.Engine.InputMode = strings.ToLower(strings.TrimSpace(c.Engine.InputMode))
	c.Engine.CheckpointDirectory = strings.TrimSpace(c.Engine.CheckpointDirectory)
	c.Engine.GroupByFields = compactStrings(c.Engine.GroupByFields)
	c.MongoSync.URI = strings.TrimSpace(c.MongoSync.URI)
	c.MongoSync.Database = strings.TrimSpace(c.MongoSync.Database)
	c.MongoSync.RulesCollection = strings.TrimSpace(c.MongoSync.RulesCollection)
	c.MongoSync.StateCollection = strings.TrimSpace(c.MongoSync.StateCollection)
	c.MongoSync.StateName = strings.TrimSpace(c.MongoSync.StateName)
	c.MongoSync.SnapshotCollection = strings.TrimSpace(c.MongoSync.SnapshotCollection)
	c.MongoSync.SnapshotName = strings.TrimSpace(c.MongoSync.SnapshotName)
	c.MongoSync.RedisNotify.Channel = strings.TrimSpace(c.MongoSync.RedisNotify.Channel)
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
	if c.Engine.InputMode == "" {
		c.Engine.InputMode = "organization_payload"
	}
	if c.Engine.InputWindow <= 0 {
		c.Engine.InputWindow = 30 * time.Minute
	}
	if c.Engine.ParallelCorrelation.MinLogs <= 0 {
		c.Engine.ParallelCorrelation.MinLogs = 5000
	}
	if c.Engine.ParallelCorrelation.TargetLogsPerShard <= 0 {
		c.Engine.ParallelCorrelation.TargetLogsPerShard = 1500
	}
	if c.Engine.ParallelCorrelation.MaxWorkers <= 0 {
		c.Engine.ParallelCorrelation.MaxWorkers = 8
	}
	if c.Engine.ParallelCorrelation.DistributedTargetShardDuration <= 0 {
		c.Engine.ParallelCorrelation.DistributedTargetShardDuration = 750 * time.Millisecond
	}
	if c.Engine.ParallelCorrelation.DistributedShardTimeout <= 0 {
		c.Engine.ParallelCorrelation.DistributedShardTimeout = 5 * time.Second
	}
	if c.Engine.ParallelCorrelation.DistributedRunReserve <= 0 {
		c.Engine.ParallelCorrelation.DistributedRunReserve = 3 * time.Second
	}
	if c.Engine.ParallelCorrelation.DistributedMinShardsPerWorker <= 0 {
		c.Engine.ParallelCorrelation.DistributedMinShardsPerWorker = 1
	}
	if c.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker <= 0 {
		c.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker = 10
	}
	if c.Engine.ParallelCorrelation.ShardPollInterval <= 0 {
		c.Engine.ParallelCorrelation.ShardPollInterval = 20 * time.Millisecond
	}
	if c.Distributed.WorkerIDEnv == "" {
		c.Distributed.WorkerIDEnv = "RCA_WORKER_ID"
	}
	if c.Distributed.LeaseTTL <= 0 {
		c.Distributed.LeaseTTL = 45 * time.Second
	}
	if c.Distributed.LeaseHeartbeatInterval <= 0 {
		c.Distributed.LeaseHeartbeatInterval = 15 * time.Second
	}
	if c.Distributed.ClaimLimitPerCycle <= 0 {
		c.Distributed.ClaimLimitPerCycle = 32
	}
	if c.Distributed.StreamConsumerGroup == "" {
		c.Distributed.StreamConsumerGroup = "rca-correlation"
	}
	if c.Distributed.FullLogCacheTTL <= 0 {
		c.Distributed.FullLogCacheTTL = 2 * time.Hour
	}
	if c.Autoscaling.InputBasis == "" {
		c.Autoscaling.InputBasis = "incremental_logs"
	}
	if c.Autoscaling.InputLowWatermark <= 0 {
		c.Autoscaling.InputLowWatermark = 1000
	}
	if c.Autoscaling.InputHighWatermark <= 0 {
		c.Autoscaling.InputHighWatermark = 100000
	}
	if c.Autoscaling.ScaleDownCooldownCycles <= 0 {
		c.Autoscaling.ScaleDownCooldownCycles = 3
	}
	if c.Autoscaling.Scheduler.MinInterval <= 0 {
		c.Autoscaling.Scheduler.MinInterval = 20 * time.Second
	}
	if c.Autoscaling.Scheduler.MaxInterval <= 0 {
		c.Autoscaling.Scheduler.MaxInterval = 90 * time.Second
	}
	if c.Autoscaling.Scheduler.TimeoutRatio <= 0 {
		c.Autoscaling.Scheduler.TimeoutRatio = 0.9
	}
	if c.Autoscaling.Scheduler.TargetCycleUtilization <= 0 {
		c.Autoscaling.Scheduler.TargetCycleUtilization = 0.8
	}
	if c.Autoscaling.Scheduler.TimeoutScaleUpMultiplier <= 0 {
		c.Autoscaling.Scheduler.TimeoutScaleUpMultiplier = 1.5
	}
	if c.Autoscaling.Fetcher.MinGroupedLookupBatchSize <= 0 {
		c.Autoscaling.Fetcher.MinGroupedLookupBatchSize = 250
	}
	if c.Autoscaling.Fetcher.MaxGroupedLookupBatchSize <= 0 {
		c.Autoscaling.Fetcher.MaxGroupedLookupBatchSize = 2000
	}
	if c.Autoscaling.Fetcher.MaxBatchesPerCycle <= 0 {
		c.Autoscaling.Fetcher.MaxBatchesPerCycle = 4
	}
	if c.Distributed.PrefetchTimeout <= 0 {
		c.Distributed.PrefetchTimeout = 5 * time.Second
	}
	if c.Distributed.PrefetchMaxDocIDs <= 0 {
		c.Distributed.PrefetchMaxDocIDs = 1000
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
	if c.Fetcher.GroupedLookupBatchSize <= 0 {
		c.Fetcher.GroupedLookupBatchSize = 100
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
	if c.Autoscaling.InputBasis != "incremental_logs" {
		return errors.New("autoscaling.input_basis must be incremental_logs")
	}
	if c.Autoscaling.InputLowWatermark > c.Autoscaling.InputHighWatermark {
		return errors.New("autoscaling.input_low_watermark must be less than or equal to autoscaling.input_high_watermark")
	}
	if c.Autoscaling.ScaleDownCooldownCycles <= 0 {
		return errors.New("autoscaling.scale_down_cooldown_cycles must be greater than zero")
	}
	if c.Autoscaling.Scheduler.MinInterval < 10*time.Second {
		return errors.New("autoscaling.scheduler.min_interval must be greater than or equal to 10s")
	}
	if c.Autoscaling.Scheduler.MaxInterval > 90*time.Second {
		return errors.New("autoscaling.scheduler.max_interval must be less than or equal to 90s")
	}
	if c.Autoscaling.Scheduler.MinInterval > c.Autoscaling.Scheduler.MaxInterval {
		return errors.New("autoscaling.scheduler.min_interval must be less than or equal to autoscaling.scheduler.max_interval")
	}
	if c.Autoscaling.Scheduler.TimeoutRatio <= 0 || c.Autoscaling.Scheduler.TimeoutRatio >= 1 {
		return errors.New("autoscaling.scheduler.timeout_ratio must be greater than zero and less than one")
	}
	if c.Autoscaling.Scheduler.TargetCycleUtilization <= 0 || c.Autoscaling.Scheduler.TargetCycleUtilization >= 1 {
		return errors.New("autoscaling.scheduler.target_cycle_utilization must be greater than zero and less than one")
	}
	if c.Autoscaling.Scheduler.TimeoutScaleUpMultiplier < 1 {
		return errors.New("autoscaling.scheduler.timeout_scale_up_multiplier must be greater than or equal to one")
	}
	if c.Autoscaling.Fetcher.MinGroupedLookupBatchSize < 100 || c.Autoscaling.Fetcher.MinGroupedLookupBatchSize > 10000 {
		return errors.New("autoscaling.fetcher.min_grouped_lookup_batch_size must be between 100 and 10000")
	}
	if c.Autoscaling.Fetcher.MaxGroupedLookupBatchSize < 100 || c.Autoscaling.Fetcher.MaxGroupedLookupBatchSize > 10000 {
		return errors.New("autoscaling.fetcher.max_grouped_lookup_batch_size must be between 100 and 10000")
	}
	if c.Autoscaling.Fetcher.MinGroupedLookupBatchSize > c.Autoscaling.Fetcher.MaxGroupedLookupBatchSize {
		return errors.New("autoscaling.fetcher.min_grouped_lookup_batch_size must be less than or equal to autoscaling.fetcher.max_grouped_lookup_batch_size")
	}
	if c.Autoscaling.Fetcher.MaxBatchesPerCycle <= 0 {
		return errors.New("autoscaling.fetcher.max_batches_per_cycle must be greater than zero")
	}
	if c.Distributed.Enabled {
		if c.Distributed.WorkerIDEnv == "" {
			return errors.New("distributed.worker_id_env must not be empty when distributed.enabled is true")
		}
		if c.Distributed.LeaseTTL <= 0 {
			return errors.New("distributed.lease_ttl must be greater than zero when distributed.enabled is true")
		}
		if c.Distributed.LeaseHeartbeatInterval <= 0 {
			return errors.New("distributed.lease_heartbeat_interval must be greater than zero when distributed.enabled is true")
		}
		if c.Distributed.LeaseHeartbeatInterval >= c.Distributed.LeaseTTL {
			return errors.New("distributed.lease_heartbeat_interval must be less than distributed.lease_ttl")
		}
		if c.Distributed.ClaimLimitPerCycle <= 0 {
			return errors.New("distributed.claim_limit_per_cycle must be greater than zero when distributed.enabled is true")
		}
		if c.Distributed.StreamConsumerGroup == "" {
			return errors.New("distributed.stream_consumer_group must not be empty when distributed.enabled is true")
		}
		if c.Distributed.PrefetchFullLogs {
			if c.Distributed.PrefetchTimeout <= 0 {
				return errors.New("distributed.prefetch_timeout must be greater than zero when distributed.prefetch_full_logs is true")
			}
			if c.Distributed.PrefetchMaxDocIDs <= 0 {
				return errors.New("distributed.prefetch_max_doc_ids must be greater than zero when distributed.prefetch_full_logs is true")
			}
		}
		if c.Distributed.FullLogCacheTTL <= 0 {
			return errors.New("distributed.full_log_cache_ttl must be greater than zero when distributed.enabled is true")
		}
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
	if c.Elasticsearch.WriteHistory && c.Elasticsearch.Index == "" {
		return errors.New("elasticsearch.index must not be empty when elasticsearch.write_history_index is true")
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
	switch c.Engine.InputMode {
	case "organization_payload", "redis_stream":
	default:
		return fmt.Errorf("engine.input_mode %q is not supported", c.Engine.InputMode)
	}
	if c.Engine.InputWindow <= 0 {
		return errors.New("engine.input_window must be greater than zero")
	}
	if c.Engine.InputMode == "redis_stream" && len(c.Engine.GroupByFields) == 0 {
		return errors.New("engine.group_by_fields must contain at least one field when engine.input_mode is redis_stream")
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
	if c.Engine.ParallelCorrelation.Enabled {
		if c.Engine.ParallelCorrelation.MinLogs <= 0 {
			return errors.New("engine.parallel_correlation.min_logs must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.TargetLogsPerShard <= 0 {
			return errors.New("engine.parallel_correlation.target_logs_per_shard must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.MaxWorkers <= 1 {
			return errors.New("engine.parallel_correlation.max_workers must be greater than one when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.DistributedTargetShardDuration <= 0 {
			return errors.New("engine.parallel_correlation.distributed_target_shard_duration must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.DistributedShardTimeout <= 0 {
			return errors.New("engine.parallel_correlation.distributed_shard_timeout must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.DistributedRunReserve <= 0 {
			return errors.New("engine.parallel_correlation.distributed_run_reserve must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.DistributedMinShardsPerWorker <= 0 {
			return errors.New("engine.parallel_correlation.distributed_min_shards_per_worker must be greater than zero when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.DistributedMaxShardsPerWorker < c.Engine.ParallelCorrelation.DistributedMinShardsPerWorker {
			return errors.New("engine.parallel_correlation.distributed_max_shards_per_worker must be greater than or equal to engine.parallel_correlation.distributed_min_shards_per_worker when engine.parallel_correlation.enabled is true")
		}
		if c.Engine.ParallelCorrelation.ShardPollInterval <= 0 {
			return errors.New("engine.parallel_correlation.shard_poll_interval must be greater than zero when engine.parallel_correlation.enabled is true")
		}
	}
	if c.MongoSync.Enabled {
		if c.MongoSync.URI == "" {
			return errors.New("mongo_sync.uri must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.Database == "" {
			return errors.New("mongo_sync.database must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.RulesCollection == "" {
			return errors.New("mongo_sync.rules_collection must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.StateCollection == "" {
			return errors.New("mongo_sync.state_collection must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.StateName == "" {
			return errors.New("mongo_sync.state_name must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.UseSnapshot || c.MongoSync.WriteSnapshot {
			if c.MongoSync.SnapshotCollection == "" {
				return errors.New("mongo_sync.snapshot_collection must not be empty when snapshot sync is enabled")
			}
			if c.MongoSync.SnapshotName == "" {
				return errors.New("mongo_sync.snapshot_name must not be empty when snapshot sync is enabled")
			}
		}
		if c.MongoSync.RedisNotify.Enabled {
			if c.MongoSync.RedisNotify.Channel == "" {
				return errors.New("mongo_sync.redis_notify.channel must not be empty when redis notify is enabled")
			}
			if c.MongoSync.RedisNotify.ReconnectDelay <= 0 {
				return errors.New("mongo_sync.redis_notify.reconnect_delay must be greater than zero when redis notify is enabled")
			}
		}
		if c.MongoSync.Timeout <= 0 {
			return errors.New("mongo_sync.timeout must be greater than zero when mongo_sync.enabled is true")
		}
	}
	switch c.Fetcher.Mode {
	case "mock":
	case "elasticsearch":
		if c.Fetcher.Index == "" {
			return errors.New("fetcher.index must not be empty when fetcher.mode is elasticsearch")
		}
		if c.Fetcher.GroupedLookupBatchSize <= 0 {
			return errors.New("fetcher.grouped_lookup_batch_size must be greater than zero when fetcher.mode is elasticsearch")
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
