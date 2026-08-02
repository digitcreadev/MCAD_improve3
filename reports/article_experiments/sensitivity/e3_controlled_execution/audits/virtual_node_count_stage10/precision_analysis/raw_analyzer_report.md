# SA3 stage-10 precision analysis

## Bootstrap contract

- Structural seed clusters: `10`
- Measurements per seed and cell: `100`
- Bootstrap repetitions: `10000`
- Confidence level: `95%`
- Median precision target: `10%`
- p95 precision target: `15%`

| Level | Step | Median | Median RHW | p95 | p95 RHW | Pass |
|---:|---:|---:|---:|---:|---:|---|
| 6 | 1 | 0.344749 | 0.79% | 0.613223 | 1.42% | True |
| 6 | 2 | 0.290751 | 1.26% | 0.546918 | 1.33% | True |
| 12 | 1 | 0.402110 | 1.10% | 0.727644 | 1.67% | True |
| 12 | 2 | 0.343171 | 2.09% | 0.655151 | 2.78% | True |
| 24 | 1 | 0.535223 | 1.42% | 0.975809 | 1.79% | True |
| 24 | 2 | 0.477994 | 1.32% | 0.928373 | 2.31% | True |

## Gate result

- All median targets met: `True`
- All p95 targets met: `True`
- Stage sufficient: `True`
- Extension required: `False`
- Next stage: `SA4_membership_density_design`

Scientific freeze and final latency claims remain disabled.
