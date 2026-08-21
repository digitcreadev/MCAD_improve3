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

## R3-A2 semantic/novelty refinement

### Paper-level claim boundary
The paper's core non-human claim is objective-relative analytical completion and
safe contribution control. R3's specific estimand remains physical work/time
avoided **conditional on** the frozen semantic decisions and backend embedding.

MCAD constructs the analytical basis prescribed by the instantiated objective.
The adequacy of that particular objective instantiation to the real business
need is an upstream validity assumption. Human/organizational decision quality
is downstream and is not inferred by R3.

### Objective graph mapping
`O={c_i}` remains the semantic target already used by NH-R1/NH-R2.

`G_O` denotes the structural objective graph. In the current implementation:
- objective nodes connect to constraint nodes via `HAS_CONSTRAINT`;
- constraint nodes connect to virtual analytical nodes via `REQUIRES_NV`;
- alternative sufficient supports are represented by `requirement_sets`
  containing virtual-node identifiers.

Support sets may be drawn as logical support nodes/hyperedges in the paper, but
they are not currently materialized as a separate physical CKG node type.

Virtual nodes are therefore **not identical to constraints**. They represent
analytical realization/calculation points associated with constraints.

### Constraint states
Current implementation states `none`, `partial`, `total` correspond to:
`UNRESOLVED`, `PARTIALLY_SUPPORTED`, `COMPUTABLE`.

`ceval()` treats alternative sufficient `requirement_sets` disjunctively.
Partial-progress reporting currently follows the selected session support
policy; no broader claim about optimal progress across every alternative support
is made by R3-A2.

### Canonical Query Profile
CQP is treated as a major enabling contribution:

> language-agnostic canonicalization of analytical queries for objective-relative semantic reasoning.

The current repository implements SQL and MDX analytical extraction into a
shared feature vocabulary. DAX is an explicit future target, not current
experimental support.

### Evidence-realizability
For scientific exposition, distinguish:
`semantic admissibility pre-NVAC`
from
`evidence realizability/non-vacuity`
from
`acquired evidence`
from
`contribution`
from
`action policy`.

The existing overall SAT/gate outcome is preserved; R3-A2 only makes the
substructure explicit for reporting and instrumentation.

`NONCONTRIBUTIVE_NOW != SAFE_TO_PRUNE`.

All gate/probe overhead remains included in R3 resource accounting.
