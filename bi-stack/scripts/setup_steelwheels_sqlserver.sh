#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
COMPOSE_FILE="$ROOT/bi-stack/docker-compose.yml"
SA_PASSWORD="${ADVENTUREWORKS_SA_PASSWORD:-MCAD_AwDWDemo!2026}"
SERVICE="adventureworks-sqlserver"
DB="${STEELWHEELS_SQLSERVER_DATABASE:-SteelWheels}"
SQL_FILE="$ROOT/bi-stack/steelwheels/sql/init_steelwheels_sqlserver.sql"

echo "=== MCAD V9.5.4 SteelWheels SQL Server setup ==="
echo "repo_root=$ROOT"
echo "database=$DB"
echo "sql_file=$SQL_FILE"

[[ -s "$SQL_FILE" ]] || { echo "ERROR: missing SQL file: $SQL_FILE" >&2; exit 2; }

echo "Starting SQL Server container..."
ADVENTUREWORKS_SA_PASSWORD="$SA_PASSWORD" docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
CID="$(ADVENTUREWORKS_SA_PASSWORD="$SA_PASSWORD" docker compose -f "$COMPOSE_FILE" ps -q "$SERVICE")"
[[ -n "$CID" ]] || { echo "ERROR: cannot resolve SQL Server container id." >&2; exit 3; }

_sqlcmd_exec() {
  local query="$1"
  if docker exec "$CID" test -x /opt/mssql-tools18/bin/sqlcmd >/dev/null 2>&1; then
    docker exec "$CID" /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$SA_PASSWORD" -Q "$query"
  elif docker exec "$CID" test -x /opt/mssql-tools/bin/sqlcmd >/dev/null 2>&1; then
    docker exec "$CID" /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -Q "$query"
  else
    docker run --rm --network mcad_net mcr.microsoft.com/mssql-tools /opt/mssql-tools/bin/sqlcmd -S "$SERVICE" -U sa -P "$SA_PASSWORD" -Q "$query"
  fi
}

_sqlcmd_file() {
  local path="$1"
  if docker exec "$CID" test -x /opt/mssql-tools18/bin/sqlcmd >/dev/null 2>&1; then
    docker exec -i "$CID" /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$SA_PASSWORD" < "$path"
  elif docker exec "$CID" test -x /opt/mssql-tools/bin/sqlcmd >/dev/null 2>&1; then
    docker exec -i "$CID" /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" < "$path"
  else
    cat "$path" | docker run --rm -i --network mcad_net mcr.microsoft.com/mssql-tools /opt/mssql-tools/bin/sqlcmd -S "$SERVICE" -U sa -P "$SA_PASSWORD"
  fi
}

echo "Waiting for SQL Server readiness..."
for i in $(seq 1 90); do
  if _sqlcmd_exec "SELECT 1 AS ready" >/dev/null 2>&1; then
    echo "SQL Server is ready."
    break
  fi
  [[ "$i" != "90" ]] || { echo "ERROR: SQL Server not ready." >&2; docker logs "$CID" --tail=120 >&2 || true; exit 4; }
  sleep 2
done

echo "Initializing SteelWheels database..."
_sqlcmd_file "$SQL_FILE"

echo "Verifying SteelWheels database..."
_sqlcmd_exec "SELECT DB_NAME() AS current_db; SELECT COUNT_BIG(*) AS OrderFactRows FROM [$DB].dbo.orderfact;"

echo "SteelWheels SQL Server setup completed."
