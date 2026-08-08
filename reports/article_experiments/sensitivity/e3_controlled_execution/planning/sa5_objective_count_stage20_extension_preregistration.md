# SA5 objective-count — Stage-20 extension preregistration

Stage-10 completed successfully as a scientific precision analysis, but the preregistered precision gate was not met. Stage-10 is immutable and must not be rerun.

## Stage-20 extension

- Reuse Stage-10 replications 0–9 without functional, timing, or precision rerun.
- Add replications 10–19 only, using the already-preregistered Stage-20 seed schedule whose first ten seeds exactly match the actual SA5 Stage-10 prefix.
- Preserve levels 1, 2, 5, 10, 20, 50 and steps 1–32.
- Preserve 10 warmups and 100 measurements per seed/level/step cell.
- Combined Stage-20 precision input: 20 structural-seed clusters and 384,000 measurement observations.
- Cluster bootstrap: 10,000 repetitions, seed 20260728, confidence 0.95.
- Median relative half-width target: 0.10; p95 target: 0.15.
- Gate: every canonical level-step cell must meet both targets.

## Stopping rule

- If Stage-20 passes: freeze SA5 and exit the campaign immediately.
- If Stage-20 fails: do not rerun Stage-20; persist it and preregister the already-supported Stage-30 extension once.
- Stage-30 is the maximum protocol stage. No Stage beyond 30 is authorized. After Stage-30, SA5 closes either with a precision PASS or with a documented precision-limit conclusion.
