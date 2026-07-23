#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
WARNS=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; FAILS=$((FAILS+1)); }
warn(){ echo "[WARN] $1"; WARNS=$((WARNS+1)); }

printf '=== MCAD V9.5.2a AdventureWorks import/schema fix check ===\n'
printf 'repo_root=%s\n' "$ROOT"

OBJ="$ROOT/bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
SC="$ROOT/bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"
IMPORT="$ROOT/bi-stack/scripts/import_adventureworks_objective_scenario.sh"
RUNNER="$ROOT/bi-stack/scripts/run_adventureworks_demo_validation.py"
DOC="$ROOT/bi-stack/docs/V9_5_2A_ADVENTUREWORKS_IMPORT_VALIDATION_FIX.md"

[[ -f "$OBJ" ]] && ok "corrected objective JSON exists" || fail "objective JSON missing"
[[ -f "$SC" ]] && ok "AdventureWorks scenario JSON exists" || fail "AdventureWorks scenario JSON missing"
[[ -f "$IMPORT" ]] && ok "improved import script exists" || fail "import script missing"
[[ -f "$RUNNER" ]] && ok "AdventureWorks evidence runner exists" || fail "runner missing"
[[ -f "$DOC" ]] && ok "V9.5.2a documentation exists" || fail "documentation missing"

python3 - <<'PY' "$OBJ" "$SC" || FAILS=$((FAILS+1))
import json, sys
obj=json.load(open(sys.argv[1], encoding='utf-8'))
sc=json.load(open(sys.argv[2], encoding='utf-8'))
assert obj['id']=='O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN'
assert obj['dw_id']=='adventureworks_sql_direct'
assert obj['dataset']=='AdventureWorksDW'
seen=set()
for i,c in enumerate(obj.get('constraints') or []):
    assert c.get('measure'), f'constraint {i} measure missing'
    assert c.get('grain'), f'constraint {i} grain missing'
    assert isinstance(c.get('slicers'), dict), f'constraint {i} slicers missing'
    vnode=bool(c.get('virtual_node') or c.get('virtual_node_id') or c.get('node_id'))
    vnodes=c.get('virtual_nodes') if isinstance(c.get('virtual_nodes'), list) else []
    assert vnode or vnodes, f'constraint {i} virtual node binding missing'
    if vnode and vnodes:
        top=str(c.get('virtual_node') or c.get('virtual_node_id') or c.get('node_id'))
        ids=[str(v.get('id') or v.get('node_id') or '') if isinstance(v,dict) else str(v) for v in vnodes]
        assert top not in ids, f'constraint {i} duplicates top-level virtual_node inside virtual_nodes: {top}'
    for vid in ([str(c.get('virtual_node') or c.get('virtual_node_id') or c.get('node_id'))] if vnode else []) + [str(v.get('id') or v.get('node_id') or '') for v in vnodes if isinstance(v,dict)]:
        if vid:
            assert vid not in seen, f'duplicate virtual node id across objective: {vid}'
            seen.add(vid)
assert sc['objective_id']==obj['id']
assert sc['dw_id']=='adventureworks_sql_direct'
qs=sc.get('queries') or []
assert qs and all(q.get('expected_decision') in ('ALLOW','BLOCK') for q in qs)
print('[OK] objective has no duplicate virtual_node/virtual_nodes binding and scenario annotations are valid')
PY

if grep -q "objective validation" "$IMPORT" && grep -q "HTTPError" "$IMPORT"; then
  ok "import script validates objective first and prints HTTP error body"
else
  fail "import script does not expose objective validation diagnostics"
fi

python3 -m py_compile "$RUNNER" && ok "AdventureWorks runner compiles" || fail "AdventureWorks runner does not compile"

if [[ "$FAILS" -eq 0 ]]; then
  printf 'Summary: fails=0 warnings=%s\n' "$WARNS"
else
  printf 'Summary: fails=%s warnings=%s\n' "$FAILS" "$WARNS"
  exit 1
fi
