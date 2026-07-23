#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
WARNS=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; FAILS=$((FAILS+1)); }
warn(){ echo "[WARN] $1"; WARNS=$((WARNS+1)); }

printf '=== MCAD V9.5.1 AdventureWorks objective/scenario pack check ===\n'
printf 'repo_root=%s\n' "$ROOT"

OBJ="$ROOT/bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
SC="$ROOT/bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"
ADAPTER="$ROOT/bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py"
DW="$ROOT/bi-stack/mcad-proxy/datawarehouses.yaml"
IMPORT="$ROOT/bi-stack/scripts/import_adventureworks_objective_scenario.sh"
DOC="$ROOT/bi-stack/docs/V9_5_1_ADVENTUREWORKS_OBJECTIVE_SCENARIO_PACK.md"

[[ -f "$OBJ" ]] && ok "objective JSON exists" || fail "objective JSON missing"
[[ -f "$SC" ]] && ok "AdventureWorks scenario JSON exists" || fail "AdventureWorks scenario JSON missing"
[[ -f "$ADAPTER" ]] && ok "AdventureWorks adapter exists" || fail "AdventureWorks adapter missing"
[[ -f "$IMPORT" ]] && ok "import script exists" || fail "import script missing"
[[ -f "$DOC" ]] && ok "documentation exists" || fail "documentation missing"

python3 - <<'PY' "$OBJ" "$SC" || FAILS=$((FAILS+1))
import json, sys
obj=json.load(open(sys.argv[1], encoding='utf-8'))
sc=json.load(open(sys.argv[2], encoding='utf-8'))
assert obj['id']=='O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN'
assert obj['dw_id']=='adventureworks_sql_direct'
assert obj['dataset']=='AdventureWorksDW'
assert len(obj.get('constraints', []))==3
for c in obj['constraints']:
    assert c.get('measure')
    assert c.get('grain')
    assert c.get('slicers')
    assert c.get('virtual_node') or c.get('virtual_nodes')
assert sc['objective_id']==obj['id']
assert sc['dw_id']=='adventureworks_sql_direct'
assert sc['dataset']=='AdventureWorksDW'
qs=sc.get('queries') or []
assert len(qs) >= 5
assert any(q.get('expected_decision')=='ALLOW' for q in qs)
assert any(q.get('expected_decision')=='BLOCK' for q in qs)
assert any('CrossJoin' in (q.get('mdx') or '') for q in qs)
print('[OK] objective/scenario JSON schema is coherent')
PY

if grep -q "id: adventureworks_sql_direct" "$DW" && grep -A25 "id: adventureworks_sql_direct" "$DW" | grep -q "enabled: true"; then
  ok "adventureworks_sql_direct is enabled in datawarehouses.yaml"
else
  fail "adventureworks_sql_direct is not enabled in datawarehouses.yaml"
fi

if grep -q "SalesTerritoryGroup" "$ADAPTER" && grep -q "t.SalesTerritoryGroup = 'Europe'" "$ADAPTER" && ! grep -q "elif \"territory\" in q or \"region\" in q" "$ADAPTER"; then
  ok "adapter supports Month x Territory grouping and Europe filter"
else
  fail "adapter does not include the V9.5.1 Month x Territory mapping"
fi

python3 -m py_compile "$ADAPTER" && ok "AdventureWorks adapter compiles" || fail "AdventureWorks adapter does not compile"

if [[ "$FAILS" -eq 0 ]]; then
  printf 'Summary: fails=0 warnings=%s\n' "$WARNS"
else
  printf 'Summary: fails=%s warnings=%s\n' "$FAILS" "$WARNS"
  exit 1
fi
