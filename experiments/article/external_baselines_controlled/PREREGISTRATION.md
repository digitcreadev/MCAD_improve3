# Phase 2B-3A preregistration

## Frozen purpose

Phase 2B-3A creates a controlled interchange boundary.  It does not perform an
experiment.  Native values may be retained in `raw_outputs`, but no threshold,
binary normalization, ranking claim, or MCAD pruning decision is derived from
them.

## Before any later execution

1. Pin the external source and publication environment independently of this
   skeleton.
2. Declare whether the method observes the current query result, history, or an
   auxiliary query before collecting outcomes.
3. Count all physical and auxiliary queries separately and retain backend,
   auxiliary, and adapter time separately.
4. Preserve native outputs and decisions without interpreting them as MCAD
   `ALLOW`, `BLOCK`, or `SAFE_TO_PRUNE`.
5. Treat Djedaini execution, if ever developed, as a **paper-faithful
   reimplementation**, not native reproduction.
6. Do not describe ASSESS build/test-compilation success as runtime integration
   success or as a safe-pruning oracle.

## Phase boundary

No database, container, benchmark workload, historical campaign, or protected
artifact is launched or changed in this phase.  The only admissible outcomes are
contract construction, validation, and explicit unavailable/status envelopes.
