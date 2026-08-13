# MCAD policy benchmark report

- Scenario config: `backend/harness/scenarios.yaml`
- Policies: ablation_ceval_any_intersection, ablation_no_real, ablation_no_sat, baseline_measure_overlap, baseline_naive, baseline_random_matched, mcad

## Key takeaways

- MCAD mean final coverage: **0.333**
- MCAD mean AUC φ(t): **0.211**
- MCAD false allow rate: **0.000**
- MCAD false block rate: **0.000**
- MCAD latency p50/p95/p99 (ms): **0.232 / 0.407 / 0.677**

## Policy summary

|policy|mean_phi_final|mean_auc_phi|mean_false_allow_rate|mean_false_block_rate|mean_non_contrib_exec_rate|latency_p50_ms|latency_p95_ms|latency_p99_ms|
|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|0.333333|0.211111|0.1|0.0|0.1|0.2303|0.423439|0.751799|
|ablation_no_real|0.333333|0.211111|0.1|0.0|0.1|0.24085|0.42257|0.740208|
|ablation_no_sat|0.333333|0.211111|0.0|0.0|0.0|0.28415|0.510105|0.719121|
|baseline_measure_overlap|0.333333|0.211111|0.566667|0.0|0.566667|0.0189|0.02781|0.035204|
|baseline_naive|0.333333|0.211111|0.666667|0.0|0.666667|0.0014|0.0022|0.002501|
|baseline_random_matched|0.190667|0.121333|0.400667|0.142667|0.427667|0.0039|0.0056|0.007006|
|mcad|0.333333|0.211111|0.0|0.0|0.0|0.2321|0.406844|0.677005|