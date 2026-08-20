# Scientific contract

Parent NH-R2 commit: `21ae791c850c019f07554e006ce9db82e1ac8769`

Frozen parent semantic digest: `0ddb625598790bef5b3046201680c7b2f540d335dfb8cd276ff52b34be47b4b8`
Frozen parent R2 freeze: `5c1b7e930e92ab11835e3d3cfba7af2a50e9ade281be2e29b04f7f11792bdb1e`
Frozen parent R2 results ZIP: `ffc5ddd93c9428715757c36bd987a87282cbe15e83a0e1557658fbda6c218bcb`

R3 preserves all NH-R1/NH-R2 semantic classifications. It does not retune
`SAFE_TO_PRUNE`, relabel held-out test rows, or infer human utility.

The primary R3 estimand is **net physical work avoided** under safe pruning,
conditional on the deterministic real-backend workload embedding.

All gate overhead is included. Any NVAC/backend probe performed to decide
whether a query should be suppressed is counted as backend work and treatment
overhead. Therefore "BLOCK/PRUNE" is not equated with zero backend cost.

Inadmissibility (`SAT_FALSE`) remains separate from strategic dispensability.

R3 claims must be limited to the measured backends, templates, and experimental
environment. The symbolic R2 evidence atoms are not asserted to be one-to-one
business equivalents of AdventureWorks cells.
