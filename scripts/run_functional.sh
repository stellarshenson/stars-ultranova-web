#!/bin/bash
# Run the functional browser harness (Playwright, headless Chrome).
# Boots its own server on port 9820 with an isolated database.
set -o pipefail

cd "$(dirname "$0")/.."
mkdir -p logs/functional

RUN_FUNCTIONAL=1 uv run pytest tests/functional -q 2>&1 | tee logs/functional/run.log
