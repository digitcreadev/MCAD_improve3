# R3-E7 XMLA inference engine synthetic tests

R3-E7 implements the inference machinery frozen by R3-E6 without ingesting any measured XMLA receipt.

## What is implemented

- paired one-sided sign-flip test of the mean paired difference;
- Holm step-down adjustment;
- stratified percentile bootstrap of the paired mean difference;
- descriptive secondary paired summaries without confirmatory p-values.

Production defaults remain frozen at 100,000 sign-flip replicates and 20,000 bootstrap replicates.

## Synthetic-only test namespace

`MCAD-NH-R3-E7|SYNTHETIC_ONLY|45dc105e6e9c1ef800323af2a78987a2b8ddcf11|v1`

SHA-256:

`f37c7d43e21dd56bb46c563ce4c58d12cbac6880f7d9d1d2876c215ad5ab4666`

The synthetic stream is separate from every frozen production seed stream in R3-E6.

## Synthetic tests

The engine tests a 20-stratum x 15-session design with zero, strictly negative and strictly positive paired effects, exact Holm test vectors, deterministic random-stream replay, stratified bootstrap determinism and the absence of confirmatory p-values for secondary eMondrian diagnostics.

## Current boundary

No measured receipt can be supplied through the R3-E7 CLI. No bundle access, Docker, network/backend I/O, real p-value, real confidence interval, real effect analysis or measurement is permitted.

R3-D/D4 is not recomputed. The frozen D4 engine is only an algorithmic semantic reference.

## Next

R3-E8 freezes the pre-bundle completion/resume handoff. Runtime materialization still waits for verified recovery of the benabib2 bundle and the new-host E2 read-only revalidation.
