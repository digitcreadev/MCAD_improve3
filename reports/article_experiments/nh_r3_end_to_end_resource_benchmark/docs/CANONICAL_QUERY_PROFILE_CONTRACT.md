# Canonical Query Profile (CQP) contract

## Scientific claim
CQP is a language-agnostic canonicalization of analytical queries for
objective-relative semantic reasoning.

It is not a claim to have invented query intermediate representations.

## Current common feature vocabulary
Current SQL/MDX extractors provide common analytical features including:
- language;
- cube/source;
- measures;
- dimensions/group-by/granularity;
- slicers/restrictions;
- aggregators/analytics;
- temporal scope/window.

## Current demonstrated implementation scope
- SQL: implemented parser/canonical plan.
- MDX: implemented parser/canonical plan.
- DAX: not implemented; future adapter/parser target.

## Safety rule
A future language adapter may participate in safe pruning only when it preserves
the fields required by the MCAD reasoning contract with sufficient fidelity.

Otherwise the operational policy must fail open rather than infer safe pruning
from missing canonical semantics.
