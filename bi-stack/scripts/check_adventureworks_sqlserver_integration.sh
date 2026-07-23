#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"; MODE="${2:-static}"
fail=0; warn=0
ok(){ echo "[OK] $1"; }; warnf(){ echo "[WARN] $1"; warn=$((warn+1)); }; failf(){ echo "[FAIL] $1"; fail=$((fail+1)); }
contains(){ grep -qE "$2" "$1" 2>/dev/null; }

echo "=== MCAD V9.5.0 AdventureWorksDW SQL Server Docker integration check ==="
echo "repo_root=$ROOT"; echo "mode=$MODE"
[[ -f "$ROOT/bi-stack/docker-compose.yml" ]] && ok "docker-compose.yml exists" || failf "docker-compose.yml missing"
[[ -f "$ROOT/bi-stack/mcad-proxy/datawarehouses.yaml" ]] && ok "datawarehouses.yaml exists" || failf "datawarehouses.yaml missing"
[[ -f "$ROOT/bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py" ]] && ok "AdventureWorks adapter exists" || failf "AdventureWorks adapter missing"
[[ -f "$ROOT/bi-stack/scripts/setup_adventureworks_sqlserver.sh" ]] && ok "SQL Server setup script exists" || failf "setup script missing"
[[ -f "$ROOT/bi-stack/adventureworks/sql/restore_adventureworksdw2022.sql" ]] && ok "restore SQL script exists" || failf "restore SQL script missing"
[[ -f "$ROOT/bi-stack/docs/V9_5_0_ADVENTUREWORKSDW_SQLSERVER_DOCKER.md" ]] && ok "V9.5.0 documentation exists" || failf "documentation missing"
contains "$ROOT/bi-stack/docker-compose.yml" "adventureworks-sqlserver" && ok "SQL Server Docker service is declared" || failf "adventureworks-sqlserver service not declared"
contains "$ROOT/bi-stack/docker-compose.yml" "mcr.microsoft.com/mssql/server:2022-latest" && ok "SQL Server 2022 image is configured" || failf "SQL Server 2022 image missing"
contains "$ROOT/bi-stack/mcad-proxy/datawarehouses.yaml" "id: adventureworks_sql_direct" && ok "adventureworks_sql_direct is registered" || failf "adventureworks_sql_direct missing"
contains "$ROOT/bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py" "pytds" && ok "adapter uses python-tds" || failf "adapter does not use python-tds"
contains "$ROOT/bi-stack/mcad-proxy/Dockerfile" "python-tds" && ok "mcad-proxy Dockerfile installs python-tds" || failf "mcad-proxy Dockerfile does not install python-tds"
if [[ "$MODE" == "live" ]]; then
  echo "--- live checks ---"
  curl -fsS http://127.0.0.1:9000/health >/tmp/mcad_v950_proxy_health.json && ok "mcad-proxy health responds" || failf "mcad-proxy health failed"
  curl -fsS 'http://127.0.0.1:9000/mcad/datawarehouses?include_disabled=true' | grep -q "adventureworks_sql_direct" && ok "proxy exposes adventureworks_sql_direct" || failf "proxy does not expose adventureworks_sql_direct"
  if curl -fsS http://127.0.0.1:9000/mcad/datawarehouses/adventureworks_sql_direct/health >/tmp/mcad_v950_aw_health.json; then
    if grep -q '"database_ready"[[:space:]]*:[[:space:]]*true' /tmp/mcad_v950_aw_health.json; then ok "AdventureWorksDW adapter health is OK"; else warnf "AdventureWorksDW adapter reachable but database may not be restored yet"; cat /tmp/mcad_v950_aw_health.json; fi
  else failf "AdventureWorksDW adapter health endpoint failed"; fi
fi
echo "Summary: fails=$fail warnings=$warn"
[[ "$fail" == "0" ]]
