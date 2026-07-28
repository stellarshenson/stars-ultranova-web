#!/usr/bin/env bash
# Detached runner for the doctrine modifier balance sweep.
# Runs validate, then the stance grid, then the posture grid, then reports both.
# Output is teed to logs/balance-sweep.log; per-candidate records checkpoint
# incrementally to results/balance/<axis>.jsonl and an interrupted run resumes.
set -u
cd /home/lab/workspace/private/games/stars-ultranova-web

WORKERS="${WORKERS:-60}"
LOG=logs/balance-sweep.log

{
  echo "=== balance sweep start $(date -Is) workers=${WORKERS} ==="
  echo "--- validate ---"
  python scripts/balance_sweep.py --mode validate
  echo "--- sweep stance ---"
  python scripts/balance_sweep.py --mode sweep --axis stance --workers "${WORKERS}"
  echo "--- sweep posture ---"
  python scripts/balance_sweep.py --mode sweep --axis posture --workers "${WORKERS}"
  echo "--- report stance ---"
  python scripts/balance_sweep.py --mode report --axis stance --top 15
  echo "--- report posture ---"
  python scripts/balance_sweep.py --mode report --axis posture --top 15
  echo "=== balance sweep done $(date -Is) ==="
} 2>&1 | tee "${LOG}"
