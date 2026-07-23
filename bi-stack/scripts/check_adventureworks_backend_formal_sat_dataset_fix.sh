#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
ok(){ printf '[OK] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
BACKEND="$ROOT/backend/mcad/formal_sat.py"
API="$ROOT/bi-stack/mcad-api/app.py"
APPLY="$ROOT/bi-stack/scripts/apply_adventureworks_backend_formal_sat_dataset_fix.py"
[ -f "$APPLY" ] && ok "V9.5.2d apply script exists" || fail "missing V9.5.2d apply script"
[ -f "$BACKEND" ] && ok "canonical backend formal_sat.py exists" || fail "missing backend/mcad/formal_sat.py"
if [ -f "$BACKEND" ]; then
  grep -q 'def _mcad_known_members_for_features' "$BACKEND" && ok "backend has dataset-aware member selector" || fail "backend missing dataset-aware member selector"
  grep -q 'AdventureWorksDW' "$BACKEND" && grep -q '"Bikes"' "$BACKEND" && grep -q '"Europe"' "$BACKEND" && ok "backend has AdventureWorks member dictionary" || fail "backend missing AdventureWorks dictionary"
  grep -q 'known_members = _mcad_known_members_for_features(features)' "$BACKEND" && ok "slc_ok/nvac use dataset-aware members" || fail "backend SAT does not use dataset-aware known members"
  grep -q '"dw_id": features.get("dw_id")' "$BACKEND" && ok "backend NVAC probe forwards dw_id" || fail "backend NVAC probe does not forward dw_id"
  grep -q 'features\["dw_id"\] = query_spec.get("dw_id")' "$BACKEND" && ok "backend evaluate entry preserves dw_id" || fail "backend evaluate entry does not preserve dw_id"
  python -m py_compile "$BACKEND" && ok "backend formal_sat.py compiles" || fail "backend formal_sat.py does not compile"
fi
if [ -f "$API" ]; then
  grep -q 'query_spec\["dw_id"\] = eval_dw_id' "$API" && ok "mcad-api copies active dw_id into query_spec" || fail "mcad-api does not copy dw_id into query_spec"
  python -m py_compile "$API" && ok "mcad-api app.py compiles" || fail "mcad-api app.py does not compile"
fi
python -m py_compile "$APPLY" && ok "apply script compiles" || fail "apply script does not compile"
printf 'Summary: fails=%s warnings=0\n' "$FAILS"
exit "$FAILS"
