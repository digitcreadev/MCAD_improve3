# R3-E14 D14 frozen XMLA result interpretation

## Boundary

- Source: exact D12-frozen D11 raw inference result bytes.
- No effect, p-value, confidence interval, or measurement was recomputed.
- Metric-specific XMLA replication claims are authorized.
- New global system-benefit, backend-equivalence, effect-homogeneity, and cross-backend synthesis claims are not authorized.

## Measurement integrity

- Integrity: **PASS_ALL_11_FROZEN_E6_INTEGRITY_REQUIREMENTS**
- Arm receipts: 900
- Semantic sessions: 300

## Primary metric-specific replication: SAFE_PRUNING - PERMISSIVE_GATED

| Metric | Status | Safe mean | Permissive mean | Mean diff | % change | 95% CI | Holm p | Safe lower/higher/equal |
|---|---|---:|---:|---:|---:|---|---:|---|
| `full_backend_execution_count` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 5.4 | 21.6 | -16.2 | -75% | [-16.3066667, -16.0933333] | 7.99992e-05 | 300/0/0 |
| `backend_request_count_including_gate_probes` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 11.4966667 | 27.6966667 | -16.2 | -58.4908% | [-16.3066667, -16.09] | 7.99992e-05 | 300/0/0 |
| `client_wall_ms` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 2991.13954 | 5484.80663 | -2493.66709 | -45.465% | [-2519.14638, -2469.57544] | 7.99992e-05 | 300/0/0 |
| `sqlserver_cpu_usage_usec_delta` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 1054876.4 | 3112025.16 | -2057148.76 | -66.1032% | [-2073075.16, -2041404.65] | 7.99992e-05 | 300/0/0 |
| `sqlserver_io_rbytes_delta` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 179200 | 416358.4 | -237158.4 | -56.9602% | [-276957.867, -193754.112] | 7.99992e-05 | 157/28/115 |
| `sqlserver_io_wbytes_delta` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 693186.56 | 1223191.89 | -530005.333 | -43.3297% | [-841742.037, -23389.0133] | 7.99992e-05 | 299/1/0 |
| `response_bytes` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 225339.547 | 810012.513 | -584672.967 | -72.1807% | [-588492.829, -580817.672] | 7.99992e-05 | 300/0/0 |
| `time_to_analytical_objective_completion_ms` | CONFIRMED_METRIC_SPECIFIC_REPLICATION | 1577.87608 | 2098.16438 | -520.288297 | -24.7973% | [-563.934414, -477.241028] | 7.99992e-05 | 251/49/0 |

- Metric-specific confirmations: **8/8**.
- This count is descriptive of the preregistered metric-specific decisions; it is **not** a new global system-benefit claim.

## Secondary break-even: SAFE_PRUNING - UNGATED_EXECUTE_ADMISSIBLE

Descriptive only; no confirmatory p-value or confirmatory claim is authorized.

| Metric | Direction | Safe mean | Ungated mean | Mean diff | % change | 95% CI | CI vs 0 |
|---|---|---:|---:|---:|---:|---|---|
| `full_backend_execution_count` | SAFE_LOWER_MEAN | 5.4 | 21.6 | -16.2 | -75% | [-16.3066667, -16.0933333] | ENTIRELY_BELOW_ZERO |
| `backend_request_count_including_gate_probes` | SAFE_LOWER_MEAN | 11.4966667 | 21.6 | -10.1033333 | -46.7747% | [-10.23, -9.97666667] | ENTIRELY_BELOW_ZERO |
| `client_wall_ms` | SAFE_LOWER_MEAN | 2991.13954 | 3180.11888 | -188.97934 | -5.94252% | [-211.41263, -165.738574] | ENTIRELY_BELOW_ZERO |
| `sqlserver_cpu_usage_usec_delta` | SAFE_LOWER_MEAN | 1054876.4 | 2713404.52 | -1658528.13 | -61.1235% | [-1674156.88, -1642716.41] | ENTIRELY_BELOW_ZERO |
| `sqlserver_io_rbytes_delta` | SAFE_LOWER_MEAN | 179200 | 303076.693 | -123876.693 | -40.8731% | [-152808.107, -87640.064] | ENTIRELY_BELOW_ZERO |
| `sqlserver_io_wbytes_delta` | SAFE_LOWER_MEAN | 693186.56 | 881660.587 | -188474.027 | -21.3772% | [-420224.043, 264453.248] | INCLUDES_ZERO |
| `response_bytes` | SAFE_LOWER_MEAN | 225339.547 | 779470.97 | -554131.423 | -71.0907% | [-557947.689, -550327.725] | ENTIRELY_BELOW_ZERO |
| `time_to_analytical_objective_completion_ms` | SAFE_HIGHER_MEAN | 1577.87608 | 1193.37118 | 384.504904 | 32.2201% | [362.649556, 406.244273] | ENTIRELY_ABOVE_ZERO |

## XMLA-specific resource diagnostics

Descriptive only; no confirmatory p-values or reduction claims are authorized.

| Metric | Comparator | Direction | Safe mean | Comparator mean | Mean diff | % change | 95% CI | CI vs 0 |
|---|---|---|---:|---:|---:|---:|---|---|
| `emondrian_cpu_usage_usec_delta` | PERMISSIVE_GATED | SAFE_LOWER_MEAN | 232480.627 | 509758.45 | -277277.823 | -54.394% | [-299054.769, -257295.901] | ENTIRELY_BELOW_ZERO |
| `emondrian_cpu_usage_usec_delta` | UNGATED_EXECUTE_ADMISSIBLE | SAFE_LOWER_MEAN | 232480.627 | 430633.023 | -198152.397 | -46.0142% | [-218764.406, -179020.253] | ENTIRELY_BELOW_ZERO |
| `emondrian_io_rbytes_delta` | PERMISSIVE_GATED | SAFE_LOWER_MEAN | 1693.01333 | 4874.24 | -3181.22667 | -65.2661% | [-10949.9733, 1488.21333] | INCLUDES_ZERO |
| `emondrian_io_rbytes_delta` | UNGATED_EXECUTE_ADMISSIBLE | SAFE_LOWER_MEAN | 1693.01333 | 2908.16 | -1215.14667 | -41.784% | [-6225.92, 2362.02667] | INCLUDES_ZERO |
| `emondrian_io_wbytes_delta` | PERMISSIVE_GATED | SAFE_HIGHER_MEAN | 1696221.87 | 1547223.04 | 148998.827 | 9.63008% | [-610099.883, 922219.179] | INCLUDES_ZERO |
| `emondrian_io_wbytes_delta` | UNGATED_EXECUTE_ADMISSIBLE | SAFE_HIGHER_MEAN | 1696221.87 | 266786.133 | 1429435.73 | 535.798% | [862425.429, 2053025.45] | ENTIRELY_ABOVE_ZERO |

## Claim boundary

- Metric-specific XMLA replication claim assignments: executed under D13.
- New global system-benefit claim: NOT AUTHORIZED / NOT EXECUTED.
- Backend equivalence claim: NOT AUTHORIZED / NOT EXECUTED.
- Effect homogeneity claim: NOT AUTHORIZED / NOT EXECUTED.
- Cross-backend effect-difference test or synthesis: NOT AUTHORIZED / NOT EXECUTED.
- Article claim integration: blocked pending D15 byte freeze.

