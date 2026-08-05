# SA4 membership-density timing preregistration preflight

- Status: `PASS`
- Structural replications: `10`
- Density levels: `25, 50, 75, 100`
- Frozen functional steps: `952`
- Available workload lengths: `23 steps × 2`, `24 steps × 8`
- Balanced timing steps: `1..23`
- Timing cluster cells: `920`
- Precision cells: `92`
- Warmup observations: `9200`
- Measurement observations: `92000`
- Functional rerun required: `false`
- Timing execution authorized: `false`
- Latency claims authorized: `false`

## Required preparation

Create ten new timing-only workloads and execution specifications restricted to steps `1..23`. Existing functional outputs must remain immutable.

## Precision protocol proposed

- Cluster unit: structural seed
- Bootstrap repetitions: `10000`
- Confidence level: `95%`
- Median RHW target: `10%`
- p95 RHW target: `15%`

## Next stage

`formalize_membership_density_timing_preregistration`
