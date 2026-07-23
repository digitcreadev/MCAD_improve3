# MCAD V9.5.2 AdventureWorksDW Evidence Validation Pack

Generated at: `2026-06-20T00:16:02+0000`
Base URL: `http://127.0.0.1:9000`
Objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
Scenario: `adventureworks_sales_margin_territory_q1_q6`
DW: `adventureworks_sql_direct`

## Summary

- Overall status: **PASS**
- Passed steps: **6 / 6**
- Physical ALLOW executions: **3**
- BLOCK without physical execution: **3**
- Output directory: `/workspaces/MCAD_improve3/bi-stack/demo-evidence/runs/adventureworks_20260620_001416`

## Validation Steps

| # | Query | Pass | Expected | Decision | Reason | Physical | Path | Adapter | Rows | Digest |
|---:|---|---:|---|---|---|---:|---|---|---:|---|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ✅ | ALLOW | ALLOW | ALLOW_NEW_TOTAL | True | sqlserver_direct | adventureworks_direct | 36 | bff89680bed53988… |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ✅ | ALLOW | ALLOW | ALLOW_NEW_TOTAL | True | sqlserver_direct | adventureworks_direct | 36 | cebfa31bc504d467… |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ✅ | ALLOW | ALLOW | ALLOW_NEW_TOTAL | True | sqlserver_direct | adventureworks_direct | 36 | 782d819e63768dcf… |
| 4 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | ✅ | BLOCK | BLOCK | BLOCK_OUT_OF_OBJECTIVE_SCOPE | False | — | — | — | — |
| 5 | AW_Q5_BLOCK_BAD_GRAIN_YEAR | ✅ | BLOCK | BLOCK | BLOCK_GRAIN_MISMATCH | False | — | — | — | — |
| 6 | AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT | ✅ | BLOCK | BLOCK | BLOCK_REDUNDANT_DPHI_ZERO | False | — | — | — | — |

## Interpretation

This pack validates the real AdventureWorksDW SQL Server Direct path.
ALLOW queries must pass through MCAD before physical SQL Server execution.
BLOCK queries must remain non-physical (`physical_execution=false`).
The scenario length is read dynamically from the JSON file; it is not fixed to Q1-Q6.
