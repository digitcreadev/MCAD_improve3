# Expected invariants

- parent R1 exact SHA-256 and freeze exact SHA-256;
- local reference model byte-identical to R1;
- 1,200 sessions;
- 28,800 candidate positions per policy;
- 86,400 decision rows total;
- 1,200/1,200 SAFE vs PERMISSIVE objective preservation;
- zero false prune of immediate/deferred contributors;
- every SAT-valid invalid-contract candidate fails open rather than prunes;
- one replay row per SAFE `PRUNE`;
- resource claims stay `NOT_PROMOTED_AT_R2`.

Timing fields are environment-dependent and are not semantic gate invariants.

Reproducibility is separated into two layers:
- `semantic_digest.json` is environment-independent and must reproduce exactly for the frozen config/code;
- `environment.json`, runtime logs, and gate latency/CPU fields are provenance telemetry and may differ across Codespaces/machines.
