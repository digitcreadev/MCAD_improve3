# SA4 membership-density Stage-10 portfolio precision decision

- Status: `pass`
- Factor: `membership_density`
- Successful bootstrap executions: `1`
- Measurements: `92,000`
- Structural clusters: `10`
- Inferential cells: `4`
- Bootstrap repetitions: `10,000`
- All median RHW targets met: `true`
- All p95 RHW targets met: `true`
- All precision targets met: `true`
- Failing cells: `0`
- Stage-10 sufficient: `true`
- Stage-20 extension required: `false`

## Canonical cell results

| Density | Median ms | Median RHW | Median pass | p95 ms | p95 RHW | p95 pass |
|---:|---:|---:|:---:|---:|---:|:---:|
| 25 | n/a | 0.006101 | true | n/a | 0.023701 | true |
| 50 | n/a | 0.006567 | true | n/a | 0.018646 | true |
| 75 | n/a | 0.006595 | true | n/a | 0.015337 | true |
| 100 | n/a | 0.006613 | true | n/a | 0.019849 | true |

## Raw analyzer interpretation

The raw analyzer label `constraint_count` and its raw next-stage value are retained for provenance but are non-authoritative.

## Next stage

`prepare_membership_density_stage10_freeze`
