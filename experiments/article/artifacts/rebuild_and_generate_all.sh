#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-.}"
cd "$REPO_ROOT"

RUN_ID="article_abc_$(date -u +%Y%m%dT%H%M%SZ)"
OUT_ROOT="reports/article_experiments"
FIG_DIR="figures"

# Defaults reproduce the current article-scale protocol used by the repo scripts.
A_REPEATS="${MCAD_ARTICLE_A_REPEATS:-75}"
B_REPEATS="${MCAD_ARTICLE_B_REPEATS:-10}"
C_REPEATS="${MCAD_ARTICLE_C_REPEATS:-12}"
BOOTSTRAP="${MCAD_ARTICLE_BOOTSTRAP:-1000}"
SEED="${MCAD_ARTICLE_SEED:-20260625}"

echo "=== MCAD article A-B-C artifact rebuild ==="
echo "run_id=$RUN_ID"
echo "A_REPEATS=$A_REPEATS B_REPEATS=$B_REPEATS C_REPEATS=$C_REPEATS BOOTSTRAP=$BOOTSTRAP SEED=$SEED"

echo
 echo "=== 1/3 Run current article benchmark ==="
python experiments/article/run_article_rebuild.py \
  --out-root "$OUT_ROOT" \
  --run-id "$RUN_ID" \
  --overwrite \
  --seed "$SEED" \
  --bootstrap "$BOOTSTRAP" \
  --a-repeats "$A_REPEATS" \
  --b-repeats "$B_REPEATS" \
  --c-repeats "$C_REPEATS"

RUN_DIR="$OUT_ROOT/$RUN_ID"

echo
 echo "=== 2/3 Generate article figures and LaTeX tables ==="
python experiments/article/artifacts/generate_article_artifacts.py \
  --run-dir "$RUN_DIR" \
  --out-dir "$RUN_DIR/paper_artifacts" \
  --figures-dir "$FIG_DIR"

echo
 echo "=== 3/3 Summary ==="
python experiments/article/artifacts/summarize_artifact_inputs.py \
  --run-dir "$RUN_DIR" \
  --artifact-dir "$RUN_DIR/paper_artifacts"

echo
 echo "[OK] Complete."
echo "RUN_DIR=$RUN_DIR"
echo "FIG_DIR=$FIG_DIR"
echo "TABLE_DIR=$RUN_DIR/paper_artifacts/tables"
echo "MANIFEST=$RUN_DIR/paper_artifacts/artifact_manifest.json"
