#!/bin/bash

# Infrastructure setup script (minikube + Prometheus, NO workmodel deployment)
# This is the one-time setup that prepares the environment
# Workmodel deployments are handled separately by Experiment Runner

set -e

echo "=========================================="
echo "muBench Infrastructure Setup"
echo "=========================================="
echo "This script sets up:"
echo "  - minikube cluster configuration and startup"
echo "  - mubench Docker container"
echo "  - kubectl config"
echo "  - Prometheus installation (Prometheus-only)"
echo "  - muBench PodMonitor"
echo ""
echo "This script does NOT deploy any workmodels."
echo "Workmodel deployments are handled by Experiment Runner."
echo "=========================================="
echo ""

echo "Setting up minikube configuration..."
minikube config set memory 358400  # 350GB in MB (leaving some RAM for host system)
minikube config set cpus 28        # 28 vCPUs (leaving 4 for host system)
minikube config set disk-size 1024000  # 1TB in MB (we can increase this if needed)

echo "Starting minikube..."
minikube start \
  --cpus=28 \
  --memory=358400 \
  --disk-size=1024000 \
  --extra-config=kubelet.max-pods=1500 \
  --driver=docker \
  --container-runtime=containerd \
  --network-plugin=cni \
  --extra-config=kubelet.reserved-cpus=0,1,2,3 \
  --extra-config=kubelet.reserved-memory=0:memory=4Gi \
  --extra-config=kubelet.cpu-manager-policy=static \
  --extra-config=kubelet.topology-manager-policy=single-numa-node

echo "Starting mubench container..."
# Get the absolute path to muBench root (parent of scripts directory)
MUBENCH_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker run -d --name mubench --network minikube -v "${MUBENCH_ROOT}:/root/muBench" msvcbench/mubench || {
    echo "mubench container already exists, continuing..."
}

echo "Copying kubectl config..."
minikube kubectl -- config view --flatten > config
docker cp config mubench:/root/.kube/config

echo "Installing Prometheus (Prometheus-only, no Grafana/Jaeger/Kiali/Istio)..."
docker exec mubench bash -c "cd /root/muBench/Monitoring/kubernetes-full-monitoring && bash ./prometheus-only-install.sh"

echo ""
echo "=========================================="
echo "Infrastructure Setup Complete!"
echo "=========================================="
echo ""
echo "What's ready:"
echo "  ✓ minikube cluster running"
echo "  ✓ mubench container running"
echo "  ✓ Prometheus installed in 'monitoring' namespace"
echo "  ✓ muBench PodMonitor deployed"
echo ""
echo "Next steps:"
echo ""
echo "1. Start Prometheus port-forward (on server):"
echo "   ./scripts/start-prometheus-port-forward.sh"
echo "   OR manually:"
echo "   kubectl -n monitoring port-forward svc/prometheus-nodeport 30000:9090 &"
echo ""
echo "   Note: Gateway port-forward will be started by Experiment Runner"
echo "   after each deployment (gateway service doesn't exist until then)."
echo ""
echo "2. Start SSH tunnels (on host machine):"
echo "   ./scripts/tunnels-local.sh"
echo ""
echo "3. Run Experiment Runner (on host machine):"
echo "   cd ~/Documents/Research\ Project/experiment-runner"
echo "   python experiment-runner/ examples/mubench-benchmarking/RunnerConfig.py"
echo ""
echo "=========================================="

