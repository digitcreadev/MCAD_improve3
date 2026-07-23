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

echo "=== MCAD V9.5.4 SteelWheels strict double-path validation pack check ==="

echo
echo "--- SQL Direct Q1-Q6 pack ---"
bash "$ROOT/bi-stack/scripts/check_steelwheels_validation_pack.sh" "$ROOT"

echo
echo "--- XMLA/eMondrian files ---"
require_file "bi-stack/emondrian-steelwheels/Dockerfile"
require_file "bi-stack/emondrian-steelwheels/WEB-INF/datasources.xml"
require_file "bi-stack/emondrian-steelwheels/WEB-INF/datasources.multi-dw.xml"
require_file "bi-stack/emondrian-steelwheels/WEB-INF/web.xml"
require_file "bi-stack/emondrian-steelwheels/WEB-INF/classes/mondrian.properties"
require_file "bi-stack/emondrian-steelwheels/WEB-INF/schema/SteelWheels.xml"
require_file "bi-stack/reports/steelwheels_xmla_q1_q2_probe.json"
require_file "bi-stack/direct-scenarios/steelwheels_xmla_emea_classic_cars_q1_q6.json"
require_file "bi-stack/reports/steelwheels_xmla_q1_q6_mcad_execute_check.json"
require_file "bi-stack/scripts/run_steelwheels_xmla_q1_q6_validation.py"

echo
echo "--- XMLA config checks ---"
require_grep 'emondrian-steelwheels:' \
  "bi-stack/docker-compose.yml" \
  "docker-compose declares emondrian-steelwheels"

require_grep '8083:8080' \
  "bi-stack/docker-compose.yml" \
  "emondrian-steelwheels exposes 8083"

require_grep 'emondrian-steelwheels' \
  "bi-stack/docker-compose.yml" \
  "mcad-proxy depends on or references emondrian-steelwheels"

require_grep 'id: steelwheels_xmla' \
  "bi-stack/mcad-proxy/datawarehouses.yaml" \
  "steelwheels_xmla exists in registry"

require_grep 'xmla_url: http://emondrian-steelwheels:8080/emondrian/xmla' \
  "bi-stack/mcad-proxy/datawarehouses.yaml" \
  "steelwheels_xmla points to dedicated eMondrian service"

require_grep 'DataSourceName>SteelWheels' \
  "bi-stack/emondrian-steelwheels/WEB-INF/datasources.xml" \
  "SteelWheels datasource is declared"

require_grep 'databaseName=SteelWheels' \
  "bi-stack/emondrian-steelwheels/WEB-INF/datasources.xml" \
  "SteelWheels XMLA datasource targets SQL Server SteelWheels database"

require_grep '<Schema name="SteelWheels">' \
  "bi-stack/emondrian-steelwheels/WEB-INF/schema/SteelWheels.xml" \
  "SteelWheels Mondrian schema exists"

require_grep '<Cube name="SteelWheelsSales"' \
  "bi-stack/emondrian-steelwheels/WEB-INF/schema/SteelWheels.xml" \
  "SteelWheelsSales cube exists"

require_grep '<Measure name="Sales"' \
  "bi-stack/emondrian-steelwheels/WEB-INF/schema/SteelWheels.xml" \
  "Sales measure exists in XMLA schema"

require_grep '<Measure name="Quantity"' \
  "bi-stack/emondrian-steelwheels/WEB-INF/schema/SteelWheels.xml" \
  "Quantity measure exists in XMLA schema"

echo
echo "--- XMLA strict Q1-Q6 report checks ---"
python - "$ROOT/bi-stack/reports/steelwheels_xmla_q1_q2_probe.json" "$ROOT/bi-stack/reports/steelwheels_xmla_q1_q6_mcad_execute_check.json" <<'PY'
import json
import sys

q1q2_path, q1q6_path = sys.argv[1], sys.argv[2]

q1q2 = json.load(open(q1q2_path, encoding="utf-8"))
assert q1q2.get("all_ok") is True, "XMLA Q1-Q2 probe all_ok must be true"
assert q1q2.get("dw_id") == "steelwheels_xmla"

q1q6 = json.load(open(q1q6_path, encoding="utf-8"))
assert q1q6.get("all_ok") is True, "strict XMLA Q1-Q6 all_ok must be true"
assert q1q6.get("strict_symmetric") is True, "strict_symmetric must be true"
assert q1q6.get("objective_id") == "O_STEELWHEELS_EMEA_CLASSIC_CARS_MONTH_SALES_QUANTITY"
assert q1q6.get("dw_id") == "steelwheels_xmla"
assert q1q6.get("scenario_id") == "steelwheels_xmla_emea_classic_cars_q1_q6"

rows = q1q6.get("results") or []
assert len(rows) == 6, f"expected 6 XMLA rows, got {len(rows)}"

expected_decisions = ["ALLOW", "ALLOW", "BLOCK", "BLOCK", "BLOCK", "BLOCK"]
actual_decisions = [str(x.get("got")).upper() for x in rows]
assert actual_decisions == expected_decisions, f"unexpected XMLA decisions: {actual_decisions}"

expected_reasons = [
    "ALLOW_NEW_TOTAL",
    "ALLOW_NEW_TOTAL",
    "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
    "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
    "BLOCK_GRAIN_MISMATCH",
    "BLOCK_REDUNDANT_DPHI_ZERO",
]
actual_reasons = [x.get("reason_code") for x in rows]
assert actual_reasons == expected_reasons, f"unexpected XMLA reason codes: {actual_reasons}"

for row in rows[:2]:
    assert row.get("physical_execution") is True, f"{row.get('id')} must execute physically"
    assert row.get("adapter_id") == "xmla_mondrian", f"{row.get('id')} adapter mismatch"
    assert row.get("selected_dw_id") == "steelwheels_xmla", f"{row.get('id')} selected DW mismatch"
    assert row.get("xmla_response_type") == "ExecuteResponse", f"{row.get('id')} must be ExecuteResponse"
    assert row.get("xmla_valid_response") is True, f"{row.get('id')} XMLA response must be valid"
    assert row.get("xmla_has_fault") is False, f"{row.get('id')} must have no XMLA fault"

for row in rows[2:]:
    assert row.get("physical_execution") is False, f"{row.get('id')} must not execute physically"
    assert row.get("adapter_id") is None, f"{row.get('id')} adapter must be None for BLOCK"

print("[OK] SteelWheels XMLA strict Q1-Q6 report validates symmetric ALLOW/BLOCK and real XMLA execution")
PY

echo
echo "=== SteelWheels strict double-path validation pack OK ==="
