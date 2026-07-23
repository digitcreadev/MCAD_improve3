# V9.5.1 — AdventureWorks Objective + Scenario Pack

## Purpose

V9.5.1 adds the first MCAD objective/scenario pack for the real SQL Server Docker-backed AdventureWorksDW adapter introduced in V9.5.0.

This step does **not** require a fixed Q1-Q6 format.  The delivered scenario contains six queries because this is a convenient validation shape: three useful ALLOW queries and three BLOCK cases.

## Added files

- `bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json`
- `bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json`
- `bi-stack/scripts/import_adventureworks_objective_scenario.sh`
- `bi-stack/scripts/check_adventureworks_objective_scenario_pack.sh`
- `bi-stack/docs/V9_5_1_ADVENTUREWORKS_OBJECTIVE_SCENARIO_PACK.md`

V9.5.1 also hardens the AdventureWorks direct adapter so MDX-like queries mentioning both `Month` and `Territory` are translated to SQL Server queries grouped by the composite `Month x SalesTerritoryRegion` grain.

## Objective

`O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`

The objective asks MCAD to make the following resources calculable for AdventureWorksDW:

- `SalesAmount` for Bikes / Europe / 2013 by Month and SalesTerritoryRegion;
- `TotalProductCost` for Bikes / Europe / 2013 by Month and SalesTerritoryRegion;
- `GrossMargin = SalesAmount - TotalProductCost` for Bikes / Europe / 2013 by Month and SalesTerritoryRegion.

## Scenario

`adventureworks_sales_margin_territory_q1_q6`

| Query | Expected | Purpose |
|---|---|---|
| AW_Q1 | ALLOW | SalesAmount at target grain/slicers |
| AW_Q2 | ALLOW | TotalProductCost at target grain/slicers |
| AW_Q3 | ALLOW | GrossMargin at target grain/slicers |
| AW_Q4 | BLOCK | Accessories instead of Bikes |
| AW_Q5 | BLOCK | Year grain instead of Month grain |
| AW_Q6 | BLOCK | Redundant SalesAmount after Q1 |

## Installation

Copy the delivered files, then run:

```bash
bash bi-stack/scripts/check_adventureworks_objective_scenario_pack.sh .
```

## Import into the live MCAD API

After SQL Server is restored and the BI stack is up:

```bash
ADVENTUREWORKS_SA_PASSWORD='MCAD_AwDWDemo!2026' \
  bash bi-stack/scripts/setup_adventureworks_sqlserver.sh .

docker compose -f bi-stack/docker-compose.yml up -d \
  adventureworks-sqlserver emondrian pivot4j mcad-api mcad-proxy

bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .
```

The script imports the objective, validates/imports the scenario, and creates a smoke-test session using `adventureworks_sql_direct`.

## Boundary

V9.5.1 provides the objective/scenario pack and semantic mapping hardening.  A full automated AdventureWorks evidence validation pack is intentionally left for V9.5.2.
