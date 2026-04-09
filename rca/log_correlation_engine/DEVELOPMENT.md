# Development Guide

## Setting Up Development Environment

### Prerequisites
- Go 1.21 or later
- Docker (for Redis and Elasticsearch)
- Make or PowerShell (for build scripts)

### Quick Start

1. **Clone/Navigate to project:**
```bash
cd log_correlation_engine
```

2. **Download dependencies:**
```bash
make deps
# or
go mod download
```

3. **Start Redis and Elasticsearch:**
```bash
docker-compose up -d
```

4. **Build:**
```bash
make build
# or
./build.sh
```

5. **Run:**
```bash
make run
# or
./bin/correlation-engine
```

## Project Structure Details

### Adding a New Rule

1. Edit `rules/rules.json`
2. Add new rule object with required fields
3. Engine auto-reloads (if hot reload enabled)
4. Or restart and observe in logs

Example:
```json
{
  "id": "CORR_XXXX_MY_RULE",
  "organization_id": "135098068173316952064",
  "rule_type": "ordered_signal_sequence",
  "level": "critical",
  "window": "15m",
  "priority": 5,
  "sequence": [...]
}
```

### Adding a New Signal Handler

The engine doesn't need explicit signal handlers - it matches any signal in rules.

To add support for a new signal type:
1. Define the signal in your signalization engine
2. Add it to the `sequence` field of relevant rules
3. The correlation engine will automatically match it

### Creating Custom Interfaces

**Example: Custom Redis implementation for cluster:**

```go
// internal/redis/cluster.go
package redis

type ClusterClient struct {
    cluster *redis.ClusterClient
    logger *zap.Logger
}

func (c *ClusterClient) GetSignalizedLogs(ctx context.Context, orgID string) ([]models.SignalizedLog, error) {
    // Cluster-aware implementation
}

func (c *ClusterClient) PublishResult(ctx context.Context, result *models.CorrelationResult) error {
    // Cluster-aware implementation
}
```

Then in `main.go`:
```go
redisClient, err := redis.NewClusterClient(cfg.Redis, logger)
```

### Testing

**Run all tests:**
```bash
make test
```

**Run specific test:**
```bash
go test -v -run TestSlidingWindowMatch ./internal/engine/
```

**Run with coverage:**
```bash
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

**Test a specific package:**
```bash
go test -v ./internal/engine/
go test -v ./internal/redis/
go test -v ./internal/utils/
```

## Code Style

- Follow `gofmt` formatting
- Use idiomatic Go naming (CamelCase for exported, lowercase for internal)
- Interface names end with `Interface` suffix
- Use `ctx context.Context` as first parameter
- Error handling: explicit `if err != nil`

**Format code:**
```bash
make fmt
```

## Debugging

### Enable Debug Logging
Set in `config.yml`:
```yaml
logging:
  level: "debug"
```

### Common Issues

**Connection Refused (Redis):**
- Check Redis is running: `docker ps`
- Check address in config.yml matches

**No results being emitted:**
- Check rules.json is valid JSON
- Check organization_id matches source logs
- Check log timestamps are recent (window constraint)
- Enable debug logging to see detailed matching

**Memory leaks:**
- Ensure `Close()` is called on all resources
- Check for goroutine leaks: `pprof`
- Monitor metrics in status logs

## Performance Profiling

### CPU Profile
```bash
# With pprof endpoint (requires adding net/http/pprof)
curl http://localhost:6060/debug/pprof/profile > cpu.prof
go tool pprof cpu.prof
```

### Memory Profile
```bash
curl http://localhost:6060/debug/pprof/heap > mem.prof
go tool pprof mem.prof
```

### Metrics
Check logs for processing time:
```
"correlation completed" org_id=XXX logs_count=100 rules_count=5 results_count=2 time_ms=45
```

## Deployment

### Docker Build
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o correlation-engine ./cmd/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
COPY --from=builder /app/correlation-engine /
COPY config/config.yml ./config/
COPY rules/rules.json ./rules/
EXPOSE 8080
CMD ["./correlation-engine"]
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-correlation-engine
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: engine
        image: log-correlation-engine:latest
        env:
        - name: CONFIG_PATH
          value: /etc/config/config.yml
        volumeMounts:
        - name: config
          mountPath: /etc/config
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: correlation-engine-config
```

## Contributing

### Before Submitting PR

1. Run tests: `make test`
2. Format code: `make fmt`
3. Check for unused imports: `go mod tidy`
4. Update CHANGELOG if user-facing change
5. Update README if API changes

### Commit Message Guidelines

```
type: description

- Add details here if needed
- Explain why if not obvious

Examples:
- feat: add hot reload support
- fix: correct deduplication window logic
- docs: update architecture guide
- refactor: simplify score calculation
```

## Troubleshooting

### Rule not matching

1. Check rule JSON syntax: `jq . rules/rules.json`
2. Verify organization_id matches
3. Check log timestamps within window
4. Enable debug logging
5. Add temporary debug output to engine.go

### Engine crashes

1. Check config.yml validity: `yq . config/config.yml`
2. Ensure Redis/ES are accessible
3. Check logs for panics
4. Review recent changes

### Performance degradation

1. Check log volume: examine metrics in logs
2. Profile CPU: see Performance Profiling section
3. Consider scaling: add more workers
4. Check rule complexity: simplify where possible

## Release Process

1. Update version in README.md
2. Update CHANGELOG.md
3. Create annotated git tag: `git tag -a v1.0.0 -m "Release 1.0.0"`
4. Build release binary: `make build`
5. Push tag: `git push origin v1.0.0`
