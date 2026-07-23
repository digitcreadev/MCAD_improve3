#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
APP="$ROOT/bi-stack/mcad-proxy/app.py"
UI="$ROOT/bi-stack/mcad-proxy/session_ui.html"
DW="$ROOT/bi-stack/mcad-proxy/datawarehouses.yaml"
fails=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; fails=$((fails+1)); }
contains(){ grep -qE "$2" "$1"; }

echo "=== MCAD V9.4.3b evidence dedup/session result/DW guard check ==="
echo "repo_root=$ROOT"
[ -f "$APP" ] && ok "app.py exists" || fail "app.py missing"
[ -f "$UI" ] && ok "session_ui.html exists" || fail "session_ui.html missing"
[ -f "$DW" ] && ok "datawarehouses.yaml exists" || fail "datawarehouses.yaml missing"

contains "$APP" "_selectable_datawarehouse_items" && ok "proxy filters selectable DWs" || fail "proxy does not filter selectable DWs"
contains "$APP" "_ensure_dw_enabled_or_400" && ok "session creation rejects disabled DWs" || fail "session creation disabled-DW guard missing"
contains "$APP" "BLOCK_DISABLED_DW" && ok "disabled DW returns explicit BLOCK_DISABLED_DW" || fail "disabled DW decision code missing"
contains "$APP" "include_disabled" && ok "datawarehouse endpoint can expose disabled entries only on request" || fail "include_disabled support missing"

contains "$UI" "affichée une seule fois" && ok "MCAD Decision no longer duplicates full evidence block" || fail "evidence duplicate warning missing"
contains "$UI" "SESSION_EXECUTION_STATE_BY_SESSION" && ok "UI stores per-session execution result state" || fail "per-session execution state store missing"
contains "$UI" "mcad_v943b_execution_state_" && ok "UI persists session result state in sessionStorage" || fail "sessionStorage persistence missing"
contains "$UI" "DW .*disabled or not integrated" && ok "UI blocks execution for disabled/unimplemented DWs" || fail "UI disabled DW execution guard missing"
contains "$UI" "filter\(x => \(typeof x==='string'\) \|\| x.enabled !== false\)" && ok "UI filters disabled DWs from selector" || fail "UI selector does not filter disabled DWs"

PYTHONPATH="$ROOT/bi-stack/mcad-proxy" python -m py_compile "$APP" && ok "app.py compiles" || fail "app.py compile failed"
node -e "const fs=require('fs');const html=fs.readFileSync('$UI','utf8');const scripts=[...html.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)].map(m=>m[1]);scripts.forEach((s,i)=>new Function(s));" && ok "session_ui JavaScript syntax is valid" || fail "session_ui JavaScript syntax failed"

echo "Summary: fails=$fails warnings=0"
exit "$fails"
