#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/workspaces/MCAD_improve3}"
cd "$REPO"
export PYTHONPATH="$REPO:$REPO/backend${PYTHONPATH:+:$PYTHONPATH}"

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
ROOT="reports/article_experiments/phase2_smoke_${RUN_ID}"
mkdir -p "$ROOT"

python -m py_compile \
  backend/harness/run_baselines_and_ablations.py \
  backend/harness/run_robustness_benchmark.py \
  backend/harness/run_scalability_benchmark.py \
  backend/harness/run_statistical_analysis.py

python backend/harness/run_baselines_and_ablations.py \
  --config backend/harness/scenarios.yaml \
  --repeats 2 \
  --seed 20260720 \
  --results-dir "$ROOT/baselines_ablations"

python backend/harness/run_scalability_benchmark.py \
  --results-dir "$ROOT/scalability" \
  --scales 1 2 \
  --steps-per-session 3 \
  --growth-scale 2 \
  --growth-steps 12 \
  --keep-last-n 4

printf '%s\n' "$ROOT" > reports/article_experiments/latest_phase2_smoke_path.txt
find "$ROOT" -maxdepth 3 -type f | sort

echo "[OK] Phase 2 smoke completed: $ROOT"
