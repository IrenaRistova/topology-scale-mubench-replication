# Locust Quick Start Guide

## Quick Test

1. **Start SSH tunnel** (in separate terminal):
   ```bash
   ./scripts/gateway-tunnel-local.sh
   ```

2. **Activate venv and run Locust**:
   ```bash
   source venv/bin/activate
   cd Benchmarks/Locust
   locust -f locustfile.py --headless -u 10 -r 2 -t 1m --host http://localhost:9090
   ```

## Common Commands

### Basic Test (1 minute)
```bash
locust -f locustfile.py --headless -u 10 -r 2 -t 1m --host http://localhost:9090
```

### Phase 3 Benchmark (10 minutes with CSV export)
```bash
locust -f locustfile.py --headless -u 50 -r 5 -t 10m --host http://localhost:9090 --csv=results
```

### Check Locust Version
```bash
source venv/bin/activate
locust --version
```

## Files Created

- `locustfile.py`: Main Locust test file with stochastic and trace-driven patterns
- `requirements.txt`: Locust dependency
- `README.md`: Complete documentation
- `QUICKSTART.md`: This quick reference

## Next Steps

1. Ensure SSH tunnel is running
2. Deploy muBench application
3. Test headless execution
4. Verify Prometheus metrics

See `README.md` for detailed documentation.

