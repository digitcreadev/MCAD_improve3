#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
ok(){ printf '[OK] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }

[ -f "$ROOT/bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py" ] && ok "apply patch script exists" || fail "missing apply patch script"
[ -f "$ROOT/bi-stack/mcad-proxy/app.py" ] && ok "proxy app.py exists" || fail "missing proxy app.py"
[ -f "$ROOT/bi-stack/mcad-api/app.py" ] && ok "mcad-api app.py exists" || fail "missing mcad-api app.py"

grep -q "flattening imported virtual_nodes" "$ROOT/bi-stack/mcad-proxy/app.py" && ok "proxy scenario validator flattens imported virtual_nodes" || fail "proxy scenario validator does not flatten virtual_nodes"
grep -q "AdventureWorksDW" "$ROOT/bi-stack/mcad-proxy/app.py" && grep -q "measure = \"SalesAmount\"" "$ROOT/bi-stack/mcad-proxy/app.py" && ok "NVAC probe uses AdventureWorks-safe SalesAmount measure" || fail "NVAC probe still appears FoodMart-only"
grep -q '"dw_id": str(features.get("dw_id") or "")' "$ROOT/bi-stack/mcad-api/app.py" && ok "mcad-api forwards dw_id to NVAC probe" || fail "mcad-api does not forward dw_id to NVAC probe"
grep -q "context: Optional\[Dict\[str, Any\]\] = None" "$ROOT/bi-stack/mcad-api/app.py" && grep -q "context=context" "$ROOT/bi-stack/mcad-api/app.py" && ok "formal SAT receives eval context" || fail "formal SAT does not receive eval context"
python -m py_compile "$ROOT/bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py" && ok "apply script compiles" || fail "apply script does not compile"
python -m py_compile "$ROOT/bi-stack/mcad-proxy/app.py" && ok "proxy app.py compiles" || fail "proxy app.py does not compile"
python -m py_compile "$ROOT/bi-stack/mcad-api/app.py" && ok "mcad-api app.py compiles" || fail "mcad-api app.py does not compile"
printf 'Summary: fails=%s warnings=0\n' "$FAILS"
exit "$FAILS"
