# API Reference

## Interfaces

### Redis Client Interface

Used for fetching signalized logs and publishing results.

```go
type ClientInterface interface {
    // GetSignalizedLogs fetches logs for an organization
    GetSignalizedLogs(ctx context.Context, orgID string) ([]models.SignalizedLog, error)
    
    // PublishResult publishes a correlation result
    PublishResult(ctx context.Context, result *models.CorrelationResult) error
    
    // Close closes the connection
    Close() error
    
    // Ping checks connectivity
    Ping(ctx context.Context) error
}
```

**Default Implementation:** `redis.Client`
- Connects to Redis using `go-redis`
- Key format: `RCA:{orgID}:signaled_logs`
- Result publication: `RCA:{orgID}:correlated_events`

### Rule Loader Interface

Used for loading and managing correlation rules.

```go
type LoaderInterface interface {
    // LoadRules loads all rules
    LoadRules() ([]models.Rule, error)
    
    // HotReload enables automatic reloading
    HotReload() error
    
    // Close stops hot reload
    Close() error
}
```

**Default Implementation:** `rules.FileLoader`
- Loads from JSON file (rules/rules.json)
- Hot reload every 30 seconds (when enabled)
- Thread-safe with RWMutex

### Correlation Engine Interface

Core business logic for matching rules against logs.

```go
type CorrelationEngineInterface interface {
    // CorrelateAsync processes logs and applies rules
    CorrelateAsync(ctx context.Context, orgID string, logs []models.FullLog, rules []models.Rule) ([]models.CorrelationResult, error)
}
```

**Default Implementation:** `engine.Engine`
- 9-step matching algorithm
- Concurrent processing per organization
- Sliding window sequence matching

### Elasticsearch Writer Interface

Used for persisting correlation results.

```go
type WriterInterface interface {
    // WriteResult writes a result to Elasticsearch
    WriteResult(ctx context.Context, result *models.CorrelationResult) error
    
    // Close closes the connection
    Close() error
    
    // Ping checks connectivity
    Ping(ctx context.Context) error
}
```

**Default Implementation:** `elastic.Writer`
- Uses official Elasticsearch Go client
- Index: `rca_correlated_events`
- Document format: JSON-serialized CorrelationResult

### Log Fetcher Interface

Used for fetching full log details by document ID.

```go
type LogFetcherInterface interface {
    // FetchLog fetches a log by document ID
    FetchLog(docID string) (*models.FullLog, error)
}
```

**Default Implementation:** `loader.MockLogFetcher`
- In-memory cache for testing
- Can be extended for Elasticsearch or custom sources

## Data Models

### Rule

```go
type Rule struct {
    ID                  string            // Unique rule identifier
    OrganizationID      string            // Organization ID
    RuleType            string            // always "ordered_signal_sequence"
    Window              string            // Time window (e.g., "15m")
    MaxGapBetweenSteps  string            // Max gap between sequence steps
    GroupBy             []string          // Fields to group logs by
    Priority            int               // Lower number = higher priority
    Sequence            []SequenceStep    // Ordered sequence of signals
    NotSequence         []NegativeStep    // Signals that cancel the rule
    Deduplication       Deduplication     // Deduplication configuration
}
```

### SequenceStep

```go
type SequenceStep struct {
    SignalKey string // Signal to match
    MinCount  int    // Minimum occurrences for this step
    Within    string // Time window for this step
}
```

### SignalizedLog (from Redis)

```go
type SignalizedLog struct {
    Signal    string    // Signal name
    LogLevel  string    // log_level
    DocID     string    // Document ID for full log fetch
    Timestamp time.Time // When signal occurred
}
```

### FullLog (fetched via DocID)

```go
type FullLog struct {
    DocID     string                 // Document ID
    Timestamp time.Time              // Timestamp
    Signal    string                 // Signal name
    LogLevel  string                 // Log level
    Metadata  map[string]interface{} // Arbitrary metadata (e.g., host.name, event.organization)
}
```

### CorrelationResult (output to ES)

```go
type CorrelationResult struct {
    LogID           []ResultLog        // Compact matched logs [{id, severity}]
    RuleCompletion  float64            // 0.0-1.0
    RuleID          string             // Which rule matched
    SequenceMatch   float64            // 0.0-1.0 ordered-sequence progress
}
```

## Configuration (config.yml)

```yaml
redis:
  addr: "localhost:6379"          # Redis address
  db: 0                           # Database number
  password: ""                    # Password (optional)

elasticsearch:
  addresses:
    - "http://localhost:9200"    # ES endpoints
  username: ""                   # Username (optional)
  password: ""                   # Password (optional)

engine:
  default_window: "30m"          # Default window for rules without explicit window
  default_max_gap: "5m"          # Default max gap between steps
  rules_file: "rules/rules.json" # Path to rules file
  processing_interval: "10s"     # How often to process

logging:
  level: "info"                  # debug, info, warn, error
```

## Algorithm Reference

### Matching Algorithm (9 Steps)

Given a rule and a set of logs:

1. **Filter**: Get rules for organization
2. **Group**: Group logs by `group_by` fields
3. **Sort**: Sort each group by timestamp (ascending)
4. **Deduplicate**: Remove duplicates within dedup window
5. **Slide**: For each position in log stream:
   - Define window: [timestamp, timestamp + rule.window]
   - Try to match sequence starting from this position
   - Return matched logs if all steps match
6. **Match Sequence**: For each step in rule.sequence:
   - Find log with matching signal within rule.window
   - Check time gap from previous step ≤ rule.max_gap_between_steps
   - Continue to next step
7. **Validate Negatives**: If any not_sequence signal appears → fail
8. **Score**: Calculate rule_completion and sequence_match
9. **Emit**: If rule_completion ≥ rule.trigger_threshold → return result

### Score Calculation

```
matched_weight = sum(weights of matched steps)
total_weight = sum(weights of all steps)
rule_completion = matched_weight / total_weight

sequence_match = (matched_steps / total_steps) * 100
```

## Usage Examples

### Initialize Engine

```go
// Load config
cfg, err := loader.LoadConfig("config/config.yml")

// Create Redis client
redis, err := redis.NewClient(cfg.Redis.Addr, cfg.Redis.Password, cfg.Redis.DB, logger)

// Create Elasticsearch writer
esWriter, err := elastic.NewWriter(cfg.Elasticsearch.Addresses, "", "", "rca_correlated_events", logger)

// Create rule loader
ruleLoader, err := rules.NewFileLoader(cfg.Engine.RulesFile, logger)
ruleLoader.HotReload() // Optional

// Create engine
engine, err := engine.NewEngine(cfg.Engine, logger)
```

### Process Logs

```go
// Get logs from Redis
logs, err := redis.GetSignalizedLogs(ctx, orgID)

// Fetch full logs
fullLogs := []models.FullLog{}
for _, sigLog := range logs {
    fullLog, err := logFetcher.FetchLog(sigLog.DocID)
    fullLogs = append(fullLogs, *fullLog)
}

// Apply rules
results, err := engine.CorrelateAsync(ctx, orgID, fullLogs, ruleLoader.GetRules())

// Write results
for _, result := range results {
    esWriter.WriteResult(ctx, &result)
    redis.PublishResult(ctx, &result)
}
```

## Error Handling

All functions return `error` as last return value. Common errors:

- `"failed to connect to Redis"` - Redis unreachable
- `"failed to parse config file"` - Invalid YAML
- `"failed to read rules file"` - Rules file not found
- `"elasticsearch error"` - ES connection/indexing issue
- Context cancellation via `ctx.Done()`

Handle gracefully:

```go
if err != nil {
    logger.Warn("operation failed", zap.Error(err))
    // Continue processing or retry
}
```

## Performance Tips

1. **Reduce log volume**: Filter at source or with sampling
2. **Simplify rules**: Fewer steps = faster matching
3. **Increase window**: Larger windows = slower matching
4. **Add indices**: For custom log fechers, index by doc_id
5. **Batch writes**: Collect results before bulk indexing
6. **Cache logs**: Keep frequently accessed logs in memory
7. **Monitor metrics**: Track processing time and adjust

## Future API Changes

- [ ] gRPC API for remote operation
- [ ] Rule validation API
- [ ] Metrics export endpoint
- [ ] Rule testing sandbox
