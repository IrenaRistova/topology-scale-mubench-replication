# Section 4: Experiment Execution

This folder contains everything needed to **re-run** the topology–scale muBench experiment: the [Experiment Runner](https://github.com/S2-group/experiment-runner) framework, a copy of [muBench](https://github.com/mSvcBench/muBench), and the experiment definition (factors, workflow, measurement logic). It corresponds to **Section 4** of the paper.

**If you want to replicate the experiment**, start with **[HOW_TO_RUN_THE_EXPERIMENT.md](HOW_TO_RUN_THE_EXPERIMENT.md)** in this folder. It gives step-by-step commands for server setup, tunnels, and running the experiment.

---

## What is in this folder

| Item | Description |
|------|-------------|
| **`experiment-runner/`** | [Experiment Runner](https://github.com/S2-group/experiment-runner) (S2-group). Snapshot: [26bdb52](https://github.com/S2-group/experiment-runner/tree/26bdb52b6ad9ceb61d634b8e4503eb5d711eab1e). Framework + examples; no `venv/`, `.git/`, or `__pycache__`. |
| **`muBench/`** | muBench tree used for this experiment. Includes the 18 workmodel JSONs (Section 3 planning artifacts), K8s deployer, Locust benchmark, and the **five scripts** used in the run (see below). Trimmed from upstream: no manual-topology generators, no Alibaba/jmeter/Teastore examples. |
| **`experiment-runner/examples/mubench-benchmarking/`** | **Experiment definition**: `RunnerConfig.py`, `README.md`, `EXPERIMENT_ARCHITECTURE.md`. This is where the run table (180 runs), workflow hooks, and integration with muBench, Locust, Prometheus, and EnergiBridge are defined. |

**Layout:** `experiment-runner/` and `muBench/` are **siblings** here. `RunnerConfig.py` resolves muBench via `MUBENCH_DIR` to the `muBench/` folder in this directory when you run from the replication package.

---

## Where results and analysis live (replication package)

The **data** and **analysis** for the paper are **not** under this folder. They are at the top level of the replication package:

| Role | Path (from replication package root) |
|------|--------------------------------------|
| **Data from the run** (run table + per-run folders) | **`5_results_data/`** — `run_table.csv`, `raw_runs/`, `RUN_TABLE_COLUMNS_EXPLANATION.md`. See [5_results_data/README.md](../5_results_data/README.md). |
| **Analysis** (notebooks and outputs for the paper) | **`5_results_analysis/`** — Jupyter notebooks, figures, tables. Uses `5_results_data/run_table.csv`. See [5_results_analysis/README.md](../5_results_analysis/README.md). |

So: **4_experiment_execution** = how to run the experiment (Section 4); **`5_results_data/`** = what was observed; **`5_results_analysis/`** = Jupyter notebooks that produce the paper’s tables and figures (Section 5).

---

## Prerequisites (to replicate)

A full list of **what to install** (Locust, EnergiBridge, Python deps, server stack) is in **[HOW_TO_RUN_THE_EXPERIMENT.md § What to install](HOW_TO_RUN_THE_EXPERIMENT.md#what-to-install)**. Summary:

- **Host:** Python 3.8+, Experiment Runner deps (`pip install -r experiment-runner/requirements.txt`), **Locust** (RunnerConfig expects `muBench/venv/bin/locust` — create `muBench/venv` and run `pip install -r muBench/Benchmarks/Locust/requirements.txt`), and SSH to the server.
- **Server (e.g. gl3):** Kubernetes (e.g. Minikube), Docker, kubectl, Prometheus, **[EnergiBridge](https://github.com/S2-group/energibridge)** (in PATH for RAPL energy), and a copy of muBench with the same scripts and workmodels as **`muBench/`** in this folder.
- **Connectivity:** SSH tunnels so that from the host, the gateway is at `http://localhost:9090` and Prometheus at `http://localhost:30000` (see HOW_TO_RUN).

---

## How to replicate — quick map

1. **Read** [HOW_TO_RUN_THE_EXPERIMENT.md](HOW_TO_RUN_THE_EXPERIMENT.md) for the full sequence.
2. **On the server:** one-time `muBench/scripts/setup-infrastructure.sh`; per experiment `muBench/scripts/start-prometheus-port-forward.sh`. Optional: `verify-deployment.sh`, `run-sar-on-server.sh`.
3. **On the host:** per experiment, run `muBench/scripts/tunnels-local.sh` (from this folder: `muBench/scripts/tunnels-local.sh`), then run the Experiment Runner (see below).
4. **Run the experiment** (from the replication package root or from `4_experiment_execution/experiment-runner/`):

   ```bash
   cd "4_experiment_execution/experiment-runner"
   pip install -r requirements.txt
   source .venv/bin/activate   # or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && source .venv/bin/activate
   python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py
   ```

   Results are written under `experiment-runner/examples/mubench-benchmarking/experiments/mubench_phase3_benchmarking/` (run table + per-run directories). The replication package’s **`5_results_data/`** is a snapshot of that output from when the experiment was run for the paper.

5. **Reproduce only tables/figures** (no re-run): run the Jupyter notebooks in **`5_results_analysis/`** using **`5_results_data/run_table.csv`** — see [5_results_analysis/README.md](../5_results_analysis/README.md).

---

## muBench copy in this folder (Section 3 planning + Section 4 execution)

The **`muBench/`** tree here holds both **Section 3** planning artifacts (workmodels) and the scripts used in **Section 4** execution:

- **Workmodels (Section 3):** The 18 files referenced by `get_workmodel_path()` in `RunnerConfig.py`:  
  `workmodel-serial-{5,10,20}services.json`, `workmodel-parallel-{5,10,20}services.json`, `workmodelA-{5,10}services.json` + `workmodelA.json`, `workmodelC-*`, `workmodelC-multi-*`, `workmodelD-*` under `Examples/`.
- **Scripts used (Section 4):**  
  `scripts/setup-infrastructure.sh`, `scripts/start-prometheus-port-forward.sh`, `scripts/tunnels-local.sh`, `scripts/verify-deployment.sh`, `scripts/run-sar-on-server.sh`.
- **Configs:** e.g. `Configs/K8sParameters.json` and related JSONs used by the deployer.

On the **server**, you need a matching environment (same scripts and workmodels). You can copy this `muBench/` to the server (e.g. as `~/muBench`) or sync the relevant parts.

---

## More detail

- **Experiment design, factors, workflow:**  
  `experiment-runner/examples/mubench-benchmarking/README.md` and **`EXPERIMENT_ARCHITECTURE.md`** in that folder.
- **Diagram of the experiment flow:**  
  `5_results_analysis/figures/expflow.pdf` (at the replication package root).
- **Run commands, tunnels, cleanup:**  
  [HOW_TO_RUN_THE_EXPERIMENT.md](HOW_TO_RUN_THE_EXPERIMENT.md).
