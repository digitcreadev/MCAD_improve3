#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
shift || true
BASE_URL="${MCAD_PROXY_BASE_URL:-${MCAD_PROXY_BASE:-http://127.0.0.1:9000}}"
PYTHON_BIN="${PYTHON:-python3}"

echo "=== MCAD V9.5.2 AdventureWorksDW Evidence Validation Pack ==="
echo "repo_root=$ROOT"
echo "base_url=$BASE_URL"
echo "retry_attempts=${MCAD_AW_DEMO_RETRY_ATTEMPTS:-24}"
echo "retry_sleep_s=${MCAD_AW_DEMO_RETRY_SLEEP_S:-1.0}"

"$PYTHON_BIN" "$ROOT/bi-stack/scripts/run_adventureworks_demo_validation.py" "$ROOT" --base-url "$BASE_URL" "$@"

echo
echo "Generated artifacts are written under: bi-stack/demo-evidence/runs/adventureworks_<timestamp>"
echo "latest_adventureworks_path.txt points to the most recent AdventureWorks run."
