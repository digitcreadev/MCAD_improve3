# MCAD Decision Detail — S_0001 / step 4

- Objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
- Decision: **BLOCK**
- Reason code: `BLOCK_OUT_OF_OBJECTIVE_SCOPE`
- Reason: Query conflicts with objective scope constraints (context/slicer/time incompatibility).
- φ: 0.0
- Δφ: 0.0

## Formal explanation
Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête. Décision BLOCK : le QP est valide mais son contexte est hors périmètre de l’objectif actif, donc Ceval(QP,O)=∅.

### Reasoning steps
- QP interroge le cube Adventure Works DW avec les mesures SalesAmount, le grain Date.Calendar, Date.Month, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region et les slicers {"Product.Product Category": "Accessories", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}.
- SAT(QP)=true : toutes les clauses formelles disponibles sont satisfaites (grain_ok, agg_ok, unit_ok, slc_ok, time_ok, nvac_ok).
- nvac_ok(QP)=true : méthode=hybrid_probe, estimated_cells=3, probe_attempted=True.
- Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête.
- Décision BLOCK : le QP est valide mais son contexte est hors périmètre de l’objectif actif, donc Ceval(QP,O)=∅.

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
    "Product.Product Category": "Accessories",
    "Sales Territory.Sales Territory Group": "Europe",
    "Date.Calendar Year": "2013"
  },
  "probe": {
    "probe_attempted": true,
    "probe_url": "http://mcad-proxy:9000/bi/nvac-probe",
    "elapsed_ms": 75,
    "non_empty": true,
    "count": 3,
    "probe_query": "SELECT {[Measures].[SalesAmount]} ON COLUMNS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
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
      "generated_sql": "SELECT TOP (200)\n       t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion,\n       CAST(SUM(f.SalesAmount) AS DECIMAL(18,2)) AS [SalesAmount]\nFROM dbo.FactInternetSales AS f\nJOIN dbo.DimDate AS d ON d.DateKey = f.OrderDateKey\nLEFT JOIN dbo.DimSalesTerritory AS t ON t.SalesTerritoryKey = f.SalesTerritoryKey\nLEFT JOIN dbo.DimProduct AS p ON p.ProductKey = f.ProductKey\nLEFT JOIN dbo.DimProductSubcategory AS ps ON ps.ProductSubcategoryKey = p.ProductSubcategoryKey\nLEFT JOIN dbo.DimProductCategory AS pc ON pc.ProductCategoryKey = ps.ProductCategoryKey\nWHERE f.SalesAmount IS NOT NULL AND d.CalendarYear = 2013 AND t.SalesTerritoryGroup = 'Europe' AND pc.EnglishProductCategoryName = 'Accessories'\nGROUP BY t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion\nORDER BY t.SalesTerritoryGroup, t.SalesTerritoryCountry, t.SalesTerritoryRegion;",
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
          "SalesAmount": 60599.81
        },
        {
          "SalesTerritoryGroup": "Europe",
          "SalesTerritoryCountry": "Germany",
          "SalesTerritoryRegion": "Germany",
          "SalesAmount": 59388.39
        },
        {
          "SalesTerritoryGroup": "Europe",
          "SalesTerritoryCountry": "United Kingdom",
          "SalesTerritoryRegion": "United Kingdom",
          "SalesAmount": 73967.62
        }
      ],
      "row_count": 3,
      "status_code": 200,
      "elapsed_ms": 72,
      "response_bytes": 1839,
      "response_digest": "ec2bf430015c9758",
      "result_digest": "ec2bf430015c9758"
    }
  },
  "empty_reason": null,
  "rule": "probe_count_drives_nvac_ok"
}
```

## Query specification
```json
{
  "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
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
    "Product.Product Category": "Accessories",
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
  "fingerprint": "ef766d4bc33e4201",
  "dw_id": "adventureworks_sql_direct",
  "dataset": null
}
```

## MDX
```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

## Execution Evidence

| Step | Query | MCAD | Path | Adapter | Physical | HTTP | Elapsed ms | Rows | Digest |
|---:|---|---|---|---|:---:|---:|---:|---:|---|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 47 | 36 | `27f82d304c05597c` |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 48 | 36 | `96c72ae5f5a72ca7` |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 54 | 36 | `0eb3f0bc9de12094` |
| 4 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | BLOCK | not_executed | — | false |  |  |  | `—` |

### Evidence summary

```json
{
  "contract_version": "mcad.execution_evidence_archive.v1",
  "evidence_rows": 4,
  "physical_execution_count": 3,
  "mcad_blocked_count": 1,
  "xmla_execution_count": 0,
  "direct_bi_execution_count": 3,
  "digest_count": 3,
  "execution_paths": {
    "sqlserver_direct": 3,
    "not_executed": 1
  },
  "adapters": {
    "adventureworks_direct": 3,
    "none": 1
  }
}
```
