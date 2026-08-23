#!/usr/bin/env bash
set +e
set +u
set -o pipefail

REPO="${1:-/workspaces/MCAD_improve3}"

PROTECTED_SQL="ca2434ae491845dec2d2a5dc4ef4b1056f6eb20282024c64a191c3ac5d1f264c"
PROTECTED_API="5767c68c60ecfe5450a9af6ccde82221c3076f9046f82a5a8353865bd73292c1"
PROTECTED_PROXY="ebd1dca12df3cff15dc411c9a5902dc16547c6a78708fd42ff6623cddd9fd612"

CLONE_SQL="7eb03679a67d80f1f9d708a0ecc42ee1d89e4f60ec26ff0fea2925f1b041395c"
CLONE_API="ec03867deaf7fb31a909eef371895189603be78b8526b14528155cea645f7c8b"
CLONE_PROXY="c12ba832d2f59b55037e6086d3021e66b8093c6fb3ef5cb26a37c0796ff20786"

SQL_IMAGE="sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89"
API_IMAGE="sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840"
PROXY_IMAGE="sha256:2494827f7dda2769fcd80e1659bbb2520b0aafe52fdefdc79e6fff07db0fe6b4"

CLONE_SQL_STARTED="2026-08-23T22:18:02.732381299Z"
CLONE_PROXY_STARTED="2026-08-23T22:18:03.115559786Z"
CLONE_API_STARTED="2026-08-23T22:18:03.377969372Z"

PRESERVED="/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_INTERRUPTED_20260823T211928Z_PRESERVED_20260823T215439Z.tar.gz"
PRESERVED_SHA="1c5bb0d802e1400a38c8bd57d629553f331821771d8bfbf83424caecd5d7fb37"
OLD_ATTEMPT="/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_ATTEMPT_20260823T211928Z"

TMP_API="/tmp/mcad_r3d3_r3_api_openapi.$$"
TMP_PROXY="/tmp/mcad_r3d3_r3_proxy_openapi.$$"
TMP_HEALTH="/tmp/mcad_r3d3_r3_health.$$"

cleanup() {
  rm -f "$TMP_API" "$TMP_PROXY" "$TMP_HEALTH"
}
trap cleanup EXIT

fail() {
  echo
  echo "R3_D3_R3_ONE_SHOT_PREMEASUREMENT_GATE=FAIL reason=$1"
  echo "measurement_performed=false"
  echo "backend_query_executed=false"
  echo "docker_or_service_mutation_performed=false"
  echo "effect_analysis_performed=false"
  echo "fallback_120_activated=false"
  exit 1
}

inspect_scalar() {
  docker inspect -f "$2" "$1" 2>/dev/null
}

echo "=== R3-D3-R3 replacement PRIMARY 300 one-shot premeasurement gate (READ-ONLY) ==="
echo "MEASUREMENT_ALLOWED_IN_THIS_SCRIPT=false"
echo "BACKEND_QUERY_ALLOWED=false"
echo "DOCKER_OR_SERVICE_MUTATION_ALLOWED=false"
echo "EFFECT_ANALYSIS_ALLOWED=false"
echo "FALLBACK_120_ACTIVATED=false"
echo "REPLACEMENT_PRIMARY_300_AUTHORIZED=true"
echo "RERUN_SCOPE=FULL_PRIMARY_300_FROM_BLOCK_1"

command -v docker >/dev/null 2>&1 || fail "docker_not_available"
command -v curl >/dev/null 2>&1 || fail "curl_not_available"
command -v gh >/dev/null 2>&1 || fail "gh_not_available"

echo
echo "=== 1. Stable Codespace host gate ==="

[ -n "${CODESPACE_NAME:-}" ] || fail "CODESPACE_NAME_not_set"
CS_JSON="$(gh codespace view -c "$CODESPACE_NAME" --json name,state,idleTimeoutMinutes 2>/dev/null)"
[ "$?" -eq 0 ] || fail "gh_codespace_view_failed"
printf '%s\n' "$CS_JSON"

CS_NAME="$(printf '%s' "$CS_JSON" | python -c 'import json,sys; print(json.load(sys.stdin).get("name",""))')"
CS_STATE="$(printf '%s' "$CS_JSON" | python -c 'import json,sys; print(json.load(sys.stdin).get("state",""))')"
CS_IDLE="$(printf '%s' "$CS_JSON" | python -c 'import json,sys; print(json.load(sys.stdin).get("idleTimeoutMinutes",""))')"

[ "$CS_NAME" = "shiny-pancake-wvgr9v47w4r6c9qwr" ] || fail "codespace_name_changed"
[ "$CS_STATE" = "Available" ] || fail "codespace_not_Available"
[ "$CS_IDLE" = "240" ] || fail "codespace_idle_timeout_not_240"

echo "codespace_name=$CS_NAME"
echo "codespace_state=$CS_STATE"
echo "codespace_idle_timeout_minutes=$CS_IDLE"
echo "stable_host_gate=PASS"

echo
echo "=== 2. Protected historical runtime remains EXITED and untouched ==="

for spec in \
  "$PROTECTED_SQL|2026-08-23T10:02:34.457234573Z|$SQL_IMAGE|protected_sqlserver" \
  "$PROTECTED_API|2026-08-23T10:09:46.36179959Z|$API_IMAGE|protected_mcad_api" \
  "$PROTECTED_PROXY|2026-08-23T10:08:25.609823871Z|$PROXY_IMAGE|protected_mcad_proxy"
do
  IFS='|' read -r cid started image label <<< "$spec"
  docker inspect "$cid" >/dev/null 2>&1 || fail "${label}_missing"
  state="$(inspect_scalar "$cid" '{{.State.Status}}')"
  actual_started="$(inspect_scalar "$cid" '{{.State.StartedAt}}')"
  restarts="$(inspect_scalar "$cid" '{{.RestartCount}}')"
  actual_image="$(inspect_scalar "$cid" '{{.Image}}')"
  echo "${label}=${cid}|${state}|${actual_started}|${restarts}|${actual_image}"
  [ "$state" = "exited" ] || fail "${label}_not_exited"
  [ "$actual_started" = "$started" ] || fail "${label}_started_at_changed"
  [ "$restarts" = "0" ] || fail "${label}_restart_count_changed"
  [ "$actual_image" = "$image" ] || fail "${label}_image_changed"
done

echo "protected_historical_runtime_exact_exited_continuity=PASS"

echo
echo "=== 3. Rebound isolated clone exact continuity ==="

for spec in \
  "$CLONE_SQL|$CLONE_SQL_STARTED|$SQL_IMAGE|clone_sqlserver" \
  "$CLONE_PROXY|$CLONE_PROXY_STARTED|$PROXY_IMAGE|clone_mcad_proxy" \
  "$CLONE_API|$CLONE_API_STARTED|$API_IMAGE|clone_mcad_api"
do
  IFS='|' read -r cid started image label <<< "$spec"
  docker inspect "$cid" >/dev/null 2>&1 || fail "${label}_missing"
  state="$(inspect_scalar "$cid" '{{.State.Status}}')"
  actual_started="$(inspect_scalar "$cid" '{{.State.StartedAt}}')"
  restarts="$(inspect_scalar "$cid" '{{.RestartCount}}')"
  actual_image="$(inspect_scalar "$cid" '{{.Image}}')"
  echo "${label}=${cid}|${state}|${actual_started}|${restarts}|${actual_image}"
  [ "$state" = "running" ] || fail "${label}_not_running"
  [ "$actual_started" = "$started" ] || fail "${label}_started_at_changed_since_R2"
  [ "$restarts" = "0" ] || fail "${label}_restart_count_changed"
  [ "$actual_image" = "$image" ] || fail "${label}_image_changed"
done

echo "rebound_isolated_clone_exact_continuity=PASS"

echo
echo "=== 4. Read-only HTTP route/health gate ==="

api_health_status="$(curl -sS -o "$TMP_HEALTH" -w '%{http_code}' http://127.0.0.1:18000/health || true)"
api_openapi_status="$(curl -sS -o "$TMP_API" -w '%{http_code}' http://127.0.0.1:18000/openapi.json || true)"
proxy_openapi_status="$(curl -sS -o "$TMP_PROXY" -w '%{http_code}' http://127.0.0.1:19000/openapi.json || true)"

echo "isolated_api_health_http=$api_health_status"
echo "isolated_api_openapi_http=$api_openapi_status"
echo "isolated_proxy_openapi_http=$proxy_openapi_status"

[ "$api_health_status" = "200" ] || fail "isolated_api_health_not_200"
[ "$api_openapi_status" = "200" ] || fail "isolated_api_openapi_not_200"
[ "$proxy_openapi_status" = "200" ] || fail "isolated_proxy_openapi_not_200"

python - "$TMP_API" "$TMP_PROXY" <<'PY'
import json, sys
api=json.load(open(sys.argv[1], encoding="utf-8"))
proxy=json.load(open(sys.argv[2], encoding="utf-8"))
api_paths=set((api.get("paths") or {}).keys())
proxy_paths=set((proxy.get("paths") or {}).keys())
if "/sessions/create" not in api_paths:
    raise SystemExit("missing /sessions/create")
for route in ("/bi/r3/measurement/gate-only", "/bi/r3/measurement/full-execute"):
    if route not in proxy_paths:
        raise SystemExit("missing " + route)
print("api_required_routes=PASS")
print("proxy_required_measurement_routes=PASS")
PY
[ "$?" -eq 0 ] || fail "route_contract_failed"

echo "isolated_clone_readonly_http_contract=PASS"

echo
echo "=== 5. Anti-redo / preservation / credential / capacity gate ==="

[ -d "$OLD_ATTEMPT" ] || fail "old_interrupted_attempt_missing"
[ -f "$PRESERVED" ] || fail "preserved_interrupted_archive_missing"
ACTUAL_PRESERVED_SHA="$(sha256sum "$PRESERVED" | awk '{print $1}')"
echo "preserved_interrupted_archive_sha256=$ACTUAL_PRESERVED_SHA"
[ "$ACTUAL_PRESERVED_SHA" = "$PRESERVED_SHA" ] || fail "preserved_interrupted_archive_sha_changed"

OLD_RECEIPTS="$(find "$OLD_ATTEMPT/results/arm_runs" -maxdepth 1 -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
echo "old_interrupted_attempt_arm_receipts=$OLD_RECEIPTS"
[ "$OLD_RECEIPTS" = "297" ] || fail "old_interrupted_attempt_receipt_count_changed"

REPLACEMENT_ATTEMPTS="$(find /workspaces -maxdepth 1 -type d -name 'MCAD_R3_D3_REPLACEMENT_PRIMARY_ATTEMPT_*' -print | LC_ALL=C sort)"
if [ -n "$REPLACEMENT_ATTEMPTS" ]; then
  echo "preexisting_replacement_attempts:"
  printf '%s\n' "$REPLACEMENT_ATTEMPTS"
  fail "preexisting_replacement_attempt_requires_audit"
fi
echo "preexisting_replacement_attempts=NONE"

D3_PROCESS="$(
  ps -eo pid=,ppid=,stat=,etime=,cmd= \
    | grep -E 'r3_d3_primary_confirmatory_one_shot\.py|R3_D3_REPLACEMENT_PRIMARY' \
    | grep -v -E 'grep -E|r3_d3_r3_one_shot_premeasurement_readonly\.sh' \
    || true
)"
[ -z "$D3_PROCESS" ] || {
  echo "$D3_PROCESS"
  fail "D3_process_already_running"
}
echo "d3_measurement_process_running=false"

secret_present="$(
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CLONE_SQL" 2>/dev/null \
    | grep -c '^MSSQL_SA_PASSWORD=.'
)"
[ "$secret_present" -ge 1 ] || fail "isolated_sql_credential_material_missing"
echo "isolated_sql_credential_material_present=true"
echo "credential_value_printed=false"

avail_kb="$(df -Pk /workspaces | awk 'NR==2 {print $4}')"
echo "workspaces_available_kb=$avail_kb"
[ -n "$avail_kb" ] || fail "cannot_read_workspaces_space"

echo "partial_attempt_reused=false"
echo "resume_from_arm_298=false"
echo "fallback_120_activated=false"
echo "replacement_output_directory_must_not_preexist=true"

echo
echo "measurement_performed=false"
echo "backend_query_executed=false"
echo "docker_or_service_mutation_performed=false"
echo "effect_analysis_performed=false"
echo "confirmatory_claim_authorized=false"
echo "R3_D3_R3_ONE_SHOT_PREMEASUREMENT_GATE=PASS_READY_FOR_R4_REPLACEMENT_EXECUTION"
