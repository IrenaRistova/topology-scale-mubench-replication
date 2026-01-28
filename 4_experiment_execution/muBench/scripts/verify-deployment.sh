#!/bin/bash

# Verify muBench deployment - checks pod status, connectivity, and baseline CPU
# Use this to verify your topology is deployed correctly before running workloads
# 
# IMPORTANT: Run this INSIDE the mubench container where kubectl is configured
# Usage: ./scripts/verify-deployment.sh [namespace] [gateway-url]
# 
# From server (outside container):
#   docker exec -it mubench bash -c "cd /root/muBench && ./scripts/verify-deployment.sh [namespace] [gateway-url]"
# 
# From inside container:
#   cd /root/muBench && ./scripts/verify-deployment.sh [namespace] [gateway-url]
# 
# NOTE: For sar CPU monitoring:
#   - sar is NOT installed in the container
#   - Run sar separately on the server (outside container): sar -P ALL 1 100
#   - sar shows host system CPU (same metrics whether inside or outside container)

set -e

# Configuration
NAMESPACE="${1:-default}"
GATEWAY_URL="${2:-http://localhost:9090}"
SAR_DURATION="${SAR_DURATION:-10}"  # Short duration for baseline check (10 seconds)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "muBench Deployment Verification"
echo "=========================================="
echo "Namespace: $NAMESPACE"
echo "Gateway URL: $GATEWAY_URL"
echo "Purpose: Verify topology deployment (no workload running)"
echo "=========================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."
MISSING_DEPS=0

if ! command_exists kubectl; then
    echo -e "${RED}✗ kubectl not found${NC}"
    MISSING_DEPS=1
else
    echo -e "${GREEN}✓ kubectl found${NC}"
fi

if ! command_exists sar; then
    echo -e "${YELLOW}⚠ sar not found${NC}"
    if command_exists apt-get; then
        echo "  Install with: sudo apt-get install sysstat"
    elif command_exists yum; then
        echo "  Install with: sudo yum install sysstat"
    fi
else
    echo -e "${GREEN}✓ sar found${NC}"
fi

if ! command_exists curl; then
    echo -e "${YELLOW}⚠ curl not found (needed for connectivity tests)${NC}"
else
    echo -e "${GREEN}✓ curl found${NC}"
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${RED}Missing required dependencies. Please install them first.${NC}"
    exit 1
fi
echo ""

# Check namespace exists
echo "=========================================="
echo "1. Namespace Check"
echo "=========================================="
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    echo -e "${RED}✗ Namespace '$NAMESPACE' does not exist${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Namespace '$NAMESPACE' exists${NC}"
echo ""

# Check pod status
echo "=========================================="
echo "2. Pod Status Check"
echo "=========================================="
ALL_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null || true)

if [ -z "$ALL_PODS" ]; then
    echo -e "${RED}✗ No pods found in namespace '$NAMESPACE'${NC}"
    exit 1
fi

# Filter out gateway pod for service pods
SERVICE_PODS=$(echo "$ALL_PODS" | grep -E "^s[0-9]" || true)
GATEWAY_POD=$(echo "$ALL_PODS" | grep -E "gw-nginx|nginx" || true)

echo "Service Pods:"
if [ -z "$SERVICE_PODS" ]; then
    echo -e "${RED}✗ No service pods (s0, s1, ...) found${NC}"
else
    echo "$SERVICE_PODS" | while read -r line; do
        POD_NAME=$(echo "$line" | awk '{print $1}')
        POD_STATUS=$(echo "$line" | awk '{print $3}')
        POD_READY=$(echo "$line" | awk '{print $2}')
        RESTARTS=$(echo "$line" | awk '{print $4}')
        
        if [ "$POD_STATUS" = "Running" ] && [[ "$POD_READY" =~ ^[0-9]+/[0-9]+$ ]] && [ "${POD_READY%%/*}" = "${POD_READY##*/}" ]; then
            if [ "$RESTARTS" = "0" ]; then
                echo -e "  ${GREEN}✓${NC} $POD_NAME: $POD_STATUS ($POD_READY ready, $RESTARTS restarts)"
            else
                echo -e "  ${YELLOW}⚠${NC} $POD_NAME: $POD_STATUS ($POD_READY ready, $RESTARTS restarts)"
            fi
        else
            echo -e "  ${RED}✗${NC} $POD_NAME: $POD_STATUS ($POD_READY ready)"
        fi
    done
fi

if [ -n "$GATEWAY_POD" ]; then
    echo ""
    echo "Gateway Pod:"
    echo "$GATEWAY_POD" | while read -r line; do
        POD_NAME=$(echo "$line" | awk '{print $1}')
        POD_STATUS=$(echo "$line" | awk '{print $3}')
        POD_READY=$(echo "$line" | awk '{print $2}')
        if [ "$POD_STATUS" = "Running" ] && [[ "$POD_READY" =~ ^[0-9]+/[0-9]+$ ]]; then
            echo -e "  ${GREEN}✓${NC} $POD_NAME: $POD_STATUS ($POD_READY ready)"
        else
            echo -e "  ${YELLOW}⚠${NC} $POD_NAME: $POD_STATUS ($POD_READY ready)"
        fi
    done
fi

# Count pods
TOTAL_SERVICE_PODS=$(echo "$SERVICE_PODS" | wc -l)
RUNNING_SERVICE_PODS=$(echo "$SERVICE_PODS" | grep -c "Running" || echo "0")
READY_SERVICE_PODS=$(echo "$SERVICE_PODS" | awk '{print $2}' | grep -E '^[0-9]+/[0-9]+$' | awk -F'/' '{if ($1==$2) print}' | wc -l)

echo ""
echo "Summary:"
echo "  Total service pods: $TOTAL_SERVICE_PODS"
echo "  Running: $RUNNING_SERVICE_PODS"
echo "  Ready: $READY_SERVICE_PODS"

if [ "$READY_SERVICE_PODS" -lt "$TOTAL_SERVICE_PODS" ]; then
    echo -e "${YELLOW}⚠ Not all pods are ready${NC}"
    echo "  Run: kubectl get pods -n $NAMESPACE to see details"
fi
echo ""

# Check services
echo "=========================================="
echo "3. Service Endpoints Check"
echo "=========================================="
SERVICES=$(kubectl get svc -n "$NAMESPACE" --no-headers 2>/dev/null | grep -E "^s[0-9]" | awk '{print $1}' || true)

if [ -n "$SERVICES" ]; then
    SVC_COUNT=$(echo "$SERVICES" | wc -l)
    echo -e "${GREEN}✓ Found $SVC_COUNT service endpoints${NC}"
    echo ""
    echo "Service endpoints:"
    echo "$SERVICES" | head -10 | while read -r svc; do
        SVC_TYPE=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.type}' 2>/dev/null || echo "unknown")
        SVC_PORT=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "unknown")
        echo "  - $svc (Type: $SVC_TYPE, Port: $SVC_PORT)"
    done
    if [ "$SVC_COUNT" -gt 10 ]; then
        echo "  ... and $((SVC_COUNT - 10)) more services"
    fi
else
    echo -e "${YELLOW}⚠ No service endpoints found${NC}"
fi

# Check gateway service
GATEWAY_SVC=$(kubectl get svc -n "$NAMESPACE" | grep -E "gw-nginx|nginx" | head -1 | awk '{print $1}' || echo "")
if [ -n "$GATEWAY_SVC" ]; then
    echo ""
    echo -e "${GREEN}✓ Gateway service: $GATEWAY_SVC${NC}"
    kubectl get svc "$GATEWAY_SVC" -n "$NAMESPACE" -o wide
fi
echo ""

# Test gateway connectivity
echo "=========================================="
echo "4. Gateway Connectivity Test"
echo "=========================================="
if command_exists curl; then
    echo "Testing gateway endpoint: $GATEWAY_URL/s0"
    echo ""
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$GATEWAY_URL/s0" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✓ Gateway is accessible (HTTP $HTTP_CODE)${NC}"
        echo "  Testing response..."
        RESPONSE=$(curl -s --max-time 5 "$GATEWAY_URL/s0" 2>/dev/null | head -c 100)
        if [ -n "$RESPONSE" ]; then
            echo -e "${GREEN}✓ Service s0 is responding${NC}"
            echo "  Response preview: ${RESPONSE}..."
        else
            echo -e "${YELLOW}⚠ Service responded but with empty body${NC}"
        fi
    elif [ "$HTTP_CODE" = "000" ]; then
        echo -e "${YELLOW}⚠ Cannot connect to gateway${NC}"
        echo "  This may be normal if:"
        echo "    - Gateway is not exposed (no port-forward or LoadBalancer IP)"
        echo "    - You're running this from a different machine"
        echo "    - SSH tunnel is not set up"
    else
        echo -e "${YELLOW}⚠ Gateway returned HTTP $HTTP_CODE${NC}"
    fi
else
    echo -e "${YELLOW}⚠ curl not available - skipping connectivity test${NC}"
fi
echo ""

# Test a few service endpoints directly (if accessible)
if command_exists curl && [ "$HTTP_CODE" = "200" ]; then
    echo "Testing additional service endpoints..."
    TEST_SERVICES=$(echo "$SERVICES" | head -3)
    for svc in $TEST_SERVICES; do
        if [ "$svc" != "s0" ]; then
            SVC_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$GATEWAY_URL/$svc" 2>/dev/null || echo "000")
            if [ "$SVC_HTTP_CODE" = "200" ]; then
                echo -e "  ${GREEN}✓${NC} $svc: accessible"
            else
                echo -e "  ${YELLOW}⚠${NC} $svc: HTTP $SVC_HTTP_CODE"
            fi
        fi
    done
    echo ""
fi

# Baseline CPU monitoring
echo "=========================================="
echo "5. Baseline CPU Utilization (sar)"
echo "=========================================="
echo "Monitoring CPU for ${SAR_DURATION} seconds to establish baseline..."
echo "Expected: Low CPU usage (pods idle, no workload running)"
echo ""
echo "NOTE: sar monitors the HOST system CPU (same whether run inside or outside container)"
echo "      If sar is not available in container, run it separately on the server:"
echo "      sar -P ALL 1 $SAR_DURATION"
echo ""

OUTPUT_DIR="verification-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

if command_exists sar; then
    echo "Running: sar -P ALL 1 $SAR_DURATION"
    sar -P ALL 1 "$SAR_DURATION" > "$OUTPUT_DIR/baseline-cpu.log" 2>&1
else
    echo -e "${YELLOW}⚠ sar not available in container${NC}"
    echo "  Run sar separately on the server (outside container):"
    echo "  sar -P ALL 1 $SAR_DURATION > baseline-cpu.log"
    echo "  (sar shows host system CPU - same metrics whether inside or outside container)"
    touch "$OUTPUT_DIR/baseline-cpu.log"
    echo "# sar not run - run manually on server host" > "$OUTPUT_DIR/baseline-cpu.log"
fi

echo ""
echo "CPU Baseline Summary:"
if grep -q "Average" "$OUTPUT_DIR/baseline-cpu.log"; then
    AVG_CPU=$(grep "Average" "$OUTPUT_DIR/baseline-cpu.log" | tail -1 | awk '{print $NF}')
    echo "  Average CPU utilization: ${AVG_CPU}%"
    
    # Check if CPU is reasonable for idle state
    AVG_CPU_NUM=$(echo "$AVG_CPU" | sed 's/%//' | awk '{print int($1)}')
    if [ "$AVG_CPU_NUM" -lt 20 ]; then
        echo -e "  ${GREEN}✓ CPU usage is low (expected for idle pods)${NC}"
    elif [ "$AVG_CPU_NUM" -lt 50 ]; then
        echo -e "  ${YELLOW}⚠ CPU usage is moderate (may indicate background activity)${NC}"
    else
        echo -e "  ${RED}✗ CPU usage is high (unexpected for idle state)${NC}"
    fi
else
    echo "  (Could not parse CPU average)"
fi

echo ""
echo "Last 3 CPU readings:"
tail -3 "$OUTPUT_DIR/baseline-cpu.log" | grep -E "^[0-9]" | tail -3 || echo "  (No data available)"

echo ""
echo "Full CPU log saved to: $OUTPUT_DIR/baseline-cpu.log"
echo ""

# Pod resource usage (if metrics-server available)
echo "=========================================="
echo "6. Pod Resource Usage"
echo "=========================================="
if kubectl top pods -n "$NAMESPACE" --containers 2>/dev/null > "$OUTPUT_DIR/pod-resources.log"; then
    echo -e "${GREEN}✓ Resource metrics available${NC}"
    echo ""
    echo "Current resource usage:"
    cat "$OUTPUT_DIR/pod-resources.log" | head -10
    if [ "$(cat "$OUTPUT_DIR/pod-resources.log" | wc -l)" -gt 10 ]; then
        echo "  ... (showing first 10 pods)"
    fi
else
    echo -e "${YELLOW}⚠ Resource metrics not available${NC}"
    echo "  (metrics-server may not be installed)"
    echo "  Install with: kubectl apply -f <metrics-server-manifest>"
fi
echo ""

# Final summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="

ALL_GOOD=true

if [ "$READY_SERVICE_PODS" -eq "$TOTAL_SERVICE_PODS" ] && [ "$RUNNING_SERVICE_PODS" -eq "$TOTAL_SERVICE_PODS" ]; then
    echo -e "${GREEN}✓ All pods are running and ready${NC}"
else
    echo -e "${RED}✗ Some pods are not ready${NC}"
    ALL_GOOD=false
fi

if [ -n "$GATEWAY_SVC" ]; then
    echo -e "${GREEN}✓ Gateway service exists${NC}"
else
    echo -e "${YELLOW}⚠ Gateway service not found${NC}"
fi

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Gateway is accessible and responding${NC}"
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${YELLOW}⚠ Gateway connectivity not verified (may need port-forward or SSH tunnel)${NC}"
else
    echo -e "${YELLOW}⚠ Gateway returned HTTP $HTTP_CODE${NC}"
fi

if [ -n "$SERVICES" ]; then
    echo -e "${GREEN}✓ Service endpoints configured ($SVC_COUNT services)${NC}"
else
    echo -e "${RED}✗ No service endpoints found${NC}"
    ALL_GOOD=false
fi

echo ""
echo "Output files saved to: $OUTPUT_DIR/"
echo "  - baseline-cpu.log: CPU utilization baseline"
echo "  - pod-resources.log: Pod resource usage (if available)"

echo ""
if [ "$ALL_GOOD" = true ]; then
    echo -e "${GREEN}✓ Deployment verification complete - topology appears healthy${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. If gateway is not accessible, set up port-forward or SSH tunnel"
    echo "  2. Run your workload: python3 Benchmarks/Runner/Runner.py -c Configs/RunnerParameters-external.json"
    echo "  3. Monitor during workload: ./scripts/monitor-pods.sh"
    exit 0
else
    echo -e "${YELLOW}⚠ Deployment has some issues - review the checks above${NC}"
    exit 1
fi

