# MCAD Formal Session Report — S_0001

- Objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
- Generated at: `2026-07-17T19:05:33.021431+00:00`
- Total queries: **6**
- ALLOW / BLOCK: **3 / 3**
- Completion rate: **1.000**
- φ(t): **1.0**

## Objective coverage

- Covered constraints: `aw_real_c1_sales_amount, aw_real_c2_total_product_cost, aw_real_c3_gross_margin`
- Remaining constraints: `—`

## Reason-code distribution

```json
{
  "ALLOW_NEW_TOTAL": 3,
  "BLOCK_OUT_OF_OBJECTIVE_SCOPE": 1,
  "BLOCK_GRAIN_MISMATCH": 1,
  "BLOCK_REDUNDANT_DPHI_ZERO": 1
}
```

## Formal trace table

| Step | SAT(QP) | Failed clauses | Ceval(QP,O) | Δφ | Decision | Reason | nvac method |
|---:|:---:|---|---|---:|---|---|---|
| 1 | true | — | aw_real_c1_sales_amount | 0.3333333333333333 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 2 | true | — | aw_real_c2_total_product_cost | 0.3333333333333333 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 3 | true | — | aw_real_c3_gross_margin | 0.3333333333333333 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 4 | true | — | ∅ | 0.0 | BLOCK | BLOCK_OUT_OF_OBJECTIVE_SCOPE | hybrid_probe |
| 5 | false | grain_ok | ∅ | 0.0 | BLOCK | BLOCK_GRAIN_MISMATCH | hybrid_probe |
| 6 | true | — | ∅ | 0.0 | BLOCK | BLOCK_REDUNDANT_DPHI_ZERO | hybrid_probe |

## Per-query formal explanations

### Step 1 — ALLOW / ALLOW_NEW_TOTAL

Ceval(QP,O) contient 1 contrainte(s) calculable(s) : aw_real_c1_sales_amount. Décision ALLOW : Δφ=0.3333333333333333 indique un gain marginal positif pour la session.

- Measures: `SalesAmount`
- Grain: `Date.Calendar, Date.Month, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

### Step 2 — ALLOW / ALLOW_NEW_TOTAL

Ceval(QP,O) contient 1 contrainte(s) calculable(s) : aw_real_c2_total_product_cost. Décision ALLOW : Δφ=0.3333333333333333 indique un gain marginal positif pour la session.

- Measures: `TotalProductCost`
- Grain: `Date.Calendar, Date.Month, Measures.TotalProductCost, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[TotalProductCost]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

### Step 3 — ALLOW / ALLOW_NEW_TOTAL

Ceval(QP,O) contient 1 contrainte(s) calculable(s) : aw_real_c3_gross_margin. Décision ALLOW : Δφ=0.3333333333333333 indique un gain marginal positif pour la session.

- Measures: `GrossMargin`
- Grain: `Date.Calendar, Date.Month, Measures.GrossMargin, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[GrossMargin]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

### Step 4 — BLOCK / BLOCK_OUT_OF_OBJECTIVE_SCOPE

Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête. Décision BLOCK : le QP est valide mais son contexte est hors périmètre de l’objectif actif, donc Ceval(QP,O)=∅.

- Measures: `SalesAmount`
- Grain: `Date.Calendar, Date.Month, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Accessories", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

### Step 5 — BLOCK / BLOCK_GRAIN_MISMATCH

nvac_ok(QP)=true : méthode=hybrid_probe, estimated_cells=3, probe_attempted=True. Comme SAT(QP)=false, MCAD bloque la requête avant toute contribution décisionnelle.

- Measures: `SalesAmount`
- Grain: `Date.Calendar, Date.Calendar Year, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Calendar Year].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

### Step 6 — BLOCK / BLOCK_REDUNDANT_DPHI_ZERO

Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête. Décision BLOCK : la requête est redondante, les contraintes correspondantes ont déjà été couvertes dans la session, donc Δφ=0.

- Measures: `SalesAmount`
- Grain: `Date.Calendar, Date.Month, Measures.SalesAmount, Sales Territory.Sales Territory, Sales Territory.Sales Territory Region`
- Slicers: `{"Product.Product Category": "Bikes", "Sales Territory.Sales Territory Group": "Europe", "Date.Calendar Year": "2013"}`
- nvac_ok: `True` via `hybrid_probe`

```mdx
SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])
```

## Execution Evidence for Metrics

| Step | Query | MCAD | Path | Adapter | Physical | HTTP | Elapsed ms | Rows | Digest |
|---:|---|---|---|---|:---:|---:|---:|---:|---|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 49 | 36 | `50ab82f87826fcad` |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 49 | 36 | `f3012474ae5c4255` |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 50 | 36 | `8a4cc85806217b90` |
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
