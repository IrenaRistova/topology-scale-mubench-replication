# muBench Phase 3 Benchmarking — Experiment Definition

This folder contains the **experiment definition** used for the topology–scale muBench study: `RunnerConfig.py`. It defines the run table, workflow hooks, and integration with muBench, Locust, Prometheus, and EnergiBridge.

**Full experiment flow:** **`EXPERIMENT_ARCHITECTURE.md`** in this folder describes the complete experiment flow, architecture, and per-run workflow (hooks, components, data layout). It matches the behaviour implemented in `RunnerConfig.py`. The diagram `expflow.pdf` is in **`5_results_analysis/figures/`** at the package root.

**In this replication package:** The **data from when this experiment was run** (run table and raw per-run files) is provided at the package root under **`5_results_data/`**. Tables and figures for the paper are produced by **`5_results_analysis/`** (Section 5) using that data. This folder holds only the experiment logic, not the results.

---

## What `RunnerConfig.py` does

`RunnerConfig` configures [Experiment Runner](https://github.com/S2-group/experiment-runner) to:

1. **Define the run table** — 6 topologies × 3 system sizes × 10 repetitions = **180 runs**, with factors and data columns.
2. **Deploy muBench** on a remote Kubernetes cluster (server `gl3`) via SSH and K8sDeployer.
3. **Run Locust** in headless mode against the deployed gateway to generate HTTP load.
4. **Collect Prometheus** CPU/memory metrics for the run’s namespace.
5. **Measure energy** with EnergiBridge (Intel RAPL) on the server during the load phase.
6. **Persist results** per run (Locust CSVs, Prometheus values, EnergiBridge CSV) and aggregate them into a run table.

All timing, endpoints, and paths are set in `RunnerConfig.py`.

---

## Experiment design

**Factors:**

| Factor         | Levels |
|----------------|--------|
| **topology**   | `sequential_fanout`, `parallel_fanout`, `chain_with_branching`, `hierarchical_tree`, `probabilistic_tree`, `complex_mesh` |
| **system_size**| `5`, `10`, `20` (number of services) |

**Repetitions:** 10 per (topology, size)  
**Total runs:** 6 × 3 × 10 = **180**

**Topology → workmodel mapping** (see `get_workmodel_path()` in `RunnerConfig.py`):

- `sequential_fanout` → workmodel-serial-{5|10|20}services.json  
- `parallel_fanout` → workmodel-parallel-{5|10|20}services.json  
- `chain_with_branching` → workmodelA-{5|10|20}services.json / workmodelA.json  
- `hierarchical_tree` → workmodelC-{5|10|20}services.json / workmodelC.json  
- `probabilistic_tree` → workmodelC-multi-{5|10|20}services.json / workmodelC-multi.json  
- `complex_mesh` → workmodelD-{5|10|20}services.json / workmodelD.json  

Workmodels are resolved under muBench’s `Examples/` (path built from `MUBENCH_DIR` in the config).

---

## Main parameters (in `RunnerConfig.py`)

| Parameter                 | Value   | Meaning |
|---------------------------|---------|--------|
| `time_between_runs_in_ms` | 60 000  | 1 minute cooldown between runs |
| `LOCUST_USERS`            | 100     | Concurrent Locust users |
| `LOCUST_SPAWN_RATE`       | 50      | Users spawned per second |
| `LOCUST_DURATION`         | `"10m"` | Load phase duration |
| `GATEWAY_URL`             | `http://localhost:9090` | Gateway (via SSH port-forward) |
| `PROMETHEUS_URL`          | `http://localhost:30000` | Prometheus (via SSH tunnel) |

Execution assumes SSH to host **`gl3`** (Kubernetes, muBench, EnergiBridge) and tunnels from the **local** machine to gateway and Prometheus.

---

## Workflow: what happens in each hook

The config subscribes to Experiment Runner events. For each run, the sequence is:

1. **`before_experiment`**  
   Check muBench components; start SSH tunnels for gateway (9090) and Prometheus (30000) if not already running; check Prometheus health.

2. **`start_run`**  
   - Map (topology, size) to workmodel path and generate `K8sParameters.json` on the server.  
   - Create (or clean) Kubernetes namespace `mubench-{topology}-{size}-{replicate}`.  
   - Run muBench’s K8sDeployer on the server to deploy the workmodel.  
   - Wait for all pods in the namespace to be ready (timeout depends on size).  
   - Start `kubectl port-forward` for `gw-nginx` so the gateway is reachable at `localhost:9090`.  
   - Write `namespace.txt` in the run directory for later hooks.

3. **`start_measurement`**  
   Record measurement start time; start **EnergiBridge** on the server (writes CSV under `/tmp/energibridge_{namespace}/`).

4. **`interact`**  
   - Gateway readiness: poll `GATEWAY_URL/s0` until 3 consecutive 200 responses.  
   - Run **Locust** headless: `-u LOCUST_USERS`, `-r LOCUST_SPAWN_RATE`, `-t LOCUST_DURATION`, CSV and HTML under run dir `locust/`.

5. **`stop_measurement`**  
   - Record measurement end time.  
   - Stop EnergiBridge (SIGTERM), wait, then copy `energibridge.csv` from the server into the run dir as `energibridge_output.csv`.  
   - Query Prometheus for CPU and memory over the run’s namespace; write `prometheus_cpu.txt` and `prometheus_memory.txt` in the run dir.

6. **`stop_run`**  
   Delete the run’s Kubernetes namespace.

7. **`populate_run_data`**  
   Parse run-dir artifacts and return a dict of metrics for the run table:
   - **Locust:** `results_stats.csv` → throughput_rps, avg_latency_ms, p95_latency_ms, failure_rate, request_count.  
   - **Prometheus:** `prometheus_cpu.txt` / `prometheus_memory.txt` → cpu_usage_avg, memory_usage_avg.  
   - **EnergiBridge:** `energibridge_output.csv` → energy (PACKAGE_ENERGY delta), dram_energy (DRAM_ENERGY delta), cpu_usage_eb_avg, cpu_freq_avg, memory_used_avg, memory_total; **RAPL overflow** is corrected when last < first using a 262144 J ceiling.

8. **`after_experiment`**  
   Clean up any remaining EnergiBridge process on the server.

Experiment Runner writes the returned dict into the run table and, by default, stores each run’s directory under `results_output_path / name /` (e.g. `run_0_repetition_0/`, …).

---

## Data columns in the run table

Defined in `create_run_table_model()` → `data_columns`:

- **Locust:** `throughput_rps`, `avg_latency_ms`, `p95_latency_ms`, `failure_rate`, `request_count`  
- **Prometheus:** `cpu_usage_avg`, `memory_usage_avg`  
- **EnergiBridge:** `energy`, `dram_energy`, `cpu_usage_eb_avg`, `cpu_freq_avg`, `memory_used_avg`, `memory_total`

Plus Experiment Runner’s `__run_id` and `__done`.  
The **data from the run** of this experiment, and the meaning of each column, are described in the replication package under **`5_results_data/README.md`** and **`5_results_data/RUN_TABLE_COLUMNS_EXPLANATION.md`**.

---

## Where things live in the replication package

| Role           | Location | Paper section |
|----------------|----------|----------------|
| **Experiment definition** (this RunnerConfig) | `4_experiment_execution/experiment-runner/examples/mubench-benchmarking/` | Section 4 |
| **Data from when the experiment was run**    | **`5_results_data/`** (run table + `raw_runs/`) at package root | Section 5 |
| **Scripts and figures used in the paper**    | **`5_results_analysis/`** at package root | Section 5 |

So: *this* README describes *how* the experiment was executed and what RunnerConfig does; *what* was observed is in **`5_results_data/`**, and *how* it was turned into tables/figures is in **`5_results_analysis/`**.

---

## Running this experiment (full re-run)

To re-execute the same experiment you need:

- **muBench** (sibling to the experiment-runner repo or path set via `MUBENCH_DIR`), with workmodels under `Examples/` and K8sDeployer.
- **Server (e.g. gl3):** Kubernetes (e.g. Minikube), Prometheus, **[EnergiBridge](https://github.com/S2-group/energibridge)** (in PATH for RAPL energy), and the same workmodel files. EnergiBridge runs on the server and is started/stopped by the runner via SSH.
- **SSH** to the server and tunnels so that, from the machine running Experiment Runner, the gateway is at `http://localhost:9090` and Prometheus at `http://localhost:30000`.
- **Locust** — the runner calls `LOCUST_EXECUTABLE` with `LOCUST_FILE`. By default these are `muBench/venv/bin/locust` and `muBench/Benchmarks/Locust/locustfile.py`. You must create `muBench/venv`, install Locust there (e.g. `pip install -r Benchmarks/Locust/requirements.txt`), or point `LOCUST_EXECUTABLE` at another Locust binary.

**What to install (Locust, EnergiBridge, Python deps, server stack)** and **full run instructions** (server one-time setup, Prometheus port-forward, SSH tunnels, optional verify-deployment/run-sar, cleanup, and the exact run command) are in:

- **`HOW_TO_RUN_THE_EXPERIMENT.md`** (in `4_experiment_execution/`, one level up from `experiment-runner/`) — see **§ What to install** and the rest of that file.

From the **experiment-runner** root (inside this replication package):

```bash
cd "4_experiment_execution/experiment-runner"
pip install -r requirements.txt
python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py
```

Results will be written under the config’s `results_output_path` (by default under this example’s `experiments/`). The replication package’s **`5_results_data/`** is a snapshot of the data produced when the experiment was run for the paper; re-running creates new result directories and does not overwrite `5_results_data/` unless you copy them there.

---

## References

- [Experiment Runner](https://github.com/S2-group/experiment-runner)
- [Section 4: Experiment execution](../../../README.md) — layout of this folder, and where `5_results_data/` and `5_results_analysis/` live in the replication package
