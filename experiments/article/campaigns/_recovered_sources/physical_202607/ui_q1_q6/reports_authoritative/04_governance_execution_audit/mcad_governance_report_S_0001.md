# MCAD Governance Report

- Session: S_0001
- Objective: O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN
- Data warehouse: adventureworks_sql_direct
- Total queries: 6
- ALLOW: 3
- BLOCK: 3
- Final cumulative φ≤t(O): 1

## Reason-code distribution

```json
{
  "ALLOW_NEW_TOTAL": 3,
  "BLOCK_OUT_OF_OBJECTIVE_SCOPE": 1,
  "BLOCK_GRAIN_MISMATCH": 1,
  "BLOCK_REDUNDANT_DPHI_ZERO": 1
}
```

## Ordered governance trace

| Step | Query | Decision | Reason | SAT | Local φ | Cumulative φ≤t | Δφ | Physical | Path | Adapter | Rows |
|---:|---|---|---|:---:|---:|---:|---:|:---:|---|---|---:|
| 1 | AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY | ALLOW | ALLOW_NEW_TOTAL | true | 0.3333333333333333 | 0.3333333333333333 | 0.3333333333333333 | true | sqlserver_direct | adventureworks_direct | 36 |
| 2 | AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY | ALLOW | ALLOW_NEW_TOTAL | true | 0.6666666666666666 | 0.6666666666666666 | 0.3333333333333333 | true | sqlserver_direct | adventureworks_direct | 36 |
| 3 | AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY | ALLOW | ALLOW_NEW_TOTAL | true | 1 | 1 | 0.3333333333333333 | true | sqlserver_direct | adventureworks_direct | 36 |
| 4 | AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY | BLOCK | BLOCK_OUT_OF_OBJECTIVE_SCOPE | true | 0 | 1 | 0 | false | — | — |  |
| 5 | AW_Q5_BLOCK_BAD_GRAIN_YEAR | BLOCK | BLOCK_GRAIN_MISMATCH | false | 1 | 1 | 0 | false | — | — |  |
| 6 | AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT | BLOCK | BLOCK_REDUNDANT_DPHI_ZERO | true | 1 | 1 | 0 | false | — | — |  |

## Machine-readable JSON

```json
{
  "version": "mcad.governance_report.download.v1",
  "generated_at_utc": "2026-07-17T19:07:08.240Z",
  "session_id": "S_0001",
  "objective_id": "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN",
  "dw_id": "adventureworks_sql_direct",
  "scope_query": "",
  "summary": {
    "total_queries": 6,
    "allow_count": 3,
    "block_count": 3,
    "other_count": 0,
    "reason_code_distribution": {
      "ALLOW_NEW_TOTAL": 3,
      "BLOCK_OUT_OF_OBJECTIVE_SCOPE": 1,
      "BLOCK_GRAIN_MISMATCH": 1,
      "BLOCK_REDUNDANT_DPHI_ZERO": 1
    },
    "final_cumulative_phi_leq_t": 1
  },
  "rows": [
    {
      "step_index": 1,
      "query_id": "AW_Q1_ALLOW_SALES_AMOUNT_MONTH_TERRITORY",
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "formal_sat": true,
      "local_phi": 0.3333333333333333,
      "cumulative_phi_leq_t": 0.3333333333333333,
      "delta_phi": 0.3333333333333333,
      "physical_execution": true,
      "execution_status": "EXECUTED",
      "execution_path": "sqlserver_direct",
      "adapter_id": "adventureworks_direct",
      "row_count": 36
    },
    {
      "step_index": 2,
      "query_id": "AW_Q2_ALLOW_TOTAL_PRODUCT_COST_MONTH_TERRITORY",
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "formal_sat": true,
      "local_phi": 0.6666666666666666,
      "cumulative_phi_leq_t": 0.6666666666666666,
      "delta_phi": 0.3333333333333333,
      "physical_execution": true,
      "execution_status": "EXECUTED",
      "execution_path": "sqlserver_direct",
      "adapter_id": "adventureworks_direct",
      "row_count": 36
    },
    {
      "step_index": 3,
      "query_id": "AW_Q3_ALLOW_GROSS_MARGIN_MONTH_TERRITORY",
      "decision": "ALLOW",
      "reason_code": "ALLOW_NEW_TOTAL",
      "formal_sat": true,
      "local_phi": 1,
      "cumulative_phi_leq_t": 1,
      "delta_phi": 0.3333333333333333,
      "physical_execution": true,
      "execution_status": "EXECUTED",
      "execution_path": "sqlserver_direct",
      "adapter_id": "adventureworks_direct",
      "row_count": 36
    },
    {
      "step_index": 4,
      "query_id": "AW_Q4_BLOCK_OUT_OF_OBJECTIVE_CATEGORY",
      "decision": "BLOCK",
      "reason_code": "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
      "formal_sat": true,
      "local_phi": 0,
      "cumulative_phi_leq_t": 1,
      "delta_phi": 0,
      "physical_execution": false,
      "execution_status": "MCAD_BLOCKED",
      "execution_path": "",
      "adapter_id": "",
      "row_count": ""
    },
    {
      "step_index": 5,
      "query_id": "AW_Q5_BLOCK_BAD_GRAIN_YEAR",
      "decision": "BLOCK",
      "reason_code": "BLOCK_GRAIN_MISMATCH",
      "formal_sat": false,
      "local_phi": 1,
      "cumulative_phi_leq_t": 1,
      "delta_phi": 0,
      "physical_execution": false,
      "execution_status": "MCAD_BLOCKED",
      "execution_path": "",
      "adapter_id": "",
      "row_count": ""
    },
    {
      "step_index": 6,
      "query_id": "AW_Q6_BLOCK_REDUNDANT_SALES_AMOUNT",
      "decision": "BLOCK",
      "reason_code": "BLOCK_REDUNDANT_DPHI_ZERO",
      "formal_sat": true,
      "local_phi": 1,
      "cumulative_phi_leq_t": 1,
      "delta_phi": 0,
      "physical_execution": false,
      "execution_status": "MCAD_BLOCKED",
      "execution_path": "",
      "adapter_id": "",
      "row_count": ""
    }
  ]
}
```
