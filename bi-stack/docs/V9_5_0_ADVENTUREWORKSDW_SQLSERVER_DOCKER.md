# V9.5.0 — AdventureWorksDW SQL Server Docker Integration

## Scope

This version adds a real SQL Server Docker-backed AdventureWorksDW path to the BI stack:

```text
AdventureWorksDW2022.bak
→ SQL Server 2022 Docker container
→ adventureworks_sql_direct registry entry
→ adventureworks_direct adapter
→ MCAD-controlled execution gateway
```

The FoodMart XMLA/eMondrian and FoodMart Direct BI paths remain unchanged.

## Setup SQL Server + restore AdventureWorksDW

```bash
ADVENTUREWORKS_SA_PASSWORD='MCAD_AwDWDemo!2026'   bash bi-stack/scripts/setup_adventureworks_sqlserver.sh .
```

The setup script downloads `AdventureWorksDW2022.bak` if missing, starts SQL Server, restores `AdventureWorksDW2022`, and verifies `dbo.FactInternetSales`.

## Rebuild proxy

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d adventureworks-sqlserver mcad-proxy
```

## Checks

```bash
bash bi-stack/scripts/check_adventureworks_sqlserver_integration.sh . static
bash bi-stack/scripts/check_adventureworks_sqlserver_integration.sh . live
```

## Data warehouse id

```text
adventureworks_sql_direct
```

UI label:

```text
AdventureWorksDW via SQL Server Direct
```

## Adapter contract

The adapter returns physical execution evidence: `adapter_id`, `execution_path`, `database`, `elapsed_ms`, `row_count`, `response_digest`, `columns`, and `rows`.

## Supported first subset

V9.5.0 implements a controlled first subset: read-only SQL Server `SELECT` queries and MDX-like demo input mapped to AdventureWorksDW T-SQL for SalesAmount, TotalProductCost, OrderQuantity, and GrossMargin over year/month/territory. Full AdventureWorks objectives and scenarios are planned for V9.5.1.
