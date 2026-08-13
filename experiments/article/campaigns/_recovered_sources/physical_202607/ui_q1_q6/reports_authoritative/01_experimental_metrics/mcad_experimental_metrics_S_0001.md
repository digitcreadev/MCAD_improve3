# MCAD Experimental Metrics — S_0001

- Objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
- Generated at: `2026-07-17T19:03:30.862305+00:00`
- Total queries: **6**
- ALLOW / BLOCK: **3 / 3**
- SAT true / false: **5 / 1**
- Final φ(t): **1.0**
- Completion rate: **1.000**
- Average eval time: **404.00 ms**

## Distributions

### Decision distribution
```json
{
  "ALLOW": 3,
  "BLOCK": 3
}
```

### Reason-code distribution
```json
{
  "ALLOW_NEW_TOTAL": 3,
  "BLOCK_OUT_OF_OBJECTIVE_SCOPE": 1,
  "BLOCK_GRAIN_MISMATCH": 1,
  "BLOCK_REDUNDANT_DPHI_ZERO": 1
}
```

### Failed SAT-clause distribution
```json
{
  "none": 5,
  "grain_ok": 1
}
```

### nvac method distribution
```json
{
  "hybrid_probe": 6
}
```

## Objective coverage

- Covered constraints: `aw_real_c1_sales_amount, aw_real_c2_total_product_cost, aw_real_c3_gross_margin`
- Remaining constraints: `—`

## Query-by-query metrics trace

| Step | SAT | Failed clauses | nvac | Ceval | Δφ | φ≤t | Decision | Reason |
|---:|:---:|---|---|---|---:|---:|---|---|
| 1 | true | — | hybrid_probe | aw_real_c1_sales_amount | 0.3333333333333333 | 0.3333333333333333 | ALLOW | ALLOW_NEW_TOTAL |
| 2 | true | — | hybrid_probe | aw_real_c2_total_product_cost | 0.3333333333333333 | 0.6666666666666666 | ALLOW | ALLOW_NEW_TOTAL |
| 3 | true | — | hybrid_probe | aw_real_c3_gross_margin | 0.3333333333333333 | 1.0 | ALLOW | ALLOW_NEW_TOTAL |
| 4 | true | — | hybrid_probe | ∅ | 0.0 | 1.0 | BLOCK | BLOCK_OUT_OF_OBJECTIVE_SCOPE |
| 5 | false | grain_ok | hybrid_probe | ∅ | 0.0 | 1.0 | BLOCK | BLOCK_GRAIN_MISMATCH |
| 6 | true | — | hybrid_probe | ∅ | 0.0 | 1.0 | BLOCK | BLOCK_REDUNDANT_DPHI_ZERO |