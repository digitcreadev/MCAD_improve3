# SA4 membership-density portfolio timing preregistration

- Status: `PASS`
- Structural seed clusters: `10`
- Density levels: `25, 50, 75, 100`
- Raw local positions per cluster: `23`
- Raw timing cells: `920`
- Formal measurements: `92,000`
- Portfolio measurements per cluster: `2,300`
- Inferential precision cells: `4`
- Bootstrap repetitions: `10,000`
- Median RHW target: `10%`
- p95 RHW target: `15%`
- Timing execution authorized: `false`

## Estimand

Density-level latency distribution over seed-specific canonical 23-query portfolios.

Local query positions are not interpreted as semantically identical across structural seeds.

## Analysis adapter

The immutable raw timing rows are copied into a derived analysis CSV. The original local step and query digest are retained as provenance, while the analyzer-facing `step_index` is set to the synthetic portfolio value `0`.

- Analyzer levels: `25,50,75,100`
- Analyzer steps: `0`
- Measurements per cluster: `2300`

## Next stage

`prepare_membership_density_timing_inputs`
