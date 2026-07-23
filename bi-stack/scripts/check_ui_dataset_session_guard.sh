#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
UI="$ROOT/bi-stack/mcad-proxy/session_ui.html"
APP="$ROOT/bi-stack/mcad-proxy/app.py"

ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1" >&2; exit 1; }

[ -f "$UI" ] || fail "session_ui.html exists"
[ -f "$APP" ] || fail "app.py exists"

grep -q "function datasetKey" "$UI" || fail "UI datasetKey helper missing"
grep -q "function objectiveCompatibleWithDw" "$UI" || fail "UI objective/DW compatibility helper missing"
grep -q "function renderObjectiveSelectForDw" "$UI" || fail "UI objective selector filtering missing"
grep -q "function bindDatasetAwareSessionSelectors" "$UI" || fail "UI DW change binding missing"
ok "UI dataset-aware objective filtering is wired"

grep -q "_assert_session_objective_dw_compatible" "$APP" || fail "backend session compatibility guard missing"
grep -q "OBJECTIVE_DW_DATASET_MISMATCH" "$APP" || fail "backend mismatch error code missing"
grep -q "_session_guard_objective_dataset" "$APP" || fail "backend objective dataset inference missing"
ok "backend objective/DW dataset guard is wired"

python - "$APP" <<'PYCODE'
import ast
import pathlib
import sys

ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
PYCODE
ok "app.py syntax is valid"

echo
echo "=== UI dataset-aware session guard OK ==="
