# R3-A2 formal refinement

## Objective
`O={c_i}` is the semantic target. `G_O` is its structural realization in the CKG.

Implementation mapping:
`objective --HAS_CONSTRAINT--> constraint --REQUIRES_NV--> virtual_node`.

`requirement_sets` encode alternative sufficient sets of virtual-node
realizations. For exposition, those sets may be represented as support
hyperedges or logical support nodes.

Evidence records are distinct runtime objects linked to constraints/virtual
nodes.

## Calculability
A required constraint is computable when at least one declared sufficient
requirement set is satisfied by acquired session evidence.

## States
Paper terminology:
`UNRESOLVED -> PARTIALLY_SUPPORTED -> COMPUTABLE`.

Current implementation terminology:
`none -> partial -> total`.

The mapping is semantic; R3-A2 does not alter frozen R1/R2 decisions.

## Important alternative-support nuance
`ceval()` accepts any sufficient `requirement_set`.

Current partial-state reporting uses a selected support according to the
session-support policy. The paper must not claim an all-alternatives optimal
partial-progress state unless a later harmonization explicitly implements and
tests it.
