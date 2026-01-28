#!/bin/bash

# Start Prometheus port-forward only (for per-experiment setup)
# Gateway port-forward will be started by Experiment Runner after each deployment

set -e

PROMETHEUS_NAMESPACE="${1:-monitoring}"
PROMETHEUS_SVC="${2:-prometheus-nodeport}"
PROMETHEUS_LOCAL_PORT="${3:-30000}"
PROMETHEUS_SVC_PORT="${4:-9090}"

echo "=========================================="
echo "Prometheus Port-Forward Setup (Server-side)"
echo "=========================================="
echo "Prometheus:"
echo "  Namespace: $PROMETHEUS_NAMESPACE"
echo "  Service: $PROMETHEUS_SVC"
echo "  Local Port: $PROMETHEUS_LOCAL_PORT"
echo "  Service Port: $PROMETHEUS_SVC_PORT"
echo "=========================================="
echo ""

# Check if kubectl is available
if ! command -v kubectl >/dev/null 2>&1; then
    echo "Error: kubectl not found"
    exit 1
fi

# Check if service exists
if ! kubectl get svc "$PROMETHEUS_SVC" -n "$PROMETHEUS_NAMESPACE" >/dev/null 2>&1; then
    echo "Error: Prometheus service '$PROMETHEUS_SVC' not found in namespace '$PROMETHEUS_NAMESPACE'"
    echo ""
    echo "Available services in namespace '$PROMETHEUS_NAMESPACE':"
    kubectl get svc -n "$PROMETHEUS_NAMESPACE"
    exit 1
fi

# Check if port-forward already exists
if pgrep -f "kubectl port-forward.*$PROMETHEUS_SVC.*$PROMETHEUS_LOCAL_PORT" > /dev/null; then
    echo "Prometheus port-forward already running"
    echo "PID: $(pgrep -f "kubectl port-forward.*$PROMETHEUS_SVC.*$PROMETHEUS_LOCAL_PORT")"
    exit 0
fi

# Check if port is in use
if command -v lsof >/dev/null 2>&1; then
    if lsof -ti:${PROMETHEUS_LOCAL_PORT} >/dev/null 2>&1; then
        echo "Warning: Port ${PROMETHEUS_LOCAL_PORT} is already in use"
        echo "Killing existing process..."
        lsof -ti:${PROMETHEUS_LOCAL_PORT} | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
fi

# Start Prometheus port-forward
echo "Starting Prometheus port-forward..."
echo "Command: kubectl port-forward svc/$PROMETHEUS_SVC $PROMETHEUS_LOCAL_PORT:$PROMETHEUS_SVC_PORT -n $PROMETHEUS_NAMESPACE"
kubectl port-forward svc/$PROMETHEUS_SVC $PROMETHEUS_LOCAL_PORT:$PROMETHEUS_SVC_PORT -n "$PROMETHEUS_NAMESPACE" &
PROMETHEUS_PF_PID=$!

sleep 3

# Verify port-forward
echo ""
echo "Verifying Prometheus port-forward..."
if command -v curl >/dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$PROMETHEUS_LOCAL_PORT/api/v1/status/config" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" != "000" ] && [ "$HTTP_CODE" != "" ]; then
        echo "✓ Prometheus port-forward is working! (HTTP $HTTP_CODE)"
    else
        echo "⚠ Prometheus connection test failed (HTTP $HTTP_CODE)"
        echo "Port-forward may still be starting..."
    fi
else
    echo "✓ Prometheus port-forward started (cannot verify without curl)"
fi

echo ""
echo "=========================================="
echo "Port-Forward Status"
echo "=========================================="
if ps -p $PROMETHEUS_PF_PID > /dev/null 2>&1; then
    echo "✓ Prometheus port-forward running (PID: $PROMETHEUS_PF_PID)"
    echo ""
    echo "Access Prometheus at: http://localhost:$PROMETHEUS_LOCAL_PORT"
    echo ""
    echo "To stop: kill $PROMETHEUS_PF_PID"
else
    echo "✗ Prometheus port-forward failed to start"
    exit 1
fi

echo ""
echo "=========================================="
echo ""
echo "Note: Gateway port-forward will be started by Experiment Runner"
echo "after each muBench deployment (namespace changes per run)."
echo ""



















