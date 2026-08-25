# R3-E6 XMLA replication inference protocol

This checkpoint is frozen before any measured XMLA execution.

## Primary XMLA replication family

The same eight R3 primary metrics are evaluated on the frozen 300-session / 900-arm-run XMLA replication cohort. The primary comparison is `SAFE_PRUNING - PERMISSIVE_GATED`; lower is better for every shared primary metric.

- one-sided paired sign-flip test;
- 100,000 Monte Carlo permutations;
- Holm step-down familywise correction over all eight metrics at alpha = 0.05;
- 95% stratified percentile bootstrap confidence interval with 20,000 replicates;
- equal session weighting across the 20 x 15 frozen strata;
- metric-specific replication claims only;
- no global system-benefit claim.

## Secondary analyses

`SAFE_PRUNING - UNGATED_EXECUTE_ADMISSIBLE` remains secondary/descriptive. The three eMondrian-specific resource metrics remain secondary attribution diagnostics only; no confirmatory p-values are authorized for them.

## Integrity boundary

Exactly 900 future arm receipts are required. Negative cgroup deltas are never clamped. Partial or mechanically invalid attempts are frozen for audit and cannot be rerun automatically or because of observed effects.

## Cross-backend interpretation

A metric can later be described as confirmed on both SQL Direct and XMLA only if the already-frozen D4 claim for that metric is confirmed and the XMLA metric passes the complete eight-metric XMLA Holm family. This does not authorize a global system-benefit, backend-equivalence, effect-homogeneity, or cross-backend difference claim.

## Randomness

All future permutation/bootstrap streams are frozen now from the outcome-independent namespace:

`MCAD-NH-R3-E6|XMLA_REPLICATION|effd3a0677bc943f51faf87f4808743136ba027b|v1`

SHA-256:

`b3bcfe0ff7bbc0b2a7fb786f76dcdb9973de72380ff55f312b0fa172ed2475e5`

See `config/r3_e6_xmla_replication_seed_manifest.json` for per-metric seeds.

## Current execution boundary

This is a static protocol freeze only: no bundle access, Docker, backend query, measured receipt ingestion, p-value calculation on real data, confidence interval calculation on real data, or measurement.
