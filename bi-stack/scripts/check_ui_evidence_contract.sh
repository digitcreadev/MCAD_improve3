#!/usr/bin/env bash
set -u
ROOT="${1:-.}"
APP="$ROOT/bi-stack/mcad-proxy/app.py"
UI="$ROOT/bi-stack/mcad-proxy/session_ui.html"
XMLA="$ROOT/bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py"
DIRECT="$ROOT/bi-stack/mcad-proxy/execution/adapters/foodmart_direct_adapter.py"
FAILS=0
WARNINGS=0
ok(){ echo "[OK] $*"; }
fail(){ echo "[FAIL] $*"; FAILS=$((FAILS+1)); }
warn(){ echo "[WARN] $*"; WARNINGS=$((WARNINGS+1)); }
contains(){ local file="$1" pat="$2" msg="$3"; if grep -qE "$pat" "$file" 2>/dev/null; then ok "$msg"; else fail "$msg"; fi }

echo "=== MCAD V9.4.3 UI evidence contract check ==="
echo "repo_root=$ROOT"

[ -f "$APP" ] || fail "app.py exists"
[ -f "$UI" ] || fail "session_ui.html exists"
[ -f "$XMLA" ] || fail "xmla_mondrian_adapter.py exists"
[ -f "$DIRECT" ] || fail "foodmart_direct_adapter.py exists"

contains "$APP" "mcad\.execution_evidence\.v1" "proxy builds mcad.execution_evidence.v1"
contains "$APP" "LAST_EXECUTION_EVIDENCE" "proxy stores LAST_EXECUTION_EVIDENCE"
contains "$APP" "@app\.get\(\"/mcad/evidence/current\"\)" "proxy exposes /mcad/evidence/current"
contains "$APP" "\"execution_evidence\": execution_evidence" "/bi/execute returns execution_evidence"
contains "$APP" "get_gateway\(\)\.execute" "/bi/execute uses hybrid gateway"

contains "$UI" "renderExecutionEvidenceBlock" "UI renders Execution Evidence block"
contains "$UI" "LAST_EXECUTION_EVIDENCE" "UI keeps LAST_EXECUTION_EVIDENCE"
contains "$UI" "/mcad/evidence/current" "UI refreshes current evidence endpoint"
contains "$UI" "MCAD gate" "UI labels MCAD gate evidence"
contains "$UI" "Digest" "UI displays result digest"

contains "$XMLA" "xmla_response_type" "XMLA adapter reports xmla_response_type"
contains "$XMLA" "xmla_valid_response" "XMLA adapter reports valid XMLA response flag"
contains "$XMLA" "result_digest" "XMLA adapter exposes result_digest alias"
contains "$DIRECT" "execution_path" "Direct BI adapter exposes execution_path"
contains "$DIRECT" "result_digest" "Direct BI adapter exposes result_digest alias"

if grep -q "execute_direct_query(query_text" "$APP" 2>/dev/null; then
  fail "app.py still calls execute_direct_query(query_text) directly in /bi/execute"
else
  ok "app.py does not call execute_direct_query(query_text) directly"
fi

echo "Summary: fails=$FAILS warnings=$WARNINGS"
[ "$FAILS" -eq 0 ]
