"""
Experiment Runner configuration for muBench Phase 3 benchmarking.

Orchestrates:
1. muBench deployments (via K8sDeployer)
2. Locust workload execution (headless mode)
3. Prometheus metric collection
4. EnergiBridge energy measurement
5. Experiment workflow for 18 system configurations (6 topologies × 3 sizes) × 10 replicates

Folder Structure:
- Experiment Runner: ~/Documents/Research Project/experiment-runner/
- muBench: ~/Documents/Research Project/muBench/
- Sibling directories with relative paths
"""

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure as output

from typing import Dict, List, Any, Optional
from pathlib import Path
from os.path import dirname, realpath
import subprocess
import time
import json
import csv
import shlex
import re
import signal


class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    
    # Path to muBench (sibling directory)
    MUBENCH_DIR = ROOT_DIR.parent.parent.parent / 'muBench'
    
    # ================================ USER SPECIFIC CONFIG ================================
    """The name of the experiment."""
    name: str = "mubench_phase3_benchmarking"
    
    """The path in which Experiment Runner will create a folder with the name `self.name`, 
    in order to store the results from this experiment."""
    results_output_path: Path = ROOT_DIR / 'experiments'
    
    """Experiment operation type. Use AUTO for automated execution."""
    operation_type: OperationType = OperationType.AUTO
    
    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    # FULL EXPERIMENT settings
    time_between_runs_in_ms: int = 60000  # 1 minute cooldown between runs
    
    # muBench configuration paths
    LOCUST_FILE = MUBENCH_DIR / 'Benchmarks' / 'Locust' / 'locustfile.py'
    LOCUST_EXECUTABLE = MUBENCH_DIR / 'venv' / 'bin' / 'locust'  # Full path to Locust executable
    K8S_DEPLOYER = MUBENCH_DIR / 'Deployers' / 'K8sDeployer' / 'RunK8sDeployer.py'
    SSH_TUNNEL_SCRIPT = MUBENCH_DIR / 'scripts' / 'tunnels-local.sh'
    K8S_PARAMS_TEMPLATE = MUBENCH_DIR / 'Configs' / 'K8sParameters.json'
    
    # Gateway configuration
    GATEWAY_URL = "http://localhost:9090"
    GATEWAY_TEST_ENDPOINT = "/s0"
    
    # Prometheus configuration
    PROMETHEUS_URL = "http://localhost:30000"  # Via SSH tunnel
    
    # Locust configuration - HIGH LOAD settings
    LOCUST_USERS = 100  # Number of concurrent users
    LOCUST_SPAWN_RATE = 50  # Users spawned per second
    # FULL EXPERIMENT settings
    LOCUST_DURATION = "10m"  # 10 minutes per run
    
    # SSH tunnel process
    ssh_tunnel_process = None
    
    # EnergiBridge on server (stored per run)
    energibridge_pid = None
    energibridge_server_dir = None
    
    def __init__(self):
        """Executes immediately after program start, on config load"""
        
        # Verify muBench directory exists
        if not self.MUBENCH_DIR.exists():
            raise FileNotFoundError(f"muBench directory not found at {self.MUBENCH_DIR}")
        
        # Verify key files exist
        if not self.LOCUST_FILE.exists():
            raise FileNotFoundError(f"Locust file not found at {self.LOCUST_FILE}")
        if not self.K8S_DEPLOYER.exists():
            output.console_log(f"Warning: K8sDeployer not found at {self.K8S_DEPLOYER} (will skip deployment)")
        
        # Check EnergiBridge on server
        try:
            result = subprocess.run(
                ['ssh', 'gl3', 'which energibridge'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                output.console_log(f"EnergiBridge found on server at: {result.stdout.strip()}")
            else:
                output.console_log("Warning: EnergiBridge not found on server")
        except Exception as e:
            output.console_log(f"Warning: Could not check EnergiBridge on server: {e}")
        
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN, self.before_run),
            (RunnerEvents.START_RUN, self.start_run),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT, self.interact),
            (RunnerEvents.STOP_MEASUREMENT, self.stop_measurement),
            (RunnerEvents.STOP_RUN, self.stop_run),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT, self.after_experiment)
        ])
        self.run_table_model = None  # Initialized later
        
        output.console_log("muBench benchmarking config loaded")
        output.console_log(f"muBench directory: {self.MUBENCH_DIR}")
        output.console_log(f"Locust file: {self.LOCUST_FILE}")
        output.console_log(f"Configuration: {self.LOCUST_USERS} users, {self.LOCUST_SPAWN_RATE} spawn rate, {self.LOCUST_DURATION} duration")
        output.console_log(f"Cooldown between runs: {self.time_between_runs_in_ms}ms")
    
    def get_workmodel_path(self, topology: str, size: int) -> Path:
        """Map topology and size to workmodel file path."""
        mapping = {
            "sequential_fanout": {
                5: "workmodel-serial-5services.json",
                10: "workmodel-serial-10services.json",
                20: "workmodel-serial-20services.json"
            },
            "parallel_fanout": {
                5: "workmodel-parallel-5services.json",
                10: "workmodel-parallel-10services.json",
                20: "workmodel-parallel-20services.json"
            },
            "chain_with_branching": {
                5: "workmodelA-5services.json",
                10: "workmodelA-10services.json",
                20: "workmodelA.json"
            },
            "hierarchical_tree": {
                5: "workmodelC-5services.json",
                10: "workmodelC-10services.json",
                20: "workmodelC.json"
            },
            "probabilistic_tree": {
                5: "workmodelC-multi-5services.json",
                10: "workmodelC-multi-10services.json",
                20: "workmodelC-multi.json"
            },
            "complex_mesh": {
                5: "workmodelD-5services.json",
                10: "workmodelD-10services.json",
                20: "workmodelD.json"
            }
        }
        
        if topology not in mapping:
            raise ValueError(f"Unknown topology: {topology}")
        if size not in mapping[topology]:
            raise ValueError(f"Unknown size for {topology}: {size}")
        
        workmodel_file = mapping[topology][size]
        workmodel_path = self.MUBENCH_DIR / 'Examples' / workmodel_file
        
        if not workmodel_path.exists():
            raise FileNotFoundError(f"Workmodel file not found: {workmodel_path}")
        
        return workmodel_path
    
    def create_namespace(self, namespace: str) -> bool:
        """Create Kubernetes namespace if it doesn't exist."""
        try:
            result = subprocess.run(
                ['ssh', 'gl3', f'kubectl get namespace {namespace}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output.console_log(f"  Namespace '{namespace}' already exists")
                return True
            
            output.console_log(f"  Creating namespace '{namespace}'...")
            result = subprocess.run(
                ['ssh', 'gl3', f'kubectl create namespace {namespace}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output.console_log(f"  ✓ Namespace '{namespace}' created")
                return True
            else:
                output.console_log(f"  ✗ Failed to create namespace: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            output.console_log(f"  ✗ Timeout creating namespace '{namespace}'")
            return False
        except Exception as e:
            output.console_log(f"  ✗ Error creating namespace: {e}")
            return False
    
    def delete_namespace(self, namespace: str) -> bool:
        """Delete Kubernetes namespace."""
        try:
            output.console_log(f"  Deleting namespace '{namespace}'...")
            result = subprocess.run(
                ['ssh', 'gl3', f'kubectl delete namespace {namespace}'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                output.console_log(f"  ✓ Namespace '{namespace}' deleted")
                return True
            else:
                output.console_log(f"  ✗ Failed to delete namespace: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            output.console_log(f"  ✗ Timeout deleting namespace '{namespace}'")
            return False
        except Exception as e:
            output.console_log(f"  ✗ Error deleting namespace: {e}")
            return False
    
    def query_prometheus(self, query: str, timeout: int = 30) -> Optional[Dict]:
        """Query Prometheus API."""
        try:
            import requests
            
            url = f"{self.PROMETHEUS_URL}/api/v1/query"
            params = {'query': query}
            
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] == 'success':
                return data['data']
            else:
                output.console_log(f"  ⚠ Prometheus query failed: {data.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            output.console_log(f"  ⚠ Prometheus query error: {e}")
            return None
    
    def get_cpu_usage(self, namespace: str) -> Optional[float]:
        """Get average CPU usage for all pods in namespace."""
        query = f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])'
        
        data = self.query_prometheus(query)
        if not data or 'result' not in data:
            return None
        
        values = []
        for result in data['result']:
            if 'value' in result and len(result['value']) > 1:
                try:
                    values.append(float(result['value'][1]))
                except (ValueError, IndexError):
                    continue
        
        if not values:
            return None
        
        return sum(values) / len(values)
    
    def get_memory_usage(self, namespace: str) -> Optional[float]:
        """Get average memory usage for all pods in namespace (in bytes)."""
        query = f'container_memory_working_set_bytes{{namespace="{namespace}"}}'
        
        data = self.query_prometheus(query)
        if not data or 'result' not in data:
            return None
        
        values = []
        for result in data['result']:
            if 'value' in result and len(result['value']) > 1:
                try:
                    values.append(float(result['value'][1]))
                except (ValueError, IndexError):
                    continue
        
        if not values:
            return None
        
        return sum(values) / len(values)
    
    def check_ssh_tunnels(self) -> bool:
        """Check if SSH tunnels for gateway (9090) and Prometheus (30000) are running."""
        try:
            result = subprocess.run(
                ['pgrep', '-fa', r'ssh.*-L.*(9090|30000)'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            tunnels_output = result.stdout.strip()
            has_gateway = '9090' in tunnels_output
            has_prometheus = '30000' in tunnels_output
            
            return has_gateway and has_prometheus
        except Exception as e:
            output.console_log(f"  ⚠ Error checking SSH tunnels: {e}")
            return False
    
    def start_ssh_tunnels(self) -> bool:
        """Start SSH tunnels using the tunnels-local.sh script."""
        try:
            tunnel_script = self.MUBENCH_DIR / 'scripts' / 'tunnels-local.sh'
            if not tunnel_script.exists():
                output.console_log(f"  ⚠ Tunnel script not found: {tunnel_script}")
                return False
            
            output.console_log(f"  Starting SSH tunnels via {tunnel_script}...")
            result = subprocess.run(
                ['bash', str(tunnel_script)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            time.sleep(3)
            
            if self.check_ssh_tunnels():
                output.console_log("  ✓ SSH tunnels started successfully")
                return True
            else:
                output.console_log("  ⚠ SSH tunnels may not have started correctly")
                return False
                
        except Exception as e:
            output.console_log(f"  ⚠ Error starting SSH tunnels: {e}")
            return False
    
    def create_run_table_model(self) -> RunTableModel:
        """Create and return the run_table model.
        
        Factors:
        - Topology: 6 levels
        - System Size: 3 levels (5, 10, 20 services)
        
        Repetitions: 10 per configuration
        Total runs: 6 × 3 × 10 = 180 runs
        """
        
        topology_factor = FactorModel(
            "topology",
            [
                "sequential_fanout",
                "parallel_fanout",
                "chain_with_branching",
                "hierarchical_tree",
                "probabilistic_tree",
                "complex_mesh"
            ]
        )
        
        size_factor = FactorModel(
            "system_size",
            [5, 10, 20]
        )
        
        self.run_table_model = RunTableModel(
            factors=[topology_factor, size_factor],
            exclude_combinations=[],
            # FULL EXPERIMENT settings
            repetitions=10,  # 10 repetitions per configuration = 180 total runs
            shuffle=True,
            data_columns=[
                # Locust metrics
                "throughput_rps",
                "avg_latency_ms",
                "p95_latency_ms",
                "failure_rate",
                "request_count",
                # Prometheus metrics
                "cpu_usage_avg",
                "memory_usage_avg",
                # EnergiBridge metrics
                "energy",
                "dram_energy",
                "cpu_usage_eb_avg",
                "cpu_freq_avg",
                "memory_used_avg",
                "memory_total",
            ]
        )
        return self.run_table_model
    
    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here."""
        
        output.console_log("Setting up experiment environment...")
        
        output.console_log(f"Verifying muBench components...")
        output.console_log(f"  Locust file: {'✓' if self.LOCUST_FILE.exists() else '✗'}")
        output.console_log(f"  K8sDeployer: {'✓' if self.K8S_DEPLOYER.exists() else '✗'}")
        
        # Check and start SSH tunnels if needed
        output.console_log("Checking SSH tunnels...")
        if self.check_ssh_tunnels():
            output.console_log("  ✓ SSH tunnels already running")
        else:
            output.console_log("  SSH tunnels not running, attempting to start...")
            self.start_ssh_tunnels()
        
        # Verify Prometheus connectivity
        output.console_log("Verifying Prometheus connectivity...")
        try:
            import requests
            response = requests.get(f"{self.PROMETHEUS_URL}/-/healthy", timeout=5)
            if response.status_code == 200:
                output.console_log("  ✓ Prometheus accessible")
            else:
                output.console_log(f"  ⚠ Prometheus returned status {response.status_code}")
        except Exception as e:
            output.console_log(f"  ⚠ Could not verify Prometheus: {e}")
        
        output.console_log("Experiment setup complete. Gateway will be verified per run after deployment.")
    
    def before_run(self) -> None:
        """Perform any activity required before starting a run."""
        pass
    
    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here."""
        
        topology = context.execute_run['topology']
        size = context.execute_run['system_size']
        replicate = context.run_nr
        
        output.console_log(f"Starting run: topology={topology}, size={size}, replicate={replicate}")
        
        # Determine wait times based on system size
        if size == 20:
            pod_wait_timeout = 600
            post_ready_wait = 10
        elif size == 10:
            pod_wait_timeout = 400
            post_ready_wait = 5
        else:
            pod_wait_timeout = 300
            post_ready_wait = 3
        
        # 1. Map topology+size to workmodel file
        try:
            workmodel_path = self.get_workmodel_path(topology, size)
            output.console_log(f"  Workmodel: {workmodel_path.name}")
        except Exception as e:
            output.console_log(f"  ✗ Failed to get workmodel path: {e}")
            raise
        
        # 2. Clean up any existing deployment for this topology+size
        topology_clean = topology.replace('_', '-')
        cleanup_pattern = f"mubench-{topology_clean}-{size}-"
        try:
            list_cmd = ['ssh', 'gl3', 'kubectl get namespaces -o name']
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if cleanup_pattern in line and f"-{replicate}" not in line:
                        existing_ns = line.replace('namespace/', '')
                        output.console_log(f"  Deleting existing namespace: {existing_ns}")
                        self.delete_namespace(existing_ns)
        except Exception as e:
            output.console_log(f"  ⚠ Error during cleanup: {e}")
        
        # 3. Delete and recreate namespace
        namespace = f"mubench-{topology_clean}-{size}-{replicate}"
        
        try:
            check_cmd = ['ssh', 'gl3', f'kubectl get namespace {namespace}']
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output.console_log(f"  Deleting existing namespace '{namespace}' for fresh deployment...")
                self.delete_namespace(namespace)
                time.sleep(5)
        except Exception as e:
            output.console_log(f"  ⚠ Error checking/deleting namespace: {e}")
        
        if not self.create_namespace(namespace):
            raise RuntimeError(f"Failed to create namespace: {namespace}")
        
        # 4. Generate K8sParameters.json on server
        try:
            with open(self.K8S_PARAMS_TEMPLATE, 'r') as f:
                config = json.load(f)
            
            config['K8sParameters']['namespace'] = namespace
            
            if workmodel_path.is_absolute():
                try:
                    workmodel_path_rel = workmodel_path.relative_to(self.MUBENCH_DIR)
                except ValueError:
                    workmodel_path_rel = workmodel_path
            else:
                workmodel_path_rel = workmodel_path
            config['WorkModelPath'] = str(workmodel_path_rel)
            
            run_output_dir = f"SimulationWorkspace/{namespace}"
            config['OutputPath'] = run_output_dir
            
            mkdir_cmd = f"mkdir -p ~/muBench/experiments/{namespace}"
            subprocess.run(['ssh', 'gl3', mkdir_cmd], capture_output=True, timeout=10)
            
            import base64
            config_json = json.dumps(config, indent=3)
            config_b64 = base64.b64encode(config_json.encode('utf-8')).decode('ascii')
            
            server_config_path = f"~/muBench/experiments/{namespace}/K8sParameters.json"
            write_cmd = f"echo '{config_b64}' | base64 -d > {server_config_path}"
            result = subprocess.run(
                ['ssh', 'gl3', write_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to write config to server: {result.stderr}")
            
            output.console_log(f"  Generated K8sParameters.json on server")
            
        except Exception as e:
            output.console_log(f"  ✗ Failed to generate K8sParameters: {e}")
            raise
        
        # 5. Execute K8sDeployer on server
        output.console_log(f"  Deploying muBench application...")
        try:
            deploy_cmd = f"cd ~/muBench && echo 'y' | python3 Deployers/K8sDeployer/RunK8sDeployer.py -c experiments/{namespace}/K8sParameters.json"
            result = subprocess.run(
                ['ssh', 'gl3', deploy_cmd],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                output.console_log(f"  ✗ K8sDeployer failed: {result.stderr}")
                raise RuntimeError(f"K8sDeployer failed with exit code {result.returncode}")
            
            output.console_log("  ✓ K8sDeployer completed")
            
        except subprocess.TimeoutExpired:
            output.console_log("  ✗ K8sDeployer timed out")
            raise RuntimeError("K8sDeployer timed out")
        except Exception as e:
            output.console_log(f"  ✗ K8sDeployer error: {e}")
            raise
        
        # 6. Wait for pods to be ready
        output.console_log(f"  Waiting for pods to be ready (timeout={pod_wait_timeout}s)...")
        try:
            wait_cmd = f"kubectl wait --for=condition=ready pod --all -n {namespace} --timeout={pod_wait_timeout}s"
            result = subprocess.run(
                ['ssh', 'gl3', wait_cmd],
                capture_output=True,
                text=True,
                timeout=pod_wait_timeout + 20
            )
            
            if result.returncode == 0:
                output.console_log("  ✓ All pods ready")
            else:
                output.console_log(f"  ⚠ Some pods not ready: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            output.console_log("  ⚠ Timeout waiting for pods (continuing anyway)")
        except Exception as e:
            output.console_log(f"  ⚠ Error waiting for pods: {e}")
        
        if post_ready_wait > 0:
            output.console_log(f"  Waiting {post_ready_wait}s for services to stabilize...")
            time.sleep(post_ready_wait)
        
        # 7. Start gateway port-forward
        output.console_log("  Starting gateway port-forward...")
        try:
            check_svc_cmd = f"kubectl get svc gw-nginx -n {namespace}"
            svc_check = subprocess.run(
                ['ssh', 'gl3', check_svc_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if svc_check.returncode != 0:
                time.sleep(5)
                svc_check = subprocess.run(
                    ['ssh', 'gl3', check_svc_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if svc_check.returncode != 0:
                output.console_log(f"  ⚠ Gateway service 'gw-nginx' not found")
            else:
                subprocess.run(
                    ['ssh', 'gl3', 'pkill -f "kubectl port-forward.*gw-nginx"'],
                    capture_output=True,
                    timeout=5
                )
                time.sleep(1)
                
                subprocess.Popen([
                    'ssh', 'gl3',
                    f'kubectl port-forward svc/gw-nginx 9090:80 -n {namespace}'
                ])
                
                time.sleep(5)
                output.console_log("  ✓ Gateway port-forward started")
                
        except Exception as e:
            output.console_log(f"  ⚠ Error starting gateway port-forward: {e}")
        
        # Store namespace for later use
        context.run_dir.mkdir(parents=True, exist_ok=True)
        with open(context.run_dir / "namespace.txt", "w") as f:
            f.write(namespace)
    
    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        
        output.console_log("Starting measurement phase...")
        
        context.run_dir.mkdir(parents=True, exist_ok=True)
        
        with open(context.run_dir / "measurement_start.txt", "w") as f:
            f.write(str(time.time()))
        
        # Start EnergiBridge on SERVER via SSH
        try:
            namespace_file = context.run_dir / "namespace.txt"
            if namespace_file.exists():
                with open(namespace_file, 'r') as f:
                    namespace = f.read().strip()
            else:
                namespace = "unknown"
            
            server_output_dir = f"/tmp/energibridge_{namespace}"
            subprocess.run(
                ['ssh', 'gl3', f'mkdir -p {server_output_dir}'],
                capture_output=True,
                timeout=10
            )
            
            # Start EnergiBridge on server in background
            # Note: --summary writes to {output_file}-summary.txt automatically
            energibridge_cmd = f"nohup energibridge -o {server_output_dir}/energibridge.csv --summary sleep 99999 > /dev/null 2>&1 & echo $!"
            
            output.console_log(f"  Starting EnergiBridge on server...")
            result = subprocess.run(
                ['ssh', 'gl3', energibridge_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                self.energibridge_pid = result.stdout.strip()
                self.energibridge_server_dir = server_output_dir
                output.console_log(f"  ✓ EnergiBridge started on server (PID: {self.energibridge_pid})")
            else:
                output.console_log(f"  ⚠ Failed to start EnergiBridge on server: {result.stderr}")
                self.energibridge_pid = None
                self.energibridge_server_dir = None
                
        except Exception as e:
            output.console_log(f"  ⚠ Failed to start EnergiBridge: {e}")
            self.energibridge_pid = None
            self.energibridge_server_dir = None
    
    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here."""
        
        topology = context.execute_run['topology']
        size = context.execute_run['system_size']
        
        # Enhanced gateway readiness check
        output.console_log(f"  Verifying gateway readiness for {topology} size={size}...")
        
        if size == 20:
            max_retries = 20
            stabilization_wait = 5
        else:
            max_retries = 15
            stabilization_wait = 3
        
        consecutive_successes = 0
        required_successes = 3
        gateway_ready = False
        
        import requests
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.GATEWAY_URL}/s0", timeout=10)
                if response.status_code == 200:
                    consecutive_successes += 1
                    output.console_log(f"    Gateway check {attempt+1}: OK ({consecutive_successes}/{required_successes})")
                    if consecutive_successes >= required_successes:
                        gateway_ready = True
                        break
                else:
                    consecutive_successes = 0
                    output.console_log(f"    Gateway check {attempt+1}: status {response.status_code}")
            except Exception as e:
                consecutive_successes = 0
                output.console_log(f"    Gateway check {attempt+1}: {str(e)[:50]}")
            
            time.sleep(2)
        
        if gateway_ready:
            output.console_log(f"  ✓ Gateway ready! Waiting {stabilization_wait}s for stabilization...")
            time.sleep(stabilization_wait)
        else:
            output.console_log(f"  ⚠ Gateway not fully ready after {max_retries} attempts, proceeding anyway...")
        
        output.console_log(f"Executing Locust workload: {self.LOCUST_USERS} users, {self.LOCUST_SPAWN_RATE} spawn rate, {self.LOCUST_DURATION}")
        
        locust_output_dir = context.run_dir / "locust"
        locust_output_dir.mkdir(parents=True, exist_ok=True)
        
        locust_cmd = [
            str(self.LOCUST_EXECUTABLE),
            '-f', str(self.LOCUST_FILE),
            '--headless',
            '-u', str(self.LOCUST_USERS),
            '-r', str(self.LOCUST_SPAWN_RATE),
            '-t', self.LOCUST_DURATION,
            '--host', self.GATEWAY_URL,
            '--csv', str(locust_output_dir / 'results'),
            '--html', str(locust_output_dir / 'results.html'),
            'StochasticBenchmarkUser'
        ]
        
        output.console_log(f"  Command: {' '.join(locust_cmd)}")
        
        try:
            locust_output_file = locust_output_dir / "locust_output.txt"
            with open(locust_output_file, "w") as f:
                result = subprocess.run(
                    locust_cmd,
                    cwd=str(self.MUBENCH_DIR),
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=900  # 15 minutes timeout
                )
            
            if result.returncode == 0:
                output.console_log("✓ Locust execution completed successfully")
            else:
                output.console_log(f"⚠ Locust exited with code {result.returncode}")
        
        except subprocess.TimeoutExpired:
            output.console_log("⚠ Locust execution timed out")
        except Exception as e:
            output.console_log(f"⚠ Locust execution failed: {e}")
    
    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        
        output.console_log("Stopping measurement phase...")
        
        with open(context.run_dir / "measurement_end.txt", "w") as f:
            f.write(str(time.time()))
        
        # Stop EnergiBridge on server and retrieve results
        if hasattr(self, 'energibridge_pid') and self.energibridge_pid is not None:
            try:
                output.console_log("  Stopping EnergiBridge on server...")
                
                # Send SIGTERM and wait for EnergiBridge to finish gracefully and write summary
                subprocess.run(
                    ['ssh', 'gl3', f'kill -TERM {self.energibridge_pid}'],
                    capture_output=True,
                    timeout=10
                )
                output.console_log("  Waiting for EnergiBridge to write summary...")
                time.sleep(3)  # Give more time to write summary
                
                # Debug: List files in the output directory
                debug_result = subprocess.run(
                    ['ssh', 'gl3', f'ls -la {self.energibridge_server_dir}/'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                output.console_log(f"  [DEBUG] Server files: {debug_result.stdout.strip()}")
                
                if hasattr(self, 'energibridge_server_dir') and self.energibridge_server_dir:
                    output.console_log("  Retrieving EnergiBridge results from server...")
                    server_dir = self.energibridge_server_dir
                    
                    # Use ssh cat to retrieve files (more reliable than scp for this case)
                    try:
                        # Get CSV file
                        csv_cmd = f'cat {server_dir}/energibridge.csv'
                        csv_result = subprocess.run(
                            ['ssh', 'gl3', csv_cmd],
                            capture_output=True,
                            timeout=60
                        )
                        
                        if csv_result.returncode == 0 and csv_result.stdout:
                            with open(context.run_dir / 'energibridge_output.csv', 'wb') as f:
                                f.write(csv_result.stdout)
                            output.console_log(f"  ✓ EnergiBridge CSV retrieved ({len(csv_result.stdout)} bytes)")
                        else:
                            output.console_log(f"  ⚠ Failed to retrieve EnergiBridge CSV: {csv_result.stderr.decode() if csv_result.stderr else 'empty'}")
                    except Exception as e:
                        output.console_log(f"  ⚠ Error retrieving EnergiBridge CSV: {e}")
                    
                    subprocess.run(
                        ['ssh', 'gl3', f'rm -rf {self.energibridge_server_dir}'],
                        capture_output=True,
                        timeout=10
                    )
                
                output.console_log("  ✓ EnergiBridge stopped")
                
            except Exception as e:
                output.console_log(f"  ⚠ Error stopping EnergiBridge: {e}")
            finally:
                self.energibridge_pid = None
                self.energibridge_server_dir = None
        
        # Query Prometheus metrics
        namespace_file = context.run_dir / "namespace.txt"
        if namespace_file.exists():
            with open(namespace_file, 'r') as f:
                namespace = f.read().strip()
            
            output.console_log(f"  Querying Prometheus metrics for namespace '{namespace}'...")
            
            cpu_usage = self.get_cpu_usage(namespace)
            if cpu_usage is not None:
                output.console_log(f"  CPU usage: {cpu_usage:.4f}")
                with open(context.run_dir / "prometheus_cpu.txt", "w") as f:
                    f.write(str(cpu_usage))
            else:
                output.console_log("  ⚠ Could not query CPU usage")
            
            memory_usage = self.get_memory_usage(namespace)
            if memory_usage is not None:
                output.console_log(f"  Memory usage: {memory_usage / (1024**2):.2f} MB")
                with open(context.run_dir / "prometheus_memory.txt", "w") as f:
                    f.write(str(memory_usage))
            else:
                output.console_log("  ⚠ Could not query memory usage")
    
    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run."""
        
        topology = context.execute_run['topology']
        size = context.execute_run['system_size']
        replicate = context.run_nr
        
        output.console_log(f"Stopping run: topology={topology}, size={size}, replicate={replicate}")
        
        namespace_file = context.run_dir / "namespace.txt"
        if namespace_file.exists():
            with open(namespace_file, 'r') as f:
                namespace = f.read().strip()
            output.console_log(f"  Namespace: {namespace}")
            
            # Delete namespace after run completes
            output.console_log(f"  Cleaning up namespace '{namespace}'...")
            self.delete_namespace(namespace)
    
    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, Any]]:
        """Parse and process any measurement data here."""
        
        output.console_log("Parsing measurement data...")
        
        def safe_float(value, default=0.0):
            if value is None or value == '' or value == 'N/A':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if value is None or value == '' or value == 'N/A':
                return default
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return default
        
        locust_output_dir = context.run_dir / "locust"
        results = {}
        
        # Parse Locust CSV results
        locust_stats_file = locust_output_dir / "results_stats.csv"
        if locust_stats_file.exists():
            try:
                with open(locust_stats_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('Name') == 'Aggregated':
                            results['throughput_rps'] = safe_float(row.get('Requests/s'))
                            results['avg_latency_ms'] = safe_float(row.get('Average Response Time'))
                            results['p95_latency_ms'] = safe_float(row.get('95%'))
                            
                            total_requests = safe_int(row.get('Request Count'))
                            failures = safe_int(row.get('Failure Count'))
                            results['request_count'] = total_requests
                            results['failure_rate'] = failures / total_requests if total_requests > 0 else 0.0
                            
                            output.console_log(f"  Locust: {results['throughput_rps']:.2f} RPS, {results['avg_latency_ms']:.2f}ms avg, {total_requests} requests")
                            break
                
                if 'throughput_rps' not in results:
                    output.console_log("  ⚠ No Aggregated row found in Locust CSV")
                    results['throughput_rps'] = 0.0
                    results['avg_latency_ms'] = 0.0
                    results['p95_latency_ms'] = 0.0
                    results['failure_rate'] = 0.0
                    results['request_count'] = 0
                    
            except Exception as e:
                output.console_log(f"  ⚠ Error parsing Locust CSV: {e}")
                results['throughput_rps'] = 0.0
                results['avg_latency_ms'] = 0.0
                results['p95_latency_ms'] = 0.0
                results['failure_rate'] = 0.0
                results['request_count'] = 0
        else:
            output.console_log("  ⚠ Locust stats file not found")
            results['throughput_rps'] = 0.0
            results['avg_latency_ms'] = 0.0
            results['p95_latency_ms'] = 0.0
            results['failure_rate'] = 0.0
            results['request_count'] = 0
        
        # Parse Prometheus metrics
        cpu_file = context.run_dir / "prometheus_cpu.txt"
        memory_file = context.run_dir / "prometheus_memory.txt"
        
        if cpu_file.exists():
            try:
                with open(cpu_file, 'r') as f:
                    results['cpu_usage_avg'] = float(f.read().strip())
            except Exception:
                results['cpu_usage_avg'] = 0.0
        else:
            results['cpu_usage_avg'] = 0.0
        
        if memory_file.exists():
            try:
                with open(memory_file, 'r') as f:
                    results['memory_usage_avg'] = float(f.read().strip())
            except Exception:
                results['memory_usage_avg'] = 0.0
        else:
            results['memory_usage_avg'] = 0.0
        
        # Parse EnergiBridge results (following official example pattern)
        energibridge_csv = context.run_dir / "energibridge_output.csv"
        
        # Initialize EnergiBridge defaults
        results['energy'] = 0.0
        results['dram_energy'] = 0.0
        results['cpu_usage_eb_avg'] = 0.0
        results['cpu_freq_avg'] = 0.0
        results['memory_used_avg'] = 0.0
        results['memory_total'] = 0.0
        
        # Parse EnergiBridge CSV following official example:
        # https://github.com/S2-group/experiment-runner/blob/master/examples/energibridge-profiling/RunnerConfig.py
        if energibridge_csv.exists():
            try:
                import pandas as pd
                df = pd.read_csv(energibridge_csv)
                
                if len(df) > 1:
                    # RAPL counter overflow correction
                    # MaxCount = 262144 J (2^18) - standard Intel RAPL limit
                    RAPL_MAX_ENERGY = 262144.0
                    
                    def correct_overflow(first, last, max_count=RAPL_MAX_ENERGY):
                        """Correct RAPL counter overflow if detected."""
                        if last < first:  # Overflow detected
                            return (max_count - first) + last
                        return last - first
                    
                    # PACKAGE_ENERGY is the main CPU energy metric (cumulative - last minus first)
                    if 'PACKAGE_ENERGY (J)' in df.columns:
                        first_pkg = float(df['PACKAGE_ENERGY (J)'].iloc[0])
                        last_pkg = float(df['PACKAGE_ENERGY (J)'].iloc[-1])
                        results['energy'] = round(correct_overflow(first_pkg, last_pkg), 3)
                        if last_pkg < first_pkg:
                            output.console_log(f"  Package Energy: {results['energy']:.3f} J (overflow corrected)")
                        else:
                            output.console_log(f"  Package Energy: {results['energy']:.3f} J")
                    
                    # DRAM energy (cumulative - last minus first)
                    if 'DRAM_ENERGY (J)' in df.columns:
                        first_dram = float(df['DRAM_ENERGY (J)'].iloc[0])
                        last_dram = float(df['DRAM_ENERGY (J)'].iloc[-1])
                        results['dram_energy'] = round(correct_overflow(first_dram, last_dram), 3)
                        if last_dram < first_dram:
                            output.console_log(f"  DRAM Energy: {results['dram_energy']:.3f} J (overflow corrected)")
                        else:
                            output.console_log(f"  DRAM Energy: {results['dram_energy']:.3f} J")
                    
                    # CPU usage - average of all CPU_USAGE columns (no units in column names)
                    cpu_usage_cols = [c for c in df.columns if c.startswith('CPU_USAGE_')]
                    if cpu_usage_cols:
                        results['cpu_usage_eb_avg'] = round(float(df[cpu_usage_cols].mean().mean()), 2)
                        output.console_log(f"  CPU Usage: {results['cpu_usage_eb_avg']:.1f}% ({len(cpu_usage_cols)} cores)")
                    
                    # CPU frequency - average of all CPU_FREQUENCY columns (no units in column names)
                    cpu_freq_cols = [c for c in df.columns if c.startswith('CPU_FREQUENCY_')]
                    if cpu_freq_cols:
                        results['cpu_freq_avg'] = round(float(df[cpu_freq_cols].mean().mean()), 2)
                        output.console_log(f"  CPU Freq: {results['cpu_freq_avg']:.0f} MHz ({len(cpu_freq_cols)} cores)")
                    
                    # Memory (column names may or may not have units)
                    mem_used_col = 'USED_MEMORY (Bytes)' if 'USED_MEMORY (Bytes)' in df.columns else 'USED_MEMORY'
                    mem_total_col = 'TOTAL_MEMORY (Bytes)' if 'TOTAL_MEMORY (Bytes)' in df.columns else 'TOTAL_MEMORY'
                    
                    if mem_used_col in df.columns:
                        results['memory_used_avg'] = round(float(df[mem_used_col].mean()), 0)
                        output.console_log(f"  Memory Used: {results['memory_used_avg'] / (1024**3):.1f} GB")
                    
                    if mem_total_col in df.columns:
                        results['memory_total'] = round(float(df[mem_total_col].iloc[0]), 0)
                        output.console_log(f"  Memory Total: {results['memory_total'] / (1024**3):.1f} GB")
                
            except ImportError:
                # Fallback without pandas
                output.console_log("  ⚠ pandas not available, using basic CSV parsing")
                try:
                    with open(energibridge_csv, 'r') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        
                        if rows and len(rows) > 1:
                            # RAPL counter overflow correction
                            RAPL_MAX_ENERGY = 262144.0
                            
                            def correct_overflow_fallback(first, last, max_count=RAPL_MAX_ENERGY):
                                if last < first:  # Overflow detected
                                    return (max_count - first) + last
                                return last - first
                            
                            # PACKAGE_ENERGY is the main energy metric (last - first)
                            if 'PACKAGE_ENERGY (J)' in rows[0]:
                                first_pkg = safe_float(rows[0].get('PACKAGE_ENERGY (J)'))
                                last_pkg = safe_float(rows[-1].get('PACKAGE_ENERGY (J)'))
                                results['energy'] = round(correct_overflow_fallback(first_pkg, last_pkg), 3)
                            
                            # DRAM energy (last - first)
                            if 'DRAM_ENERGY (J)' in rows[0]:
                                first_dram = safe_float(rows[0].get('DRAM_ENERGY (J)'))
                                last_dram = safe_float(rows[-1].get('DRAM_ENERGY (J)'))
                                results['dram_energy'] = round(correct_overflow_fallback(first_dram, last_dram), 3)
                            
                            # Memory total (from first row) - handle both column name formats
                            if 'TOTAL_MEMORY' in rows[0]:
                                results['memory_total'] = safe_float(rows[0].get('TOTAL_MEMORY'))
                            elif 'TOTAL_MEMORY (Bytes)' in rows[0]:
                                results['memory_total'] = safe_float(rows[0].get('TOTAL_MEMORY (Bytes)'))
                            
                            # Averages
                            cpu_usage_sum = 0
                            cpu_usage_count = 0
                            cpu_freq_sum = 0
                            cpu_freq_count = 0
                            memory_sum = 0
                            memory_count = 0
                            
                            for row in rows:
                                for key, val in row.items():
                                    if key.startswith('CPU_USAGE_'):
                                        v = safe_float(val)
                                        if v > 0:
                                            cpu_usage_sum += v
                                            cpu_usage_count += 1
                                    elif key.startswith('CPU_FREQUENCY_'):
                                        v = safe_float(val)
                                        if v > 0:
                                            cpu_freq_sum += v
                                            cpu_freq_count += 1
                                    elif key in ('USED_MEMORY', 'USED_MEMORY (Bytes)'):
                                        v = safe_float(val)
                                        if v > 0:
                                            memory_sum += v
                                            memory_count += 1
                            
                            if cpu_usage_count > 0:
                                results['cpu_usage_eb_avg'] = round(cpu_usage_sum / cpu_usage_count, 2)
                            if cpu_freq_count > 0:
                                results['cpu_freq_avg'] = round(cpu_freq_sum / cpu_freq_count, 2)
                            if memory_count > 0:
                                results['memory_used_avg'] = round(memory_sum / memory_count, 0)
                                
                except Exception as e2:
                    output.console_log(f"  ⚠ Error with fallback CSV parsing: {e2}")
                    
            except Exception as e:
                output.console_log(f"  ⚠ Error parsing EnergiBridge CSV: {e}")
        else:
            output.console_log("  ⚠ EnergiBridge CSV file not found - energy metrics will be 0")
        
        return results
    
    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here."""
        
        output.console_log("Cleaning up experiment environment...")
        
        # Stop EnergiBridge on server if still running
        if hasattr(self, 'energibridge_pid') and self.energibridge_pid is not None:
            try:
                subprocess.run(['ssh', 'gl3', f'kill -9 {self.energibridge_pid}'],
                               capture_output=True, timeout=10)
            except:
                pass
            self.energibridge_pid = None
        
        output.console_log("Experiment complete!")
    
    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path: Path = None
