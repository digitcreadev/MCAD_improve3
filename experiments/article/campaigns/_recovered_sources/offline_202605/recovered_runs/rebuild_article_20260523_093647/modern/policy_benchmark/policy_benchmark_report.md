# MCAD policy benchmark report

- Scenario config: `backend/harness/scenarios.yaml`
- Policies: ablation_ceval_any_intersection, ablation_no_real, ablation_no_sat, baseline_measure_overlap, baseline_naive, baseline_random_matched, mcad

## Key takeaways

- MCAD mean final coverage: **0.333**
- MCAD mean AUC φ(t): **0.211**
- MCAD false allow rate: **0.000**
- MCAD false block rate: **0.000**
- MCAD latency p50/p95/p99 (ms): **0.208 / 0.371 / 0.612**

## Policy summary

|policy|mean_phi_final|mean_auc_phi|mean_false_allow_rate|mean_false_block_rate|mean_non_contrib_exec_rate|latency_p50_ms|latency_p95_ms|latency_p99_ms|
|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|0.333333|0.211111|0.1|0.0|0.1|0.20475|0.366863|0.679005|
|ablation_no_real|0.333333|0.211111|0.1|0.0|0.1|0.211|0.398682|0.675447|
|ablation_no_sat|0.333333|0.211111|0.0|0.0|0.0|0.25765|0.427415|0.684193|
|baseline_measure_overlap|0.333333|0.211111|0.566667|0.0|0.566667|0.0127|0.020503|0.026602|
|baseline_naive|0.333333|0.211111|0.666667|0.0|0.666667|0.001|0.0015|0.0021|
|baseline_random_matched|0.190667|0.121333|0.400667|0.142667|0.427667|0.0027|0.0042|0.006509|
|mcad|0.333333|0.211111|0.0|0.0|0.0|0.20845|0.371437|0.611519|