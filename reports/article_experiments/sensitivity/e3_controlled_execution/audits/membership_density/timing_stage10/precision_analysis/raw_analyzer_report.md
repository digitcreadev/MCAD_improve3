# SA3 stage-10 precision analysis

## Bootstrap contract

- Structural seed clusters: `10`
- Measurements per seed and cell: `2300`
- Bootstrap repetitions: `10000`
- Confidence level: `95%`
- Median precision target: `10%`
- p95 precision target: `15%`

| Level | Step | Median | Median RHW | p95 | p95 RHW | Pass |
|---:|---:|---:|---:|---:|---:|---|
| 25 | 0 | 0.456054 | 0.61% | 0.897460 | 2.37% | True |
| 50 | 0 | 0.459504 | 0.66% | 0.907403 | 1.86% | True |
| 75 | 0 | 0.462777 | 0.66% | 0.910817 | 1.53% | True |
| 100 | 0 | 0.465190 | 0.66% | 0.916927 | 1.98% | True |

## Gate result

- All median targets met: `True`
- All p95 targets met: `True`
- Stage sufficient: `True`
- Extension required: `False`
- Next stage: `SA4_membership_density_design`

Scientific freeze and final latency claims remain disabled.
