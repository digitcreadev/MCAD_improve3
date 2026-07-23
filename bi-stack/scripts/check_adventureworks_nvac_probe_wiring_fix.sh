#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
ok(){ printf '[OK] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
API="$ROOT/bi-stack/mcad-api/app.py"
BACKEND="$ROOT/backend/mcad/formal_sat.py"
COMPOSE="$ROOT/bi-stack/docker-compose.yml"
APPLY="$ROOT/bi-stack/scripts/apply_adventureworks_nvac_probe_wiring_fix.py"
[ -f "$APPLY" ] && ok "V9.5.2e apply script exists" || fail "missing V9.5.2e apply script"
[ -f "$API" ] && ok "mcad-api app.py exists" || fail "missing mcad-api app.py"
[ -f "$BACKEND" ] && ok "backend formal_sat.py exists" || fail "missing backend/mcad/formal_sat.py"
[ -f "$COMPOSE" ] && ok "docker-compose.yml exists" || fail "missing bi-stack/docker-compose.yml"
if [ -f "$API" ]; then
  grep -q 'mcad-proxy:9000/bi/nvac-probe' "$API" && ok "mcad-api default NVAC probe URL targets proxy port 9000" || fail "mcad-api NVAC probe URL does not target mcad-proxy:9000"
  grep -q 'def _mcad_api_call_nvac_probe' "$API" && ok "mcad-api has integration NVAC probe callback" || fail "mcad-api missing integration NVAC probe callback"
  grep -q 'nvac_probe=_mcad_api_call_nvac_probe' "$API" && ok "formal SAT is called with NVAC probe callback" || fail "formal SAT is not called with NVAC probe callback"
  grep -q '"dw_id": str(features.get("dw_id") or "")' "$API" && ok "NVAC probe payload forwards dw_id" || fail "NVAC probe payload does not forward dw_id"
  grep -q '"dataset": str(features.get("dataset") or "")' "$API" && ok "NVAC probe payload forwards dataset" || fail "NVAC probe payload does not forward dataset"
  grep -q '"dw_id": features.get("dw_id")' "$API" && ok "NVAC cache key is DW-aware" || fail "NVAC cache key is not DW-aware"
  python -m py_compile "$API" && ok "mcad-api app.py compiles" || fail "mcad-api app.py does not compile"
fi
if [ -f "$BACKEND" ]; then
  grep -q '"dw_id": features.get("dw_id")' "$BACKEND" && ok "backend optional NVAC probe receives dw_id" || fail "backend optional NVAC probe does not receive dw_id"
  grep -q '"dataset": features.get("dataset")' "$BACKEND" && ok "backend optional NVAC probe receives dataset" || fail "backend optional NVAC probe does not receive dataset"
  python -m py_compile "$BACKEND" && ok "backend formal_sat.py compiles" || fail "backend formal_sat.py does not compile"
fi
if [ -f "$COMPOSE" ]; then
  grep -q 'MCAD_NVAC_MODE: "hybrid"' "$COMPOSE" && ok "docker-compose sets MCAD_NVAC_MODE=hybrid" || fail "docker-compose missing MCAD_NVAC_MODE=hybrid"
  grep -q 'MCAD_NVAC_PROBE_URL: "http://mcad-proxy:9000/bi/nvac-probe"' "$COMPOSE" && ok "docker-compose sets correct NVAC probe URL" || fail "docker-compose missing correct MCAD_NVAC_PROBE_URL"
fi
python -m py_compile "$APPLY" && ok "apply script compiles" || fail "apply script does not compile"
printf 'Summary: fails=%s warnings=0\n' "$FAILS"
exit "$FAILS"
