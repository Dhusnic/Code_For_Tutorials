# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-04-07

### Added
- Initial release of log correlation engine
- Sliding window sequence matching algorithm
- Rule-based correlation with ordered sequence rules
- Redis input for signalized logs
- Elasticsearch output for correlated events
- Hot reload support for rules.json
- Structured logging with zap
- Configurable defaults from config.yml
- Deduplication within configurable windows
- Support for negative conditions in rules
- Score calculation (rule_completion and sequence_match)
- Per-organization concurrent processing
- Mock log fetcher for testing
- Interface-based design for extensibility
- Comprehensive test suite
- Docker Compose for local development

### Features
- **Ordered Sequence Matching**: Matches multi-step failure patterns
- **Time Window Constraints**: Apply `window`, `within`, and `max_gap_between_steps`
- **Deduplication**: Remove duplicates within time window
- **Negative Conditions**: Cancel rule on specific signal occurrence
- **Priority Handling**: Order emitted results by priority
- **Graceful Shutdown**: Context-based cancellation
- **Error Recovery**: Robust error handling without panic
- **Metrics**: Track processed logs and matched rules
