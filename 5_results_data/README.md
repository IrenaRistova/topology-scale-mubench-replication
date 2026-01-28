# Section 5: Results data

This directory contains the experiment data used for all tables, plots, and statistical tests in the paper. It corresponds to **Section 5** (Results and Analysis — data) of the paper.

**Paper section:** Section 5.

## Contents

- **`run_table.csv`** — Core artifact. One row per (run, repetition). Columns include: topology, system_size, throughput_rps, avg_latency_ms, p95_latency_ms, failure_rate, request_count, cpu_usage_avg, memory_usage_avg, energy, dram_energy, and derived metrics. All analysis in the paper is based on this file.

- **`RUN_TABLE_COLUMNS_EXPLANATION.md`** — Describes every column in `run_table.csv`: meaning, data source (Locust / Prometheus / EnergiBridge), units, and how values are computed from the raw run folders.

- **`raw_runs/`** — Per-run, per-repetition folders (`run_X_repetition_Y`). Each folder contains:
  - **Locust results**: `locust/` — `locust_output.txt`, `results_stats.csv`, `results_stats_history.csv`, `results.html`, `results_failures.csv`, `results_exceptions.csv`
  - **Prometheus logs**: `prometheus_cpu.txt`, `prometheus_memory.txt` — CPU and memory time series for the measurement window
  - **EnergiBridge**: `energibridge_output.csv` — RAPL energy (package + DRAM) samples
  - **Metadata**: `measurement_start.txt`, `measurement_end.txt`, `namespace.txt`

**Provenance:** Data produced by the Experiment Runner when running the experiment defined in **`4_experiment_execution/`** (Section 4). Run table and per-run directories correspond to `4_experiment_execution/experiment-runner/examples/mubench-benchmarking/experiments/mubench_phase3_benchmarking/`.

**Omitted file (GitHub size limit):** One raw EnergiBridge file — `raw_runs/run_15_repetition_5/energibridge_output.csv` — exceeds GitHub’s 100 MB file limit and is not included in this repository. Its aggregated energy metrics are in `run_table.csv`. To obtain the raw file, re-run that run (run 15, repetition 5) using the instructions in [4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md](../4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md).

**Analysis:** The scripts in **`5_results_analysis/`** (Section 5) use this data to produce the paper’s figures and tables. See [5_results_analysis/README.md](../5_results_analysis/README.md).
