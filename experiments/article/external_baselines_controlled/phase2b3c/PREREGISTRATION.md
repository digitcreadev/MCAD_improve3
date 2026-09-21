# MCAD Phase 2B-3C1 preregistration

**Status:** frozen contract. **Execution status:** not authorized.

## Purpose and authority

This contract preregisters a later controlled smoke of five native Delian
measures at publication-aligned commit
`606f94afe88767665ce185566ca8357a56f736d2`. It is based on merged Phase
2B-3B HEAD `f38807edcafde2547c177d79ce5b0d78891b3491` and tree
`9bfc5077f54bab353b4a1a9cc7d1f7e618d85e59`. The machine-readable files are
normative for exact values.

The later smoke asks only whether the preregistered measures remain exercisable
through publication-aligned native tests in the reconstructed environment. It
is not a comparative benchmark.

## Scientific boundary

The native JUnit tests for measures classified `pre_result` invoke
`SessionQueryProcessorEngine.answerCubeQueryWithInterestMeasures(...)` and
therefore execute database queries in the test harness. A PASS establishes
native implementation reproducibility only. It is **not** pre-backend evidence,
not a P2a timing measurement, and cannot support latency or backend-avoidance
claims. All captured timing is `SMOKE_DIAGNOSTIC_ONLY`, non-comparative, and
excluded from comparative tables.

No threshold, AUROC/AUPRC, MCAD superiority, cost superiority, or
ALLOW/BLOCK/SAFE_TO_PRUNE equivalence/conversion may be inferred. A failure is
an execution/reproducibility failure, not falsification of the Delian paper.

## Frozen future-run rules

Each track gets an independently clean exact source export, the frozen dump
overlay, MySQL 8.0.33, and a 300-second Maven-command timeout. The future runner
must record exit status, full output, Surefire reports, toolchain and OS/kernel,
Docker version, and the exact MySQL image identity when available. It fails
closed on timeout, nonzero exit, assertion failure, absent schema/history
fixture, source/hash mismatch, or unexpected test count. Toolchains must never
be silently changed after failure; a change requires a newly labelled run.

`FamilyBasedRelevance` is excluded because its helping-query behavior requires
a separate auxiliary-query cost/accounting preregistration. Djedaini and ASSESS
runtime execution are excluded. Comparative instrumentation belongs to a later
phase; auxiliary-query counts must not be inferred where no auxiliary query is
issued in a preregistered track.

Phase 2B-3C2 may later create an isolated external runner and report only
`CONTROLLED_NATIVE_DELIAN_SMOKE_PASS` or a precise failure classification.
