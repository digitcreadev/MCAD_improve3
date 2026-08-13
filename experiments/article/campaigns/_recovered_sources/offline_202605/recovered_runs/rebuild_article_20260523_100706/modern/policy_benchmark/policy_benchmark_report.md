# MCAD policy benchmark report

- Scenario config: `backend/harness/scenarios.yaml`
- Policies: ablation_ceval_any_intersection, ablation_no_real, ablation_no_sat, baseline_measure_overlap, baseline_naive, baseline_random_matched, mcad

## Key takeaways

- MCAD mean final coverage: **0.333**
- MCAD mean AUC φ(t): **0.211**
- MCAD false allow rate: **0.000**
- MCAD false block rate: **0.000**
- MCAD latency p50/p95/p99 (ms): **0.247 / 0.621 / 0.696**

## Policy summary

|policy|mean_phi_final|mean_auc_phi|mean_false_allow_rate|mean_false_block_rate|mean_non_contrib_exec_rate|latency_p50_ms|latency_p95_ms|latency_p99_ms|
|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|0.333333|0.211111|0.1|0.0|0.1|0.2125|0.61596|0.86882|
|ablation_no_real|0.333333|0.211111|0.1|0.0|0.1|0.25355|0.641944|0.700944|
|ablation_no_sat|0.333333|0.211111|0.0|0.0|0.0|0.2686|0.639114|0.759919|
|baseline_measure_overlap|0.333333|0.211111|0.566667|0.0|0.566667|0.0131|0.023204|0.029203|
|baseline_naive|0.333333|0.211111|0.666667|0.0|0.666667|0.0009|0.0015|0.0019|
|baseline_random_matched|0.190667|0.121333|0.400667|0.142667|0.427667|0.0027|0.0045|0.006106|
|mcad|0.333333|0.211111|0.0|0.0|0.0|0.24735|0.621491|0.696226|