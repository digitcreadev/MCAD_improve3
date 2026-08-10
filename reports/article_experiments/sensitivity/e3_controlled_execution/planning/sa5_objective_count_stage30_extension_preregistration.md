# SA5 objective-count — Stage-30 extension preregistration

Stage-20 completed exactly once and did not meet the preregistered precision target. Stage-20 is immutable and must not be rerun.

## Stage-30 extension

- Reuse replications 0–19 without functional, timing, or precision rerun.
- Add replications 20–29 only.
- The ten new structural seeds are frozen now using an outcome-independent SHA-256 derivation recorded in the JSON preregistration.
- Seed selection does not inspect Stage-20 cell-level precision outcomes.
- Preserve objective-count levels 1, 2, 5, 10, 20, 50.
- Preserve steps 1–32.
- Preserve 10 warmups and 100 measurements per seed/level/step cell.
- Combined Stage-30 precision input: 30 structural-seed clusters and 576,000 measurement observations.
- Cluster bootstrap: 10,000 repetitions, seed 20260728, confidence 0.95.
- Median relative half-width target: 0.10; p95 target: 0.15.
- Every canonical level-step cell must meet both targets.

## Final stopping rule

- If Stage-30 passes: freeze SA5 and exit the campaign.
- If Stage-30 does not meet the precision targets: persist the result and close SA5 with a documented precision-limit review.
- Stage-30 is the maximum protocol stage.
- No Stage-40 or other extension is authorized.

## Authorization

- This preregistration does not authorize Stage-30 execution.
- A separate explicit operator authorization is required after merge.
