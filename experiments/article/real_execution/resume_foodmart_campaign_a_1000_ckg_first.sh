#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

BATCH_ROOT="reports/article_experiments/foodmart_campaign_a_batches"
LIB_DIR="experiments/article/real_execution/foodmart_campaign_a_library_runtime_feasible"
RUNNER="experiments/article/real_execution/run_foodmart_campaign_a_batch.py"
VALIDATOR="experiments/article/real_execution/validate_foodmart_campaign_a_batch_run.py"
SUMMARIZER="experiments/article/real_execution/summarize_foodmart_campaign_a_1000_from_manifest.py"
CKG_EVENTS="bi-stack/mcad-api-data/ckg_events.jsonl"

EVIDENCE_ROOT="${1:-}"

if [ -z "$EVIDENCE_ROOT" ]; then
  EVIDENCE_ROOT="$(ls -td reports/article_experiments/foodmart_campaign_a_1000_ckg_first_* 2>/dev/null | head -1 || true)"
fi

if [ -z "$EVIDENCE_ROOT" ]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  EVIDENCE_ROOT="reports/article_experiments/foodmart_campaign_a_1000_ckg_first_${STAMP}"
fi

mkdir -p "$EVIDENCE_ROOT/logs"
mkdir -p "$BATCH_ROOT"

test -f "$RUNNER" || { echo "[FAIL] Missing runner: $RUNNER"; exit 1; }
test -f "$VALIDATOR" || { echo "[FAIL] Missing validator: $VALIDATOR"; exit 1; }
test -f "$SUMMARIZER" || { echo "[FAIL] Missing summarizer: $SUMMARIZER"; exit 1; }
test -d "$LIB_DIR" || { echo "[FAIL] Missing library: $LIB_DIR"; exit 1; }

echo "[INFO] Evidence root: $EVIDENCE_ROOT"
echo "[INFO] Batch root: $BATCH_ROOT"
echo "[INFO] CKG events current line count: $(wc -l < "$CKG_EVENTS" | tr -d ' ')"
echo

if [ ! -f "$EVIDENCE_ROOT/run_metadata.env" ]; then
  {
    echo "CAMPAIGN_KIND=foodmart_campaign_a_1000_ckg_first"
    echo "RUN_RESUMED_AT_UTC=$(date -u +%Y%m%dT%H%M%SZ)"
    echo "EVIDENCE_ROOT=$EVIDENCE_ROOT"
    echo "BATCH_ROOT=$BATCH_ROOT"
    echo "LIB_DIR=$LIB_DIR"
    echo "CKG_EVENTS=$CKG_EVENTS"
    echo "RAW_POLICY=none"
    echo "EXPECTED_OFFSETS=0,100,200,300,400,500,600,700,800,900"
  } > "$EVIDENCE_ROOT/run_metadata.env"
fi

: > "$EVIDENCE_ROOT/runs_manifest.txt"
: > "$EVIDENCE_ROOT/batch_summaries.jsonl"

run_or_reuse_offset() {
  local OFFSET="$1"
  local LOG="$EVIDENCE_ROOT/logs/batch_offset_${OFFSET}.log"
  local RUN_DIR=""

  if RUN_DIR="$(python "$VALIDATOR" --offset "$OFFSET" --batch-root "$BATCH_ROOT" 2>/dev/null)"; then
    echo "[REUSE] offset=$OFFSET run_dir=$RUN_DIR"
  else
    echo
    echo "============================================================"
    echo "[START] Campaign A batch offset=$OFFSET limit=100"
    echo "============================================================"

    TMP_LOG="/tmp/mcad_batch_offset_${OFFSET}.log"

    set +e
    python -u "$RUNNER" \
      --limit 100 \
      --offset "$OFFSET" \
      --dw-id foodmart \
      --sampling stratified \
      --library-dir "$LIB_DIR" \
      --raw-policy none \
      > "$TMP_LOG" 2>&1
    RC="$?"
    set -e

    tail -200 "$TMP_LOG" > "$LOG" 2>/dev/null || true
    echo
    echo "=== Tail of offset ${OFFSET} log ==="
    tail -80 "$TMP_LOG" 2>/dev/null || true

    if [ "$RC" -ne 0 ]; then
      echo "[FAIL] Batch offset=$OFFSET failed with exit code $RC"
      echo "[INFO] Full temporary log kept at: $TMP_LOG"
      exit "$RC"
    fi

    rm -f "$TMP_LOG"

    RUN_DIR="$(python "$VALIDATOR" --offset "$OFFSET" --batch-root "$BATCH_ROOT")"
    echo "[OK] offset=$OFFSET run_dir=$RUN_DIR"
  fi

  echo "$RUN_DIR" >> "$EVIDENCE_ROOT/runs_manifest.txt"

  python - "$RUN_DIR" <<'PY' >> "$EVIDENCE_ROOT/batch_summaries.jsonl"
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
s = json.loads((d / "campaign_a_batch_summary.json").read_text(encoding="utf-8"))
print(json.dumps(s, ensure_ascii=False))
PY
}

for OFFSET in 0 100 200 300 400 500 600 700 800 900; do
  run_or_reuse_offset "$OFFSET"
done

python "$SUMMARIZER" --evidence-root "$EVIDENCE_ROOT"

sed -i '/^CKG_FINAL_LINE_COUNT=/d' "$EVIDENCE_ROOT/run_metadata.env" 2>/dev/null || true
echo "CKG_FINAL_LINE_COUNT=$(wc -l < "$CKG_EVENTS" | tr -d ' ')" >> "$EVIDENCE_ROOT/run_metadata.env"

echo
echo "[DONE] Campaign A 1000 CKG-first resume completed."
echo "[DONE] Evidence root: $EVIDENCE_ROOT"
echo "[DONE] Summary:"
cat "$EVIDENCE_ROOT/campaign_a_1000_preliminary_summary.json"
