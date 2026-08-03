# SA4 membership-density non-mutating precision adapter preregistration

- Status: `preregistered`
- Factor: `membership_density`
- Structural replications: `10`
- Density levels: `25, 50, 75, 100`
- Synthetic analyzer step: `0`
- Timing-report cells: `40`
- Inferential cells: `4`
- Measurements per structural cluster: `2,300`
- Measurements per inferential cell: `23,000`
- Total measurements: `92,000`

## Non-mutating strategy

The raw timing CSV files and the preregistered precision analyzer remain byte-for-byte unchanged.

A measurement-only observation adapter maps the 23 seed-specific queries to synthetic analyzer `step_index=0` while preserving row-level source provenance.

The raw analyzer label `constraint_count` and its raw next-stage value are explicitly non-authoritative.

A canonical decision wrapper will publish the scientific factor as `membership_density`.

## Authorization

- Adapter-input materialization: `authorized`
- Precision-analyzer execution: `not authorized`
- Stage-20 execution: `not authorized`
- Latency claims: `not authorized`

## Next stage

`materialize_membership_density_non_mutating_precision_adapter_inputs`
