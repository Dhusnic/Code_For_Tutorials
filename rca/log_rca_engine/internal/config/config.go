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
	Interval   time.Duration `yaml:"interval"`
	RunTimeout time.Duration `yaml:"run_timeout"`
}

type AutoscalingSchedulerConfig struct {
	MinInterval              time.Duration `yaml:"min_interval"`
	MaxInterval              time.Duration `yaml:"max_interval"`
	TimeoutRatio             float64       `yaml:"timeout_ratio"`
	TargetCycleUtilization   float64       `yaml:"target_cycle_utilization"`
	TimeoutScaleUpMultiplier float64       `yaml:"timeout_scale_up_multiplier"`
}

type AutoscalingReaderConfig struct {
	MinPageSize      int `yaml:"min_page_size"`
	MaxPageSize      int `yaml:"max_page_size"`
	MaxPagesPerCycle int `yaml:"max_pages_per_cycle"`
}

type AutoscalingConfig struct {
	Enabled                 bool                       `yaml:"enabled"`
	InputBasis              string                     `yaml:"input_basis"`
	InputLowWatermark       int                        `yaml:"input_low_watermark"`
	InputHighWatermark      int                        `yaml:"input_high_watermark"`
	ScaleDownCooldownCycles int                        `yaml:"scale_down_cooldown_cycles"`
	Scheduler               AutoscalingSchedulerConfig `yaml:"scheduler"`
	Reader                  AutoscalingReaderConfig    `yaml:"reader"`
}

type ElasticsearchConfig struct {
	Addresses           []string      `yaml:"addresses"`
	Username            string        `yaml:"username"`
	Password            string        `yaml:"password"`
	APIKey              string        `yaml:"api_key"`
	CorrelationIndex    string        `yaml:"correlation_index"`
	SourceIndexFallback string        `yaml:"source_index_fallback"`
	RequestTimeout      time.Duration `yaml:"request_timeout"`
	PageSize            int           `yaml:"page_size"`
	ReplayWindow        time.Duration `yaml:"replay_window"`
}

type RulesConfig struct {
	File string `yaml:"file"`
}

type TopologyConfig struct {
	File string `yaml:"file"`
}

type StorageConfig struct {
	ResultsFile    string `yaml:"results_file"`
	CheckpointFile string `yaml:"checkpoint_file"`
}

type MongoSyncConfig struct {
	Enabled            bool              `yaml:"enabled"`
	URI                string            `yaml:"uri"`
	Database           string            `yaml:"database"`
	RulesCollection    string            `yaml:"rules_collection"`
	TopologyCollection string            `yaml:"topology_collection"`
	ResultsCollection  string            `yaml:"results_collection"`
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
	Address        string        `yaml:"address"`
	Username       string        `yaml:"username"`
	Password       string        `yaml:"password"`
	DB             int           `yaml:"db"`
	Channel        string        `yaml:"channel"`
	ReconnectDelay time.Duration `yaml:"reconnect_delay"`
}

type ScoringWeightsConfig struct {
	SequenceMatch    float64 `yaml:"sequence_match"`
	DependencyMatch  float64 `yaml:"dependency_match"`
	TimeProximity    float64 `yaml:"time_proximity"`
	SignalSeverity   float64 `yaml:"signal_severity"`
	RuleCompleteness float64 `yaml:"rule_completeness"`
}

type ScoringConfig struct {
	ConfidenceThreshold       float64              `yaml:"confidence_threshold"`
	ProbableCauseMinThreshold float64              `yaml:"probable_cause_min_threshold"`
	NearbyLogTriggerThreshold float64              `yaml:"nearby_log_trigger_threshold"`
	Weights                   ScoringWeightsConfig `yaml:"weights"`
}

type OpenAIConfig struct {
	Enabled              bool          `yaml:"enabled"`
	BaseURL              string        `yaml:"base_url"`
	APIKey               string        `yaml:"api_key"`
	Model                string        `yaml:"model"`
	RequestTimeout       time.Duration `yaml:"request_timeout"`
	NeighborhoodLogLimit int           `yaml:"neighborhood_log_limit"`
	MaxOutputTokens      int           `yaml:"max_output_tokens"`
}

type Config struct {
	ServiceName   string              `yaml:"service_name"`
	Logging       LoggingConfig       `yaml:"logging"`
	Scheduler     SchedulerConfig     `yaml:"scheduler"`
	Autoscaling   AutoscalingConfig   `yaml:"autoscaling"`
	Elasticsearch ElasticsearchConfig `yaml:"elasticsearch"`
	Rules         RulesConfig         `yaml:"rules"`
	Topology      TopologyConfig      `yaml:"topology"`
	Storage       StorageConfig       `yaml:"storage"`
	MongoSync     MongoSyncConfig     `yaml:"mongo_sync"`
	Scoring       ScoringConfig       `yaml:"scoring"`
	OpenAI        OpenAIConfig        `yaml:"openai"`
}

func Load(path string) (Config, error) {
	cfg := defaultConfig()
	if strings.TrimSpace(path) != "" {
		payload, err := os.ReadFile(filepath.Clean(path))
		if err != nil {
			return Config{}, fmt.Errorf("read config file: %w", err)
		}
		if err := yaml.Unmarshal(payload, &cfg); err != nil {
			return Config{}, fmt.Errorf("parse config file: %w", err)
		}
		baseDir := filepath.Dir(filepath.Clean(path))
		cfg.resolvePaths(baseDir)
	}
	cfg.normalize()
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func defaultConfig() Config {
	return Config{
		ServiceName: "log-rca-engine",
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
		Scheduler: SchedulerConfig{
			Interval:   time.Minute,
			RunTimeout: 50 * time.Second,
		},
		Autoscaling: AutoscalingConfig{
			Enabled:                 false,
			InputBasis:              "correlation_events",
			InputLowWatermark:       100,
			InputHighWatermark:      5000,
			ScaleDownCooldownCycles: 3,
			Scheduler: AutoscalingSchedulerConfig{
				MinInterval:              20 * time.Second,
				MaxInterval:              90 * time.Second,
				TimeoutRatio:             0.9,
				TargetCycleUtilization:   0.8,
				TimeoutScaleUpMultiplier: 1.5,
			},
			Reader: AutoscalingReaderConfig{
				MinPageSize:      100,
				MaxPageSize:      1000,
				MaxPagesPerCycle: 10,
			},
		},
		Elasticsearch: ElasticsearchConfig{
			Addresses:           []string{"http://localhost:9200"},
			CorrelationIndex:    "rca_correlated_incidents_current*",
			SourceIndexFallback: "*",
			RequestTimeout:      20 * time.Second,
			PageSize:            100,
			ReplayWindow:        time.Hour,
		},
		Scoring: ScoringConfig{
			ConfidenceThreshold:       7,
			ProbableCauseMinThreshold: 0,
			NearbyLogTriggerThreshold: 5.5,
			Weights: ScoringWeightsConfig{
				SequenceMatch:    0.30,
				DependencyMatch:  0.25,
				TimeProximity:    0.15,
				SignalSeverity:   0.15,
				RuleCompleteness: 0.15,
			},
		},
		OpenAI: OpenAIConfig{
			BaseURL:              "https://api.openai.com/v1",
			Model:                "gpt-4o-mini",
			RequestTimeout:       30 * time.Second,
			NeighborhoodLogLimit: 50,
			MaxOutputTokens:      1200,
		},
		MongoSync: MongoSyncConfig{
			Database:           "dhusnic_test_db",
			RulesCollection:    "correlation_rules",
			TopologyCollection: "topology_data",
			ResultsCollection:  "rca_results",
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
	}
}

func (c *Config) resolvePaths(baseDir string) {
	c.Rules.File = resolvePath(baseDir, c.Rules.File)
	c.Topology.File = resolvePath(baseDir, c.Topology.File)
	c.Storage.ResultsFile = resolvePath(baseDir, c.Storage.ResultsFile)
	c.Storage.CheckpointFile = resolvePath(baseDir, c.Storage.CheckpointFile)
}

func resolvePath(baseDir, value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" || filepath.IsAbs(trimmed) {
		return trimmed
	}
	return filepath.Clean(filepath.Join(baseDir, trimmed))
}

func (c *Config) normalize() {
	c.ServiceName = strings.TrimSpace(c.ServiceName)
	c.Logging.Level = strings.TrimSpace(c.Logging.Level)
	c.Logging.Format = strings.TrimSpace(strings.ToLower(c.Logging.Format))
	c.Autoscaling.InputBasis = strings.TrimSpace(strings.ToLower(c.Autoscaling.InputBasis))
	c.Elasticsearch.Username = strings.TrimSpace(c.Elasticsearch.Username)
	c.Elasticsearch.Password = strings.TrimSpace(c.Elasticsearch.Password)
	c.Elasticsearch.APIKey = strings.TrimSpace(c.Elasticsearch.APIKey)
	c.Elasticsearch.CorrelationIndex = strings.TrimSpace(c.Elasticsearch.CorrelationIndex)
	c.Elasticsearch.SourceIndexFallback = strings.TrimSpace(c.Elasticsearch.SourceIndexFallback)
	c.Rules.File = strings.TrimSpace(c.Rules.File)
	c.Topology.File = strings.TrimSpace(c.Topology.File)
	c.Storage.ResultsFile = strings.TrimSpace(c.Storage.ResultsFile)
	c.Storage.CheckpointFile = strings.TrimSpace(c.Storage.CheckpointFile)
	c.MongoSync.URI = strings.TrimSpace(c.MongoSync.URI)
	c.MongoSync.Database = strings.TrimSpace(c.MongoSync.Database)
	c.MongoSync.RulesCollection = strings.TrimSpace(c.MongoSync.RulesCollection)
	c.MongoSync.TopologyCollection = strings.TrimSpace(c.MongoSync.TopologyCollection)
	c.MongoSync.ResultsCollection = strings.TrimSpace(c.MongoSync.ResultsCollection)
	c.MongoSync.StateCollection = strings.TrimSpace(c.MongoSync.StateCollection)
	c.MongoSync.StateName = strings.TrimSpace(c.MongoSync.StateName)
	c.MongoSync.SnapshotCollection = strings.TrimSpace(c.MongoSync.SnapshotCollection)
	c.MongoSync.SnapshotName = strings.TrimSpace(c.MongoSync.SnapshotName)
	c.MongoSync.RedisNotify.Address = strings.TrimSpace(c.MongoSync.RedisNotify.Address)
	c.MongoSync.RedisNotify.Username = strings.TrimSpace(c.MongoSync.RedisNotify.Username)
	c.MongoSync.RedisNotify.Channel = strings.TrimSpace(c.MongoSync.RedisNotify.Channel)
	c.OpenAI.BaseURL = strings.TrimRight(strings.TrimSpace(c.OpenAI.BaseURL), "/")
	c.OpenAI.APIKey = strings.TrimSpace(c.OpenAI.APIKey)
	c.OpenAI.Model = strings.TrimSpace(c.OpenAI.Model)

	addresses := make([]string, 0, len(c.Elasticsearch.Addresses))
	for _, address := range c.Elasticsearch.Addresses {
		trimmed := strings.TrimSpace(address)
		if trimmed != "" {
			addresses = append(addresses, trimmed)
		}
	}
	c.Elasticsearch.Addresses = addresses
	if c.Autoscaling.InputBasis == "" {
		c.Autoscaling.InputBasis = "correlation_events"
	}
	if c.Autoscaling.InputLowWatermark <= 0 {
		c.Autoscaling.InputLowWatermark = 100
	}
	if c.Autoscaling.InputHighWatermark <= 0 {
		c.Autoscaling.InputHighWatermark = 5000
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
	if c.Autoscaling.Reader.MinPageSize <= 0 {
		c.Autoscaling.Reader.MinPageSize = 100
	}
	if c.Autoscaling.Reader.MaxPageSize <= 0 {
		c.Autoscaling.Reader.MaxPageSize = 1000
	}
	if c.Autoscaling.Reader.MaxPagesPerCycle <= 0 {
		c.Autoscaling.Reader.MaxPagesPerCycle = 10
	}
}

func trimNonEmptyStrings(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
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
	if c.Scheduler.RunTimeout > c.Scheduler.Interval {
		return errors.New("scheduler.run_timeout must be less than or equal to scheduler.interval")
	}
	if c.Autoscaling.InputBasis != "correlation_events" {
		return errors.New("autoscaling.input_basis must be correlation_events")
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
	if c.Autoscaling.Reader.MinPageSize < 10 || c.Autoscaling.Reader.MinPageSize > 10000 {
		return errors.New("autoscaling.reader.min_page_size must be between 10 and 10000")
	}
	if c.Autoscaling.Reader.MaxPageSize < 10 || c.Autoscaling.Reader.MaxPageSize > 10000 {
		return errors.New("autoscaling.reader.max_page_size must be between 10 and 10000")
	}
	if c.Autoscaling.Reader.MinPageSize > c.Autoscaling.Reader.MaxPageSize {
		return errors.New("autoscaling.reader.min_page_size must be less than or equal to autoscaling.reader.max_page_size")
	}
	if c.Autoscaling.Reader.MaxPagesPerCycle <= 0 {
		return errors.New("autoscaling.reader.max_pages_per_cycle must be greater than zero")
	}
	if len(c.Elasticsearch.Addresses) == 0 {
		return errors.New("elasticsearch.addresses must contain at least one value")
	}
	if c.Elasticsearch.CorrelationIndex == "" {
		return errors.New("elasticsearch.correlation_index must not be empty")
	}
	if c.Elasticsearch.RequestTimeout <= 0 {
		return errors.New("elasticsearch.request_timeout must be greater than zero")
	}
	if c.Elasticsearch.PageSize <= 0 {
		return errors.New("elasticsearch.page_size must be greater than zero")
	}
	if c.Elasticsearch.ReplayWindow < 0 {
		return errors.New("elasticsearch.replay_window must not be negative")
	}
	if c.Rules.File == "" {
		return errors.New("rules.file must not be empty")
	}
	if c.Topology.File == "" {
		return errors.New("topology.file must not be empty")
	}
	if c.Storage.ResultsFile == "" {
		return errors.New("storage.results_file must not be empty")
	}
	if c.Storage.CheckpointFile == "" {
		return errors.New("storage.checkpoint_file must not be empty")
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
		if c.MongoSync.TopologyCollection == "" {
			return errors.New("mongo_sync.topology_collection must not be empty when mongo_sync.enabled is true")
		}
		if c.MongoSync.ResultsCollection == "" {
			return errors.New("mongo_sync.results_collection must not be empty when mongo_sync.enabled is true")
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
			if c.MongoSync.RedisNotify.Address == "" {
				return errors.New("mongo_sync.redis_notify.address must not be empty when redis notify is enabled")
			}
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
	if c.Scoring.ConfidenceThreshold <= 0 || c.Scoring.ConfidenceThreshold > 10 {
		return errors.New("scoring.confidence_threshold must be between 0 and 10")
	}
	if c.Scoring.ProbableCauseMinThreshold < 0 || c.Scoring.ProbableCauseMinThreshold > 10 {
		return errors.New("scoring.probable_cause_min_threshold must be between 0 and 10")
	}
	if c.Scoring.ProbableCauseMinThreshold > c.Scoring.ConfidenceThreshold {
		return errors.New("scoring.probable_cause_min_threshold must be less than or equal to scoring.confidence_threshold")
	}
	if c.Scoring.NearbyLogTriggerThreshold < 0 || c.Scoring.NearbyLogTriggerThreshold > 10 {
		return errors.New("scoring.nearby_log_trigger_threshold must be between 0 and 10")
	}
	weights := c.Scoring.Weights
	if weights.SequenceMatch <= 0 || weights.DependencyMatch <= 0 || weights.TimeProximity <= 0 || weights.SignalSeverity <= 0 || weights.RuleCompleteness <= 0 {
		return errors.New("all scoring weights must be greater than zero")
	}
	if c.OpenAI.Enabled {
		if c.OpenAI.BaseURL == "" {
			return errors.New("openai.base_url must not be empty when enabled")
		}
		if c.OpenAI.APIKey == "" {
			return errors.New("openai.api_key must not be empty when enabled")
		}
		if c.OpenAI.Model == "" {
			return errors.New("openai.model must not be empty when enabled")
		}
		if c.OpenAI.RequestTimeout <= 0 {
			return errors.New("openai.request_timeout must be greater than zero when enabled")
		}
	}
	if c.OpenAI.NeighborhoodLogLimit < 0 {
		return errors.New("openai.neighborhood_log_limit must not be negative")
	}
	if c.OpenAI.MaxOutputTokens < 0 {
		return errors.New("openai.max_output_tokens must not be negative")
	}
	return nil
}
