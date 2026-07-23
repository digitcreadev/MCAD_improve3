#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${1:-.}"
fails=0
warns=0
ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1"; fails=$((fails+1)); }
warn(){ echo "[WARN] $1"; warns=$((warns+1)); }
exists(){ [[ -f "$REPO_ROOT/$1" ]] && ok "$1 exists" || fail "$1 is missing"; }
contains(){ local f="$1" p="$2" m="$3"; grep -qE "$p" "$REPO_ROOT/$f" && ok "$m" || fail "$m"; }

echo "=== MCAD V9.4.5a dual-path demo validation pack contract check ==="
echo "repo_root=$REPO_ROOT"

exists "bi-stack/scripts/run_dual_path_demo_validation.py"
exists "bi-stack/scripts/run_dual_path_demo_validation.sh"
exists "bi-stack/scripts/check_dual_path_demo_pack.sh"
exists "bi-stack/docs/V9_4_5A_DUAL_PATH_VALIDATION_ISOLATION_FIX.md"
if [[ -f "$REPO_ROOT/bi-stack/mcad-proxy/app.py" ]]; then
  contains "bi-stack/mcad-proxy/app.py" "MCAD_API_UNAVAILABLE" "Proxy returns structured JSON when mcad-api is temporarily unavailable"
else
  warn "bi-stack/mcad-proxy/app.py not found in this checkout; proxy robustness check skipped"
fi

contains "bi-stack/scripts/run_dual_path_demo_validation.py" "foodmart_sql_direct" "Direct BI path is validated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "xmla|XMLA|emondrian" "XMLA/eMondrian path is validated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "Q3_BLOCK_OUT_OF_OBJECTIVE|BLOCK" "MCAD BLOCK no-exec case is validated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "adventureworks_xmla" "DW/scenario guard case is validated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "dual_path_summary\.json" "JSON summary export is generated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "dual_path_summary\.md" "Markdown summary export is generated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "dual_path_steps\.csv" "CSV step export is generated"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "response_digest|result_digest" "Execution digests are captured"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "physical_execution" "Physical-execution evidence is checked"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "retry_call|DEFAULT_RETRY_ATTEMPTS" "Live runner retries transient startup failures"
contains "bi-stack/scripts/run_dual_path_demo_validation.py" "MCAD_API_UNAVAILABLE|Connection refused" "Live runner recognises mcad-api startup unavailability"

python3 -m py_compile "$REPO_ROOT/bi-stack/scripts/run_dual_path_demo_validation.py" && ok "Python runner compiles" || fail "Python runner does not compile"

if [[ -d "$REPO_ROOT/bi-stack/demo-evidence" ]]; then
  ok "bi-stack/demo-evidence directory exists"
else
  warn "bi-stack/demo-evidence directory is missing; it will be created by the runner"
fi

echo "Summary: fails=$fails warnings=$warns"
[[ "$fails" -eq 0 ]]
