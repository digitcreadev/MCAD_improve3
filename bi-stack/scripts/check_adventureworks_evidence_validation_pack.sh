#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
MODE="${2:-static}"
FAILS=0
WARNINGS=0

ok(){ echo "[OK] $*"; }
warn(){ echo "[WARN] $*"; WARNINGS=$((WARNINGS+1)); }
fail(){ echo "[FAIL] $*"; FAILS=$((FAILS+1)); }
need_file(){ [[ -f "$ROOT/$1" ]] && ok "$1 exists" || fail "$1 missing"; }
need_grep(){ local pattern="$1" file="$2" label="$3"; grep -qE "$pattern" "$ROOT/$file" && ok "$label" || fail "$label"; }

need_file "bi-stack/scripts/run_adventureworks_demo_validation.py"
need_file "bi-stack/scripts/run_adventureworks_demo_validation.sh"
need_file "bi-stack/scripts/check_adventureworks_evidence_validation_pack.sh"
need_file "bi-stack/docs/V9_5_2_ADVENTUREWORKS_EVIDENCE_VALIDATION_PACK.md"
need_file "bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
need_file "bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"

if [[ -f "$ROOT/bi-stack/scripts/run_adventureworks_demo_validation.py" ]]; then
  python3 -m py_compile "$ROOT/bi-stack/scripts/run_adventureworks_demo_validation.py" && ok "Python runner compiles" || fail "Python runner compilation failed"
  need_grep "latest_adventureworks_path\.txt" "bi-stack/scripts/run_adventureworks_demo_validation.py" "AdventureWorks latest pointer is separate from FoodMart dual-path pointer"
  need_grep "for idx, query in enumerate\(queries" "bi-stack/scripts/run_adventureworks_demo_validation.py" "Runner supports dynamic scenario length"
  need_grep "expected_decision" "bi-stack/scripts/run_adventureworks_demo_validation.py" "Runner checks per-query expected decisions"
  need_grep "physical_execution" "bi-stack/scripts/run_adventureworks_demo_validation.py" "Runner checks physical execution evidence"
fi

if [[ -f "$ROOT/bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json" ]]; then
  python3 - <<'PY' "$ROOT/bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json" && ok "Scenario JSON is valid and has expected decision annotations" || fail "Scenario JSON validation failed"
import json, sys
p = sys.argv[1]
s = json.load(open(p, encoding='utf-8'))
assert s.get('objective_id') == 'O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN'
assert s.get('dw_id') == 'adventureworks_sql_direct'
qs = s.get('queries') or []
assert len(qs) >= 3
assert all(q.get('expected_decision') in {'ALLOW','BLOCK'} for q in qs)
assert any(q.get('expected_decision') == 'ALLOW' for q in qs)
assert any(q.get('expected_decision') == 'BLOCK' for q in qs)
PY
fi

if [[ "$MODE" == "live" ]]; then
  BASE_URL="${MCAD_PROXY_BASE_URL:-${MCAD_PROXY_BASE:-http://127.0.0.1:9000}}"
  echo "Live endpoint smoke checks against $BASE_URL"
  curl -fsS "$BASE_URL/health" >/dev/null && ok "mcad-proxy /health reachable" || fail "mcad-proxy /health unreachable"
  curl -fsS "$BASE_URL/mcad/datawarehouses/adventureworks_sql_direct/health" >/dev/null && ok "AdventureWorks DW health endpoint reachable" || fail "AdventureWorks DW health endpoint unreachable"
fi

if [[ "$FAILS" -eq 0 ]]; then
  echo "Summary: fails=0 warnings=$WARNINGS"
  exit 0
fi

echo "Summary: fails=$FAILS warnings=$WARNINGS"
exit 1
