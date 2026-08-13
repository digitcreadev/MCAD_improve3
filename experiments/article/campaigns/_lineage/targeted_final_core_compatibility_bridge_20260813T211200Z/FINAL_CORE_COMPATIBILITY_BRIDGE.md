# MCAD — Targeted final core compatibility bridge

No experiment, replay, statistical analysis, physical backend execution or timing execution was performed.

## Core bridge

- `sat` unchanged across Aug-5 CKG extension: `True`
- `real` unchanged across Aug-5 CKG extension: `True`
- `ceval` unchanged across Aug-5 CKG extension: `True`
- `phi` unchanged across Aug-5 CKG extension: `True`
- historical `_constraint_support` logic preserved in post-Aug5 method: `True`
- May `session_support_policy` hits: `0`
- Physical-package `session_support_policy` hits: `0`

## Runner bridge

- `run_baselines_and_ablations.py`: byte-identical=False; changed common functions=['play_policy_on_scenario', 'summarize_by_policy']; policy decision contract equal=True
- `run_scalability_benchmark.py`: byte-identical=True; changed common functions=[]; policy decision contract equal=None
- `run_evidence_usefulness_benchmark.py`: byte-identical=False; changed common functions=[]; policy decision contract equal=None
- `run_statistical_analysis.py`: byte-identical=False; changed common functions=['parse_args']; policy decision contract equal=None

## Final adopted chain

| Campaign | Final status | Role |
|---|---|---|
| `ui_q1_q6` | `ADOPT_MAIN_STATIC_CORE_BRIDGE_PASS` | detailed end-to-end mechanism |
| `campaign_a_foodmart` | `ADOPT_MAIN_STATIC_CORE_BRIDGE_PASS` | physical depth |
| `campaign_b_multidataset` | `ADOPT_MAIN_STATIC_CORE_BRIDGE_PASS` | multi-dataset/adaptor breadth |
| `campaign_c_backend_portability` | `ADOPT_MAIN_STATIC_CORE_BRIDGE_PASS` | paired backend portability |
| `policy_benchmark` | `SECONDARY_OR_SUPPLEMENT_COMPATIBILITY_PASS` | nominal offline baseline comparison |
| `ablations` | `SUPPLEMENT_ONLY_MAIN_ABLATIONS_FROM_ROBUSTNESS` | historical causal confirmation |
| `robustness` | `ADOPT_MAIN_FROZEN_NON_TEMPORAL` | primary baselines + ablations + robustness + system explainability |
| `scalability_ckg` | `ADOPT_MAIN_STRUCTURAL_COMPATIBILITY_PASS` | structural CKG scalability |
| `evidence_usefulness` | `OPTIONAL_SECONDARY_COMPATIBILITY_PASS` | controlled evidence reuse/bootstrap |
| `phase7_statistics` | `EXCLUDE_AS_IS_REDERIVE_ONLY_IF_REQUIRED` | historical derived statistics |
| `human_validation` | `EXCLUDE_NO_REAL_EXPERT_ANNOTATIONS` | none |
| `sensitivity_constraint_count` | `ADOPT_FINAL_CANONICAL_SOURCE_MAP_ONLY` | semantic decision sensitivity |
| `sensitivity_virtual_node_count` | `ADOPT_FINAL_CANONICAL_SOURCE_MAP_ONLY` | semantic decision sensitivity |
| `sensitivity_membership_density` | `ADOPT_FINAL_CANONICAL_SOURCE_MAP_ONLY` | semantic decision sensitivity |
| `sensitivity_objective_count` | `ADOPT_TERMINAL_STAGE30_ONLY` | terminal semantic decision precision limit |

## Important exclusions

- Historical Phase-7 statistics are not attached as-is to the final robustness freeze.
- Historical May timing is not publication-authorized.
- Simulated human/expert validation remains excluded.
- Intermediate/replayed sensitivity outputs are provenance only; use final canonical source-map selections.

Overall gate: `PASS_FINAL_ADOPTION_CHAIN_READY`

Next: persist the final adoption chain and generate publication artifacts V3 from that chain.
