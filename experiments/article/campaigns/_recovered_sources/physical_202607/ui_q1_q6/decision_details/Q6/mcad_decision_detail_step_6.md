# MCAD Decision Detail — S_0001 / step 6

- Objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
- Decision: **BLOCK**
- Reason code: `BLOCK_REDUNDANT_DPHI_ZERO`
- Reason: Contract-driven redundancy: matched constraint(s) already covered in the current session.
- φ: 1.0
- Δφ: 0.0

## Formal explanation
Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête. Décision BLOCK : la requête est redondante, les contraintes correspondantes ont déjà été couvertes dans la session, donc Δφ=0.

### Reasoning steps
- QP interroge le cube Adventure Works DW avec les mesures SalesAmount, le grain Date.Calendar, Date.Month, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region et les slicers {"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}.
- SAT(QP)=true : toutes les clauses formelles disponibles sont satisfaites (grain_ok, agg_ok, unit_ok, slc_ok, time_ok, nvac_ok).
- nvac_ok(QP)=true : méthode=hybrid_probe, estimated_cells=3, probe_attempted=None.
- Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête.
- Décision BLOCK : la requête est redondante, les contraintes correspondantes ont déjà été couvertes dans la session, donc Δφ=0.

## Formal SAT(QP)
```json
{
  "grain_ok": true,
  "agg_ok": true,
  "unit_ok": true,
  "slc_ok": true,
  "time_ok": true,
  "nvac_ok": true
}
```

## nvac_ok evidence
```json
{
  "method": "hybrid_probe",
  "known_empty": false,
  "estimated_cells": 3,
  "slicers": {
    "Product.Product Category": "Bikes",
    "Sales Territory.Sales Territory Group": "Europe",
    "Date.Calendar Year": "2013"
  },
  "probe": {
    "probe_attempted": true,
    "probe_url": "http://mcad-proxy:9000/bi/nvac-probe",
    "elapsed_ms": 959,
    "non_empty": true,
    "count": 3,
    "probe_query": "SELECT {[Measures].[SalesAmount]} ON COLUMNS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
    "probe_measure": "SalesAmount",
    "raw_probe_summary": {
      "ok": true,
      "physical_execution": true,
      "execution_mode": "real",
      "adapter_family": "sqlserver_direct",
      "adapter_id": "adventureworks_direct",
      "dw_id": "adventureworks_sql_direct",
      "dataset": "AdventureWorksDW",
      "database": "AdventureWorksDW2022",
      "logical_query_language": "mdx",
      "physical_query_language": "sqlserver_tsql",
      "logical_mapping": "SalesAmount",
      "generated_sql": "SELECT TOP (200)\n       t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion,\n       CAST(SUM(f.SalesAmount) AS DECIMAL(18,2)) AS [SalesAmount]\nFROM dbo.FactInternetSales AS f\nJOIN dbo.DimDate AS d ON d.DateKey = f.OrderDateKey\nLEFT JOIN dbo.DimSalesTerritory AS t ON t.SalesTerritoryKey = f.SalesTerritoryKey\nLEFT JOIN dbo.DimProduct AS p ON p.ProductKey = f.ProductKey\nLEFT JOIN dbo.DimProductSubcategory AS ps ON ps.ProductSubcategoryKey = p.ProductSubcategoryKey\nLEFT JOIN dbo.DimProductCategory AS pc ON pc.ProductCategoryKey = ps.ProductCategoryKey\nWHERE f.SalesAmount IS NOT NULL AND d.CalendarYear = 2013 AND t.SalesTerritoryGroup = 'Europe' AND pc.EnglishProductCategoryName = 'Bikes'\nGROUP BY t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion\nORDER BY t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion;",
      "columns": [
        "SalesTerritoryGroup",
        "SalesTerritoryCountry",
        "SalesTerritoryRegion",
        "SalesAmount"
      ],
      "rows": [
        {
          "SalesTerritoryGroup": "Europe",
          "SalesTerritoryCountry": "France",
          "SalesTerritoryRegion": "France",
          "SalesAmount": 1491724.96
        },
        {
          "SalesTerritoryGroup": "Europe",
          "SalesTerritoryCountry": "Germany",
          "SalesTerritoryRegion": "Germany",
          "SalesAmount": 1679892.32
        },
        {
          "SalesTerritoryGroup": "Europe",
          "SalesTerritoryCountry": "United Kingdom",
          "SalesTerritoryRegion": "United Kingdom",
          "SalesAmount": 2019210.81
        }
      ],
      "row_count": 3,
      "status_code": 200,
      "elapsed_ms": 926,
      "response_bytes": 1840,
      "response_digest": "2fef18a3cfd5f1c6",
      "result_digest": "2fef18a3cfd5f1c6"
    },
    "cache_hit": true
  },
  "empty_reason": null,
  "rule": "probe_count_drives_nvac_ok"
}
```

## Query specification
```json
{
  "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
  "cube": "Adventure Works DW",
  "measures": [
    "SalesAmount"
  ],
  "group_by": [
    "Date.Calendar",
    "Date.Month",
    "Measures.SalesAmount",
    "Sales Territory.Sales Territory",
    "Sales Territory.Sales Territory Region"
  ],
  "slicers": {
    "Product.Product Category": "Bikes",
    "Sales Territory.Sales Territory Group": "Europe",
    "Date.Calendar Year": "2013"
  },
  "analytics": [],
  "axes": [
    {
      "axis": "COLUMNS",
      "expression": "{[Measures].[SalesAmount]}"
    },
    {
      "axis": "ROWS",
      "expression": ", CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members)"
    }
  ],
  "time_members": [],
  "window_start": "2013-01-01",
  "window_end": "2013-12-31",
  "calculated_members": [],
  "named_sets": [],
  "language": "mdx",
  "fingerprint": "2529fe2c3e67e832",
  "dw_id": "adventureworks_sql_direct",
  "dataset": null
}
```

## MDX
```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

## Execution Evidence

| Step | Query | MCAD | Path | Adapter | Physical | HTTP | Elapsed ms | Rows | Digest |
|---:|---|---|---|---|:---:|---:|---:|---:|---|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 69 | 36 | `e59b65443bfdd043` |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 45 | 36 | `714a213065b8b779` |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 47 | 36 | `129d653f0b971887` |
| 4 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | BLOCK | not_executed | — | false |  |  |  | `—` |
| 5 | AW_Q5_BLOCK_BAD_GRAIN_YEAR | BLOCK | not_executed | — | false |  |  |  | `—` |
| 6 | AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT | BLOCK | not_executed | — | false |  |  |  | `—` |

### Evidence summary

```json
{
  "contract_version": "mcad.execution_evidence_archive.v1",
  "evidence_rows": 6,
  "physical_execution_count": 3,
  "mcad_blocked_count": 3,
  "xmla_execution_count": 0,
  "direct_bi_execution_count": 3,
  "digest_count": 3,
  "execution_paths": {
    "sqlserver_direct": 3,
    "not_executed": 3
  },
  "adapters": {
    "adventureworks_direct": 3,
    "none": 3
  }
}
```
