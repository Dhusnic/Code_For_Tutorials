# Architecture & Design

## Clean Architecture Pattern

The log correlation engine follows clean architecture principles with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   External Interfaces                    │
│              (Redis, Elasticsearch, Files)               │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                   Interface Adapters                     │
│    (redis/, elastic/, loader/config, loader/fetcher)   │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                    Business Logic                        │
│                (engine/, rules/, models/)                │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                   Utility Functions                      │
│                      (utils/)                            │
└─────────────────────────────────────────────────────────┘
```

## Module Breakdown

### `cmd/main.go` - Application Entry Point
- Initializes all components
- Sets up signal handling for graceful shutdown
- Implements the processing loop
- Orchestrates data flow between components

### `internal/models/` - Data Structures
- `Rule` - Correlation rule definition
- `SignalizedLog` - Signal from Redis
- `FullLog` - Complete log with metadata
- `CorrelationResult` - Engine output
- `SequenceStep`, `NegativeStep`, `Deduplication` - Supporting structures

### `internal/redis/` - Redis Integration
**Interface-based design:**
```go
type ClientInterface interface {
    GetSignalizedLogs(ctx context.Context, orgID string) ([]models.SignalizedLog, error)
    PublishResult(ctx context.Context, result *models.CorrelationResult) error
    Close() error
    Ping(ctx context.Context) error
}
```

**Implementation:**
- `Client` - Real Redis implementation using go-redis
- Key format: `RCA:{orgID}:signaled_logs`
- Results published to: `RCA:{orgID}:correlated_events`

### `internal/rules/` - Rule Management
**Interface-based design:**
```go
type LoaderInterface interface {
    LoadRules() ([]models.Rule, error)
    HotReload() error
    Close() error
}
```

**Implementation:**
- `FileLoader` - JSON file-based loader with optional hot reload
- Reloads every 30 seconds if enabled
- Thread-safe with RWMutex

### `internal/engine/` - Correlation Logic (Core)
**CORE BUSINESS LOGIC** - 9-step algorithm:

1. **Group by Fields**: Logs grouped by `group_by` fields from rules
2. **Sort**: Logs sorted by timestamp ascending
3. **Deduplicate**: Remove duplicates within window using dedup key
4. **Sliding Window**: Apply `window` parameter to constrain search
5. **Sequence Match**: Verify ordered signal sequence:
   - Signals must match in order
   - Each step has `min_count` and `within` constraints
   - `max_gap_between_steps` enforced
6. **Negative Conditions**: If any `not_sequence` signal appears → match fails
7. **Emit Full Match**: Results are emitted only when the full ordered sequence matches
8. **Output Annotation**:
   - `rule_completion = 1`
   - `sequence_match = 100`
9. **Priority Handling**: Results sorted by priority

**Performance Characteristics:**
- Worst-case: O(n²) for sliding window (n = logs per group)
- Best-case: O(n) with early termination on sequence mismatch
- Concurrency: Per-organization goroutine pool
- Memory: O(n) for grouping and deduplication

### `internal/elastic/` - Elasticsearch Output
**Interface-based design:**
```go
type WriterInterface interface {
    WriteResult(ctx context.Context, result *models.CorrelationResult) error
    Close() error
    Ping(ctx context.Context) error
}
```

**Implementation:**
- `Writer` - Official Elasticsearch Go client
- Index: `rca_correlated_events`
- Each result stored as separate document

### `internal/loader/` - Configuration & Data Fetching
**Config:**
```go
type Config struct {
    Redis struct { Addr, DB, Password }
    Elasticsearch struct { Addresses, Username, Password }
    Engine struct { DefaultWindow, DefaultMaxGap, RulesFile, ProcessingInterval }
    Logging struct { Level }
}
```

**LogFetcher Interface:**
```go
type LogFetcherInterface interface {
    FetchLog(docID string) (*models.FullLog, error)
}
```

**Implementations:**
- `MockLogFetcher` - In-memory cache for testing
- Extensible for Elasticsearch or other sources

### `internal/utils/` - Utilities
- **duration.go**: Parse duration strings ("5m", "1h", "30s", "2d")
- **groupby.go**: Extract and build group-by keys from nested metadata

## Concurrency Model

```
Main Loop (10s intervals)
    ├─ For each organization (sequential per organization)
    │   ├─ Fetch signalized logs from Redis
    │   ├─ Fetch full logs (parallel-safe via same interface)
    │   ├─ For each rule (parallel):
    │   │   └─ Run correlation (RWMutex on rule struct)
    │   └─ Write results (parallel-safe via interface)
    └─ Repeat
```

**Key Points:**
- No shared state between rule evaluations
- `GetRules()` returns copy (thread-safe)
- Elasticsearch/Redis clients are thread-safe
- Graceful context cancellation support

## Extensibility Points

### 1. Add Custom Log Fetcher
```go
type MyLogFetcher struct {
    esClient *elasticsearch.Client
}

func (f *MyLogFetcher) FetchLog(docID string) (*models.FullLog, error) {
    // Fetch from Elasticsearch
}
```

Then in `main.go`:
```go
logFetcher := &MyLogFetcher{esClient: esClient}
```

### 2. Add Custom Rule Loader
```go
type MongoRuleLoader struct {
    db *mongo.Client
}

func (l *MongoRuleLoader) LoadRules() ([]models.Rule, error) {
    // Load from MongoDB
}

func (l *MongoRuleLoader) HotReload() error {
    // Watch collection for changes
}
```

### 3. Add Custom Metrics Export
```go
// In main.go processing loop:
for {
    case <-ticker.C:
        metrics := correlationEngine.GetMetrics()
        prometheus.RecordMetrics(metrics)
}
```

### 4. Add Custom Output Writer
```go
type KafkaWriter struct {
    producer kafka.Writer
}

func (w *KafkaWriter) WriteResult(ctx context.Context, result *models.CorrelationResult) error {
    // Write to Kafka topic
}
```

## Error Handling Strategy

- **Redis Connection Errors**: Logged and skipped (org missing logs doesn't block others)
- **Rule Load Errors**: Logged, uses previous rules
- **Elasticsearch Write Errors**: Logged and continues (individual result failures don't block)
- **Context Timeouts**: Graceful cancellation via context.Done()
- **Panic Recovery**: Not implemented - let system panic to fail fast

## Dependencies

**External Libraries:**
- `github.com/redis/go-redis/v9` - Redis client
- `github.com/elastic/go-elasticsearch/v8` - Elasticsearch client
- `go.uber.org/zap` - Structured logging
- `gopkg.in/yaml.v3` - YAML config parsing

**Rationale:**
- All are production-grade with wide adoption
- Minimal external dependencies
- Pure Go (no CGO required)

## Performance Optimization Opportunities

1. **Batch Elasticsearch Writes**: Collect results and bulk index
2. **Rule Compilation**: Pre-compile rules to bytecode
3. **Caching**: LRU cache for log fetches
4. **Parallel Rule Evaluation**: Job queue with worker pool
5. **Memory Pooling**: sync.Pool for result objects
6. **Sampling**: Sample logs if throughput too high
7. **Circuit Breaker**: For Redis/ES failures

## Future Enhancements

- [ ] MongoDB rule loader
- [ ] Elasticsearch log fetcher
- [ ] Prometheus metrics export
- [ ] Distributed tracing (Jaeger)
- [ ] gRPC API for external rules
- [ ] Rule validation webhook
- [ ] Anomaly detection integration
- [ ] Machine learning preprocessing
