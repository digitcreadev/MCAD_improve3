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

NETWORK="mcad-r3-rerun1_r3_internal"
VOLUME="mcad-r3-rerun1_r3_sql_data"

fail() {
  echo
  echo "R3_C2_ISOLATED_RUNTIME_PREFLIGHT=FAIL reason=$1"
  echo "docker_mutation_performed=false"
  echo "service_mutation_performed=false"
  echo "backend_query_executed=false"
  echo "measurement_executed=false"
  exit 1
}

inspect_scalar() {
  docker inspect -f "$2" "$1" 2>/dev/null
}

echo "=== R3-C2 isolated-runtime READ-ONLY live preflight ==="
echo "DOCKER_INSPECT_ALLOWED=true"
echo "DOCKER_MUTATION_ALLOWED=false"
echo "SERVICE_MUTATION_ALLOWED=false"
echo "BACKEND_QUERY_ALLOWED=false"
echo "MEASUREMENT_ALLOWED=false"
echo "HTTP_GET_HEALTH_ALLOWED=true"

command -v docker >/dev/null 2>&1 || fail "docker_not_available"

echo
echo "=== Protected historical runtime exact-continuity gate ==="

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
echo "=== Isolated clone identity / isolation gate ==="

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
  [ "$actual_image" = "$image" ] || fail "${label}_image_changed"
done

docker network inspect "$NETWORK" >/dev/null 2>&1 || fail "isolated_network_missing"
docker volume inspect "$VOLUME" >/dev/null 2>&1 || fail "isolated_sql_volume_missing"

sql_volume_name="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/opt/mssql"}}{{.Name}}{{end}}{{end}}' "$CLONE_SQL")"
[ "$sql_volume_name" = "$VOLUME" ] || fail "clone_sql_volume_mismatch"

api_backend_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/backend"}}{{.Source}}{{end}}{{end}}' "$CLONE_API")"
api_backend_rw="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/backend"}}{{.RW}}{{end}}{{end}}' "$CLONE_API")"
api_data_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}' "$CLONE_API")"
proxy_data_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}' "$CLONE_PROXY")"
proxy_demo_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/demo-evidence"}}{{.Source}}{{end}}{{end}}' "$CLONE_PROXY")"

[ "$api_backend_source" = "$REPO/backend" ] || fail "clone_api_backend_source_changed"
[ "$api_backend_rw" = "false" ] || fail "clone_api_backend_not_readonly"

case "$api_data_source" in "$REPO"/*) fail "clone_api_data_inside_repo";; esac
case "$proxy_data_source" in "$REPO"/*) fail "clone_proxy_data_inside_repo";; esac
case "$proxy_demo_source" in "$REPO"/*) fail "clone_proxy_demo_inside_repo";; esac

runtime_root="$(dirname "$api_data_source")"
[ "$proxy_data_source" = "$runtime_root/proxy-data" ] || fail "clone_proxy_data_runtime_root_mismatch"
[ "$proxy_demo_source" = "$runtime_root/demo-evidence" ] || fail "clone_proxy_demo_runtime_root_mismatch"

api_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "8000/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "8000/tcp" 0).HostPort}}' "$CLONE_API")"
proxy_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "9000/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "9000/tcp" 0).HostPort}}' "$CLONE_PROXY")"
sql_bind="$(docker inspect -f '{{(index .HostConfig.PortBindings "1433/tcp" 0).HostIp}}:{{(index .HostConfig.PortBindings "1433/tcp" 0).HostPort}}' "$CLONE_SQL")"

[ "$api_bind" = "127.0.0.1:18000" ] || fail "clone_api_port_binding_changed"
[ "$proxy_bind" = "127.0.0.1:19000" ] || fail "clone_proxy_port_binding_changed"
[ "$sql_bind" = "127.0.0.1:24333" ] || fail "clone_sql_port_binding_changed"

echo "isolated_runtime_root=$runtime_root"
echo "isolated_clone_identity_and_mount_isolation=PASS"

echo
echo "=== Isolated clone liveness classification ==="

sql_state="$(inspect_scalar "$CLONE_SQL" '{{.State.Status}}')"
api_state="$(inspect_scalar "$CLONE_API" '{{.State.Status}}')"
proxy_state="$(inspect_scalar "$CLONE_PROXY" '{{.State.Status}}')"

running_count=0
[ "$sql_state" = "running" ] && running_count=$((running_count+1))
[ "$api_state" = "running" ] && running_count=$((running_count+1))
[ "$proxy_state" = "running" ] && running_count=$((running_count+1))

if [ "$running_count" -eq 3 ]; then
  echo "isolated_clone_runtime_state=RUNNING"
  api_health_status="$(curl -sS -o /tmp/mcad_r3c2_api_health.$$ -w '%{http_code}' http://127.0.0.1:18000/health || true)"
  proxy_openapi_status="$(curl -sS -o /tmp/mcad_r3c2_proxy_openapi.$$ -w '%{http_code}' http://127.0.0.1:19000/openapi.json || true)"
  rm -f /tmp/mcad_r3c2_api_health.$$ /tmp/mcad_r3c2_proxy_openapi.$$
  echo "isolated_api_health_http=$api_health_status"
  echo "isolated_proxy_openapi_http=$proxy_openapi_status"
  [ "$api_health_status" = "200" ] || fail "isolated_api_health_not_200"
  [ "$proxy_openapi_status" = "200" ] || fail "isolated_proxy_openapi_not_200"
  echo "isolated_clone_readonly_health=PASS"
  echo "R3C_NEXT_RUNTIME_ACTION=NO_CLONE_BRINGUP_REQUIRED"
elif [ "$running_count" -eq 0 ]; then
  echo "isolated_clone_runtime_state=STOPPED_INTACT"
  echo "isolated_clone_readonly_health=NOT_APPLICABLE_STOPPED"
  echo "R3C_NEXT_RUNTIME_ACTION=CLONE_ONLY_BRINGUP_REQUIRED"
else
  echo "isolated_clone_states=sql:${sql_state},api:${api_state},proxy:${proxy_state}"
  fail "isolated_clone_mixed_liveness_state"
fi

echo
echo "docker_mutation_performed=false"
echo "service_mutation_performed=false"
echo "backend_query_executed=false"
echo "measurement_executed=false"
echo "protected_historical_runtime_mutated=false"
echo "R3_C2_ISOLATED_RUNTIME_PREFLIGHT=PASS"
