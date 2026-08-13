# MCAD Q1–Q6 canonical UI evidence package

## Scope

This package curates the real UI session `S_0001` for objective
`O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN` on `AdventureWorksDW`
through `adventureworks_sql_direct` / `adventureworks_direct`.

The canonical decision order is the explicit `step_index` Q1–Q6, not the
filesystem timestamps. Q4 was re-opened/re-exported after later steps for UI
presentation correction, so timestamps are not strictly monotonic.

## Source hierarchy

1. **Authoritative numerical sources**
   - `mcad_experimental_metrics_S_0001.json`
   - `mcad_formal_session_report_S_0001.json`
2. **Execution/governance source**
   - `mcad_governance_report_S_0001.json`
3. **Per-step explanation sources**
   - `mcad_decision_detail_step_1.json` … `step_6.json`
4. **Supplementary ordering/fusion source**
   - scenario contribution report (`is_authoritative=false`)
5. **Presentation sources**
   - UI screenshots and `Q1-Q6 Experiment.pdf`

## Canonical outcome

- Queries: 6
- ALLOW: 3
- BLOCK: 3
- Physically executed: 3
- Blocked before execution: 3
- Objective constraints: 3
- Covered constraints: 3
- Final cumulative contribution: 1.0
- Completion rate: 1.0
- Remaining constraints: 0

## Article-use rules

- Use cumulative `phi_leq_t` and `delta_phi_t` for the session trajectory.
- Do not use the local `phi` field of Q4–Q6 as the session progress value.
- Use the canonical constraint identifiers from the formal report:
  `aw_real_c1_sales_amount`, `aw_real_c2_total_product_cost`,
  `aw_real_c3_gross_margin`.
- Treat screenshots as visual evidence, while numerical claims must cite the
  exported JSON/CSV reports.
- Report-level Q1/Q2 response digests differ from the earlier per-step detail
  exports, although row count, response size, backend, adapter, status and
  execution path agree. For article tables, use the later authoritative report
  digests; retain both versions in the raw package for auditability.
- This package demonstrates system-level explainability and auditability. It
  does not by itself constitute a human-subject evaluation of explanation
  comprehension.
