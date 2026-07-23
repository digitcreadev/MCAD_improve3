#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
UI="$ROOT/bi-stack/mcad-proxy/session_ui.html"
fails=0
warns=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; fails=$((fails+1)); }

echo "=== MCAD V9.4.3c runner editor action guard check ==="
echo "repo_root=$ROOT"

[ -f "$UI" ] && ok "session_ui.html exists" || fail "session_ui.html missing"

if [ -f "$UI" ]; then
  grep -q 'id="evaluateEditorQueryBtn"' "$UI" && ok "Evaluate button has a stable id" || fail "Evaluate button id missing"
  grep -q 'id="runEditorQueryBtn"' "$UI" && ok "Run button has a stable id" || fail "Run button id missing"
  grep -q 'id="addEditorQueryBtn"' "$UI" && ok "Add to scenario button has a stable id" || fail "Add to scenario button id missing"
  grep -q "\['runEditorQueryBtn','evaluateEditorQueryBtn','addEditorQueryBtn'\]" "$UI" && ok "all three editor buttons are controlled together" || fail "not all editor buttons are controlled together"
  grep -q 'const disabled=!ready || !hasText' "$UI" && ok "editor buttons are disabled when editor text is empty" || fail "empty-editor disabled guard missing"
  grep -q 'updateEditorExecutionButtons' "$UI" && ok "editor button state updater exists" || fail "editor button updater missing"
  grep -q 'V9.4.3c — Runner editor action guard' "$UI" && ok "V9.4.3c safety hook exists" || fail "V9.4.3c safety hook missing"
fi

python - "$UI" <<'PYCHECK'
from pathlib import Path
import sys
p=Path(sys.argv[1])
if p.exists():
    s=p.read_text()
    if s.count('id="addEditorQueryBtn"') != 1:
        raise SystemExit('addEditorQueryBtn should appear exactly once')
    print('[OK] addEditorQueryBtn appears exactly once')
PYCHECK

echo "Summary: fails=$fails warnings=$warns"
exit $fails
