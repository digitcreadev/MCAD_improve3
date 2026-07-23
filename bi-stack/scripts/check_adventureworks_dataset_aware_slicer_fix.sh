#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
ok(){ printf '[OK] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
API="$ROOT/bi-stack/mcad-api/app.py"
APPLY="$ROOT/bi-stack/scripts/apply_adventureworks_dataset_aware_slicer_fix.py"
[ -f "$APPLY" ] && ok "V9.5.2c apply script exists" || fail "missing V9.5.2c apply script"
[ -f "$API" ] && ok "mcad-api app.py exists" || fail "missing mcad-api app.py"
if [ -f "$API" ]; then
  grep -q "def _sat_known_members_for_features" "$API" && ok "dataset-aware slicer dictionary selector exists" || fail "missing dataset-aware slicer selector"
  grep -q "AdventureWorksDW" "$API" && grep -q '"Bikes"' "$API" && grep -q '"Europe"' "$API" && ok "AdventureWorks member dictionary is present" || fail "AdventureWorks member dictionary is missing"
  grep -q 'known_members = _sat_known_members_for_features(features)' "$API" && ok "slc_ok uses dataset-aware member dictionary" || fail "slc_ok does not use dataset-aware dictionary"
  grep -q 'query_spec\["dw_id"\] = eval_dw_id' "$API" && ok "eval context dw_id is copied into query_spec" || fail "eval context dw_id is not copied into query_spec"
  grep -q 'context: Optional\[Dict\[str, Any\]\] = None' "$API" && grep -q 'context=context' "$API" && ok "formal SAT receives eval context" || fail "formal SAT does not receive eval context"
  grep -q '"dw_id": str(features.get("dw_id") or "")' "$API" && ok "NVAC probe payload includes dw_id" || fail "NVAC probe payload does not include dw_id"
fi
python -m py_compile "$APPLY" && ok "apply script compiles" || fail "apply script does not compile"
python -m py_compile "$API" && ok "mcad-api app.py compiles" || fail "mcad-api app.py does not compile"
printf 'Summary: fails=%s warnings=0\n' "$FAILS"
exit "$FAILS"
