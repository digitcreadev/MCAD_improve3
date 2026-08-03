# SA4 membership-density timing-input materialization

- Status: `PASS`
- Derived workloads: `10`
- Derived execution specs: `10`
- Selected steps per workload: `23`
- Selected canonical instances: `40`
- Raw timing cells: `920`
- Planned warmup observations: `9,200`
- Planned measurements: `92,000`
- Excluded workload-step occurrences: `8`
- Functional source files modified: `false`
- Timing directories created: `false`
- Timing execution authorized: `false`

## Materialization rule

Each derived workload preserves its canonical payload while retaining local positions `Q001..Q023` only.

Each derived execution specification preserves the original campaign and instance selection, but references the new balanced workload and a dedicated future timing-output directory.

## Next stage

`audit_and_authorize_membership_density_timing_execution`
