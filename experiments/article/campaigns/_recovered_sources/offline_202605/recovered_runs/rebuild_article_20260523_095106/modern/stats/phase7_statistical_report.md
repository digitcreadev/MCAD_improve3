# Phase 7 statistical analysis report

This report provides bootstrap confidence intervals, paired sign-flip tests, and ablation sensitivity summaries based on the current MCAD benchmark outputs.

## Policy-level confidence intervals

|policy|n_sessions|phi_final_mean|phi_final_ci_low|phi_final_ci_high|auc_phi_mean|auc_phi_ci_low|auc_phi_ci_high|false_allow_rate_mean|false_allow_rate_ci_low|false_allow_rate_ci_high|
|---|---|---|---|---|---|---|---|---|---|---|
|ablation_ceval_any_intersection|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.111111|0.082222|0.142222|
|ablation_no_real|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.111111|0.082222|0.142222|
|ablation_no_sat|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.0|0.0|0.0|
|baseline_measure_overlap|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.592593|0.548889|0.637037|
|baseline_naive|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.703704|0.663704|0.744444|
|baseline_random_matched|450|0.180741|0.153333|0.20963|0.116543|0.097284|0.136296|0.411111|0.366667|0.457037|
|mcad|450|0.296296|0.255556|0.336296|0.191358|0.164198|0.218025|0.0|0.0|0.0|

## Paired policy comparisons (MCAD advantage)

|comparator|metric|n_pairs|mcad_advantage_mean|ci_low|ci_high|p_value_sign_flip|dominance_rate|
|---|---|---|---|---|---|---|---|
|baseline_naive|phi_final|450|0.0|0.0|0.0|1.0|0.5|
|baseline_naive|auc_phi|450|0.0|0.0|0.0|1.0|0.5|
|baseline_naive|false_allow_rate|450|0.703704|0.663704|0.744444|0.0002|0.861111|
|baseline_naive|non_contrib_exec_rate|450|0.703704|0.663704|0.744444|0.0002|0.861111|
|baseline_measure_overlap|phi_final|450|0.0|0.0|0.0|1.0|0.5|
|baseline_measure_overlap|auc_phi|450|0.0|0.0|0.0|1.0|0.5|
|baseline_measure_overlap|false_allow_rate|450|0.592593|0.548889|0.637037|0.0002|0.805556|
|baseline_measure_overlap|non_contrib_exec_rate|450|0.592593|0.548889|0.637037|0.0002|0.805556|
|baseline_random_matched|phi_final|450|0.115556|0.094815|0.137037|0.0002|0.617778|
|baseline_random_matched|auc_phi|450|0.074815|0.060741|0.089136|0.0002|0.617778|
|baseline_random_matched|false_allow_rate|450|0.411111|0.366667|0.457037|0.0002|0.717778|
|baseline_random_matched|non_contrib_exec_rate|450|0.424444|0.37963|0.470741|0.0002|0.717778|
|ablation_no_sat|phi_final|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_sat|auc_phi|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_sat|false_allow_rate|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_sat|non_contrib_exec_rate|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_real|phi_final|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_real|auc_phi|450|0.0|0.0|0.0|1.0|0.5|
|ablation_no_real|false_allow_rate|450|0.111111|0.082222|0.142222|0.0002|0.555556|
|ablation_no_real|non_contrib_exec_rate|450|0.111111|0.082222|0.142222|0.0002|0.555556|
|ablation_ceval_any_intersection|phi_final|450|0.0|0.0|0.0|1.0|0.5|
|ablation_ceval_any_intersection|auc_phi|450|0.0|0.0|0.0|1.0|0.5|
|ablation_ceval_any_intersection|false_allow_rate|450|0.111111|0.082222|0.142222|0.0002|0.555556|
|ablation_ceval_any_intersection|non_contrib_exec_rate|450|0.111111|0.082222|0.142222|0.0002|0.555556|

## Ablation sensitivity (robustness campaign)

|ablation|metric|mcad_advantage_mean|ci_low|ci_high|dominance_rate|
|---|---|---|---|---|---|
|ablation_no_sat|false_allow_rate|0.041667|0.032639|0.050695|0.625|
|ablation_no_sat|auc_phi|0.0|0.0|0.0|0.5|
|ablation_no_sat|false_block_rate|0.0|0.0|0.0|0.5|
|ablation_no_real|false_allow_rate|0.08125|0.070417|0.092292|0.75|
|ablation_no_real|auc_phi|0.0|0.0|0.0|0.5|
|ablation_no_real|false_block_rate|0.0|0.0|0.0|0.5|
|ablation_ceval_any_intersection|false_allow_rate|0.08125|0.070417|0.092292|0.75|
|ablation_ceval_any_intersection|auc_phi|0.0|0.0|0.0|0.5|
|ablation_ceval_any_intersection|false_block_rate|0.0|0.0|0.0|0.5|