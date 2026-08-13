# MCAD Scenario Contribution & Fusion Report

Generated from MCAD BI Decision Dashboard V9.4.8

## Scope
Effective session scenario: all executed queries in the active session, grouped by provenance. V9.2.14 uses strict scenario-row identity, execution-order capture, and History provenance hydration, and propagates the per-source execution order into every enriched query object. Scenario executions are bound to the exact UI row identity (scenario_instance_id, scenario_query_id, scenario_query_index); activity-proximity is used only for manual queries that match loaded scenario memberships.

## Session summary
- Session: S_0001
- Objective: O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN
- Total executed queries: 6
- Source scenarios involved: 1
- Ad hoc / unlinked queries: 0
- Final φ(t): 1.000
- Completion rate: 1.000
- Covered constraints: aw_real_c1_sales_amount, aw_real_c2_total_product_cost, aw_real_c3_gross_margin
- Remaining constraints: —

## Source contribution metrics

| Source | Type | Declared | Executed | Non-executed | ALLOW | BLOCK | Useful | Δφ total | Observed coverage | Intrinsic potential | Usefulness | Redundancy | Out-of-scope | Formal invalid | Efficiency | Avg eval ms | Interpretation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| adventureworks_sales_margin_territory_q1_q6 | source_scenario | 6 | 6 | 0 | 3 | 3 | 3 | 1.000 | 100.0% | 100.0% | 50.0% | 16.7% | 16.7% | 16.7% | 0.167 | 404.00 | fully helpful in observed order: covers all remaining target constraints |

## Global ordered effective scenario trace

| Step | Source | Query | SAT | Failed clauses | Ceval | Δφ | φ≤t | Decision | Reason | nvac |
|---:|---|---|:---:|---|---|---:|---:|---|---|---|
| 1 | adventureworks_sales_margin_territory_q1_q6 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | true | — | aw_real_c1_sales_amount | 0.333 | 0.333 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 2 | adventureworks_sales_margin_territory_q1_q6 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | true | — | aw_real_c2_total_product_cost | 0.333 | 0.667 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 3 | adventureworks_sales_margin_territory_q1_q6 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | true | — | aw_real_c3_gross_margin | 0.333 | 1.000 | ALLOW | ALLOW_NEW_TOTAL | hybrid_probe |
| 4 | adventureworks_sales_margin_territory_q1_q6 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | true | — | ∅ | 0.000 | 1.000 | BLOCK | BLOCK_OUT_OF_OBJECTIVE_SCOPE | hybrid_probe |
| 5 | adventureworks_sales_margin_territory_q1_q6 | AW_Q5_BLOCK_BAD_GRAIN_YEAR | false | grain_ok | ∅ | 0.000 | 1.000 | BLOCK | BLOCK_GRAIN_MISMATCH | hybrid_probe |
| 6 | adventureworks_sales_margin_territory_q1_q6 | AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT | true | — | ∅ | 0.000 | 1.000 | BLOCK | BLOCK_REDUNDANT_DPHI_ZERO | hybrid_probe |

## Fusion analysis

No pairwise fusion analysis available because fewer than two provenance groups were executed.

## Machine-readable JSON
```json
{
  "version": "mcad.scenario_contribution_report.v4",
  "is_authoritative": false,
  "generator": "ui_strict_row_identity_execution_order_reporter",
  "session_id": "S_0001",
  "objective_id": "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN",
  "total_queries": 6,
  "source_scenario_count": 1,
  "ad_hoc_query_count": 0,
  "total_constraints": 3,
  "final_phi": 1,
  "completion_rate": 1,
  "covered_constraints": [
    "aw_real_c1_sales_amount",
    "aw_real_c2_total_product_cost",
    "aw_real_c3_gross_margin"
  ],
  "remaining_constraints": [],
  "sources": [
    {
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "source_type": "source_scenario",
      "scenario_instance_id": "SSI_001",
      "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
      "scenario_name": "AdventureWorksDW Sales/Margin Territory validation",
      "declared_query_count": 6,
      "executed_rows_count": 6,
      "non_executed_query_count": 0,
      "metrics": {
        "query_count": 6,
        "allow_count": 3,
        "block_count": 3,
        "useful_queries": 3,
        "scenario_delta_phi": 1,
        "covered_constraints": [
          "aw_real_c1_sales_amount",
          "aw_real_c2_total_product_cost",
          "aw_real_c3_gross_margin"
        ],
        "covered_constraints_count": 3,
        "coverage_gain": 1,
        "intrinsic_potential_constraints": [
          "aw_real_c1_sales_amount",
          "aw_real_c2_total_product_cost",
          "aw_real_c3_gross_margin"
        ],
        "intrinsic_potential_count": 3,
        "intrinsic_potential_coverage": 1,
        "usefulness_rate": 0.5,
        "block_rate": 0.5,
        "redundancy_rate": 0.166667,
        "out_of_scope_rate": 0.166667,
        "formal_invalid_rate": 0.166667,
        "efficiency_score": 0.166667,
        "avg_eval_ms": 404,
        "reason_code_distribution": {
          "ALLOW_NEW_TOTAL": 3,
          "BLOCK_OUT_OF_OBJECTIVE_SCOPE": 1,
          "BLOCK_GRAIN_MISMATCH": 1,
          "BLOCK_REDUNDANT_DPHI_ZERO": 1
        },
        "decision_distribution": {
          "ALLOW": 3,
          "BLOCK": 3
        },
        "diagnostics": {
          "redundant": 1,
          "out_of_scope": 1,
          "non_target_measure": 0,
          "slicer_mismatch": 0,
          "empty_subspace": 0,
          "grain_mismatch": 1
        }
      },
      "interpretation": "fully helpful in observed order: covers all remaining target constraints",
      "enriched_queries": [
        {
          "id": "AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY",
          "label": "AW Q1 — ALLOW SalesAmount by month and territory",
          "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "ALLOW",
          "status": "done",
          "decision": "ALLOW",
          "delta_phi": 0.3333333333333333,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 0,
          "scenario_query_id": "AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 1,
          "last_execution_order_in_instance": 1,
          "reason_code": "ALLOW_NEW_TOTAL",
          "reason": "Contract-driven contribution: the QP matches pending constraint(s) of the active objective.",
          "formal_sat": true,
          "failed_sat_clauses": [],
          "passed_sat_clauses": [
            "grain_ok",
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [
            "aw_real_c1_sales_amount"
          ],
          "phi_leq_t": 0.3333333333333333,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 2208,
          "archive_step_index": 1,
          "declared_order": 1,
          "executed_order_in_source": 1,
          "execution_order_global": 1
        },
        {
          "id": "AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY",
          "label": "AW Q2 — ALLOW TotalProductCost by month and territory",
          "mdx": "SELECT {[Measures].[TotalProductCost]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "ALLOW",
          "status": "done",
          "decision": "ALLOW",
          "delta_phi": 0.3333333333333333,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 1,
          "scenario_query_id": "AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[TotalProductCost]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 2,
          "last_execution_order_in_instance": 2,
          "reason_code": "ALLOW_NEW_TOTAL",
          "reason": "Contract-driven contribution: the QP matches pending constraint(s) of the active objective.",
          "formal_sat": true,
          "failed_sat_clauses": [],
          "passed_sat_clauses": [
            "grain_ok",
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [
            "aw_real_c2_total_product_cost"
          ],
          "phi_leq_t": 0.6666666666666666,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 44,
          "archive_step_index": 2,
          "declared_order": 2,
          "executed_order_in_source": 2,
          "execution_order_global": 2
        },
        {
          "id": "AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY",
          "label": "AW Q3 — ALLOW GrossMargin by month and territory",
          "mdx": "SELECT {[Measures].[GrossMargin]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "ALLOW",
          "status": "done",
          "decision": "ALLOW",
          "delta_phi": 0.3333333333333333,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 2,
          "scenario_query_id": "AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[GrossMargin]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 3,
          "last_execution_order_in_instance": 3,
          "reason_code": "ALLOW_NEW_TOTAL",
          "reason": "Contract-driven contribution: the QP matches pending constraint(s) of the active objective.",
          "formal_sat": true,
          "failed_sat_clauses": [],
          "passed_sat_clauses": [
            "grain_ok",
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [
            "aw_real_c3_gross_margin"
          ],
          "phi_leq_t": 1,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 44,
          "archive_step_index": 3,
          "declared_order": 3,
          "executed_order_in_source": 3,
          "execution_order_global": 3
        },
        {
          "id": "AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY",
          "label": "AW Q4 — BLOCK Accessories instead of Bikes",
          "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "BLOCK",
          "status": "done",
          "decision": "BLOCK",
          "delta_phi": 0,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 3,
          "scenario_query_id": "AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Accessories], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 4,
          "last_execution_order_in_instance": 4,
          "reason_code": "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
          "reason": "Query conflicts with objective scope constraints (context/slicer/time incompatibility).",
          "formal_sat": true,
          "failed_sat_clauses": [],
          "passed_sat_clauses": [
            "grain_ok",
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [],
          "phi_leq_t": 1,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 81,
          "archive_step_index": 4,
          "declared_order": 4,
          "executed_order_in_source": 4,
          "execution_order_global": 4
        },
        {
          "id": "AW_Q5_BLOCK_BAD_GRAIN_YEAR",
          "label": "AW Q5 — BLOCK Year grain instead of Month grain",
          "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Calendar Year].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "BLOCK",
          "status": "done",
          "decision": "BLOCK",
          "delta_phi": 0,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 4,
          "scenario_query_id": "AW_Q5_BLOCK_BAD_GRAIN_YEAR",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Calendar Year].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 5,
          "last_execution_order_in_instance": 5,
          "reason_code": "BLOCK_GRAIN_MISMATCH",
          "reason": "Formal SAT clause failed: grain_ok",
          "formal_sat": false,
          "failed_sat_clauses": [
            "grain_ok"
          ],
          "passed_sat_clauses": [
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [],
          "phi_leq_t": 1,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 44,
          "archive_step_index": 5,
          "declared_order": 5,
          "executed_order_in_source": 5,
          "execution_order_global": 5
        },
        {
          "id": "AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT",
          "label": "AW Q6 — BLOCK redundant SalesAmount after Q1",
          "mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "sql": "",
          "query_type": "mdx",
          "expected_decision": "BLOCK",
          "status": "done",
          "decision": "BLOCK",
          "delta_phi": 0,
          "source": "scenario",
          "scenario_instance_id": "SSI_001",
          "source_scenario_id": "adventureworks_sales_margin_territory_q1_q6",
          "scenario_query_index": 5,
          "scenario_query_id": "AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT",
          "execution_mode": "scenario",
          "last_executed_mdx": "SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])",
          "last_execution_order_global": 6,
          "last_execution_order_in_instance": 6,
          "reason_code": "BLOCK_REDUNDANT_DPHI_ZERO",
          "reason": "Contract-driven redundancy: matched constraint(s) already covered in the current session.",
          "formal_sat": true,
          "failed_sat_clauses": [],
          "passed_sat_clauses": [
            "grain_ok",
            "agg_ok",
            "unit_ok",
            "slc_ok",
            "time_ok",
            "nvac_ok"
          ],
          "ceval": [],
          "phi_leq_t": 1,
          "nvac_ok": true,
          "nvac_method": "hybrid_probe",
          "nvac_estimated_cells": 3,
          "eval_ms": 3,
          "archive_step_index": 6,
          "declared_order": 6,
          "executed_order_in_source": 6,
          "execution_order_global": 6
        }
      ]
    }
  ],
  "ordered_trace": [
    {
      "step_index": 1,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 1,
      "declared_order": 1,
      "execution_order_global": 1,
      "query_id": "AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY",
      "query_label": "AW Q1 — ALLOW SalesAmount by month and territory",
      "formal_sat": true,
      "failed_sat_clauses": [],
      "ceval": [
        "aw_real_c1_sales_amount"
      ],
      "delta_phi": 0.3333333333333333,
      "phi_leq_t": 0.3333333333333333,
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "nvac_method": "hybrid_probe"
    },
    {
      "step_index": 2,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 2,
      "declared_order": 2,
      "execution_order_global": 2,
      "query_id": "AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY",
      "query_label": "AW Q2 — ALLOW TotalProductCost by month and territory",
      "formal_sat": true,
      "failed_sat_clauses": [],
      "ceval": [
        "aw_real_c2_total_product_cost"
      ],
      "delta_phi": 0.3333333333333333,
      "phi_leq_t": 0.6666666666666666,
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "nvac_method": "hybrid_probe"
    },
    {
      "step_index": 3,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 3,
      "declared_order": 3,
      "execution_order_global": 3,
      "query_id": "AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY",
      "query_label": "AW Q3 — ALLOW GrossMargin by month and territory",
      "formal_sat": true,
      "failed_sat_clauses": [],
      "ceval": [
        "aw_real_c3_gross_margin"
      ],
      "delta_phi": 0.3333333333333333,
      "phi_leq_t": 1,
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "nvac_method": "hybrid_probe"
    },
    {
      "step_index": 4,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 4,
      "declared_order": 4,
      "execution_order_global": 4,
      "query_id": "AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY",
      "query_label": "AW Q4 — BLOCK Accessories instead of Bikes",
      "formal_sat": true,
      "failed_sat_clauses": [],
      "ceval": [],
      "delta_phi": 0,
      "phi_leq_t": 1,
      "decision": "BLOCK",
      "reason_code": "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
      "nvac_method": "hybrid_probe"
    },
    {
      "step_index": 5,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 5,
      "declared_order": 5,
      "execution_order_global": 5,
      "query_id": "AW_Q5_BLOCK_BAD_GRAIN_YEAR",
      "query_label": "AW Q5 — BLOCK Year grain instead of Month grain",
      "formal_sat": false,
      "failed_sat_clauses": [
        "grain_ok"
      ],
      "ceval": [],
      "delta_phi": 0,
      "phi_leq_t": 1,
      "decision": "BLOCK",
      "reason_code": "BLOCK_GRAIN_MISMATCH",
      "nvac_method": "hybrid_probe"
    },
    {
      "step_index": 6,
      "source_key": "adventureworks_sales_margin_territory_q1_q6",
      "executed_order_in_source": 6,
      "declared_order": 6,
      "execution_order_global": 6,
      "query_id": "AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT",
      "query_label": "AW Q6 — BLOCK redundant SalesAmount after Q1",
      "formal_sat": true,
      "failed_sat_clauses": [],
      "ceval": [],
      "delta_phi": 0,
      "phi_leq_t": 1,
      "decision": "BLOCK",
      "reason_code": "BLOCK_REDUNDANT_DPHI_ZERO",
      "nvac_method": "hybrid_probe"
    }
  ],
  "fusion_analysis": []
}
```

## Execution Evidence by Scenario Step

| Step | Query | Decision | Path | Adapter | Physical | HTTP | Elapsed ms | Rows | Digest | XMLA |
|---:|---|---|---|---|:---:|---:|---:|---:|---|---|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 49 | 36 | `50ab82f87826fcad` |  |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 49 | 36 | `f3012474ae5c4255` |  |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ALLOW | sqlserver_direct | adventureworks_direct | true | 200 | 50 | 36 | `8a4cc85806217b90` |  |
| 4 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | BLOCK | not_executed | — | false |  |  |  | `—` |  |
| 5 | AW_Q5_BLOCK_BAD_GRAIN_YEAR | BLOCK | not_executed | — | false |  |  |  | `—` |  |
| 6 | AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT | BLOCK | not_executed | — | false |  |  |  | `—` |  |

### Evidence summary

```json
{
  "evidence_rows": 6,
  "execution_paths": {
    "sqlserver_direct": 3,
    "not_executed": 3
  }
}
```
