# Decision Log - A7 addendum

## D-A7-001 - Replace universal/internal necessity with component-sensitivity evidence
Only SAT, Real, and C_eval are manipulated by the existing targeted ablations. A7 therefore states that these links are behaviorally consequential under the controlled reference specification, not that every MCAD component is universally necessary.

## D-A7-002 - Reclassify robustness baselines as internal diagnostic reference policies
Naive, measure-overlap, and matched-random are benchmark-specific diagnostic policies, not reimplementations of neighboring published systems.

## D-A7-003 - Record no-Real / relaxed-C_eval aggregate non-identifiability
The two variants have identical aggregate false-ALLOW and non-contributive-execution rates in the exercised protocol. Distinct aggregate effect magnitudes are therefore not identified by this evidence.

## D-A7-004 - Align manuscript table and claim map
The RQ4 row of the evaluation-scope matrix and `CLAIM_EVIDENCE_MAP.csv` are updated so that traceability no longer carries the older joint-necessity formulation.

## D-A7-005 - No new science
A7 adds no experiment, session, query, timing observation, comparator implementation, or theorem; frozen data remain unchanged.
