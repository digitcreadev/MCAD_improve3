#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
APP="$ROOT/bi-stack/mcad-proxy/app.py"
UI="$ROOT/bi-stack/mcad-proxy/session_ui.html"
YAML="$ROOT/bi-stack/mcad-proxy/datawarehouses.yaml"
DOC="$ROOT/bi-stack/docs/V9_4_4_SCENARIO_OBJECTIVE_DW_COMPATIBILITY_GUARD.md"
FAIL=0
WARN=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; FAIL=$((FAIL+1)); }
warn(){ echo "[WARN] $1"; WARN=$((WARN+1)); }
contains(){ local f="$1"; local p="$2"; local msg="$3"; grep -qE "$p" "$f" && ok "$msg" || fail "$msg"; }

echo "=== MCAD V9.4.4 scenario/objective/DW compatibility guard check ==="
echo "repo_root=$ROOT"
[[ -f "$APP" ]] && ok "app.py exists" || fail "app.py exists"
[[ -f "$UI" ]] && ok "session_ui.html exists" || fail "session_ui.html exists"
[[ -f "$YAML" ]] && ok "datawarehouses.yaml exists" || fail "datawarehouses.yaml exists"
[[ -f "$DOC" ]] && ok "V9.4.4 documentation exists" || fail "V9.4.4 documentation exists"

contains "$APP" "def _scenario_compatibility\(" "backend defines scenario compatibility function"
contains "$APP" "BLOCK_SCENARIO_OBJECTIVE_DW_INCOMPATIBLE" "backend blocks incompatible scenario execution"
contains "$APP" "include_incompatible" "scenario catalog supports include_incompatible"
contains "$APP" "DATASET_MISMATCH" "backend detects dataset mismatch"
contains "$APP" "OBJECTIVE_MISMATCH" "backend detects objective mismatch"
contains "$APP" "scenario_dataset" "backend exposes scenario dataset compatibility metadata"
contains "$APP" "scenario_compatibility" "backend attaches compatibility to scenarios and decisions"
contains "$UI" "function scenarioCompatibility\(" "UI defines compatibility check"
contains "$UI" "assertScenarioCompatible" "UI refuses incompatible scenario actions"
contains "$UI" "Hidden incompatible" "UI reports hidden incompatible scenarios"
contains "$UI" "Selected scenario is incompatible" "Load button is guarded"
contains "$UI" "DATASET_MISMATCH" "UI can show dataset mismatch"
contains "$YAML" "dataset: \"?FoodMart" "FoodMart dataset is declared"
contains "$YAML" "enabled: false" "future DWs remain disabled"

python -m py_compile "$APP" && ok "app.py compiles" || fail "app.py compiles"
python - <<'PY' "$UI" >/tmp/mcad_v944_ui.js
from bs4 import BeautifulSoup
from pathlib import Path
import sys
soup=BeautifulSoup(Path(sys.argv[1]).read_text(encoding='utf-8'), 'html.parser')
print('\n'.join(script.string or script.get_text() for script in soup.find_all('script')))
PY
node --check /tmp/mcad_v944_ui.js >/dev/null && ok "session_ui JavaScript syntax is valid" || fail "session_ui JavaScript syntax is valid"
rm -f /tmp/mcad_v944_ui.js

echo "Summary: fails=$FAIL warnings=$WARN"
[[ "$FAIL" -eq 0 ]]
