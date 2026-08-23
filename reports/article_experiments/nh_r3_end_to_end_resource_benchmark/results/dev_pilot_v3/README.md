# NH-R3 DEV pilot v3 - deterministic descriptive analysis

Source archive SHA-256: `7e0e863dc72200312827dced4425eee8105e5384dfca938f53aba8bc1ad761c6`  
Source archive size: `102767` bytes.

## Integrity

- 20 semantic sessions.
- 60 arm runs: 20 per arm.
- 1,440 candidate records.
- 960 gate evaluations.
- 40 gated arm runs with a non-empty fresh MCAD session.
- 0 negative cgroup deltas.
- Warm-up: 7 success receipts, 0 ambiguous/raw receipts.
- Confirmatory claims remain unauthorized.

## Headline descriptive comparison: SAFE_PRUNING vs PERMISSIVE_GATED

- Mean backend requests: 11.800 vs 27.800
  (-57.554% change; SAFE lower in
  20/20 paired sessions).
- Mean client wall time: 1978.394 ms vs
  2934.481 ms
  (-32.581% change; SAFE lower in
  20/20 paired sessions).
- Mean time to analytical objective completion:
  1056.303 ms vs
  1331.705 ms
  (-20.680% change; SAFE lower in
  16/20 paired sessions).

These are DEV-pilot descriptive results, not confirmatory inference. No p-values
or post-hoc confirmatory claims are produced by this checkpoint.

## Files

- `dev_pilot_arm_runs.csv`: one row per measured arm run.
- `dev_pilot_arm_summary.csv`: descriptive summaries by arm and metric.
- `dev_pilot_session_paired_metrics.csv`: paired per-session metric matrix.
- `dev_pilot_paired_contrasts.csv`: paired descriptive contrasts.
- `dev_pilot_analysis.json`: machine-readable audit and headline results.
