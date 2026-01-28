# Replication Package – Topology and Scale Effects on Performance and Energy in μBench Microservices

This repository supports replication of the study on topology and scale effects on performance and energy in μBench microservices. The layout is aligned with the paper structure:

- **Section 3: Experiment Planning** — Topology definitions, workmodels, and service-graph choices. These are **not** in a separate directory; they are documented below and live inside **`4_experiment_execution/`**.
- **Section 4: Experiment Execution** — **`4_experiment_execution/`**
- **Section 5: Results and Analysis** — **`5_results_data/`** (data) and **`5_results_analysis/`** (scripts and outputs)

---

## How to cite the dataset

If this replication package is helping your research, consider citing it as follows:

```
@misc{ReplicationPackage2026,
  title     = {{Replication Package for ``Topology and Scale Effects on Performance and Energy in $\mu$Bench Microservices''}},
  author    = {Ristova, Irena},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/IrenaRistova/topology-scale-mubench-replication},
  note      = {Accessed: 2026-01-26}
}
```

*(Update the `note` field with your date of access when citing.)*

---

## Section 3: Experiment Planning (no separate folder)

The material that corresponds to **Section 3** of the paper (experiment planning: topologies, workmodels, service graphs) is contained in **`4_experiment_execution/`**:

- **Workmodel definitions:** `4_experiment_execution/muBench/Examples/` — The 18 workmodel JSON files used in the experiment (e.g. `workmodel-serial-{5,10,20}services.json`, `workmodel-parallel-*`, `workmodelA*`, `workmodelC*`, `workmodelC-multi*`, `workmodelD*`). These define topology patterns and system sizes.
- **Topology–workmodel mapping:** `4_experiment_execution/experiment-runner/examples/mubench-benchmarking/RunnerConfig.py` — The function `get_workmodel_path()` maps each (topology, size) to a workmodel file. The factors (6 topologies × 3 sizes) and design are documented in that folder’s `README.md` and `EXPERIMENT_ARCHITECTURE.md`.
- **Deployment configuration:** `4_experiment_execution/muBench/Configs/` — Configs used by the deployer (e.g. `K8sParameters.json`).

There is **no** `3_experiment_planning/` directory; the planning artifacts above are used directly by the execution in Section 4.

---

## Section 4: Experiment Execution — `4_experiment_execution/`

**Paper section:** Section 4 (Experiment Execution).

This directory contains everything needed to re-run the experiment: [Experiment Runner](https://github.com/S2-group/experiment-runner), a trimmed copy of [muBench](https://github.com/mSvcBench/muBench), and the experiment definition (`RunnerConfig.py`). It includes the workmodels and scripts used for deployment, load generation (Locust), and measurement (Prometheus, EnergiBridge).

- **Contents:** `experiment-runner/`, `muBench/`, and the mubench-benchmarking example (`RunnerConfig.py`, `EXPERIMENT_ARCHITECTURE.md`).
- **Documentation:** [4_experiment_execution/README.md](4_experiment_execution/README.md), [4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md](4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md).

---

## Section 5: Results and Analysis

### `5_results_data/` — Result data (Section 5)

**Paper section:** Section 5 (Results and Analysis — data).

Contains the experiment outputs: `run_table.csv` (aggregated metrics per run), `raw_runs/` (per-run Locust, Prometheus, and EnergiBridge outputs), and `RUN_TABLE_COLUMNS_EXPLANATION.md`.

- **Documentation:** [5_results_data/README.md](5_results_data/README.md).

### `5_results_analysis/` — Analysis scripts and outputs (Section 5)

**Paper section:** Section 5 (Results and Analysis — scripts and figures).

Contains the scripts that produce the paper’s figures and tables from `5_results_data/run_table.csv`. Outputs are written to `5_results_analysis/figures/` and `5_results_analysis/tables/`.

- **Documentation:** [5_results_analysis/README.md](5_results_analysis/README.md).

---

## Replicating the data analysis (Section 5 only)

To reproduce the paper’s tables and figures from the provided data **without** re-running the experiment:

```bash
pip install -r 5_results_analysis/requirements.txt
python3 5_results_analysis/make_results.py
```

Input: `5_results_data/run_table.csv`. Outputs: `5_results_analysis/figures/`, `5_results_analysis/tables/`. See [5_results_analysis/README.md](5_results_analysis/README.md).

---

## Running the entire replication (Sections 4 and 5)

1. **Section 4 — Experiment execution:** Follow [4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md](4_experiment_execution/HOW_TO_RUN_THE_EXPERIMENT.md) to install prerequisites, set up the server, start tunnels, and run the Experiment Runner. Results are produced under the runner’s output path; the package’s **`5_results_data/`** is a snapshot of that output.
2. **Section 5 — Analysis:** Use the run table (from step 1 or the provided `5_results_data/run_table.csv`) and run the analysis as above.

---

## About

Replication package for the study on topology and scale effects on performance and energy in μBench microservices (Experiment Runner, muBench, Locust, Prometheus, EnergiBridge).
