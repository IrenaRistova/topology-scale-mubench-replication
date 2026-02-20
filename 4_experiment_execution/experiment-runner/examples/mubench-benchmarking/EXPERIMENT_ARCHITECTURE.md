# muBench Benchmarking Experiment Architecture

This document describes the **full experiment flow and architecture**. It matches the behaviour implemented in `RunnerConfig.py` in this folder. The diagram in the replication package (`5_results_analysis/figures/figure1_experiment_execution.pdf`, paper Figure 1) is a visual counterpart.

## Overview

This document describes the complete architecture and workflow of the muBench Phase 3 benchmarking experiment, which systematically evaluates microservice topologies under load using multiple monitoring tools.

## Experiment Configuration

- **Topologies**: 6 patterns (sequential_fanout, parallel_fanout, chain_with_branching, hierarchical_tree, probabilistic_tree, complex_mesh)
- **System Sizes**: 5, 10, and 20 services
- **Repetitions**: 10 runs per configuration
- **Total Runs**: 180 (6 × 3 × 10)
- **Load**: 100 concurrent users, 50 users/s spawn rate, 10-minute duration per run
- **Cooldown**: 1 minute between runs

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HOST MACHINE (Local)                               │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              Experiment Runner (Python)                              │   │
│  │  - Orchestrates entire experiment workflow                          │   │
│  │  - Manages run table (180 configurations)                           │   │
│  │  - Coordinates deployment, measurement, and cleanup                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              │ SSH Tunnels                                   │
│                              │                                               │
│  ┌───────────────────────────┴───────────────────────────────────────┐   │
│  │                    SSH Tunnel Layer                                 │   │
│  │  ┌──────────────────────┐      ┌──────────────────────┐          │   │
│  │  │ Gateway Tunnel       │      │ Prometheus Tunnel     │          │   │
│  │  │ localhost:9090       │      │ localhost:30000      │          │   │
│  │  │ → gl3:9090           │      │ → gl3:30000          │          │   │
│  │  └──────────────────────┘      └──────────────────────┘          │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│  ┌───────────────────────────┴───────────────────────────────────────┐   │
│  │                    Locust Load Generator                             │   │
│  │  - 100 concurrent users                                             │   │
│  │  - 10-minute test duration                                         │   │
│  │  - Sends requests to gateway via localhost:9090                    │   │
│  │  - Outputs: CSV stats, HTML report                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ SSH Connection
                                    │ (via glgate jump host)
                                    │
┌───────────────────────────────────▼───────────────────────────────────────┐
│                        REMOTE SERVER (gl3)                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                    Kubernetes Cluster                                │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │         muBench Application (per run)                         │   │   │
│  │  │  Namespace: mubench-{topology}-{size}-{replicate}            │   │   │
│  │  │                                                               │   │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │   │
│  │  │  │   Service s0 │  │   Service s1 │  │   Service sN │      │   │   │
│  │  │  │  (Gateway)   │  │              │  │              │      │   │   │
│  │  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │   │   │
│  │  │         │                 │                 │               │   │   │
│  │  │         └─────────────────┴─────────────────┘               │   │   │
│  │  │                    Service Mesh                              │   │   │
│  │  │                                                               │   │   │
│  │  │  ┌──────────────────────────────────────────────────────┐   │   │   │
│  │  │  │         NGINX Gateway (gw-nginx)                      │   │   │   │
│  │  │  │         Port-forward: 9090:80                         │   │   │   │
│  │  │  │         Entry point for all requests                  │   │   │   │
│  │  │  └──────────────────────────────────────────────────────┘   │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │         Prometheus (monitoring namespace)                     │   │   │
│  │  │         - Collects metrics from all pods                      │   │   │
│  │  │         - Port-forward: 30000:9090                          │   │   │
│  │  │         - Metrics: CPU, memory, network                       │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                    EnergiBridge (Server Process)                     │   │   │
│  │  - Runs on server (not in container)                               │   │   │
│  │  - Measures CPU package energy (RAPL)                              │   │   │
│  │  - Measures DRAM energy                                             │   │   │
│  │  - Collects CPU usage, frequency, memory                            │   │   │
│  │  - Outputs: energibridge.csv                                        │   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Experiment Runner
- **Location**: Host machine
- **Role**: Orchestrates the entire experiment lifecycle
- **Key Functions**:
  - Generates run table (180 configurations)
  - Manages experiment workflow (before_experiment → start_run → start_measurement → interact → stop_measurement → populate_run_data → stop_run → after_experiment)
  - Coordinates all tools and data collection
  - Aggregates results into `run_table.csv`

### 2. muBench Deployment System
- **Location**: Remote server (gl3)
- **Tool**: K8sDeployer (`RunK8sDeployer.py`)
- **Input**: Workmodel JSON files (define topology, service count, workload)
- **Output**: Kubernetes resources (Deployments, Services, ConfigMaps)
- **Process**:
  1. Reads workmodel JSON (topology pattern, service count)
  2. Generates Kubernetes YAML files
  3. Creates namespace: `mubench-{topology}-{size}-{replicate}`
  4. Deploys all services and gateway
  5. Waits for pods to be ready

### 3. SSH Tunnels
- **Purpose**: Enable host machine to access services on remote server
- **Setup**: One-time before experiment starts
- **Tunnels**:
  - **Gateway Tunnel**: `localhost:9090 → gl3:9090`
    - Forwards to kubectl port-forward of gw-nginx service
    - Used by Locust to send requests
  - **Prometheus Tunnel**: `localhost:30000 → gl3:30000`
    - Forwards to kubectl port-forward of Prometheus service
    - Used by Experiment Runner to query metrics

### 4. Locust Load Generator
- **Location**: Host machine
- **Role**: Generates HTTP load on the microservice application
- **Configuration**:
  - 100 concurrent users
  - 50 users/second spawn rate
  - 10-minute test duration
- **Output**:
  - `results_stats.csv`: Request statistics (throughput, latency, failures)
  - `results.html`: Visual report
- **Metrics Collected**:
  - Throughput (requests/second)
  - Average latency (ms)
  - 95th percentile latency (ms)
  - Failure rate (%)

### 5. Prometheus Monitoring
- **Location**: Remote server (Kubernetes cluster, `monitoring` namespace)
- **Role**: Collects system-level metrics from all pods
- **Metrics Collected**:
  - CPU usage: `rate(container_cpu_usage_seconds_total[5m])`
  - Memory usage: `container_memory_working_set_bytes`
- **Access**: Via SSH tunnel on `localhost:30000`
- **Query Method**: REST API (`/api/v1/query`)

### 6. EnergiBridge Energy Profiler
- **Location**: Remote server (runs as process, not in container)
- **Role**: Measures hardware-level energy consumption
- **Technology**: Intel RAPL (Running Average Power Limit)
- **Metrics Collected**:
  - **Package Energy (J)**: Total CPU package energy consumption
  - **DRAM Energy (J)**: Memory subsystem energy consumption
  - **CPU Usage (%)**: Per-core CPU utilization
  - **CPU Frequency (MHz)**: Per-core CPU frequency
  - **Memory Used (Bytes)**: System memory usage
  - **Memory Total (Bytes)**: Total system memory
- **Output**: `energibridge.csv` (time-series data)
- **Special Handling**: RAPL counter overflow correction (max value: 262,144 J)

## Experiment Workflow

### Phase 1: Experiment Initialization (One-Time)

```
1. Start Prometheus port-forward on server:
   kubectl -n monitoring port-forward svc/prometheus-nodeport 30000:9090 &

2. Start SSH tunnels on host:
   ./scripts/tunnels-local.sh
   - Creates gateway tunnel (9090)
   - Creates Prometheus tunnel (30000)

3. Verify connectivity:
   - Test gateway: curl http://localhost:9090/s0
   - Test Prometheus: curl http://localhost:30000/api/v1/status/config
```

### Phase 2: Per-Run Workflow (Repeated 180 Times)

The Experiment Runner invokes hooks in this order. Each box corresponds to one hook in `RunnerConfig.py`.

```
┌─────────────────────────────────────────────────────────────┐
│ BEFORE_RUN                                                   │
│ - Select configuration (topology, size, repetition)         │
│ - Create run directory                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ START_RUN                                                    │
│ 1. Map topology+size to workmodel, generate K8sParameters   │
│ 2. Cleanup old namespaces (if any)                          │
│ 3. Create namespace mubench-{topology}-{size}-{replicate}    │
│ 4. Run K8sDeployer on server (SSH)                          │
│ 5. Wait for all pods ready                                  │
│ 6. Start gateway port-forward on server (9090:80)            │
│ 7. Write namespace.txt in run directory                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ START_MEASUREMENT                                            │
│ 1. Record measurement_start.txt                             │
│ 2. Start EnergiBridge on server:                             │
│    energibridge -o /tmp/energibridge_{namespace}/ --summary │
│    (runs in background for the duration of the load phase)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ INTERACT                                                     │
│ 1. Gateway readiness: GET localhost:9090/s0 until 3          │
│    consecutive 200 responses                                 │
│ 2. Run Locust (headless):                                    │
│    - 100 users, 50/s spawn rate, 10-minute duration         │
│    - Host http://localhost:9090                              │
│    - CSV/HTML output in run dir/locust/                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ (10 minutes)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ STOP_MEASUREMENT                                             │
│ 1. Record measurement_end.txt                                │
│ 2. Stop EnergiBridge (SIGTERM), wait for summary              │
│ 3. Retrieve energibridge.csv from server (ssh cat) →         │
│    run dir/energibridge_output.csv                           │
│ 4. Query Prometheus for CPU and memory (namespace)           │
│ 5. Write prometheus_cpu.txt, prometheus_memory.txt           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ POPULATE_RUN_DATA                                            │
│ Parse run directory and return metrics dict:                 │
│ - Locust results_stats.csv → throughput, latency, failures   │
│ - EnergiBridge CSV → energy, dram_energy, CPU, memory        │
│   (with RAPL overflow correction when last < first)          │
│ - Prometheus files → cpu_usage_avg, memory_usage_avg        │
│ Experiment Runner appends this row to run_table.csv          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ STOP_RUN                                                     │
│ 1. Delete Kubernetes namespace for this run                  │
│ 2. Wait for cooldown (1 minute) before next run              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                    Next Run
```

`before_experiment` runs once at the start (tunnels, Prometheus check). `after_experiment` runs once at the end (cleanup).

## Data Collection and Storage

### Per-Run Directory Structure

The **data from when this experiment was run** is provided in this replication package under **`5_results_data/`** at the package root. The layout of each run directory is:

```
5_results_data/raw_runs/run_X_repetition_Y/
├── namespace.txt                # Kubernetes namespace used
├── measurement_start.txt         # Timestamp
├── measurement_end.txt           # Timestamp
├── locust/
│   ├── results_stats.csv        # Locust performance metrics
│   ├── results.html             # Locust HTML report
│   └── locust_output.txt        # Full Locust log
├── energibridge_output.csv      # Energy and system metrics
├── prometheus_cpu.txt            # CPU usage from Prometheus
└── prometheus_memory.txt         # Memory usage from Prometheus
```

Aggregated results are in **`5_results_data/run_table.csv`**.

### Metrics Collected

#### Performance Metrics (Locust)
- **throughput_rps**: Requests per second
- **avg_latency_ms**: Average response time
- **p95_latency_ms**: 95th percentile latency
- **failure_rate**: Fraction of failed requests
- **request_count**: Total requests sent

#### Energy Metrics (EnergiBridge)
- **energy**: CPU package energy consumption (Joules)
- **dram_energy**: DRAM energy consumption (Joules)
- **cpu_usage_eb_avg**: Average CPU usage across all cores (%)
- **cpu_freq_avg**: Average CPU frequency (MHz)
- **memory_used_avg**: Average memory used (Bytes)
- **memory_total**: Total system memory (Bytes)

#### System Metrics (Prometheus)
- **cpu_usage_avg**: Average CPU usage rate (from container metrics)
- **memory_usage_avg**: Average memory working set (Bytes)

See **`data/RUN_TABLE_COLUMNS_EXPLANATION.md`** in the replication package for column-by-column detail.

## Key Technical Details

### RAPL Counter Overflow Handling

Intel RAPL energy counters are cumulative and have a maximum value of 262,144 Joules. When this limit is reached, the counter resets to zero, causing negative energy calculations. The system detects this overflow condition (`last_reading < first_reading`) and applies correction:

```
corrected_energy = (MAX_COUNT - first_reading) + last_reading
```

### Namespace Management

- Each run uses a unique namespace: `mubench-{topology}-{size}-{replicate}`
- Namespaces are created before deployment and deleted in `stop_run`
- Prevents resource accumulation and ensures clean state for each run

### Gateway Readiness

Before starting Locust (`interact`), the system:
- Sends HTTP requests to `GET localhost:9090/s0`
- Requires 3 consecutive successful (200) responses
- Waits a short stabilization (3–5 s depending on system size)
- Ensures the gateway is ready before load

### SSH File Transfer

EnergiBridge CSV files are retrieved using `ssh cat` instead of `scp`:
- More reliable for large files
- Handles network interruptions better
- Streams data directly into the run directory

## Experiment Results

The final **`5_results_data/run_table.csv`** contains 180 rows (one per run) with all aggregated metrics. Each row includes:
- Configuration: topology, system_size, __run_id, __done
- Performance: throughput_rps, avg_latency_ms, p95_latency_ms, failure_rate, request_count
- Energy: energy, dram_energy, cpu_usage_eb_avg, cpu_freq_avg, memory_used_avg, memory_total
- System: cpu_usage_avg, memory_usage_avg

This dataset is used by the **Jupyter notebooks in `5_results_analysis/notebooks/`** to produce the paper’s tables and figures.
