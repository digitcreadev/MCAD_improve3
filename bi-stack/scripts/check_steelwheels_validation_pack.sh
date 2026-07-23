#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

require_file() {
  local f="$1"
  [[ -f "$ROOT/$f" ]] && ok "$f exists" || fail "$f missing"
}

require_grep() {
  local pattern="$1"
  local file="$2"
  local label="$3"
  grep -qE "$pattern" "$ROOT/$file" && ok "$label" || fail "$label"
}

echo "=== MCAD V9.5.4 SteelWheels validation pack check ==="

require_file "bi-stack/scripts/setup_steelwheels_sqlserver.sh"
require_file "bi-stack/steelwheels/sql/init_steelwheels_sqlserver.sql"
require_file "bi-stack/objectives/objective_steelwheels_emea_classic_cars_month_sales_quantity.json"
require_file "bi-stack/direct-scenarios/steelwheels_emea_classic_cars_q1_q6.json"
require_file "bi-stack/reports/steelwheels_q1_q6_mcad_execute_check.json"
require_file "bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py"
require_file "bi-stack/mcad-proxy/datawarehouses.yaml"
require_file "bi-stack/docker-compose.yml"

echo
echo "--- JSON validation ---"
python -m json.tool "$ROOT/bi-stack/objectives/objective_steelwheels_emea_classic_cars_month_sales_quantity.json" >/dev/null
python -m json.tool "$ROOT/bi-stack/direct-scenarios/steelwheels_emea_classic_cars_q1_q6.json" >/dev/null
python -m json.tool "$ROOT/bi-stack/reports/steelwheels_q1_q6_mcad_execute_check.json" >/dev/null
ok "objective/scenario/report JSON are valid"

echo
echo "--- adapter checks ---"
require_grep 'for year in \("2003", "2004", "2005"\)' \
  "bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py" \
  "adapter maps upstream SteelWheels years 2003-2005"

require_grep 'TOTALPRICE' \
  "bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py" \
  "adapter maps Sales to TOTALPRICE"

require_grep 'QUANTITYORDERED' \
  "bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py" \
  "adapter maps Quantity to QUANTITYORDERED"

require_grep 'Decimal' \
  "bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py" \
  "adapter handles Decimal JSON serialization"

echo
echo "--- datawarehouse config checks ---"
require_grep 'steelwheels_sql_direct' \
  "bi-stack/mcad-proxy/datawarehouses.yaml" \
  "steelwheels_sql_direct is registered"

require_grep 'adapter: steelwheels_direct' \
  "bi-stack/mcad-proxy/datawarehouses.yaml" \
  "steelwheels_sql_direct uses steelwheels_direct adapter"

require_grep 'STEELWHEELS_SQLSERVER_DATABASE' \
  "bi-stack/docker-compose.yml" \
  "docker compose exposes SteelWheels SQL Server env"

echo
echo "--- SQL init checks ---"
require_grep 'CREATE DATABASE \[SteelWheels\]' \
  "bi-stack/steelwheels/sql/init_steelwheels_sqlserver.sql" \
  "SteelWheels database is created"

require_grep 'CREATE TABLE .*orderfact' \
  "bi-stack/steelwheels/sql/init_steelwheels_sqlserver.sql" \
  "orderfact table is created"

require_grep 'INSERT INTO .*orderfact' \
  "bi-stack/steelwheels/sql/init_steelwheels_sqlserver.sql" \
  "orderfact data is inserted"

echo
echo "--- MCAD report checks ---"
python - "$ROOT/bi-stack/reports/steelwheels_q1_q6_mcad_execute_check.json" <<'PY'
import json
import sys

p = sys.argv[1]
r = json.load(open(p, encoding="utf-8"))

assert r.get("all_ok") is True, "all_ok must be true"
assert r.get("objective_id") == "O_STEELWHEELS_EMEA_CLASSIC_CARS_MONTH_SALES_QUANTITY"
assert r.get("dw_id") == "steelwheels_sql_direct"

rows = r.get("results") or []
assert len(rows) == 6, f"expected 6 rows, got {len(rows)}"

expected = ["ALLOW", "ALLOW", "BLOCK", "BLOCK", "BLOCK", "BLOCK"]
got = [str(x.get("got")).upper() for x in rows]
assert got == expected, f"unexpected decisions: {got}"

for row in rows[:2]:
    assert row.get("physical_execution") is True, f"{row.get('id')} must execute physically"
    assert row.get("adapter_id") == "steelwheels_direct", f"{row.get('id')} adapter mismatch"
    assert row.get("selected_dw_id") == "steelwheels_sql_direct", f"{row.get('id')} selected DW mismatch"
    assert int(row.get("row_count") or 0) > 0, f"{row.get('id')} row_count must be > 0"

for row in rows[2:]:
    assert row.get("physical_execution") is False, f"{row.get('id')} must not execute physically"
    assert row.get("adapter_id") is None, f"{row.get('id')} adapter must be None for BLOCK"

print("[OK] SteelWheels Q1-Q6 MCAD report validates ALLOW/BLOCK and physical execution contract")
PY

echo
echo "=== SteelWheels validation pack OK ==="
