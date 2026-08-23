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

EXPECTED_RUNTIME_ROOT="/workspaces/MCAD_R3_ISOLATED_RUNTIME_d2f5e40171bd2daccec18e7d450644e0b510b5d8"
NETWORK="mcad-r3-rerun1_r3_internal"
VOLUME="mcad-r3-rerun1_r3_sql_data"

TMP_API="/tmp/mcad_r3d1_api_openapi.$$"
TMP_PROXY="/tmp/mcad_r3d1_proxy_openapi.$$"
TMP_HEALTH="/tmp/mcad_r3d1_api_health.$$"

cleanup() {
  rm -f "$TMP_API" "$TMP_PROXY" "$TMP_HEALTH"
}
trap cleanup EXIT

fail() {
  echo
  echo "R3_D1_ISOLATED_RUNTIME_PREFLIGHT=FAIL reason=$1"
  echo "measurement_performed=false"
  echo "backend_query_executed=false"
  echo "docker_mutation_performed=false"
  echo "service_mutation_performed=false"
  exit 1
}

inspect_scalar() {
  docker inspect -f "$2" "$1" 2>/dev/null
}

echo "=== R3-D1 isolated-runtime READ-ONLY preflight ==="
echo "MEASUREMENT_ALLOWED=false"
echo "BACKEND_QUERY_ALLOWED=false"
echo "DOCKER_MUTATION_ALLOWED=false"
echo "SERVICE_MUTATION_ALLOWED=false"
echo "DOCKER_INSPECT_ALLOWED=true"
echo "HTTP_GET_ALLOWED=true"
echo "FALLBACK_ACTIVATION_AUTHORIZED_NOW=false"

command -v docker >/dev/null 2>&1 || fail "docker_not_available"
command -v curl >/dev/null 2>&1 || fail "curl_not_available"

echo
echo "=== 1. Protected historical runtime exact continuity ==="

for spec in \
  "$PROTECTED_SQL|2026-08-23T10:02:34.457234573Z|0|$SQL_IMAGE|protected_sqlserver" \
  "$PROTECTED_API|2026-08-23T10:09:46.36179959Z|0|$API_IMAGE|protected_mcad_api" \
  "$PROTECTED_PROXY|2026-08-23T10:08:25.609823871Z|0|$PROXY_IMAGE|protected_mcad_proxy"
do
  IFS='|' read -r cid started restarts image label <<< "$spec"
  docker inspect "$cid" >/dev/null 2>&1 || fail "${label}_missing"
  state="$(inspect_scalar "$cid" '{{.State.Status}}')"
  actual_started="$(inspect_scalar "$cid" '{{.State.StartedAt}}')"
  actual_restarts="$(inspect_scalar "$cid" '{{.RestartCount}}')"
  actual_image="$(inspect_scalar "$cid" '{{.Image}}')"
  echo "${label}=${cid}|${state}|${actual_started}|${actual_restarts}|${actual_image}"
  [ "$state" = "running" ] || fail "${label}_not_running"
  [ "$actual_started" = "$started" ] || fail "${label}_started_at_changed"
  [ "$actual_restarts" = "$restarts" ] || fail "${label}_restart_count_changed"
  [ "$actual_image" = "$image" ] || fail "${label}_image_changed"
done

echo "protected_historical_runtime_exact_continuity=PASS"

echo
echo "=== 2. Isolated clone identity / liveness / mounts ==="

for spec in \
  "$CLONE_SQL|$SQL_IMAGE|clone_sqlserver" \
  "$CLONE_API|$API_IMAGE|clone_mcad_api" \
  "$CLONE_PROXY|$PROXY_IMAGE|clone_mcad_proxy"
do
  IFS='|' read -r cid image label <<< "$spec"
  docker inspect "$cid" >/dev/null 2>&1 || fail "${label}_missing"
  state="$(inspect_scalar "$cid" '{{.State.Status}}')"
  actual_image="$(inspect_scalar "$cid" '{{.Image}}')"
  echo "${label}=${cid}|${state}|${actual_image}"
  [ "$state" = "running" ] || fail "${label}_not_running"
  [ "$actual_image" = "$image" ] || fail "${label}_image_changed"
done

docker network inspect "$NETWORK" >/dev/null 2>&1 || fail "isolated_network_missing"
docker volume inspect "$VOLUME" >/dev/null 2>&1 || fail "isolated_sql_volume_missing"

sql_volume_name="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/opt/mssql"}}{{.Name}}{{end}}{{end}}' "$CLONE_SQL")"
api_backend_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/backend"}}{{.Source}}{{end}}{{end}}' "$CLONE_API")"
api_backend_rw="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/backend"}}{{.RW}}{{end}}{{end}}' "$CLONE_API")"
api_data_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}' "$CLONE_API")"
proxy_data_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}' "$CLONE_PROXY")"
proxy_demo_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/demo-evidence"}}{{.Source}}{{end}}{{end}}' "$CLONE_PROXY")"

[ "$sql_volume_name" = "$VOLUME" ] || fail "clone_sql_volume_changed"
[ "$api_backend_source" = "$REPO/backend" ] || fail "clone_api_backend_source_changed"
[ "$api_backend_rw" = "false" ] || fail "clone_api_backend_not_readonly"

runtime_root="$(dirname "$api_data_source")"
[ "$runtime_root" = "$EXPECTED_RUNTIME_ROOT" ] || fail "isolated_runtime_root_changed"
[ "$proxy_data_source" = "$EXPECTED_RUNTIME_ROOT/proxy-data" ] || fail "clone_proxy_data_root_changed"
[ "$proxy_demo_source" = "$EXPECTED_RUNTIME_ROOT/demo-evidence" ] || fail "clone_demo_evidence_root_changed"

case "$runtime_root" in "$REPO"|"$REPO"/*) fail "isolated_runtime_inside_repo";; esac

api_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "8000/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "8000/tcp" 0).HostPort}}' "$CLONE_API")"
proxy_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "9000/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "9000/tcp" 0).HostPort}}' "$CLONE_PROXY")"
sql_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "1433/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "1433/tcp" 0).HostPort}}' "$CLONE_SQL")"

[ "$api_bind" = "127.0.0.1:18000" ] || fail "clone_api_port_changed"
[ "$proxy_bind" = "127.0.0.1:19000" ] || fail "clone_proxy_port_changed"
[ "$sql_bind" = "127.0.0.1:24333" ] || fail "clone_sql_port_changed"

echo "isolated_runtime_root=$runtime_root"
echo "isolated_clone_identity_liveness_mounts=PASS"

echo
echo "=== 3. Read-only HTTP health + route contract ==="

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
required_api={"/sessions/create"}
required_proxy={"/bi/r3/measurement/gate-only", "/bi/r3/measurement/full-execute"}
missing_api=sorted(required_api-api_paths)
missing_proxy=sorted(required_proxy-proxy_paths)
if missing_api:
    raise SystemExit("missing API routes: " + ",".join(missing_api))
if missing_proxy:
    raise SystemExit("missing proxy routes: " + ",".join(missing_proxy))
print("api_required_routes=PASS")
print("proxy_required_measurement_routes=PASS")
PY
[ "$?" -eq 0 ] || fail "measurement_route_contract_missing"

echo "isolated_clone_readonly_http_contract=PASS"

echo
echo "=== 4. Credential-material / output-space / no-redo preconditions ==="

secret_present="$(
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CLONE_SQL" 2>/dev/null \
    | grep -c '^MSSQL_SA_PASSWORD=.'
)"
[ "$secret_present" -ge 1 ] || fail "isolated_sql_credential_material_missing"
echo "isolated_sql_credential_material_present=true"
echo "credential_value_printed=false"

avail_kb="$(df -Pk /workspaces | awk 'NR==2 {print $4}')"
echo "workspaces_available_kb=$avail_kb"
[ -n "$avail_kb" ] || fail "cannot_read_workspaces_free_space"

[ ! -e "$REPO/reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_d2_confirmatory_measurement_authorization.json" ] \
  || fail "D2_authorization_unexpectedly_present"

echo "clone_bringup_required=false"
echo "measurement_output_must_be_outside_repo=true"
echo "measurement_output_directory_must_not_preexist=true"
echo "future_D2_authorization_present=false"
echo "fallback_activation_authorized_now=false"
echo "effect_size_tuning_allowed=false"
echo "confirmatory_claim_authorized=false"

echo
echo "measurement_performed=false"
echo "backend_query_executed=false"
echo "docker_mutation_performed=false"
echo "service_mutation_performed=false"
echo "protected_historical_runtime_mutated=false"
echo "R3_D1_ISOLATED_RUNTIME_PREFLIGHT=PASS"
