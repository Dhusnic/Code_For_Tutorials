# File Manifest

## Core Application
- `cmd/main.go` - Application entry point, orchestration loop
- `go.mod` - Go module dependencies

## Configuration
- `config/config.yml` - Configuration template with all options
- `internal/loader/config.go` - Configuration struct & loader

## Data Models
- `internal/models/models.go` - All data structures:
  - Rule, SequenceStep, NegativeStep, Deduplication
  - SignalizedLog, FullLog, CorrelationResult
  - ProcessingMetrics

## Redis Integration
- `internal/redis/client.go` - Redis client interface & implementation
- `internal/redis/client_test.go` - Redis client tests

## Rule Management
- `rules/rules.json` - 5 sample production rules
- `internal/rules/loader.go` - File-based rule loader with hot reload

## Correlation Engine (Core)
- `internal/engine/engine.go` - 9-step matching algorithm:
  - Sliding window matching
  - Deduplication
  - Sequence validation
  - Score calculation
  - Negative conditions
  - Concurrency & metrics
- `internal/engine/engine_test.go` - Engine unit tests

## Elasticsearch Output
- `internal/elastic/writer.go` - Elasticsearch client & result writing

## Log Fetching
- `internal/loader/logfetcher.go` - LogFetcher interface & mock implementation
- `internal/loader/config.go` - Config loader (also contains LogFetcherInterface)

## Utilities
- `internal/utils/duration.go` - Duration string parsing ("5m", "1h", etc.)
- `internal/utils/groupby.go` - Group-by field extraction & key building
- `internal/utils/utils_test.go` - Utility tests

## Build & Deployment
- `Makefile` - Build targets (build, run, test, clean, fmt, lint)
- `build.sh` - Linux/Mac build script
- `build.ps1` - Windows PowerShell build script
- `docker-compose.yml` - Local Redis & Elasticsearch setup
- `.gitignore` - Git ignore patterns

## Documentation
- `README.md` - Main documentation, features, algorithm, configuration
- `QUICKSTART.md` - 5-minute getting started guide
- `ARCHITECTURE.md` - Clean architecture explanation & design patterns
- `DEVELOPMENT.md` - Development workflow, debugging, deployment
- `API.md` - Complete API reference for all interfaces
- `CHANGELOG.md` - Version history
- `PROJECT_STATUS.md` - Project completion summary

## Testing & Examples
- `test_integration.py` - Full integration test (Redis -> Engine -> Results)
- `scripts/generate-test-data.sh` - Script to generate test data

## Total Files: 30

## Code Statistics
- Go files: 14
- Documentation: 7
- Configuration: 2
- Scripts: 3
- Docker: 1
- Build files: 3

## Key Characteristics
✓ Production-ready error handling
✓ Concurrent processing (goroutines)
✓ Interface-based extensibility
✓ Fully configurable (no hardcoded values)
✓ Structured logging (zap)
✓ Context support (graceful shutdown)
✓ Hot reload for rules
✓ Comprehensive documentation
✓ Full test suite
✓ Clean architecture (SOLID principles)
