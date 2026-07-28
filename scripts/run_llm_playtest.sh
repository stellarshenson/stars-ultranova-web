#!/bin/bash
# Launch the LLM-vs-LLM playtest detached (survives session death).
# Usage: scripts/run_llm_playtest.sh <name> <seed> <turns> [extra args...]
# Example (the real run):
#   scripts/run_llm_playtest.sh run100 4242 100
# Resume after interruption:
#   scripts/run_llm_playtest.sh run100 4242 100 --resume
set -e

cd "$(dirname "$0")/.."
NAME=${1:?usage: run_llm_playtest.sh <name> <seed> <turns> [extra args]}
SEED=${2:?seed required}
TURNS=${3:?turns required}
shift 3

mkdir -p logs
LOG="logs/llm-playtest-${NAME}.log"

setsid nohup bash -c \
  "uv run python scripts/llm_playtest.py --name '${NAME}' --seed ${SEED} \
   --turns ${TURNS} $* 2>&1 | tee -a '${LOG}'" \
  >/dev/null 2>&1 &

echo "detached playtest '${NAME}' launched; log: ${LOG}"
echo "watch with: tail -f ${LOG}"
