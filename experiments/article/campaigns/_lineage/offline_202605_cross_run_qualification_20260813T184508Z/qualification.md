# MCAD offline 202605 — cross-run qualification

No new experiment, replay, benchmark, bootstrap or statistical analysis was executed.

## Scope

The six `rebuild_article_*` directories are repeated historical rebuilds of the recovered May offline suite, not six independent campaigns.

## Integrity

- recovered runs: 6
- manifest-backed candidates: 5
- pre-manifest auxiliary run: 1
- unique manifest-run input checksum registries: 1
- copied checksum-covered files: all matched their historical checksum entries

## Cross-run stability

- `policy_benchmark_summary_non_temporal`: PASS; canonical hash `f9b8e1fb62aa6c482d8ecbc9030d2e961f86d070f25e6bac5f2f9eb548ab5095`
- `policy_benchmark_session_non_temporal`: PASS; canonical hash `a45c2b35cb5ee69f48413a46c5019db385969ef6007c9281431d1d09c534ccde`
- `policy_benchmark_step_non_temporal`: PASS; canonical hash `636ad828b544aa2d5d7fc40dee410b7c00de5d19295b18985b2b05f0cb2787b6`
- `scalability_catalog_structural`: PASS; canonical hash `40e9f230231073fb569cec74fc6ac2d2c6c0aa9f96318f8d8208e86513c5d3d8`
- `scalability_growth_structural`: PASS; canonical hash `2824ed95d2ee8b02b4bb670f005887562068fd6c7be70bcdb972fb62c29c07e8`
- `evidence_usefulness_non_timestamp`: PASS; canonical hash `7f96f9ca72aa167589a19dda416fb014c273a3abc9089c2da6be1c4c0a1a6c6c`
- `evidence_bootstrap_benefit`: PASS; canonical hash `594a8e30478fff264a08a176193a595b7b58700ccfe105549abfc00a83ef3205`
- `phase7_pairwise_statistics`: PASS; canonical hash `44bde626559cc058c0986d3f39736623563316e044a615a60c79f39c558e1614`
- `phase7_policy_confidence_intervals`: PASS; canonical hash `bdcf9e908f4eff9d6bf8d76b1e767b3ee1975e64fe9161e2069dddbc78881958`
- `phase7_statistical_summary`: PASS; canonical hash `12a6b906742f14c395ef1df98e064e7ea21f2516ee273dbc253cb898fc67b722`

## Timing

Historical May timing is not authorized as final publication performance evidence. The suite remains useful for non-temporal policy outcomes and structural CKG scaling.

## Candidate publication qualification

- `policy_benchmark` → `AUTHORIZED_WITH_SCOPE_LIMIT_NON_TEMPORAL`
- `ablations` → `AUTHORIZED_WITH_SCOPE_LIMIT_NON_TEMPORAL`
- `scalability_ckg` → `AUTHORIZED_STRUCTURAL_ONLY_TIMING_RESTRICTED`
- `evidence_usefulness` → `AUTHORIZED_WITH_SCOPE_LIMIT_CONTROLLED_PHASE6`
- `phase7_statistics` → `AUTHORIZED_DERIVED_STATISTICS_WITH_SCOPE_LIMIT`
- `human_validation` → `EXCLUDED_NO_REAL_EXPERT_ANNOTATIONS`

These statuses are candidates produced by a read-only qualification audit. They are not persisted into the repository until a separate controlled commit.
