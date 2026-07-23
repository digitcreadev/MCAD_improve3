#!/usr/bin/env bash
set -u
ROOT="${1:-.}"
fails=0
warns=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; fails=$((fails+1)); }
warn(){ echo "[WARN] $1"; warns=$((warns+1)); }
need_file(){ [ -f "$ROOT/$1" ] && ok "$1 exists" || fail "$1 missing"; }
contains(){ local f="$1" pat="$2" msg="$3"; grep -qE "$pat" "$ROOT/$f" && ok "$msg" || fail "$msg"; }

echo "=== MCAD V9.4.7 demo runner/export contract check ==="
echo "repo_root=$ROOT"
need_file bi-stack/mcad-proxy/app.py
need_file bi-stack/mcad-proxy/session_ui.html
need_file bi-stack/scripts/run_dual_path_demo_validation.py
need_file bi-stack/scripts/run_dual_path_demo_validation.sh
need_file bi-stack/scripts/check_demo_runner_export.sh
need_file bi-stack/docs/V9_4_7_DEMO_RUNNER_EXPORT.md
need_file bi-stack/docker-compose.yml
contains bi-stack/mcad-proxy/app.py '@app.post\("/mcad/demo-evidence/run"\)' 'UI run endpoint exists'
contains bi-stack/mcad-proxy/app.py '@app.get\("/mcad/demo-evidence/run/status"\)' 'run status endpoint exists'
contains bi-stack/mcad-proxy/app.py 'latest/bundle\.zip' 'latest bundle endpoint exists'
contains bi-stack/mcad-proxy/app.py 'subprocess\.run' 'fixed validation runner is launched via subprocess'
contains bi-stack/mcad-proxy/app.py 'DEMO_RUN_LOCK' 'anti double-run lock exists'
contains bi-stack/mcad-proxy/app.py 'zipfile\.ZipFile' 'evidence bundle zip is generated'
contains bi-stack/docker-compose.yml './scripts:/app/scripts:ro' 'scripts are mounted into mcad-proxy container'
contains bi-stack/docker-compose.yml './demo-evidence:/app/demo-evidence:rw' 'demo evidence directory is mounted read/write'
contains bi-stack/mcad-proxy/session_ui.html 'Run Dual-Path Validation' 'UI exposes run button'
contains bi-stack/mcad-proxy/session_ui.html 'Download Evidence Bundle' 'UI exposes bundle download button'
contains bi-stack/mcad-proxy/session_ui.html 'runDualPathDemoValidation' 'UI has run handler'
contains bi-stack/mcad-proxy/session_ui.html 'pollDemoRunStatus' 'UI polls running validation status'
python -m py_compile "$ROOT/bi-stack/mcad-proxy/app.py" && ok "app.py compiles" || fail "app.py does not compile"
python -m py_compile "$ROOT/bi-stack/scripts/run_dual_path_demo_validation.py" && ok "runner compiles" || fail "runner does not compile"
if command -v node >/dev/null 2>&1; then
  python - <<'PY' "$ROOT/bi-stack/mcad-proxy/session_ui.html" >/tmp/mcad_v947_js.js
import re, sys
html=open(sys.argv[1],encoding='utf-8').read()
parts=re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S|re.I)
print('\n'.join(parts))
PY
  node --check /tmp/mcad_v947_js.js >/dev/null && ok "session_ui JavaScript syntax is valid" || fail "session_ui JavaScript syntax invalid"
else
  warn "node not available; skipped JavaScript syntax check"
fi
echo "Summary: fails=$fails warnings=$warns"
[ "$fails" -eq 0 ]
