#!/bin/bash

# Prometheus-only installation script
# This installs only Prometheus (no Grafana, Jaeger, Kiali, or Istio)
# Based on: https://github.com/mSvcBench/muBench/blob/main/Docs/Manual.md

set -e

echo "=========================================="
echo "Prometheus-Only Installation"
echo "=========================================="
echo "This will install:"
echo "  - Prometheus Operator (kube-prometheus-stack)"
echo "  - Prometheus PodMonitor for muBench services"
echo "  - Prometheus NodePort service (port 30000)"
echo ""
echo "This will NOT install:"
echo "  - Grafana"
echo "  - Jaeger"
echo "  - Kiali"
echo "  - Istio"
echo "=========================================="
echo ""

# Secure .kube
chmod go-r -R ~/.kube/

# Check if Helm is installed
if ! command -v helm >/dev/null 2>&1; then
    echo "Error: Helm is not installed"
    echo "Install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Create monitoring namespace
echo "Creating monitoring namespace..."
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# Add Prometheus Helm repository
echo "Adding Prometheus Helm repository..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator (kube-prometheus-stack)
# This includes Prometheus but we'll disable Grafana
echo "Installing Prometheus Operator..."
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --set grafana.enabled=false \
  --wait

# Wait for Prometheus to be ready
echo "Waiting for Prometheus to be ready..."
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=prometheus \
  -n monitoring \
  --timeout=300s

# Deploy muBench PodMonitor
echo "Deploying muBench PodMonitor..."
# Get absolute path to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
kubectl apply -f "$SCRIPT_DIR/mub-monitor.yaml"

# Expose Prometheus as NodePort on port 30000
echo "Exposing Prometheus as NodePort service (port 30000)..."
kubectl apply -f "$SCRIPT_DIR/prometheus-nodeport.yaml" -n monitoring

echo ""
echo "=========================================="
echo "Prometheus Installation Complete!"
echo "=========================================="
echo ""
echo "Prometheus is now accessible at:"
echo "  - NodePort: http://<MASTER_IP>:30000"
echo ""
echo "For minikube, get the URL with:"
echo "  minikube service -n monitoring prometheus-nodeport"
echo ""
echo "To access from host machine via SSH tunnel:"
echo "  1. Start port-forward on server:"
echo "     kubectl -n monitoring port-forward svc/prometheus-nodeport 30000:9090"
echo "  2. Create SSH tunnel from host:"
echo "     ssh -N -L 30000:localhost:30000 gl3"
echo "  3. Access Prometheus at: http://localhost:30000"
echo ""
echo "To verify installation:"
echo "  kubectl get pods -n monitoring"
echo "  kubectl get svc -n monitoring prometheus-nodeport"
echo ""

