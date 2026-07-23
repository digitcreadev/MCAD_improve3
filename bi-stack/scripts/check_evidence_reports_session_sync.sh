#!/usr/bin/env bash
set -u
ROOT="${1:-.}"
FAILS=0
WARNS=0
ok(){ echo "[OK] $*"; }
fail(){ echo "[FAIL] $*"; FAILS=$((FAILS+1)); }
warn(){ echo "[WARN] $*"; WARNS=$((WARNS+1)); }
need_file(){ [[ -f "$ROOT/$1" ]] && ok "$1 exists" || fail "$1 missing"; }
contains(){ local f="$1" p="$2" msg="$3"; grep -qE "$p" "$ROOT/$f" && ok "$msg" || fail "$msg"; }

echo "=== MCAD V9.4.3a evidence/report/session-sync contract check ==="
echo "repo_root=$ROOT"

need_file "bi-stack/mcad-proxy/app.py"
need_file "bi-stack/mcad-proxy/session_ui.html"
need_file "bi-stack/docs/V9_4_3A_EVIDENCE_REPORTS_SESSION_SYNC.md"

contains "bi-stack/mcad-proxy/app.py" "execution_evidence_archive\.json" "proxy archives execution evidence per session"
contains "bi-stack/mcad-proxy/app.py" "_archive_execution_evidence\(" "execution evidence is archived after /bi/execute"
contains "bi-stack/mcad-proxy/app.py" "_enrich_report_payload_with_evidence" "JSON reports/metrics are enriched with evidence"
contains "bi-stack/mcad-proxy/app.py" "_append_execution_evidence_markdown" "Markdown reports append evidence section"
contains "bi-stack/mcad-proxy/app.py" "_enrich_csv_with_evidence" "CSV exports are enriched with evidence columns"
contains "bi-stack/mcad-proxy/app.py" "/mcad/evidence/current/archive" "evidence archive endpoint exists"
contains "bi-stack/mcad-proxy/session_ui.html" "v943aClearExecutionPanels" "UI clears stale result panels on session switch"
contains "bi-stack/mcad-proxy/session_ui.html" "v943aHydrateEvidenceForActiveSession" "UI hydrates evidence for the newly active session"
contains "bi-stack/mcad-proxy/session_ui.html" "v943aEvidenceMarkdown" "UI reports include execution evidence tables"
contains "bi-stack/mcad-proxy/session_ui.html" "mcad_history_with_evidence\.csv" "history CSV export includes evidence columns"

if command -v python >/dev/null 2>&1; then
  PYTHONPATH="$ROOT/bi-stack/mcad-proxy" python -m py_compile "$ROOT/bi-stack/mcad-proxy/app.py" && ok "app.py compiles" || fail "app.py does not compile"
else
  warn "python not available; skipped py_compile"
fi

if command -v node >/dev/null 2>&1; then
  tmp="$(mktemp --suffix=.js)"
  python - <<PY > "$tmp"
from pathlib import Path
html=Path('$ROOT/bi-stack/mcad-proxy/session_ui.html').read_text(encoding='utf-8')
start=html.find('<script>')
end=html.rfind('</script>')
print(html[start+8:end] if start>=0 and end>start else '')
PY
  node --check "$tmp" >/dev/null && ok "session_ui JavaScript syntax is valid" || fail "session_ui JavaScript syntax error"
  rm -f "$tmp"
else
  warn "node not available; skipped JS syntax check"
fi

echo "Summary: fails=$FAILS warnings=$WARNS"
exit $FAILS
