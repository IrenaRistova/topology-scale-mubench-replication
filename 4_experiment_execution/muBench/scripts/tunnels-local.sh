#!/bin/bash

# Combined script to set up SSH tunnels from host machine to gl3 server
# for accessing both the muBench nginx gateway and Prometheus
# 
# Prerequisites:
# 1. Gateway port-forward must be running on gl3 server:
#    ./scripts/gateway-tunnel.sh OR ./scripts/gateway-tunnel-standalone-python.sh
# 2. Prometheus port-forward must be running on gl3 server:
#    kubectl -n monitoring port-forward svc/prometheus-nodeport 30000:9090
# 3. Ensure you can SSH to gl3 through the jump host

GATEWAY_PORT=9090
PROMETHEUS_PORT=30000

echo "=========================================="
echo "  muBench Combined SSH Tunnels Setup"
echo "=========================================="
echo ""

# Function to cleanup existing tunnels
cleanup_tunnel() {
    local port=$1
    local name=$2
    
    echo "Checking existing $name SSH tunnel (port $port)..."
    ps aux | grep "[s]sh -N -L.*${port}" | grep -v grep
    
    echo -e "\nCleaning up existing $name SSH tunnel..."
    ps aux | grep "[s]sh -N -L.*${port}" | grep -v grep | awk '{print $2}' | xargs -r kill -9
    if [ $? -eq 0 ]; then
        echo "Successfully killed $name SSH tunnel process"
    else
        echo "No $name SSH tunnel process found"
    fi
    
    # Also check for processes using the port directly
    if command -v lsof &> /dev/null; then
        PID=$(lsof -ti:${port} 2>/dev/null || true)
        if [ -n "$PID" ]; then
            echo "Found process using port ${port} (PID: $PID)"
            echo "Killing process $PID..."
            kill -9 "$PID" 2>/dev/null || true
        fi
    elif command -v fuser &> /dev/null; then
        if fuser -n tcp ${port} &>/dev/null; then
            echo "Found process using port ${port}"
            echo "Killing process..."
            fuser -k -n tcp ${port} 2>/dev/null || true
        fi
    fi
}

# Cleanup both tunnels
cleanup_tunnel $GATEWAY_PORT "Gateway"
cleanup_tunnel $PROMETHEUS_PORT "Prometheus"

sleep 2

echo -e "\nVerifying cleanup..."
ps aux | grep "[s]sh -N -L.*\(${GATEWAY_PORT}\|${PROMETHEUS_PORT}\)" | grep -v grep

echo ""
echo "=========================================="
echo "Starting SSH tunnels to gl3..."
echo "=========================================="
echo ""
echo "Prerequisites on gl3 server:"
echo "  1. Gateway: ./scripts/gateway-tunnel.sh OR ./scripts/gateway-tunnel-standalone-python.sh"
echo "  2. Prometheus: kubectl -n monitoring port-forward svc/prometheus-nodeport ${PROMETHEUS_PORT}:9090"
echo ""

# Start Gateway tunnel
echo "Starting Gateway SSH tunnel (port ${GATEWAY_PORT})..."
ssh -N \
    -L ${GATEWAY_PORT}:localhost:${GATEWAY_PORT} \
    gl3 &
GATEWAY_TUNNEL_PID=$!

# Start Prometheus tunnel
echo "Starting Prometheus SSH tunnel (port ${PROMETHEUS_PORT})..."
ssh -N \
    -L ${PROMETHEUS_PORT}:localhost:${PROMETHEUS_PORT} \
    gl3 &
PROMETHEUS_TUNNEL_PID=$!

sleep 2

# Verify tunnels are running
echo ""
echo "=========================================="
echo "Tunnel Status"
echo "=========================================="
if ps -p $GATEWAY_TUNNEL_PID > /dev/null 2>&1; then
    echo "✓ Gateway tunnel running (PID: $GATEWAY_TUNNEL_PID)"
else
    echo "✗ Gateway tunnel failed to start"
fi

if ps -p $PROMETHEUS_TUNNEL_PID > /dev/null 2>&1; then
    echo "✓ Prometheus tunnel running (PID: $PROMETHEUS_TUNNEL_PID)"
else
    echo "✗ Prometheus tunnel failed to start"
fi

echo ""
echo "=========================================="
echo "Access Information"
echo "=========================================="
echo ""
echo "Gateway (muBench application):"
echo "  URL: http://localhost:${GATEWAY_PORT}"
echo "  Test: curl -v http://localhost:${GATEWAY_PORT}/s0"
echo ""
echo "Prometheus:"
echo "  URL: http://localhost:${PROMETHEUS_PORT}"
echo "  Test: curl http://localhost:${PROMETHEUS_PORT}/api/v1/status/config"
echo ""
echo "=========================================="
echo ""
echo "Both tunnels are active. Press Ctrl+C to stop all tunnels."
echo ""
echo "To stop manually:"
echo "  kill $GATEWAY_TUNNEL_PID $PROMETHEUS_TUNNEL_PID"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping tunnels..."
    kill $GATEWAY_TUNNEL_PID $PROMETHEUS_TUNNEL_PID 2>/dev/null || true
    wait $GATEWAY_TUNNEL_PID $PROMETHEUS_TUNNEL_PID 2>/dev/null || true
    echo "Tunnels stopped."
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Wait for both tunnels
wait $GATEWAY_TUNNEL_PID $PROMETHEUS_TUNNEL_PID

