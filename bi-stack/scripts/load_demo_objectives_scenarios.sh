#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:9000}"
ROOT="${1:-.}"

echo "=== Load MCAD demo objectives/scenarios pack ==="
echo "BASE=$BASE"

OBJECTIVES=(
  "$ROOT/bi-stack/objectives/objective_demo_adventureworks_europe_bikes_2013_month_region_sales_quantity.json"
  "$ROOT/bi-stack/objectives/objective_demo_adventureworks_north_america_accessories_2013_month_region_sales_quantity.json"
  "$ROOT/bi-stack/objectives/objective_demo_steelwheels_na_motorcycles_2004_month_sales_quantity.json"
  "$ROOT/bi-stack/objectives/objective_demo_steelwheels_apac_vintage_cars_2004_month_sales_quantity.json"
)

SCENARIOS=(
  "$ROOT/bi-stack/direct-scenarios/demo_adventureworks_europe_bikes_2013_sql_direct_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_adventureworks_europe_bikes_2013_xmla_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_adventureworks_north_america_accessories_2013_sql_direct_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_adventureworks_north_america_accessories_2013_xmla_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_steelwheels_na_motorcycles_2004_sql_direct_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_steelwheels_na_motorcycles_2004_xmla_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_steelwheels_apac_vintage_cars_2004_sql_direct_q1_q6.json"
  "$ROOT/bi-stack/direct-scenarios/demo_steelwheels_apac_vintage_cars_2004_xmla_q1_q6.json"
)

echo
echo "--- objectives ---"
for f in "${OBJECTIVES[@]}"; do
  [ -f "$f" ] || { echo "[FAIL] missing objective file: $f" >&2; exit 1; }
  echo "[LOAD] $f"
  curl -sS -X POST "$BASE/mcad/objectives/import"     -H 'Content-Type: application/json'     --data-binary @"$f"     | python -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"ok": d.get("ok"), "status": d.get("status"), "objective_ids": d.get("objective_ids"), "warnings": d.get("warnings")}, ensure_ascii=False))'
done

echo
echo "--- scenarios ---"
for f in "${SCENARIOS[@]}"; do
  [ -f "$f" ] || { echo "[FAIL] missing scenario file: $f" >&2; exit 1; }
  echo "[LOAD] $f"
  curl -sS -X POST "$BASE/bi/scenarios/import"     -H 'Content-Type: application/json'     --data-binary @"$f"     | python -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"ok": d.get("ok"), "status": d.get("status"), "scenario_ids": d.get("scenario_ids"), "warnings": d.get("warnings")}, ensure_ascii=False))'
done

echo
echo "=== Demo objectives/scenarios pack loaded ==="
