# NH-R3 R3-C validation/calibration analysis

Status: **PASS_READY_FOR_R3D_STATIC_ACTIVATION**.

This directory is the frozen, non-confirmatory analysis of the 40-session
R3-C validation cohort. It is derived from the exact external C4 archive
`MCAD_R3_C4_VALIDATION_RESULTS_20260823T193237Z.tar.gz` with SHA-256
`116fc16926d7953cba90d89cee380ae494298b46327ebaf53a1152ec67711908`.

## Integrity

- analysis class: `VALIDATION_CALIBRATION_NONCONFIRMATORY`;
- 40 semantic sessions / 120 arm-runs / 2,880 candidate records;
- 1,920 gate evaluations;
- 1945 full backend executions;
- 80 fresh gated sessions;
- 7 fixed non-measured warm-up templates;
- 0 negative cgroup-delta arm-runs;
- frozen action authority preserved; live gate never relabels a frozen action;
- no effect-size tuning, scientific redesign, or confirmatory promotion.

## Arm means

| Arm | Wall ms | Completion ms | Backend requests | Full exec | NVAC probes | Response bytes | SQL CPU usec |
|---|---:|---:|---:|---:|---:|---:|---:|
| UNGATED | 1116.194 | 442.309 | 21.600 | 21.600 | 0.000 | 201170.0 | 1009585.0 |
| PERMISSIVE_GATED | 2678.297 | 1119.646 | 27.600 | 21.600 | 6.000 | 212203.9 | 1261604.7 |
| SAFE_PRUNING | 1826.214 | 902.790 | 11.425 | 5.425 | 6.000 | 61753.5 | 526180.8 |

## Primary descriptive contrast: SAFE vs PERMISSIVE

- wall time: -31.814% (40/40 lower);
- analytical-completion time: -19.368% (32/40 lower, 8/40 higher);
- all backend requests: -58.605% (40/40 lower);
- full backend executions: -74.884%;
- response bytes: -70.899%;
- SQL Server cgroup CPU: -58.293%;
- paired NVAC probes: equal in 40/40 sessions.

The wall/resource direction is also stable at the 20-stratum level:
SAFE has lower mean wall time in 20/20 strata and lower
mean completion time in 18/20 strata.

## Practical break-even contrast: SAFE vs UNGATED

- wall time: +63.611% (SAFE slower in 40/40);
- analytical-completion time: +104.108% (SAFE slower in 40/40);
- all backend requests: -47.106%;
- full backend executions: -74.884%;
- response bytes: -69.303%;
- SQL Server cgroup CPU: -47.881%.

Thus the validation preserves the same break-even tension as DEV: pruning saves
substantial backend work, bytes, and CPU, and it beats the same-gate permissive
comparator, but its gate/probe overhead still does not beat the ungated path in
elapsed time.

## DEV -> validation stability

The primary headline changes remain close to the DEV pilot:

- SAFE/PERMISSIVE wall reduction: -32.581% DEV -> -31.814% validation;
- SAFE/PERMISSIVE completion reduction: -20.680% DEV -> -19.368% validation;
- SAFE/PERMISSIVE backend-request reduction: -57.554% DEV -> -58.605% validation;
- SAFE/UNGATED wall overhead: +65.844% DEV -> +63.611% validation;
- SAFE/UNGATED completion overhead: +92.515% DEV -> +104.108% validation;
- SAFE/UNGATED backend-request reduction: -45.370% DEV -> -47.106% validation.

This is descriptive validation only. No p-values are computed.

## I/O note

Warm-cache cgroup I/O deltas are sparse/mostly zero. They are retained in the
frozen files but are not promoted to a strong disk-I/O saving claim.

## Readiness decision

R3-C is **closed without rerun**. No measurement-mechanics defect was found and
no effect-based tuning is permitted. The next station is:

`R3-D0_CONFIRMATORY_SQL_DIRECT_STATIC_ACTIVATION_NO_MEASUREMENT`

R3-D must use the already frozen confirmatory test cohort. R3-C results do not
change cohort membership, arm semantics, completion boundaries, or inclusion.
