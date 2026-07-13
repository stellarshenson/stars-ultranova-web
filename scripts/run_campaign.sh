#!/bin/bash
# Final functional test: 5 full games vs AI, 20-50 turns each
cd "$(dirname "$0")/.."
set -o pipefail
PASS=0; FAIL=0
run() {
  local name=$1 seed=$2 size=$3 players=$4 turns=$5
  if .venv/bin/python scripts/autoplay.py --name "$name" --seed "$seed" \
      --size "$size" --players "$players" --turns "$turns" 2>&1 | tee "logs/autoplay-$name.log"; then
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1))
  fi
}
run game1 11 small  2 50
run game2 23 medium 3 40
run game3 37 small  4 30
run game4 58 medium 2 35
run game5 71 tiny   2 20
echo "CAMPAIGN COMPLETE: $PASS pass, $FAIL fail"
