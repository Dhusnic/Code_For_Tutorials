# Quick Start Guide

Get the log correlation engine running in 5 minutes.

## Prerequisites

- Go 1.21+
- Docker & Docker Compose
- Make (optional, can use `build.sh` on Linux/Mac or `build.ps1` on Windows)

## Step 1: Start Infrastructure

```bash
docker-compose up -d
```

Wait for services to be healthy:
```bash
docker-compose ps
```

You'll see:
- `redis` - Ready for logs
- `elasticsearch` - Ready for results

## Step 2: Build Engine

### Linux/Mac
```bash
chmod +x build.sh
./build.sh
```

### Windows (PowerShell)
```powershell
.\build.ps1
```

### Or using Make
```bash
make build
```

Binary created at: `bin/correlation-engine` (Linux/Mac) or `bin/correlation-engine.exe` (Windows)

## Step 3: Run Engine

```bash
./bin/correlation-engine
# or on Windows:
.\bin\correlation-engine.exe
```

You'll see output like:
```
Starting log correlation engine
loaded rules count=5
Processing started
```

## Step 4: Send Test Data

In a new terminal:

### Using Python
```bash
python3 test_integration.py
```

### Using Bash (with redis-cli)
```bash
./scripts/generate-test-data.sh
```

The engine will detect the logs and apply rules.

## Step 5: Check Results

### Via Elasticsearch
```bash
curl http://localhost:9200/rca_correlated_events/_search
```

### Via Redis CLI
```bash
redis-cli
> LRANGE RCA:135098068173316952064:correlated_events 0 -1
```

## Expected Output

You should see correlation results like:

```json
{
  "log_ids": ["doc_001", "doc_002", "doc_003"],
  "rule_completion": 0.70,
  "rule_id": "CORR_9XK2_MONGO_AUTH_CHAIN",
  "sequence_match": 100,
  "organization_id": "135098068173316952064",
  "timestamp": "2026-04-07T10:28:45.919Z",
  "emit_summary": "MongoDB authentication issues escalating into connectivity failure.",
  "likely_root_cause": "Credential failure or auth configuration drift."
}
```

## Troubleshooting

### Engine won't start
```bash
# Check Redis connection
redis-cli ping

# Check Elasticsearch connection
curl http://localhost:9200

# Check config file
cat config/config.yml
```

### No results generated
1. Check engine logs - look for errors
2. Verify rule organization_id matches test data
3. Check that timestamps are recent (within window)
4. Enable debug logging in `config.yml`

### Port already in use
Change ports in `docker-compose.yml` and/or `config.yml`:
```yaml
redis:
  addr: "localhost:6380"  # Changed from 6379

elasticsearch:
  addresses:
    - "http://localhost:9201"  # Changed from 9200
```

## Next Steps

1. **Read Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Understand Rules**: See [README.md](README.md) - Rule Format section
3. **Add Custom Rules**: Edit `rules/rules.json` and restart engine
4. **Implement Custom Fetcher**: See [DEVELOPMENT.md](DEVELOPMENT.md)

## Development

**Run tests:**
```bash
make test
```

**Format code:**
```bash
make fmt
```

**Clean build:**
```bash
make clean && make build
```

## Performance Testing

Generate high-volume test data:

```bash
# Create 1000 test logs
for i in {1..1000}; do
  echo "{\"signal\": \"mongodb_auth_failed\", \"log_level\": \"warning\", \"doc_id\": \"doc_$i\", \"time_stamp\": \"$(date -u +'%Y-%m-%dT%H:%M:%S.000Z')\"}" | redis-cli -x LPUSH RCA:135098068173316952064:signaled_logs
done
```

Monitor engine performance in logs (look for `processing_time_ms`).

## Clean Up

Stop and remove containers:
```bash
docker-compose down

# Remove volumes to reset data
docker-compose down -v
```

## Production Deployment

See [DEVELOPMENT.md](DEVELOPMENT.md) - Deployment section for:
- Docker image creation
- Kubernetes deployment
- Configuration management
- Monitoring setup
