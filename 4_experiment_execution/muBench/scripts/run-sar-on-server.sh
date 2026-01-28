#!/bin/bash

# Run sar on the SERVER (gl3) to monitor CPU while muBench pods are running
# This complements verify-deployment.sh which runs inside the container
# 
# IMPORTANT: Run this on the SERVER (gl3), NOT inside the container
# sar monitors the host system CPU - same metrics whether inside or outside container
# 
# Usage: ./scripts/run-sar-on-server.sh [duration] [interval]

DURATION="${1:-100}"  # Default: 100 seconds
INTERVAL="${2:-1}"    # Default: 1 second intervals

echo "=========================================="
echo "CPU Monitoring (sar) - Server Host System"
echo "=========================================="
echo "Monitoring CPU for ${DURATION} seconds at ${INTERVAL}s intervals"
echo "This shows overall system CPU (includes all Kubernetes pods)"
echo ""
echo "NOTE: Run this on the SERVER (gl3), not inside the container"
echo "      sar shows host system CPU - same whether inside or outside container"
echo ""
echo "Press Ctrl+C to stop early"
echo "=========================================="
echo ""

OUTPUT_DIR="sar-server-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "Running: sar -P ALL $INTERVAL $DURATION"
echo "Output will be saved to: $OUTPUT_DIR/cpu.log"
echo ""

sar -P ALL "$INTERVAL" "$DURATION" | tee "$OUTPUT_DIR/cpu.log"

echo ""
echo "=========================================="
echo "CPU Summary"
echo "=========================================="
if grep -q "Average" "$OUTPUT_DIR/cpu.log"; then
    echo "Average CPU utilization per core:"
    grep "Average" "$OUTPUT_DIR/cpu.log" | tail -1
    echo ""
    echo "Full log saved to: $OUTPUT_DIR/cpu.log"
else
    echo "Could not parse CPU average"
fi

