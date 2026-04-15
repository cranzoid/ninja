#!/bin/bash
# Morning startup script — run after completing Zerodha login in browser
set -e

cd ~/trading-platform

echo ""
echo "============================="
echo " Trading Platform — Startup"
echo "============================="
echo ""

# Step 1: Stop existing uvicorn if running
echo "[ 1/4 ] Stopping old uvicorn process..."
pkill -f "uvicorn apps.api.src.main:app" 2>/dev/null && echo "       Stopped." || echo "       None running."
sleep 2

# Step 2: Start uvicorn with .env loaded
echo "[ 2/4 ] Starting API server with .env..."
set -a
source .env
set +a
nohup /home/ubuntu/.local/bin/uv run uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000 \
  >> ~/trading-platform/logs/uvicorn.log 2>&1 &
UVICORN_PID=$!
echo "       PID: $UVICORN_PID"

# Step 3: Wait for health
echo "[ 3/4 ] Waiting for server to be ready..."
for i in $(seq 1 15); do
  sleep 1
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "       Ready after ${i}s."
    break
  fi
  if [ $i -eq 15 ]; then
    echo "       ERROR: Server did not start in 15s. Check logs/uvicorn.log"
    exit 1
  fi
done

# Step 4: Compliance check
echo "[ 4/4 ] Running compliance checks..."
echo ""
RESULT=$(curl -s https://truegrowth.ninja/api/compliance/status)
ALL_PASS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['report']['all_blocking_passed'])")

echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['data']['report']['results']:
    icon = '✓' if r['status'] == 'pass' else ('!' if r['status'] == 'warning' else ('~' if r['status'] == 'skipped' else '✗'))
    print(f\"  {icon}  {r['check_name']:<20} {r['status']:<8}  {r['message']}\")
"

echo ""
if [ "$ALL_PASS" = "True" ]; then
  echo "  ALL CHECKS PASSED — Ready for shadow-live."
else
  echo "  BLOCKING CHECKS FAILED — Do NOT trade today until fixed."
fi
echo ""
