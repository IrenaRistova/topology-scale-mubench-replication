# Locust Workload Generator for muBench

Locust-based workload generator for Phase 3 benchmarking experiments.

## Prerequisites

1. **SSH Tunnel**: Ensure the gateway SSH tunnel is running:
   ```bash
   ./scripts/gateway-tunnel-local.sh
   ```
   Gateway should be accessible at: `http://localhost:9090`

2. **Python Virtual Environment**: Activate the project venv:
   ```bash
   source venv/bin/activate
   ```

3. **Locust Installation**: Install Locust (if not already installed):
   ```bash
   pip install -r Benchmarks/Locust/requirements.txt
   ```

## Usage

### Basic Headless Execution (Stochastic Benchmarks)

```bash
# From project root with venv activated
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 10 \
  -r 2 \
  -t 1m \
  --host http://localhost:9090
```

**Parameters:**
- `-u`: Number of concurrent users (e.g., 10, 50, 100)
- `-r`: Spawn rate (users per second, e.g., 2, 5, 10)
- `-t`: Test duration (e.g., `1m` for 1 minute, `10m` for 10 minutes)
- `--host`: Base URL for requests (http://localhost:9090 via SSH tunnel)

### With Metric Export (CSV)

```bash
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 50 \
  -r 5 \
  -t 10m \
  --host http://localhost:9090 \
  --csv=results
```

This creates:
- `results_stats.csv`: Request statistics
- `results_stats_history.csv`: Time-series data
- `results_failures.csv`: Failure details

### Workload Parameter Guidelines

Based on Phase 3 requirements:

| Load Intensity | Users (-u) | Spawn Rate (-r) | Use Case |
|---------------|------------|-----------------|----------|
| Light | 10 | 2 | Initial testing, small topologies |
| Medium | 50 | 5 | Standard benchmarking |
| Heavy | 100 | 10 | Stress testing, large topologies |

**Duration:**
- Warm-up: 2 minutes
- Measurement: 8 minutes
- Total: 10 minutes (`-t 10m`)

### Using Different User Classes

The locustfile includes multiple user classes:

1. **StochasticBenchmarkUser** (default): GET requests to ingress service (s0)
   - Triggers random service calls per workmodel.json probabilities
   - Use for stochastic-driven benchmarks

2. **TraceDrivenBenchmarkUser**: POST requests with JSON trace body
   - Defines exact service call sequences
   - Use for trace-driven benchmarks

To use a specific user class:

```bash
# Use StochasticBenchmarkUser (default)
locust -f Benchmarks/Locust/locustfile.py --headless -u 10 -r 2 -t 1m --host http://localhost:9090

# Use TraceDrivenBenchmarkUser
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 10 \
  -r 2 \
  -t 1m \
  --host http://localhost:9090 \
  -c TraceDrivenBenchmarkUser
```

## Benchmark Patterns

### Stochastic Benchmarks

Sends GET requests to ingress service (typically s0):
```
GET http://localhost:9090/s0
```

This triggers random service calls according to workmodel.json probabilities.

### Trace-Driven Benchmarks

Sends POST requests with JSON trace body:
```
POST http://localhost:9090/s0
Content-Type: application/json

{
  "s0__47072": [{
    "s24__71648": [{}],
    "s28__64944": [{
      "s6__5728": [{}],
      "s20__61959": [{}]
    }]
  }]
}
```

This triggers exact service call sequences defined in the trace.

## Metric Collection

### Locust Metrics

Locust collects:
- **Throughput**: Requests per second (RPS)
- **Response Times**: Min, average, max, median, 95th percentile
- **Failure Rate**: Number and percentage of failed requests
- **User Count**: Active users over time

Export to CSV:
```bash
--csv=results
```

### Prometheus Metrics

Verify traffic appears in Prometheus:
- `mub_request_processing_latency_milliseconds`
- `mub_response_size`
- `mub_internal_processing_latency_milliseconds`
- `mub_external_processing_latency_milliseconds`

## Integration with Experiment Runner

Future integration will allow Experiment Runner to:
- Control Locust execution for automated benchmarking
- Run headless mode for fixed duration (2 min warm-up + 8 min measurement)
- Collect throughput, latency, and failure metrics
- Coordinate with muBench deployment orchestration

## Troubleshooting

### Connection Refused

**Error**: `ConnectionRefusedError` or `Failed to establish connection`

**Solution**: Ensure SSH tunnel is running:
```bash
./scripts/gateway-tunnel-local.sh
```

Verify tunnel is active:
```bash
curl -v http://localhost:9090/s0
```

### No Traffic in Prometheus

**Issue**: Locust runs but no metrics appear in Prometheus

**Solution**:
1. Verify muBench application is deployed and running
2. Check Prometheus is scraping service metrics
3. Verify service endpoints are correct (s0, s1, etc.)

### High Failure Rate

**Issue**: Many requests return non-200 status codes

**Solution**:
1. Check muBench application health
2. Verify service topology matches workload
3. Reduce spawn rate (-r) to avoid overwhelming system
4. Check gateway tunnel connection

## Examples

### Quick Test (1 minute, 10 users)
```bash
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 10 \
  -r 2 \
  -t 1m \
  --host http://localhost:9090
```

### Phase 3 Benchmark (10 minutes, 50 users)
```bash
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 50 \
  -r 5 \
  -t 10m \
  --host http://localhost:9090 \
  --csv=phase3_results
```

### Stress Test (5 minutes, 100 users)
```bash
locust -f Benchmarks/Locust/locustfile.py \
  --headless \
  -u 100 \
  -r 10 \
  -t 5m \
  --host http://localhost:9090 \
  --csv=stress_test_results
```

## References

- [Locust Documentation](https://docs.locust.io/)
- [muBench Manual](../Docs/Manual.md)
- [Project Overview](../../specs/00-overview.md)
- [Feature Brief](../../specs/active/locust-workload-setup/feature-brief.md)

