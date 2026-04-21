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

type SignalCatalogConfig struct {
	Files []string `yaml:"files"`
}

type TopologyConfig struct {
	File string `yaml:"file"`
}

type StorageConfig struct {
	ResultsFile    string `yaml:"results_file"`
	CheckpointFile string `yaml:"checkpoint_file"`
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
	Elasticsearch ElasticsearchConfig `yaml:"elasticsearch"`
	Rules         RulesConfig         `yaml:"rules"`
	SignalCatalog SignalCatalogConfig `yaml:"signal_catalog"`
	Topology      TopologyConfig      `yaml:"topology"`
	Storage       StorageConfig       `yaml:"storage"`
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
	}
}

func (c *Config) resolvePaths(baseDir string) {
	c.Rules.File = resolvePath(baseDir, c.Rules.File)
	for idx, file := range c.SignalCatalog.Files {
		c.SignalCatalog.Files[idx] = resolvePath(baseDir, file)
	}
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
	c.Elasticsearch.Username = strings.TrimSpace(c.Elasticsearch.Username)
	c.Elasticsearch.Password = strings.TrimSpace(c.Elasticsearch.Password)
	c.Elasticsearch.APIKey = strings.TrimSpace(c.Elasticsearch.APIKey)
	c.Elasticsearch.CorrelationIndex = strings.TrimSpace(c.Elasticsearch.CorrelationIndex)
	c.Elasticsearch.SourceIndexFallback = strings.TrimSpace(c.Elasticsearch.SourceIndexFallback)
	c.Rules.File = strings.TrimSpace(c.Rules.File)
	c.SignalCatalog.Files = trimNonEmptyStrings(c.SignalCatalog.Files)
	c.Topology.File = strings.TrimSpace(c.Topology.File)
	c.Storage.ResultsFile = strings.TrimSpace(c.Storage.ResultsFile)
	c.Storage.CheckpointFile = strings.TrimSpace(c.Storage.CheckpointFile)
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
