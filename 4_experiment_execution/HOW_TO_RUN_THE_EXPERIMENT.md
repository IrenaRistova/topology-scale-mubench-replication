# How to Run the Experiment

This document gives the exact commands to set up and run the topology–scale muBench experiment so you can **replicate** it.

**You are here:** `4_experiment_execution/`. This folder contains `experiment-runner/`, `muBench/`, and the experiment definition in `experiment-runner/examples/mubench-benchmarking/`. All paths below are relative to **this folder** (`4_experiment_execution/`) unless otherwise noted. This corresponds to **Section 4** of the paper.

---

## What to install

You need the following **on the host** (where you run the Experiment Runner) and **on the server** (where Kubernetes and the workload run).

### On the host (your machine)

| What | Why | How |
|------|-----|-----|
| **Python 3.8+** | Experiment Runner and scripts | Install Python; use a venv for dependencies. |
| **Experiment Runner dependencies** | To run `RunnerConfig.py` | From `experiment-runner/`: `pip install -r requirements.txt` (pandas, psutil, tabulate, dill, jsonpickle). |
| **Locust** | Load generator; runner calls it during each run | RunnerConfig expects **`muBench/venv/bin/locust`**. Create a venv inside **`4_experiment_execution/muBench/`** and install Locust there: `cd muBench && python3 -m venv venv && source venv/bin/activate && pip install -r Benchmarks/Locust/requirements.txt` (or `pip install 'locust>=2.17.0'`). If you use another path, you must change `LOCUST_EXECUTABLE` in `RunnerConfig.py`. |
| **SSH** to the server | Deployments, EnergiBridge, Prometheus queries | `ssh gl3` (or your server hostname) must work. RunnerConfig uses host **`gl3`**; to use another host, edit `RunnerConfig.py` and replace `'gl3'` in the SSH calls. |

### On the server (e.g. gl3)

| What | Why | How |
|------|-----|-----|
| **Kubernetes** (e.g. Minikube) | Run muBench services | Often set up by `muBench/scripts/setup-infrastructure.sh`. See muBench manual / Docker-README if you install from scratch. |
| **Docker** | Build/run muBench images and optional container | Standard Docker install. |
| **kubectl** | Deploy and manage workloads | Install and point `KUBECONFIG` (or `~/.kube/config`) at your cluster. |
| **Prometheus** | Collect CPU/memory metrics from pods | Deployed in-cluster; `setup-infrastructure.sh` typically deploys it. Port-forward exposes it on localhost:30000. |
| **EnergiBridge** | RAPL-based energy measurement (package + DRAM) | Install from [S2-group/energibridge](https://github.com/S2-group/energibridge). Must be in **PATH** on the server so that `energibridge` runs. Requires Linux and Intel RAPL support. |
| **muBench** (scripts + workmodels) | Deploy topologies and run infra scripts | Copy **`4_experiment_execution/muBench/`** to the server (e.g. `~/muBench`) so the server has the same `scripts/`, `Examples/` workmodels, and (if you run the deployer there) `Deployers/`, `Configs/`, etc. |

**One experiment** = 180 runs (6 topologies × 3 sizes × 10 repetitions). Expect several hours. Plan server setup once; then per experiment you start Prometheus port-forward and tunnels, then run the Experiment Runner.

---

## Order of operations

| Order | Where | What |
|-------|--------|------|
| 0 | Both | Install everything in **§ What to install** (Locust in `muBench/venv`, Experiment Runner deps, EnergiBridge and stack on server, muBench copy on server). |
| 1 | Server | **One-time:** `./scripts/setup-infrastructure.sh` (minikube, Prometheus, etc.). Run from muBench root on the server. |
| 2 | Server | **Per experiment:** `./scripts/start-prometheus-port-forward.sh` (exposes Prometheus on server localhost:30000). |
| 3 | Host | **Per experiment:** From **`4_experiment_execution/muBench/`**, run `./scripts/tunnels-local.sh` (gateway 9090, Prometheus 30000). |
| 4 | Host | **Per experiment:** From **`4_experiment_execution/experiment-runner/`**, with a venv that has `requirements.txt` installed, run `python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py`. |
| 5 | Host → Server | **When done / before a fresh run:** Clean up namespaces and experiment artifacts on the server (see §3). |

---

## 1. On the server

All commands in this section are run **on the server** (or via `ssh <server> "..."`). Use your muBench root on the server (e.g. `~/muBench`). If you copied **`4_experiment_execution/muBench/`** to the server, that copy is your muBench root.

### 1.1 One-time setup (Minikube + Prometheus)

Use **`setup-infrastructure.sh`** only. It starts Minikube, the muBench container (if applicable), and Prometheus. It does **not** deploy a workmodel — the Experiment Runner deploys one per run.

```bash
# On server
cd ~/muBench   # or your muBench root on the server
./scripts/setup-infrastructure.sh
```

**Do not** use `setup.sh` for this workflow; use **`setup-infrastructure.sh`**.

### 1.2 Per-experiment: Prometheus port-forward

Start the Prometheus port-forward **once per experiment**.

```bash
# On server
cd ~/muBench
./scripts/start-prometheus-port-forward.sh
```

This exposes Prometheus on `localhost:30000` on the server. Check with:

```bash
ps aux | grep "kubectl port-forward.*prometheus"
```

### 1.3 Optional: verify deployment

After a run’s namespace exists (e.g. after the Experiment Runner has deployed), you can check pods and connectivity:

```bash
# On server — replace <namespace> with e.g. mubench-sequential-fanout-5-0
cd ~/muBench
./scripts/verify-deployment.sh <namespace> http://localhost:9090
```

### 1.4 Optional: CPU / system idleness (sar)

To inspect load or idleness on the server:

```bash
# On server, from muBench root or scripts/
./scripts/run-sar-on-server.sh 100 1
```

Runs `sar -P ALL 1 100` (100 seconds, 1 s interval). Run on the server host, not inside a container.

---

## 2. On the host

### 2.0 One-time: Python environments

**Experiment Runner** (from `experiment-runner/`):

```bash
cd "4_experiment_execution/experiment-runner"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Locust** — RunnerConfig expects `muBench/venv/bin/locust`. Create that venv:

```bash
cd "4_experiment_execution/muBench"
python3 -m venv venv
source venv/bin/activate
pip install -r Benchmarks/Locust/requirements.txt   # or: pip install 'locust>=2.17.0'
deactivate
```

Use `source venv/bin/activate` only when you need to run Locust manually; the Experiment Runner will call `muBench/venv/bin/locust` directly.

### 2.1 SSH tunnels (gateway + Prometheus)

Start tunnels **once per experiment**. They forward gateway (9090) and Prometheus (30000) from the server to your machine.

From the **replication package**, run:

```bash
cd "4_experiment_execution/muBench"
./scripts/tunnels-local.sh
```

Or from any path where you have this folder:

```bash
cd /path/to/topology-scale-mubench-replication/4_experiment_execution/muBench
./scripts/tunnels-local.sh
```

Verify:

```bash
ps aux | grep "ssh.*9090\|ssh.*30000" | grep -v grep
```

### 2.2 Python and virtualenv

Use a virtualenv with the Experiment Runner dependencies:

```bash
cd "4_experiment_execution/experiment-runner"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
source .venv/bin/activate
```

(or reuse an existing venv that has the same dependencies).

### 2.3 Run the experiment

Run the Experiment Runner with the mubench-benchmarking config. **Do not** use `Benchmarks/Runner/Runner.py` or `RunnerParameters-external.json` for this workflow.

From the **replication package root**:

```bash
cd "4_experiment_execution/experiment-runner"
source .venv/bin/activate
python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py
```

Or with an absolute path to the replication package:

```bash
cd /path/to/topology-scale-mubench-replication/4_experiment_execution/experiment-runner
source .venv/bin/activate
python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py
```

**Short test (e.g. first 250 lines, 5 min cap):**

```bash
cd "4_experiment_execution/experiment-runner"
source .venv/bin/activate
timeout 300 python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py 2>&1 | head -250
```

**Long run (log to file):**

```bash
python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py 2>&1 | tee /tmp/experiment.log
```

**Where results go:**  
The runner writes under  
`experiment-runner/examples/mubench-benchmarking/experiments/mubench_phase3_benchmarking/`  
(run table and per-run directories). In this replication package, the **data from the paper run** is provided at the package root under **`5_results_data/`** (`run_table.csv`, `raw_runs/`). Re-running creates new output in the experiment-runner tree; it does not overwrite **`5_results_data/`** unless you copy it there.

---

## 3. Cleanup (before a fresh run or to free resources)

### 3.1 Server: namespaces and experiment artifacts

This replication package does **not** include `cleanup-experiments.sh`. Use either of the following.

**Option A — Manual cleanup (recommended):**

```bash
# From host, targeting your server (e.g. gl3)
ssh gl3 "rm -rf ~/muBench/experiments/mubench-* ~/muBench/SimulationWorkspace/mubench-* 2>/dev/null; kubectl get namespaces -o name 2>/dev/null | grep '^namespace/mubench-' | xargs -r kubectl delete namespace 2>/dev/null; echo 'Server cleanup done'"
```

**Option B — If your server has a cleanup script:**

```bash
ssh gl3 "cd ~/muBench && ./scripts/cleanup-experiments.sh --all"
# When prompted, type: yes
```

### 3.2 Host: experiment output directory (optional)

To force a fully fresh experiment and let the runner create new output dirs:

```bash
rm -rf "4_experiment_execution/experiment-runner/examples/mubench-benchmarking/experiments/mubench_phase3_benchmarking"
```

Use the path that matches your replication package location.

---

## 4. Quick reference

| Step | Where | Command / script |
|------|--------|--------------------|
| Put muBench on server | Server | Copy **`4_experiment_execution/muBench/`** to e.g. `~/muBench` on the server. |
| One-time setup | Server | `cd ~/muBench && ./scripts/setup-infrastructure.sh` |
| Prometheus port-forward | Server | `cd ~/muBench && ./scripts/start-prometheus-port-forward.sh` |
| Verify pods (optional) | Server | `./scripts/verify-deployment.sh <namespace> http://localhost:9090` |
| SAR (optional) | Server | `./scripts/run-sar-on-server.sh 100 1` |
| SSH tunnels | Host | From **`4_experiment_execution/muBench/`**: `./scripts/tunnels-local.sh` |
| Run experiment | Host | From **`4_experiment_execution/experiment-runner/`** (venv active): `python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py` |
| Cleanup server | Host → Server | See §3.1 (manual or server’s `cleanup-experiments.sh`). |
| Cleanup host output (optional) | Host | `rm -rf .../experiments/mubench_phase3_benchmarking` |

**Not used in this flow:**  
`setup.sh` (use **`setup-infrastructure.sh`**);  
`python3 Benchmarks/Runner/Runner.py -c Configs/RunnerParameters-external.json` (old runner — this experiment uses Experiment Runner + **`RunnerConfig.py`**).

---

## 5. Scripts in this package’s muBench

All under **`4_experiment_execution/muBench/scripts/`**:

| Script | Purpose |
|--------|---------|
| `setup-infrastructure.sh` | One-time: Minikube, Prometheus. |
| `start-prometheus-port-forward.sh` | Per experiment: expose Prometheus on server localhost:30000. |
| `tunnels-local.sh` | Per experiment (on host): SSH tunnels for gateway (9090) and Prometheus (30000). |
| `verify-deployment.sh` | Optional: check pods and gateway for a run’s namespace. |
| `run-sar-on-server.sh` | Optional: run `sar` on the server for CPU/load. |

On the **server**, use your own muBench root (e.g. `~/muBench`). On the **host**, use **`4_experiment_execution/muBench/`** as the muBench root when running these scripts from the replication package.
