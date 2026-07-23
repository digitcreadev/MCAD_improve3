#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_ROOT="reports/article_experiments/foodmart_campaign_a_1000_ckg_first_${STAMP}"
BATCH_ROOT="reports/article_experiments/foodmart_campaign_a_batches"
LIB_DIR="experiments/article/real_execution/foodmart_campaign_a_library_runtime_feasible"
RUNNER="experiments/article/real_execution/run_foodmart_campaign_a_batch.py"
CKG_EVENTS="bi-stack/mcad-api-data/ckg_events.jsonl"

MIN_FREE_GB=6
FREE_KB="$(df -Pk /workspaces | awk 'NR==2 {print $4}')"
FREE_GB="$((FREE_KB / 1024 / 1024))"

echo "[INFO] Free space on /workspaces: ${FREE_GB}G"

if [ "$FREE_GB" -lt "$MIN_FREE_GB" ]; then
  echo "[FAIL] Not enough free space. Need at least ${MIN_FREE_GB}G."
  exit 1
fi

test -f "$RUNNER" || { echo "[FAIL] Missing runner: $RUNNER"; exit 1; }
test -d "$LIB_DIR" || { echo "[FAIL] Missing runtime-feasible library: $LIB_DIR"; exit 1; }

mkdir -p "$EVIDENCE_ROOT/logs"
mkdir -p "$BATCH_ROOT"
mkdir -p "$(dirname "$CKG_EVENTS")"
touch "$CKG_EVENTS"

CKG_BASELINE_LINE_COUNT="$(wc -l < "$CKG_EVENTS" | tr -d ' ')"

cat > "$EVIDENCE_ROOT/run_metadata.env" <<EOF
CAMPAIGN_KIND=foodmart_campaign_a_1000_ckg_first
RUN_STARTED_AT_UTC=$STAMP
EVIDENCE_ROOT=$EVIDENCE_ROOT
BATCH_ROOT=$BATCH_ROOT
LIB_DIR=$LIB_DIR
CKG_EVENTS=$CKG_EVENTS
CKG_BASELINE_LINE_COUNT=$CKG_BASELINE_LINE_COUNT
EXPECTED_OFFSETS=0,100,200,300,400,500,600,700,800,900
RAW_POLICY=none
EOF

git rev-parse HEAD > "$EVIDENCE_ROOT/git_head_before.txt" 2>/dev/null || true
git status --short > "$EVIDENCE_ROOT/git_status_before.txt" 2>/dev/null || true

: > "$EVIDENCE_ROOT/runs_manifest.txt"
: > "$EVIDENCE_ROOT/batch_summaries.jsonl"

echo "[INFO] Evidence root: $EVIDENCE_ROOT"
echo "[INFO] CKG baseline line count: $CKG_BASELINE_LINE_COUNT"
echo

run_one_offset() {
  local OFFSET="$1"
  local LOG="$EVIDENCE_ROOT/logs/batch_offset_${OFFSET}.log"

  echo
  echo "============================================================"
  echo "[START] Campaign A batch offset=$OFFSET limit=100"
  echo "============================================================"

  python -u "$RUNNER" \
    --limit 100 \
    --offset "$OFFSET" \
    --dw-id foodmart \
    --sampling stratified \
    --library-dir "$LIB_DIR" \
    --raw-policy none \
    2>&1 | tee "$LOG"

  local RUN_DIR
  RUN_DIR="$(python - "$OFFSET" "$BATCH_ROOT" <<'PY'
import json
import sys
from pathlib import Path

offset = int(sys.argv[1])
root = Path(sys.argv[2])

candidates = []
for d in root.glob("foodmart_campaign_a_batch_100_*"):
    p = d / "campaign_a_batch_summary.json"
    if not p.exists():
        continue
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue

    if int(s.get("offset", -1)) != offset:
        continue

    candidates.append((p.stat().st_mtime, d, s))

if not candidates:
    raise SystemExit(f"[FAIL] No valid summary found for offset={offset}")

candidates.sort(reverse=True, key=lambda x: x[0])
_, d, s = candidates[0]

checks = {
    "ok": s.get("ok") d, s = candidates[0]

checks = {
    "ok": s.get("ok") is True,
    "mismatch_count": int(s.get("mismatch_count", 0) or 0) == 0,
    "http_error_count": int(s.get("http_error_count", 0) or 0) == 0,
    "canonical_gate_contract_violation_count": int(s.get("canonical_gate_contract_violation_count", 0) or 0) == 0,
    "block_business_physical_execution_count": int(s.get("block_business_physical_execution_count", 0) or 0) == 0,
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"[FAIL] Invalid batch for offset={offset}: {d}; failed={bad}")

print(str(d))
PY
)"

  echo "$RUN_DIR" >> "$EVIDENCE_ROOT/runs_manifest.txt"

  python - "$RUN_DIR" <<'PY' >> "$EVIDENCE_ROOT/batch_summaries.jsonl"
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
s = json.loads((d / "campaign_a_batch_summary.json").read_text(encoding="utf-8"))
print(json.dumps(s, ensure_ascii=False))
PY

  echo "[OK] offset=$OFFSET run_dir=$RUN_DIR"
}

for OFFSET in 0 100 200 300 400 500 600 700 800 900; do
  run_one_offset "$OFFSET"
done

python - "$EVIDENCE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
runs = [Path(x.strip()) for x in (root / "runs_manifest.txt").read_text(encoding="utf-8").splitlines() if x.strip()]

totals = {
    "ok": True,
    "campaign_kind": "foodmart_campaign_a_1000_ckg_first",
    "run_count": len(runs),
    "executed_session_count": 0,
    "executed_query_count": 0,
    "strict_match_count": 0,
    "session_context_match_count": 0,
    "allow_count": 0,
    "block_count": 0,
    "allow_business_physical_execution_count": 0,
    "block_business_physical_execution_count": 0,
    "blocked_before_business_execution_count": 0,
    "canonical_gate_contract_ok_count": 0,
    "canonical_gate_contract_violation_count": 0,
    "http_error_count": 0,
    "mismatch_count": 0,
    "source_runs": [str(r) for r in runs],
}

reason_counts = {}

for r in runs:
    s = json.loads((r / "campaign_a_batch_summary.json").read_text(encoding="utf-8"))

    for k in [
        "executed_session_count",
        "executed_query_count",
        "strict_match_count",
        "session_context_match_count",
        "allow_count",
        "block_count",
        "allow_business_physical_execution_count",
        "block_business_physical_execution_count",
        "blocked_before_business_execution_count",
        "canonical_gate_contract_ok_count",
        "canonical_gate_contract_violation_count",
        "http_error_count",
        "mismatch_count",
    ]:
        totals[k] += int(s.get(k, 0) or 0)

    for reason, count in (s.get("decision_reason_counts") or {}).items():
        reason_counts[reason] = reason_counts.get(reason, 0) + int(count)

q = totals["executed_query_count"] or 1
totals["strict_match_rate"] = totals["strict_match_count"] / q
totals["session_context_match_rate"] = totals["session_context_match_count"] / q
totals["decision_reason_counts"] = reason_counts

if totals["run_count"] != 10:
    totals["ok"] = False
if totals["executed_session_count"] != 1000:
    totals["ok"] = False
if totals["mismatch_count"] != 0:
    totals["ok"] = False
if totals["http_error_count"] != 0:
    totals["ok"] = False
if totals["canonical_gate_contract_violation_count"] != 0:
    totals["ok"] = False
if totals["block_business_physical_execution_count"] != 0:
    totals["ok"] = False

(root / "campaign_a_1000_preliminary_summary.json").write_text(
    json.dumps(totals, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(json.dumps(totals, indent=2, ensure_ascii=False))
PY

CKG_FINAL_LINE_COUNT="$(wc -l < "$CKG_EVENTS" | tr -d ' ')"
echo "CKG_FINAL_LINE_COUNT=$CKG_FINAL_LINE_COUNT" >> "$EVIDENCE_ROOT/run_metadata.env"

echo
echo "[DONE] Campaign A 1000 CKG-first execution completed."
echo "[DONE] Evidence root: $EVIDENCE_ROOT"
echo "[DONE] Preliminary summary:"
cat "$EVIDENCE_ROOT/campaign_a_1000_preliminary_summary.json"
