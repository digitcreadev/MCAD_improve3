#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="bi-stack/reports/run_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "=== MCAD BI-stack direct reproducibility run ==="
echo "RUN_DIR=$RUN_DIR"

{
  echo "date=$(date -Is)"
  echo "branch=$(git branch --show-current || true)"
  echo "commit=$(git rev-parse HEAD || true)"
  echo "python=$(python --version 2>&1)"
  echo "platform=$(uname -a || true)"
} > "$RUN_DIR/environment.txt"

python bi-stack/scripts/run_q1_q6_direct_check.py \
  > "$RUN_DIR/q1_q6_direct_check.log" 2>&1

cp bi-stack/reports/q1_q6_direct_check.json "$RUN_DIR/" 2>/dev/null || true

find "$RUN_DIR" -type f | sort > "$RUN_DIR/artifact_index.txt"
find "$RUN_DIR" -type f | sort | xargs sha256sum > "$RUN_DIR/checksums.sha256"

grep -RniE "traceback|error|exception|failed|ModuleNotFoundError|unrecognized arguments" "$RUN_DIR" \
  > "$RUN_DIR/error_scan.txt" || true

if [ -s "$RUN_DIR/error_scan.txt" ]; then
  echo "WARNING: possible errors found. See $RUN_DIR/error_scan.txt"
else
  echo "No obvious errors found." > "$RUN_DIR/error_scan.txt"
  echo "No obvious errors found."
fi

cat > "$RUN_DIR/manifest.json" <<JSON
{
  "run_dir": "$RUN_DIR",
  "pipeline": "bi-stack direct Q1-Q6 reproducibility check",
  "scenario": "O_REAL_BEER_WA_MONTH / foodmart / Q1-Q6",
  "created_at": "$(date -Is)",
  "branch": "$(git branch --show-current || true)",
  "commit": "$(git rev-parse HEAD || true)"
}
JSON

echo "DONE: $RUN_DIR"
