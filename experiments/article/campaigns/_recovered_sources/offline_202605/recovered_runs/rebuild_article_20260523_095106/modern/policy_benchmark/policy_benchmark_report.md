# MCAD policy benchmark report

- Scenario config: `backend/harness/scenarios.yaml`
- Policies: ablation_ceval_any_intersection, ablation_no_real, ablation_no_sat, baseline_measure_overlap, baseline_naive, baseline_random_matched, mcad

## Key takeaways

- MCAD mean final coverage: **0.333**
- MCAD mean AUC φ(t): **0.211**
- MCAD false allow rate: **0.000**
- MCAD false block rate: **0.000**
- MCAD latency p50/p95/p99 (ms): **0.207 / 0.392 / 0.669**

## Policy summary

|policy|mean_phi_final|mean_auc_phi|mean_false_allow_rate|mean_false_block_rate|mean_non_contrib_exec_rate|latency_p50_ms|latency_p95_ms|latency_p99_ms|
|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|0.333333|0.211111|0.1|0.0|0.1|0.20405|0.39368|0.680902|
|ablation_no_real|0.333333|0.211111|0.1|0.0|0.1|0.21455|0.42038|0.703575|
|ablation_no_sat|0.333333|0.211111|0.0|0.0|0.0|0.25905|0.467811|0.692342|
|baseline_measure_overlap|0.333333|0.211111|0.566667|0.0|0.566667|0.0129|0.02149|0.030387|
|baseline_naive|0.333333|0.211111|0.666667|0.0|0.666667|0.0009|0.0013|0.001779|
|baseline_random_matched|0.190667|0.121333|0.400667|0.142667|0.427667|0.0025|0.0041|0.006935|
|mcad|0.333333|0.211111|0.0|0.0|0.0|0.20665|0.391812|0.669298|