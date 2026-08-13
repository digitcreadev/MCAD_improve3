# MCAD — Final campaign adoption matrix

This is a read-only version/lineage audit. No experiment, replay, statistic or backend execution was performed.

## Selection principle

Archive integrity/qualification is necessary but not sufficient for final manuscript adoption. Replayed runs across MCAD versions are regression lineage, not independent experimental replications.

## Core-version observations

- `backend/mcad/engine.py` SHA-256: `e8dff06a6c612ed3d1d679f3fe70075bee9589525a1a2222e13b0a640758ddb0`
- `backend/ckg/ckg_updater.py` SHA-256: `6faaa8b7dea5b682ac9ea6ecf3cf790ff6d7a4c5c56d105a52c4e7acf2ad739d`
- Aug-5 updater diff adds `session_support_policy`: `True`
- Aug-5 updater diff adds `union_requirement_sets`: `True`
- Historical May recovered tree occurrences of `session_support_policy`: `0`

## Final adoption recommendations

| Campaign | Recommendation | Version risk | Redundancy |
|---|---|---|---|
| `ui_q1_q6` | `ADOPT_MAIN_AFTER_DECISION_CONTRACT_BRIDGE` | `LOW_TO_MEDIUM` | `NONE` |
| `campaign_a_foodmart` | `ADOPT_MAIN_AFTER_STATIC_VERSION_BRIDGE` | `MEDIUM` | `LOW` |
| `campaign_b_multidataset` | `ADOPT_MAIN_AFTER_DECISION_CONTRACT_BRIDGE` | `MEDIUM` | `LOW` |
| `campaign_c_backend_portability` | `ADOPT_MAIN_AFTER_DECISION_CONTRACT_BRIDGE` | `MEDIUM` | `LOW` |
| `policy_benchmark` | `SECONDARY_OR_SUPPLEMENT_AFTER_STATIC_COMPATIBILITY` | `MEDIUM` | `MEDIUM_WITH_ROBUSTNESS` |
| `ablations` | `SUPPLEMENT_ONLY; MAIN_ABLATIONS_FROM_ROBUSTNESS` | `MEDIUM` | `HIGH_WITH_FROZEN_ROBUSTNESS` |
| `robustness` | `ADOPT_MAIN_FROZEN_NON_TEMPORAL` | `LOW` | `NONE` |
| `scalability_ckg` | `ADOPT_MAIN_STRUCTURAL_IF_STATIC_COMPATIBILITY_PASS` | `LOW_TO_MEDIUM` | `NONE_WITH_SENSITIVITY_IF_STRUCTURE_ONLY` |
| `evidence_usefulness` | `OPTIONAL_SECONDARY_IF_STATIC_COMPATIBILITY_PASS` | `MEDIUM` | `LOW` |
| `phase7_statistics` | `EXCLUDE_AS_IS_FROM_FINAL_MAIN; REDERIVE_ONLY_IF_NEEDED` | `HIGH_FOR_FINAL_CHAIN` | `DERIVED_LAYER` |
| `human_validation` | `EXCLUDE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| `sensitivity_constraint_count` | `ADOPT_MAIN_FINAL_CANONICAL_ONLY` | `LOW_CANONICAL_SOURCE_MAP` | `INTERMEDIATE_STAGES_SUPERSEDED` |
| `sensitivity_virtual_node_count` | `ADOPT_MAIN_FINAL_CANONICAL_ONLY` | `LOW_CANONICAL_SOURCE_MAP` | `INTERMEDIATE_STAGES_SUPERSEDED` |
| `sensitivity_membership_density` | `ADOPT_MAIN_FINAL_CANONICAL_ONLY` | `LOW_CANONICAL_SOURCE_MAP` | `INTERMEDIATE_STAGES_SUPERSEDED` |
| `sensitivity_objective_count` | `ADOPT_MAIN_TERMINAL_STAGE30_ONLY` | `LOW_TERMINAL` | `ALL_PRE_STAGE30_OUTPUTS_NON_FINAL` |

## Final chain

1. Q1–Q6: detailed end-to-end mechanism.
2. A/B/C: physical depth, multi-dataset breadth and paired backend portability.
3. Frozen robustness: main baseline comparison + main ablation + system explainability.
4. Structural CKG scalability: only if static compatibility bridge passes; no May timing.
5. Evidence usefulness: optional secondary evidence if compatibility bridge passes.
6. Four canonical sensitivities: final source-map only; objective-count Stage-30 terminal.
7. Historical Phase-7 statistics: exclude as-is; rederive only from final adopted inputs if inferential statistics are required.
8. Human simulated validation and legacy proxy figures: excluded.

## Next gate

Perform a targeted decision-contract compatibility bridge for Q1–Q6/B/C and a static compatibility bridge for A/scalability/evidence. Do not rerun physical backends or Stage-30.
