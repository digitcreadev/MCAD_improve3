#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
FAILS=0
WARNINGS=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; FAILS=$((FAILS+1)); }
warn(){ echo "[WARN] $1"; WARNINGS=$((WARNINGS+1)); }
require_file(){ [[ -f "$ROOT/$1" ]] && ok "$1 exists" || fail "$1 is missing"; }
require_grep(){ local pattern="$1" file="$2" label="$3"; if grep -qE "$pattern" "$ROOT/$file" 2>/dev/null; then ok "$label"; else fail "$label"; fi; }

echo "=== MCAD V9.4.6 demo evidence viewer contract check ==="
echo "repo_root=$ROOT"

require_file "bi-stack/mcad-proxy/app.py"
require_file "bi-stack/mcad-proxy/session_ui.html"
require_file "bi-stack/docker-compose.yml"
require_file "bi-stack/docs/V9_4_6_DEMO_EVIDENCE_VIEWER.md"

require_grep "MCAD_DEMO_EVIDENCE_DIR|DEMO_EVIDENCE_DIR" "bi-stack/mcad-proxy/app.py" "proxy has configurable demo evidence directory"
require_grep "@app.get\(\"/mcad/demo-evidence/latest\"\)" "bi-stack/mcad-proxy/app.py" "latest demo evidence endpoint exists"
require_grep "@app.get\(\"/mcad/demo-evidence/runs\"\)" "bi-stack/mcad-proxy/app.py" "demo evidence runs endpoint exists"
require_grep "/mcad/demo-evidence/latest/markdown" "bi-stack/mcad-proxy/app.py" "Markdown artifact endpoint exists"
require_grep "/mcad/demo-evidence/latest/csv" "bi-stack/mcad-proxy/app.py" "CSV artifact endpoint exists"
require_grep "/mcad/demo-evidence/latest/json" "bi-stack/mcad-proxy/app.py" "JSON artifact endpoint exists"
require_grep "./demo-evidence:/app/demo-evidence:rw" "bi-stack/docker-compose.yml" "docker-compose mounts demo-evidence into mcad-proxy"
require_grep "MCAD_DEMO_EVIDENCE_DIR: /app/demo-evidence" "bi-stack/docker-compose.yml" "docker-compose exports MCAD_DEMO_EVIDENCE_DIR"
require_grep "data-page=\"demo\"" "bi-stack/mcad-proxy/session_ui.html" "UI has Demo Validation page"
require_grep "loadDemoEvidence" "bi-stack/mcad-proxy/session_ui.html" "UI loads demo evidence"
require_grep "openDemoArtifact" "bi-stack/mcad-proxy/session_ui.html" "UI exposes artifact opening actions"

python -m py_compile "$ROOT/bi-stack/mcad-proxy/app.py" && ok "app.py compiles" || fail "app.py does not compile"

if command -v node >/dev/null 2>&1; then
  tmp="$(mktemp --suffix=.js)"
  python - "$ROOT/bi-stack/mcad-proxy/session_ui.html" "$tmp" <<'PY'
from pathlib import Path
import re, sys
html = Path(sys.argv[1]).read_text(encoding='utf-8')
parts = re.findall(r'<script(?: [^>]*)?>(.*?)</script>', html, flags=re.S)
Path(sys.argv[2]).write_text('\n'.join(parts), encoding='utf-8')
PY
  if node --check "$tmp" >/dev/null 2>&1; then ok "session_ui JavaScript syntax is valid"; else fail "session_ui JavaScript syntax check failed"; fi
  rm -f "$tmp"
else
  warn "node is not available; skipped JavaScript syntax check"
fi

if [[ -f "$ROOT/bi-stack/demo-evidence/latest_path.txt" ]]; then
  ok "latest_path.txt exists; UI should display latest run after rebuild"
else
  warn "latest_path.txt not found yet; run bi-stack/scripts/run_dual_path_demo_validation.sh . before using the viewer"
fi

echo "Summary: fails=$FAILS warnings=$WARNINGS"
if [[ "$FAILS" -ne 0 ]]; then exit 1; fi
