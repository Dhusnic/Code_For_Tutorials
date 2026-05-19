package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

// ElasticsearchConfig stores Elasticsearch connection settings.
type ElasticsearchConfig struct {
	Hosts                 []string
	Username              *string
	Password              *string
	APIKey                *string
	VerifyCerts           bool
	RequestTimeoutSeconds int
}

// CheckpointConfig stores checkpoint persistence settings.
type CheckpointConfig struct {
	Provider           string
	Path               string
	RedisURL           *string
	RedisPrefix        string
	PostgresDSN        *string
	PostgresTable      string
	ElasticsearchIndex string
}

// LoggingConfig stores application logging configuration.
type LoggingConfig struct {
	Level              string
	JSON               bool
	LogUnmatchedEvents bool
}

// InputConfig stores the primary event source selection.
type InputConfig struct {
	Source string
}

// KafkaConfig stores Kafka consumer settings used when input.source=kafka.
type KafkaConfig struct {
	Brokers                  []string
	Topic                    string
	GroupID                  string
	ClientID                 string
	StartOffset              string
	BatchSize                int
	ReadBatchTimeoutSeconds  float64
	MaxWaitSeconds           float64
	SessionTimeoutSeconds    int
	RebalanceTimeoutSeconds  int
	HeartbeatIntervalSeconds int
	MinBytes                 int
	MaxBytes                 int
	CommitRetries            int
	SourceIndex              string
	SourceIndexField         string
	DocumentIDPrefix         string
	MetadataField            string
	EventOriginalField       string
	IndexUnmatchedEvents     bool
	SecurityProtocol         string
	SASLMechanism            string
	Username                 *string
	Password                 *string
	TLSEnabled               bool
	InsecureSkipVerify       bool
	CAFile                   string
}

// SignalStreamConfig stores Redis stream publication settings for compact signal events.
type SignalStreamConfig struct {
	Enabled                bool
	Address                string
	Username               *string
	Password               *string
	DB                     int
	DialTimeoutSeconds     int
	ReadTimeoutSeconds     int
	WriteTimeoutSeconds    int
	StreamKey              string
	MaxLen                 int64
	OrganizationFieldPath  string
	PublishDedupEnabled    bool
	PublishDedupTTLSeconds int
	PublishDedupKeyPrefix  string
}

// ServiceConfig stores service-specific processing settings.
type ServiceConfig struct {
	Name          string
	Enabled       bool
	RuleFile      string
	SourceIndices []string
	StartTime     *string
	Query         map[string]any
}

// PipelineConfig stores pipeline runtime behavior settings.
type PipelineConfig struct {
	BatchSize                           int
	BulkMaxBatchBytes                   int
	WorkerCount                         int
	WorkerID                            int
	BulkWorkerCount                     int
	BulkQueueSize                       int
	BulkQueueEnqueueTimeoutSeconds      float64
	BulkSpoolEnabled                    bool
	BulkSpoolDirectory                  string
	BulkSpoolMaxBytes                   int
	BulkSpoolReplayIntervalSeconds      float64
	BulkAutoscalingEnabled              bool
	BulkAutoscalingMinWorkers           int
	BulkAutoscalingMaxWorkers           int
	BulkAutoscalingScaleUpQueueRatio    float64
	BulkAutoscalingScaleDownQueueRatio  float64
	BulkAutoscalingCPULimitPercent      float64
	BulkAutoscalingMemoryLimitPercent   float64
	BulkAutoscalingCheckIntervalSeconds float64
	BulkAutoscalingCooldownSeconds      float64
	BatchSizeMode                       string
	DynamicBatchMinSize                 int
	DynamicBatchMaxSize                 int
	DynamicBatchLookbackSeconds         int
	DynamicBatchTargetWindowSeconds     float64
	DynamicBatchSmoothingAlpha          float64
	AutoscalingEnabled                  bool
	AutoscalingTargetEventsPerWorkerSec float64
	AutoscalingMinWorkers               int
	AutoscalingMaxWorkers               int
	AutoscalingLagScaleUpSeconds        float64
	AutoscalingLagScaleDownSeconds      float64
	PollIntervalSeconds                 int
	TimestampField                      string
	StartTime                           string
	SourceIndices                       []string
	WriteToSourceIndex                  bool
	WriteToTargetIndex                  bool
	TargetSuffix                        string
	DeadLetterSuffix                    string
	RetryMaxAttempts                    int
	RetryInitialBackoffSeconds          float64
	RetryBackoffMultiplier              float64
	SignalMaxPerEvent                   int
	SignalSelectHighestOnly             bool
	VendorAnchorEnforcementEnabled      bool
	Services                            []ServiceConfig
}

// RuleLearningConfig stores auto-generation settings for unclassified critical signals.
type RuleLearningConfig struct {
	Enabled                 bool
	Mode                    string
	OutputDirectory         string
	MinOccurrences          int
	MaxCandidatesPerService int
	MinKeywordCount         int
	MaxKeywordsPerSignal    int
	ConditionField          string
	ConditionOp             string
	Level                   string
}

// AppConfig stores the root application configuration.
type AppConfig struct {
	Elasticsearch  ElasticsearchConfig
	Checkpoints    CheckpointConfig
	Logging        LoggingConfig
	Input          InputConfig
	Kafka          KafkaConfig
	SignalStream   SignalStreamConfig
	Pipeline       PipelineConfig
	RulesDirectory string
	RuleLearning   RuleLearningConfig
}

var (
	sizeUnits = map[string]int{
		"b":  1,
		"kb": 1024,
		"mb": 1024 * 1024,
		"gb": 1024 * 1024 * 1024,
		"tb": 1024 * 1024 * 1024 * 1024,
	}
	durationUnitsSeconds = map[string]float64{
		"ms": 0.001,
		"s":  1.0,
		"m":  60.0,
		"h":  3600.0,
		"d":  86400.0,
	}
	sizePattern     = regexp.MustCompile(`(?i)^\s*(\d+(?:\.\d+)?)\s*(b|kb|mb|gb|tb)\s*$`)
	durationPattern = regexp.MustCompile(`(?i)^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)\s*$`)
	numberPattern   = regexp.MustCompile(`^\d+(?:\.\d+)?$`)
	splitHostsRegex = regexp.MustCompile(`[;,]`)
)

// LoadAppConfig loads the application configuration from YAML.
func LoadAppConfig(path string) (AppConfig, error) {
	configPath, err := filepath.Abs(path)
	if err != nil {
		return AppConfig{}, err
	}

	contents, err := os.ReadFile(configPath)
	if err != nil {
		return AppConfig{}, err
	}

	var raw map[string]any
	if err := yaml.Unmarshal(contents, &raw); err != nil {
		return AppConfig{}, err
	}
	if raw == nil {
		return AppConfig{}, errors.New("Configuration root must be a mapping")
	}

	esValue, err := requireKey(raw, "elasticsearch")
	if err != nil {
		return AppConfig{}, err
	}
	esRaw, err := requireMapping(esValue, "elasticsearch")
	if err != nil {
		return AppConfig{}, err
	}

	pipelineValue, err := requireKey(raw, "pipeline")
	if err != nil {
		return AppConfig{}, err
	}
	pipeRaw, err := requireMapping(pipelineValue, "pipeline")
	if err != nil {
		return AppConfig{}, err
	}

	checkpointsRaw, err := optionalMapping(raw, "checkpoints")
	if err != nil {
		return AppConfig{}, err
	}
	loggingRaw, err := optionalMapping(raw, "logging")
	if err != nil {
		return AppConfig{}, err
	}
	inputRaw, err := optionalMapping(raw, "input")
	if err != nil {
		return AppConfig{}, err
	}
	kafkaRaw, err := optionalMapping(raw, "kafka")
	if err != nil {
		return AppConfig{}, err
	}
	ruleLearningRaw, err := optionalMapping(raw, "rule_learning")
	if err != nil {
		return AppConfig{}, err
	}
	signalStreamRaw, err := optionalMapping(raw, "signal_stream")
	if err != nil {
		return AppConfig{}, err
	}

	workerCount, workerID, err := resolveWorkerRuntime(pipeRaw)
	if err != nil {
		return AppConfig{}, err
	}
	esHosts, err := resolveElasticsearchHosts(esRaw)
	if err != nil {
		return AppConfig{}, err
	}
	services, err := loadServices(pipeRaw)
	if err != nil {
		return AppConfig{}, err
	}

	requestTimeoutSeconds, err := coerceSecondsInt(getOrDefault(esRaw, "request_timeout_seconds", 30), "elasticsearch.request_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	bulkMaxBatchBytes, err := coerceSizeBytes(getOrDefault(pipeRaw, "bulk_max_batch_bytes", 8*1024*1024), "pipeline.bulk_max_batch_bytes")
	if err != nil {
		return AppConfig{}, err
	}
	bulkQueueEnqueueTimeoutSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "bulk_queue_enqueue_timeout_seconds", 0.25), "pipeline.bulk_queue_enqueue_timeout_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	bulkSpoolMaxBytes, err := coerceSizeBytes(getOrDefault(pipeRaw, "bulk_spool_max_bytes", 10*1024*1024*1024), "pipeline.bulk_spool_max_bytes")
	if err != nil {
		return AppConfig{}, err
	}
	bulkSpoolReplayIntervalSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "bulk_spool_replay_interval_seconds", 1.0), "pipeline.bulk_spool_replay_interval_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	bulkAutoscalingCheckIntervalSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "bulk_autoscaling_check_interval_seconds", 2.0), "pipeline.bulk_autoscaling_check_interval_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	bulkAutoscalingCooldownSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "bulk_autoscaling_cooldown_seconds", 10.0), "pipeline.bulk_autoscaling_cooldown_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	dynamicBatchLookbackSeconds, err := coerceSecondsInt(getOrDefault(pipeRaw, "dynamic_batch_lookback_seconds", 30), "pipeline.dynamic_batch_lookback_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	dynamicBatchTargetWindowSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "dynamic_batch_target_window_seconds", 1.0), "pipeline.dynamic_batch_target_window_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	autoscalingLagScaleUpSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "autoscaling_lag_scale_up_seconds", 60.0), "pipeline.autoscaling_lag_scale_up_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	autoscalingLagScaleDownSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "autoscaling_lag_scale_down_seconds", 10.0), "pipeline.autoscaling_lag_scale_down_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	pollIntervalSeconds, err := coerceSecondsInt(getOrDefault(pipeRaw, "poll_interval_seconds", 10), "pipeline.poll_interval_seconds", 0)
	if err != nil {
		return AppConfig{}, err
	}
	retryInitialBackoffSeconds, err := coerceSecondsFloat(getOrDefault(pipeRaw, "retry_initial_backoff_seconds", 1.0), "pipeline.retry_initial_backoff_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	rulesDirectory, err := resolvePathFromConfig(configPath, stringify(getOrDefault(raw, "rules_directory", "rules")))
	if err != nil {
		return AppConfig{}, err
	}
	signalStreamDialTimeout, err := coerceSecondsInt(getOrDefault(signalStreamRaw, "dial_timeout_seconds", 5), "signal_stream.dial_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	signalStreamReadTimeout, err := coerceSecondsInt(getOrDefault(signalStreamRaw, "read_timeout_seconds", 3), "signal_stream.read_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	signalStreamWriteTimeout, err := coerceSecondsInt(getOrDefault(signalStreamRaw, "write_timeout_seconds", 3), "signal_stream.write_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	signalStreamDedupTTLSeconds, err := coerceSecondsInt(getOrDefault(signalStreamRaw, "publish_dedup_ttl_seconds", 86400), "signal_stream.publish_dedup_ttl_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	kafkaBatchTimeoutSeconds, err := coerceSecondsFloat(getOrDefault(kafkaRaw, "read_batch_timeout_seconds", 2.0), "kafka.read_batch_timeout_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	kafkaMaxWaitSeconds, err := coerceSecondsFloat(getOrDefault(kafkaRaw, "max_wait_seconds", 1.0), "kafka.max_wait_seconds")
	if err != nil {
		return AppConfig{}, err
	}
	kafkaSessionTimeoutSeconds, err := coerceSecondsInt(getOrDefault(kafkaRaw, "session_timeout_seconds", 45), "kafka.session_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	kafkaRebalanceTimeoutSeconds, err := coerceSecondsInt(getOrDefault(kafkaRaw, "rebalance_timeout_seconds", 60), "kafka.rebalance_timeout_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	kafkaHeartbeatIntervalSeconds, err := coerceSecondsInt(getOrDefault(kafkaRaw, "heartbeat_interval_seconds", 3), "kafka.heartbeat_interval_seconds", 1)
	if err != nil {
		return AppConfig{}, err
	}
	kafkaMaxBytes, err := coerceSizeBytes(getOrDefault(kafkaRaw, "max_bytes", 8*1024*1024), "kafka.max_bytes")
	if err != nil {
		return AppConfig{}, err
	}
	kafkaBrokers := normalizeElasticsearchHosts(kafkaRaw["brokers"])
	for index, broker := range kafkaBrokers {
		kafkaBrokers[index] = strings.TrimPrefix(strings.TrimPrefix(broker, "http://"), "https://")
	}
	kafkaCAFile := stringify(getOrDefault(kafkaRaw, "ca_file", ""))
	if strings.TrimSpace(kafkaCAFile) != "" {
		kafkaCAFile, err = resolvePathFromConfig(configPath, kafkaCAFile)
		if err != nil {
			return AppConfig{}, err
		}
	}

	return AppConfig{
		Elasticsearch: ElasticsearchConfig{
			Hosts:                 esHosts,
			Username:              stringPointer(esRaw["username"]),
			Password:              stringPointer(esRaw["password"]),
			APIKey:                stringPointer(esRaw["api_key"]),
			VerifyCerts:           boolDefault(esRaw, "verify_certs", true),
			RequestTimeoutSeconds: requestTimeoutSeconds,
		},
		Checkpoints: CheckpointConfig{
			Provider:           stringify(getOrDefault(checkpointsRaw, "provider", "file")),
			Path:               stringify(getOrDefault(checkpointsRaw, "path", "state/checkpoints.json")),
			RedisURL:           stringPointer(checkpointsRaw["redis_url"]),
			RedisPrefix:        stringify(getOrDefault(checkpointsRaw, "redis_prefix", "rca:checkpoint:")),
			PostgresDSN:        stringPointer(checkpointsRaw["postgres_dsn"]),
			PostgresTable:      stringify(getOrDefault(checkpointsRaw, "postgres_table", "rca_checkpoints")),
			ElasticsearchIndex: stringify(getOrDefault(checkpointsRaw, "elasticsearch_index", "rca-checkpoints")),
		},
		Logging: LoggingConfig{
			Level:              stringify(getOrDefault(loggingRaw, "level", "INFO")),
			JSON:               boolDefault(loggingRaw, "json", true),
			LogUnmatchedEvents: boolDefault(loggingRaw, "log_unmatched_events", false),
		},
		Input: InputConfig{
			Source: stringify(getOrDefault(inputRaw, "source", "elasticsearch")),
		},
		Kafka: KafkaConfig{
			Brokers:                  kafkaBrokers,
			Topic:                    stringify(getOrDefault(kafkaRaw, "topic", "")),
			GroupID:                  stringify(getOrDefault(kafkaRaw, "group_id", "")),
			ClientID:                 stringify(getOrDefault(kafkaRaw, "client_id", "signalizing-engine")),
			StartOffset:              stringify(getOrDefault(kafkaRaw, "start_offset", "latest")),
			BatchSize:                intDefault(kafkaRaw, "batch_size", intDefault(pipeRaw, "batch_size", 2000)),
			ReadBatchTimeoutSeconds:  kafkaBatchTimeoutSeconds,
			MaxWaitSeconds:           kafkaMaxWaitSeconds,
			SessionTimeoutSeconds:    kafkaSessionTimeoutSeconds,
			RebalanceTimeoutSeconds:  kafkaRebalanceTimeoutSeconds,
			HeartbeatIntervalSeconds: kafkaHeartbeatIntervalSeconds,
			MinBytes:                 intDefault(kafkaRaw, "min_bytes", 1),
			MaxBytes:                 kafkaMaxBytes,
			CommitRetries:            intDefault(kafkaRaw, "commit_retries", 3),
			SourceIndex:              stringify(getOrDefault(kafkaRaw, "source_index", "")),
			SourceIndexField:         stringify(getOrDefault(kafkaRaw, "source_index_field", "")),
			DocumentIDPrefix:         stringify(getOrDefault(kafkaRaw, "document_id_prefix", "kafka")),
			MetadataField:            stringify(getOrDefault(kafkaRaw, "metadata_field", "kafka")),
			EventOriginalField:       stringify(getOrDefault(kafkaRaw, "event_original_field", "event.original")),
			IndexUnmatchedEvents:     boolDefault(kafkaRaw, "index_unmatched_events", true),
			SecurityProtocol:         stringify(getOrDefault(kafkaRaw, "security_protocol", "plaintext")),
			SASLMechanism:            stringify(getOrDefault(kafkaRaw, "sasl_mechanism", "")),
			Username:                 stringPointer(kafkaRaw["username"]),
			Password:                 stringPointer(kafkaRaw["password"]),
			TLSEnabled:               boolDefault(kafkaRaw, "tls_enabled", false),
			InsecureSkipVerify:       boolDefault(kafkaRaw, "insecure_skip_verify", false),
			CAFile:                   kafkaCAFile,
		},
		SignalStream: SignalStreamConfig{
			Enabled:                boolDefault(signalStreamRaw, "enabled", false),
			Address:                stringify(getOrDefault(signalStreamRaw, "address", "")),
			Username:               stringPointer(signalStreamRaw["username"]),
			Password:               stringPointer(signalStreamRaw["password"]),
			DB:                     intDefault(signalStreamRaw, "db", 0),
			DialTimeoutSeconds:     signalStreamDialTimeout,
			ReadTimeoutSeconds:     signalStreamReadTimeout,
			WriteTimeoutSeconds:    signalStreamWriteTimeout,
			StreamKey:              stringify(getOrDefault(signalStreamRaw, "stream_key", "Rca:signalized_log_events")),
			MaxLen:                 int64(intDefault(signalStreamRaw, "max_len", 100000)),
			OrganizationFieldPath:  stringify(getOrDefault(signalStreamRaw, "organization_field", "event.organization")),
			PublishDedupEnabled:    boolDefault(signalStreamRaw, "publish_dedup_enabled", false),
			PublishDedupTTLSeconds: signalStreamDedupTTLSeconds,
			PublishDedupKeyPrefix:  stringify(getOrDefault(signalStreamRaw, "publish_dedup_key_prefix", "rca:signal_stream:dedupe:")),
		},
		Pipeline: PipelineConfig{
			BatchSize:                           intDefault(pipeRaw, "batch_size", 2000),
			BulkMaxBatchBytes:                   bulkMaxBatchBytes,
			WorkerCount:                         workerCount,
			WorkerID:                            workerID,
			BulkWorkerCount:                     intDefault(pipeRaw, "bulk_worker_count", 4),
			BulkQueueSize:                       intDefault(pipeRaw, "bulk_queue_size", 32),
			BulkQueueEnqueueTimeoutSeconds:      bulkQueueEnqueueTimeoutSeconds,
			BulkSpoolEnabled:                    boolDefault(pipeRaw, "bulk_spool_enabled", false),
			BulkSpoolDirectory:                  stringify(getOrDefault(pipeRaw, "bulk_spool_directory", "state/bulk_spool")),
			BulkSpoolMaxBytes:                   bulkSpoolMaxBytes,
			BulkSpoolReplayIntervalSeconds:      bulkSpoolReplayIntervalSeconds,
			BulkAutoscalingEnabled:              boolDefault(pipeRaw, "bulk_autoscaling_enabled", false),
			BulkAutoscalingMinWorkers:           intDefault(pipeRaw, "bulk_autoscaling_min_workers", 2),
			BulkAutoscalingMaxWorkers:           intDefault(pipeRaw, "bulk_autoscaling_max_workers", 16),
			BulkAutoscalingScaleUpQueueRatio:    floatDefault(pipeRaw, "bulk_autoscaling_scale_up_queue_ratio", 0.75),
			BulkAutoscalingScaleDownQueueRatio:  floatDefault(pipeRaw, "bulk_autoscaling_scale_down_queue_ratio", 0.25),
			BulkAutoscalingCPULimitPercent:      floatDefault(pipeRaw, "bulk_autoscaling_cpu_limit_percent", 85.0),
			BulkAutoscalingMemoryLimitPercent:   floatDefault(pipeRaw, "bulk_autoscaling_memory_limit_percent", 85.0),
			BulkAutoscalingCheckIntervalSeconds: bulkAutoscalingCheckIntervalSeconds,
			BulkAutoscalingCooldownSeconds:      bulkAutoscalingCooldownSeconds,
			BatchSizeMode:                       stringify(getOrDefault(pipeRaw, "batch_size_mode", "static")),
			DynamicBatchMinSize:                 intDefault(pipeRaw, "dynamic_batch_min_size", 500),
			DynamicBatchMaxSize:                 intDefault(pipeRaw, "dynamic_batch_max_size", 10000),
			DynamicBatchLookbackSeconds:         dynamicBatchLookbackSeconds,
			DynamicBatchTargetWindowSeconds:     dynamicBatchTargetWindowSeconds,
			DynamicBatchSmoothingAlpha:          floatDefault(pipeRaw, "dynamic_batch_smoothing_alpha", 0.5),
			AutoscalingEnabled:                  boolDefault(pipeRaw, "autoscaling_enabled", true),
			AutoscalingTargetEventsPerWorkerSec: floatDefault(pipeRaw, "autoscaling_target_events_per_worker_sec", 1500.0),
			AutoscalingMinWorkers:               intDefault(pipeRaw, "autoscaling_min_workers", 1),
			AutoscalingMaxWorkers:               intDefault(pipeRaw, "autoscaling_max_workers", 64),
			AutoscalingLagScaleUpSeconds:        autoscalingLagScaleUpSeconds,
			AutoscalingLagScaleDownSeconds:      autoscalingLagScaleDownSeconds,
			PollIntervalSeconds:                 pollIntervalSeconds,
			TimestampField:                      stringify(getOrDefault(pipeRaw, "timestamp_field", "@timestamp")),
			StartTime:                           stringify(getOrDefault(pipeRaw, "start_time", "now-15m")),
			SourceIndices:                       stringSlice(pipeRaw["source_indices"]),
			WriteToSourceIndex:                  boolDefault(pipeRaw, "write_to_source_index", false),
			WriteToTargetIndex:                  boolDefault(pipeRaw, "write_to_target_index", true),
			TargetSuffix:                        stringify(getOrDefault(pipeRaw, "target_suffix", "-rca")),
			DeadLetterSuffix:                    stringify(getOrDefault(pipeRaw, "dead_letter_suffix", "-rca-dead-letter")),
			RetryMaxAttempts:                    intDefault(pipeRaw, "retry_max_attempts", 4),
			RetryInitialBackoffSeconds:          retryInitialBackoffSeconds,
			RetryBackoffMultiplier:              floatDefault(pipeRaw, "retry_backoff_multiplier", 2.0),
			SignalMaxPerEvent:                   intDefault(pipeRaw, "signal_max_per_event", 2),
			SignalSelectHighestOnly:             boolDefault(pipeRaw, "signal_select_highest_only", true),
			VendorAnchorEnforcementEnabled:      boolDefault(pipeRaw, "vendor_anchor_enforcement_enabled", true),
			Services:                            services,
		},
		RulesDirectory: rulesDirectory,
		RuleLearning: RuleLearningConfig{
			Enabled:                 boolDefault(ruleLearningRaw, "enabled", false),
			Mode:                    stringify(getOrDefault(ruleLearningRaw, "mode", "suggest")),
			OutputDirectory:         stringify(getOrDefault(ruleLearningRaw, "output_directory", "rules/suggestions")),
			MinOccurrences:          intDefault(ruleLearningRaw, "min_occurrences", 10),
			MaxCandidatesPerService: intDefault(ruleLearningRaw, "max_candidates_per_service", 20),
			MinKeywordCount:         intDefault(ruleLearningRaw, "min_keyword_count", 2),
			MaxKeywordsPerSignal:    intDefault(ruleLearningRaw, "max_keywords_per_signal", 4),
			ConditionField:          stringify(getOrDefault(ruleLearningRaw, "condition_field", "message")),
			ConditionOp:             stringify(getOrDefault(ruleLearningRaw, "condition_op", "contains")),
			Level:                   stringify(getOrDefault(ruleLearningRaw, "level", "critical")),
		},
	}, nil
}

func loadServices(pipeRaw map[string]any) ([]ServiceConfig, error) {
	rawServices, ok := pipeRaw["services"]
	if !ok {
		return []ServiceConfig{}, nil
	}
	serviceList, ok := rawServices.([]any)
	if !ok {
		return nil, errors.New("pipeline.services entries must be mappings")
	}

	services := make([]ServiceConfig, 0, len(serviceList))
	for _, item := range serviceList {
		serviceRaw, ok := item.(map[string]any)
		if !ok {
			return nil, errors.New("pipeline.services entries must be mappings")
		}
		name, err := requireKey(serviceRaw, "name")
		if err != nil {
			return nil, err
		}
		ruleFile, err := requireKey(serviceRaw, "rule_file")
		if err != nil {
			return nil, err
		}

		service := ServiceConfig{
			Name:          stringify(name),
			Enabled:       boolDefault(serviceRaw, "enabled", true),
			RuleFile:      stringify(ruleFile),
			SourceIndices: stringSlice(serviceRaw["source_indices"]),
			Query:         mapValue(serviceRaw["query"]),
		}
		if rawStartTime, ok := serviceRaw["start_time"]; ok && rawStartTime != nil {
			value := stringify(rawStartTime)
			service.StartTime = &value
		}
		services = append(services, service)
	}

	return services, nil
}

func requireKey(data map[string]any, key string) (any, error) {
	value, ok := data[key]
	if !ok {
		return nil, fmt.Errorf("Missing required configuration key: %s", key)
	}
	return value, nil
}

func requireMapping(value any, name string) (map[string]any, error) {
	mapping, ok := value.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("%s must be a mapping", name)
	}
	return mapping, nil
}

func optionalMapping(raw map[string]any, key string) (map[string]any, error) {
	value, ok := raw[key]
	if !ok || value == nil {
		return map[string]any{}, nil
	}
	return requireMapping(value, key)
}

func resolveElasticsearchHosts(esRaw map[string]any) ([]string, error) {
	if hosts := loadLogHostsFromLegacySettings(); len(hosts) > 0 {
		return hosts, nil
	}
	if hosts := normalizeElasticsearchHosts(esRaw["hosts"]); len(hosts) > 0 {
		return hosts, nil
	}
	return nil, errors.New("Missing Elasticsearch hosts: set settings.LOG_HOSTS or elasticsearch.hosts")
}

func loadLogHostsFromLegacySettings() []string {
	pythonExecutables := []string{}
	if fromEnv := strings.TrimSpace(os.Getenv("PYTHON")); fromEnv != "" {
		pythonExecutables = append(pythonExecutables, fromEnv)
	}
	pythonExecutables = append(pythonExecutables, "python", "python3")

	const script = "import json\ntry:\n import settings\n value = getattr(settings, 'LOG_HOSTS', None)\nexcept Exception:\n value = None\nprint(json.dumps(value))\n"
	seen := map[string]struct{}{}
	for _, executable := range pythonExecutables {
		if executable == "" {
			continue
		}
		if _, exists := seen[executable]; exists {
			continue
		}
		seen[executable] = struct{}{}

		command := exec.Command(executable, "-c", script)
		output, err := command.Output()
		if err != nil {
			continue
		}

		var value any
		if err := json.Unmarshal([]byte(strings.TrimSpace(string(output))), &value); err != nil {
			continue
		}
		hosts := normalizeElasticsearchHosts(value)
		if len(hosts) > 0 {
			return hosts
		}
	}
	return nil
}

func normalizeElasticsearchHosts(rawHosts any) []string {
	values := []string{}

	switch typed := rawHosts.(type) {
	case string:
		text := strings.TrimSpace(typed)
		if text == "" {
			return nil
		}

		var parsed any
		if err := yaml.Unmarshal([]byte(text), &parsed); err == nil {
			if list, ok := parsed.([]any); ok {
				for _, item := range list {
					value := strings.TrimSpace(fmt.Sprint(item))
					if value != "" {
						values = append(values, value)
					}
				}
			}
		}
		if len(values) == 0 {
			if strings.Contains(text, ",") || strings.Contains(text, ";") {
				for _, part := range splitHostsRegex.Split(text, -1) {
					value := strings.TrimSpace(part)
					if value != "" {
						values = append(values, value)
					}
				}
			} else {
				values = append(values, text)
			}
		}
	case []any:
		for _, item := range typed {
			value := strings.TrimSpace(fmt.Sprint(item))
			if value != "" {
				values = append(values, value)
			}
		}
	case []string:
		for _, item := range typed {
			value := strings.TrimSpace(item)
			if value != "" {
				values = append(values, value)
			}
		}
	default:
		return nil
	}

	normalized := make([]string, 0, len(values))
	for _, host := range values {
		if strings.Contains(host, "://") {
			normalized = append(normalized, host)
		} else {
			normalized = append(normalized, "http://"+host)
		}
	}
	return normalized
}

func resolveWorkerRuntime(pipeRaw map[string]any) (int, int, error) {
	workerCount := intDefault(pipeRaw, "worker_count", 1)
	workerID := intDefault(pipeRaw, "worker_id", 0)

	if shouldPrimeWorkerCountFromPM2() {
		if instances := resolveInstancesFromAppJSON(); instances != nil {
			_ = os.Setenv("RCA_WORKER_COUNT", strconv.Itoa(*instances))
		}
	}

	if value, err := readIntFromEnv([]string{"RCA_WORKER_COUNT", "WORKER_COUNT", "PM2_INSTANCES", "INSTANCE_COUNT"}); err != nil {
		return 0, 0, err
	} else if value != nil {
		workerCount = *value
	}
	if value, err := readIntFromEnv([]string{"RCA_WORKER_ID", "WORKER_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id"}); err != nil {
		return 0, 0, err
	} else if value != nil {
		workerID = *value
	}

	if workerCount < 1 {
		return 0, 0, errors.New("pipeline.worker_count must be >= 1")
	}
	if workerID < 0 {
		return 0, 0, errors.New("pipeline.worker_id must be >= 0")
	}
	if workerID >= workerCount {
		return 0, 0, errors.New("pipeline.worker_id must satisfy 0 <= worker_id < worker_count")
	}

	return workerCount, workerID, nil
}

func shouldPrimeWorkerCountFromPM2() bool {
	if raw, ok := os.LookupEnv("RCA_WORKER_COUNT"); ok && strings.TrimSpace(raw) != "" {
		return false
	}
	for _, key := range []string{"RCA_WORKER_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id"} {
		if raw, ok := os.LookupEnv(key); ok && strings.TrimSpace(raw) != "" {
			return true
		}
	}
	return false
}

func resolveInstancesFromAppJSON() *int {
	appJSONPaths := []string{
		filepath.Join(".", "app.json"),
		filepath.Join("signalizing-engine", "app.json"),
		filepath.Join("signalizing-engine_go", "app.json"),
		filepath.Join("signalizing_go", "app.json"),
		filepath.Join("signalizing", "signalizing_go", "app.json"),
	}

	for _, path := range appJSONPaths {
		contents, err := os.ReadFile(path)
		if err != nil {
			continue
		}

		var payload map[string]any
		if err := json.Unmarshal(contents, &payload); err != nil {
			continue
		}

		apps, ok := payload["apps"].([]any)
		if !ok || len(apps) == 0 {
			continue
		}

		appName := strings.TrimSpace(os.Getenv("PM2_APP_NAME"))
		if appName == "" {
			appName = "signalizing-engine"
		}

		var selected map[string]any
		for _, appRaw := range apps {
			app, ok := appRaw.(map[string]any)
			if !ok {
				continue
			}
			if strings.TrimSpace(fmt.Sprint(app["name"])) == appName {
				selected = app
				break
			}
			if selected == nil {
				selected = app
			}
		}
		if selected == nil {
			continue
		}

		switch instances := selected["instances"].(type) {
		case int:
			if instances > 0 {
				return &instances
			}
		case float64:
			value := int(instances)
			if value > 0 {
				return &value
			}
		case string:
			text := strings.ToLower(strings.TrimSpace(instances))
			if text == "" {
				continue
			}
			if text == "max" {
				value := runtime.NumCPU()
				if cpuCount := os.Getenv("NUMBER_OF_PROCESSORS"); cpuCount != "" {
					if parsed, err := strconv.Atoi(cpuCount); err == nil && parsed > 0 {
						value = parsed
					}
				}
				if value < 1 {
					value = 1
				}
				return &value
			}
			if parsed, err := strconv.Atoi(text); err == nil && parsed > 0 {
				return &parsed
			}
		}
	}

	return nil
}

func readIntFromEnv(varNames []string) (*int, error) {
	for _, varName := range varNames {
		raw, exists := os.LookupEnv(varName)
		if !exists {
			continue
		}
		text := strings.TrimSpace(raw)
		if text == "" {
			continue
		}
		value, err := strconv.Atoi(text)
		if err != nil {
			return nil, fmt.Errorf("%s must be an integer, got: %q", varName, raw)
		}
		return &value, nil
	}
	return nil, nil
}

func resolvePathFromConfig(configPath string, value string) (string, error) {
	if filepath.IsAbs(value) {
		return value, nil
	}
	return filepath.Abs(filepath.Join(filepath.Dir(configPath), value))
}

func coerceSizeBytes(value any, keyName string) (int, error) {
	switch typed := value.(type) {
	case bool:
		return 0, fmt.Errorf("%s must be a size, not boolean", keyName)
	case int:
		if typed < 1 {
			return 0, fmt.Errorf("%s must be at least 1 byte", keyName)
		}
		return typed, nil
	case int64:
		if typed < 1 {
			return 0, fmt.Errorf("%s must be at least 1 byte", keyName)
		}
		return int(typed), nil
	case float64:
		result := int(typed)
		if result < 1 {
			return 0, fmt.Errorf("%s must be at least 1 byte", keyName)
		}
		return result, nil
	case string:
		text := strings.TrimSpace(typed)
		if text == "" {
			return 0, fmt.Errorf("%s cannot be empty", keyName)
		}
		if numberPattern.MatchString(text) {
			number, err := strconv.ParseFloat(text, 64)
			if err != nil {
				return 0, err
			}
			result := int(number)
			if result < 1 {
				return 0, fmt.Errorf("%s must be at least 1 byte", keyName)
			}
			return result, nil
		}

		match := sizePattern.FindStringSubmatch(text)
		if match == nil {
			return 0, fmt.Errorf("%s must be numeric bytes or unit value like '8MB', got: %q", keyName, typed)
		}
		number, err := strconv.ParseFloat(match[1], 64)
		if err != nil {
			return 0, err
		}
		unit := strings.ToLower(match[2])
		result := int(number * float64(sizeUnits[unit]))
		if result < 1 {
			return 0, fmt.Errorf("%s must be at least 1 byte", keyName)
		}
		return result, nil
	default:
		return 0, fmt.Errorf("%s has unsupported type: %T", keyName, value)
	}
}

func coerceSecondsFloat(value any, keyName string) (float64, error) {
	switch typed := value.(type) {
	case bool:
		return 0, fmt.Errorf("%s must be a duration, not boolean", keyName)
	case int:
		if typed < 0 {
			return 0, fmt.Errorf("%s must be >= 0 seconds", keyName)
		}
		return float64(typed), nil
	case int64:
		if typed < 0 {
			return 0, fmt.Errorf("%s must be >= 0 seconds", keyName)
		}
		return float64(typed), nil
	case float64:
		if typed < 0 {
			return 0, fmt.Errorf("%s must be >= 0 seconds", keyName)
		}
		return typed, nil
	case string:
		text := strings.TrimSpace(typed)
		if text == "" {
			return 0, fmt.Errorf("%s cannot be empty", keyName)
		}
		if numberPattern.MatchString(text) {
			number, err := strconv.ParseFloat(text, 64)
			if err != nil {
				return 0, err
			}
			if number < 0 {
				return 0, fmt.Errorf("%s must be >= 0 seconds", keyName)
			}
			return number, nil
		}

		match := durationPattern.FindStringSubmatch(text)
		if match == nil {
			return 0, fmt.Errorf("%s must be numeric seconds or duration value like '10s', got: %q", keyName, typed)
		}
		number, err := strconv.ParseFloat(match[1], 64)
		if err != nil {
			return 0, err
		}
		unit := strings.ToLower(match[2])
		seconds := number * durationUnitsSeconds[unit]
		if seconds < 0 {
			return 0, fmt.Errorf("%s must be >= 0 seconds", keyName)
		}
		return seconds, nil
	default:
		return 0, fmt.Errorf("%s has unsupported type: %T", keyName, value)
	}
}

func coerceSecondsInt(value any, keyName string, minimum int) (int, error) {
	seconds, err := coerceSecondsFloat(value, keyName)
	if err != nil {
		return 0, err
	}
	coerced := int(math.Ceil(seconds))
	if coerced < minimum {
		return 0, fmt.Errorf("%s must be >= %d second(s)", keyName, minimum)
	}
	return coerced, nil
}

func getOrDefault(data map[string]any, key string, defaultValue any) any {
	if value, ok := data[key]; ok {
		return value
	}
	return defaultValue
}

func stringify(value any) string {
	return fmt.Sprint(value)
}

func stringPointer(value any) *string {
	if value == nil {
		return nil
	}
	text := fmt.Sprint(value)
	if text == "<nil>" {
		return nil
	}
	return &text
}

func stringSlice(value any) []string {
	switch typed := value.(type) {
	case []string:
		return append([]string{}, typed...)
	case []any:
		result := make([]string, 0, len(typed))
		for _, item := range typed {
			result = append(result, fmt.Sprint(item))
		}
		return result
	default:
		return []string{}
	}
}

func mapValue(value any) map[string]any {
	if value == nil {
		return nil
	}
	mapping, ok := value.(map[string]any)
	if !ok {
		return nil
	}
	return mapping
}

func boolDefault(data map[string]any, key string, defaultValue bool) bool {
	value, ok := data[key]
	if !ok {
		return defaultValue
	}
	typed, ok := value.(bool)
	if !ok {
		return defaultValue
	}
	return typed
}

func intDefault(data map[string]any, key string, defaultValue int) int {
	value, ok := data[key]
	if !ok {
		return defaultValue
	}
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	default:
		return defaultValue
	}
}

func floatDefault(data map[string]any, key string, defaultValue float64) float64 {
	value, ok := data[key]
	if !ok {
		return defaultValue
	}
	switch typed := value.(type) {
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case float64:
		return typed
	default:
		return defaultValue
	}
}
