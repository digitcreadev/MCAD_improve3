# Audit findings for the MCAD Q1–Q6 UI session

## Confirmed

- One session identifier (`S_0001`) and one objective identifier are used by
  all four report families.
- The canonical trace contains exactly six ordered steps.
- Q1, Q2 and Q3 are `ALLOW_NEW_TOTAL` and each adds one previously uncovered
  objective constraint.
- Cumulative coverage progresses `1/3 → 2/3 → 1`.
- Q4 is blocked as out of objective scope; Q5 is blocked because `grain_ok`
  fails; Q6 is blocked as redundant with zero marginal contribution.
- The three ALLOW queries are physically executed through SQL Server Direct,
  using `adventureworks_direct`, with 36 returned rows each.
- The three BLOCK queries are stopped before backend execution.
- Final completion rate and cumulative contribution are both 1.0.

## Curation cautions

- Use `step_index` as the authoritative order because Q4 was re-exported later.
- Do not interpret Q5/Q6 local `phi=1` as a new contribution; their
  `delta_phi_t=0` and cumulative `phi_leq_t=1` are the relevant values.
- Prefer formal objective constraint IDs over shorter graph aliases such as
  `c_sales` or `c_profit` when writing the article.
- The scenario contribution report is useful for ordered trace presentation,
  but it declares `is_authoritative=false`; numerical claims should be sourced
  from the formal and experimental reports.
- Q1/Q2 response digests differ between the early step detail downloads and
  the later authoritative report exports. Other execution fields agree. The
  package preserves both values rather than hiding the difference.
