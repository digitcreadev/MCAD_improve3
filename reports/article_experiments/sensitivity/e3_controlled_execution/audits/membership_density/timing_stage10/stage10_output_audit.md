# SA4 membership-density Stage-10 output audit

- Status: `PASS`
- Successful replications: `10/10`
- Raw timing cells: `920`
- Warmups: `9,200`
- Measurements: `92,000`
- Total observations: `101,200`
- Functional mismatches: `0`
- Direct per-cell count balance: `true`

## Interpretation of `all_cells_exactly_balanced=false`

The field concerns measurement-order positions, not the number of observations assigned to each factor-level/query cell.

There are 100 measurement rounds and 92 order positions. Division gives quotient 1 and remainder 8. Each cell therefore occupies 84 positions once and 8 positions twice.

Exact full positional balance is impossible under the preregistered 100-round protocol. The reported `false` value is therefore expected and does not invalidate the timing evidence.

- Timing rerun required: `false`
- Precision analysis authorized: `false`
- Latency claims authorized: `false`

## Next stage

`prepare_membership_density_portfolio_analysis_adapter`
