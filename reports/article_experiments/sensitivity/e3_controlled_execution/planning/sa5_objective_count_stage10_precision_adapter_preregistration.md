# SA5 objective-count Stage-10 precision adapter preregistration

Status: `preregistered_before_precision_analysis`

## Frozen precision contract

- Factor: `objective_count`
- Stage: `10`
- Structural-seed clusters: `10`
- Measurements per seed and canonical cell: `100`
- Bootstrap repetitions: `10000`
- Bootstrap seed: `20260728`
- Confidence level: `0.95`
- Median relative half-width target: `0.10`
- p95 relative half-width target: `0.15`

The adapter is deterministic and may only select the `measurement` phase and perform schema adaptation. It may not remove outliers, trim, winsorize, impute, aggregate, transform timing values, or choose thresholds from observed SA5 timing values.

Precision analysis, bootstrap execution, scientific interpretation, scientific freeze, and manuscript integration remain unauthorized.

