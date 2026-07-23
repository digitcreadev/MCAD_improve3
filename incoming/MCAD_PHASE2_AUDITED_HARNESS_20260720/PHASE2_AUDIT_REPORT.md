# MCAD Phase 2 — Audit of baselines, ablations, robustness, scalability, and statistics

Date: 2026-07-20
Audited source: `MCAD_improve3-main(3).zip`
Reference harness: `Old_backend_harness.zip`

## Executive conclusion

The current article benchmark (`experiments/article/run_article_experiments.py`) must not be used as the scientific source for baselines, ablations, or latency claims. Its MCAD policy returns the scenario oracle label directly, its execution status is inferred from `decision == ALLOW`, and its latency is largely synthetic/deterministic. The artifact generator also explicitly contains proxy figures for evidence bootstrap and ablation sensitivity.

The old backend harness is compatible with the current `backend.ckg.ckg_updater.CKGGraph` implementation. It invokes `sat`, `real`, `ceval`, `phi`, and `evaluate_step` directly. Compilation and two local smoke benchmarks completed successfully against the audited repository snapshot.

## Classification of scripts

### Reject as primary scientific evidence

- `experiments/article/run_article_experiments.py`
  - `mcad_gate` returns `query.true_label` directly.
  - Baseline correctness is scored against the same oracle labels.
  - `executed` is defined as `decision == ALLOW`, not a physical backend execution.
  - `simulate_latency_ms` injects deterministic synthetic latency.

- `experiments/article/artifacts/generate_article_artifacts.py`
  - contains `figure_bootstrap_proxy`;
  - contains `figure_ablation_proxy`;
  - the existing scalability figure is not the structural CKG benchmark;
  - human-validation output must not be interpreted as completed expert validation unless actual annotations are supplied.

These scripts may remain useful for deterministic replay, formatting, or regression checks, but their outputs must be labelled accordingly.

### Accept for controlled offline evaluation

- `backend/harness/run_baselines_and_ablations.py`
  - calls the real CKG reasoning implementation;
  - compares MCAD, naive, measure-overlap, matched-random, and three ablations;
  - records real local decision latency;
  - uses oracle scenario labels only for outcome scoring.

- `backend/harness/run_robustness_benchmark.py`
  - reuses the real policy evaluator;
  - stratifies scenarios by robustness type;
  - computes explainable-block metrics.

- `backend/harness/run_scalability_benchmark.py`
  - builds scaled CKGs;
  - calls `evaluate_step`;
  - measures nodes, edges, virtual nodes, evaluation latency, snapshot time/size, memory, and compaction.

- `backend/harness/run_statistical_analysis.py`
  - bootstrap confidence intervals;
  - paired bootstrap advantages;
  - sign-flip permutation tests;
  - dominance rates;
  - ablation sensitivity.

## Scientific scope

The restored harness is an offline, controlled evaluation of the MCAD reasoning engine. It is not a physical SQL/XMLA execution benchmark. Physical-execution claims remain grounded in the frozen UI and Campaigns A/B/C evidence.

The scenario oracle is acceptable for scoring precision, false-allow, and false-block outcomes, provided the article states that scenario labels are controlled ground truth and are not used by the MCAD decision procedure itself.

## Smoke-test evidence

The following checks passed against the current repository snapshot:

1. Python compilation of the four principal scripts.
2. Baselines/ablations benchmark with two repeats.
3. Structural CKG scalability benchmark at scales 1 and 2.
4. Generation of all expected CSV, JSON, Markdown, and PNG outputs.

## Required article terminology

Use:

- “controlled offline evaluation of the MCAD reasoning engine”;
- “oracle-labelled scenarios used only for scoring”;
- “local reasoning latency”;
- “structural scalability of the CKG”.

Do not use:

- “real backend execution” for these harness runs;
- “physical execution latency”;
- “human validation” before expert annotations exist;
- “industrial scalability”.
