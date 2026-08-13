# MCAD policy benchmark report

- Scenario config: `backend/harness/scenarios.yaml`
- Policies: ablation_ceval_any_intersection, ablation_no_real, ablation_no_sat, baseline_measure_overlap, baseline_naive, baseline_random_matched, mcad

## Key takeaways

- MCAD mean final coverage: **0.333**
- MCAD mean AUC φ(t): **0.211**
- MCAD false allow rate: **0.000**
- MCAD false block rate: **0.000**
- MCAD latency p50/p95/p99 (ms): **0.247 / 0.563 / 0.676**

## Policy summary

|policy|mean_phi_final|mean_auc_phi|mean_false_allow_rate|mean_false_block_rate|mean_non_contrib_exec_rate|latency_p50_ms|latency_p95_ms|latency_p99_ms|
|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|0.333333|0.211111|0.1|0.0|0.1|0.24415|0.591634|0.819054|
|ablation_no_real|0.333333|0.211111|0.1|0.0|0.1|0.2454|0.617401|0.734099|
|ablation_no_sat|0.333333|0.211111|0.0|0.0|0.0|0.27125|0.586568|0.75702|
|baseline_measure_overlap|0.333333|0.211111|0.566667|0.0|0.566667|0.0134|0.022803|0.033309|
|baseline_naive|0.333333|0.211111|0.666667|0.0|0.666667|0.0009|0.0015|0.001978|
|baseline_random_matched|0.190667|0.121333|0.400667|0.142667|0.427667|0.0027|0.0045|0.009774|
|mcad|0.333333|0.211111|0.0|0.0|0.0|0.2471|0.562642|0.676099|