# MCAD — Artifact authority policy

This policy defines the precedence for every numerical value, table, figure,
experimental conclusion, and manuscript claim.

## Authority order

1. canonical or frozen primary result;
2. recovered historical primary result explicitly qualified for use;
3. normalized publication-ready dataset derived from (1) or (2);
4. authorized statistic derived from that dataset;
5. regenerated table or figure;
6. manuscript claim;
7. historical editorial artifact or screenshot.

A lower-level artifact never silently overrides a higher-level source.

## Artifact statuses

- `SOURCE_BACKED`: directly traceable to primary/frozen evidence.
- `REGENERATE_FROM_PRIMARY`: retain the design, regenerate the final artifact.
- `HISTORICAL_EDITORIAL_REFERENCE`: useful for layout/editorial genealogy only.
- `PROXY_EXCLUDED`: proxy or semantically mismatched artifact; not scientific evidence.
- `HUMAN_VALIDATION_EXCLUDED`: simulated or non-canonical human annotation provenance.
- `SUPERSEDED`: valid historical checkpoint replaced by a fuller qualified build.

## Scientific scope constraints

- Q1-Q6 is one six-step instrumented trace, not six independent observations.
- Physical BI execution and controlled offline replay/benchmark are distinct evidence classes.
- Semantic decision latency is not backend execution latency.
- Robustness-contained baselines/ablations retain robustness-protocol scope.
- Recovered standalone May baselines/ablations remain distinct until cross-run qualification.
- Legacy scalability artifacts must be regenerated from qualified structural CKG outputs.
- Legacy evidence-usefulness artifacts must be regenerated from qualified Phase-6 outputs.
- UI screenshots are presentation evidence; authoritative numeric reports remain the numerical source.
- `sim_expert_*` outputs do not authorize human/expert validation claims.
- Objective-count Stage-30 is terminal: no rerun, no additional bootstrap, no Stage-40.

## Final publication chain

qualified primary/frozen source
→ normalized data with provenance
→ authorized statistics
→ regenerated figure/table
→ claim-evidence matrix
→ LaTeX section
→ manuscript/PDF
