# MCAD Sensitivity Design — Semantic Binding E1.1

## Status

This document binds the frozen E1 sensitivity design to the inspected
production representation of CKGGraph.

It does not modify the frozen E1 archive and does not report an
experimental result.

## Canonical production representation

The canonical in-memory hierarchy is:

    CKGGraph.objectives
      objective_id
        constraints
          constraint_id
            virtual_nodes
            requirement_sets

There are no canonical top-level dictionaries named:

- constraints;
- virtual_nodes;
- requirement_sets.

## NetworkX representation

The production graph is stored in:

    CKGGraph.G

The bootstrap process materialises:

- objective nodes;
- KPI nodes;
- constraint nodes;
- virtual-node nodes;
- HAS_KPI edges;
- HAS_CONSTRAINT edges;
- REQUIRES_NV edges.

Requirement sets are not represented as NetworkX nodes or edges.
They remain nested lists inside constraint metadata.

## Generator representation

The structural generator must first produce a canonical objective
document compatible with bootstrap_objectives().

It must not mutate CKGGraph internals directly unless an audited
production API is introduced later.

The generated document must contain:

- objectives;
- KPI identifiers;
- semantically distinct constraints;
- virtual-node definitions;
- requirement sets.

## Factor implementation binding

### Objective count

Permitted implementation:

- generate structurally equivalent but identifier-distinct objectives;
- or use clone_objective after one canonical objective is loaded.

For deterministic manifests, generation before bootstrap is preferred.

### Constraint count

Must be realised by generating distinct constraints inside the selected
objective.

clone_objective must not be used to implement this factor.

### Virtual-node count

Must be realised by changing the number of valid NV declarations while
holding the selected objective's constraint count fixed.

Useful, supporting, and irrelevant NV counts must be distinguished.

### Requirement-set membership density

Let:

    M = set of all (constraint, requirement_set_index, nv_id)
        memberships present in the generated objective.

Let:

    P = sum over constraints c of:
        number_of_requirement_sets(c) * number_of_declared_NVs(c)

The realised membership density is:

    d_membership = |M| / P

provided P > 0.

Requested and realised values must both be recorded.

This metric describes nested requirement-set membership. It is not the
NetworkX graph density.

### Workload noise

Noise remains a property of generated query plans and oracle labels.
It must not be implemented by inserting malformed graph objects.

## Requirement-set semantics

Within one requirement set, all referenced NVs are jointly required.

Across requirement sets of one constraint, the alternatives are
disjunctive: satisfying any complete requirement set makes the
constraint calculable.

## Structural invariants

### SB1 — Objective hierarchy integrity

Every generated constraint belongs to exactly one generated objective.

### SB2 — NV declaration integrity

Every NV referenced by a requirement set is declared in the same
constraint's virtual_nodes list.

### SB3 — Graph projection integrity

After bootstrap, each generated objective, constraint and NV has the
expected production graph node.

### SB4 — Edge integrity

After bootstrap:

- each objective has HAS_CONSTRAINT edges to its constraints;
- each constraint has REQUIRES_NV edges to its declared NVs.

### SB5 — Requirement-set preservation

The requirement sets loaded in CKGGraph.objectives are byte-equivalent
to the canonical generated requirement sets after deterministic
normalisation.

### SB6 — No evaluation mutation

The E2.1 structural generator must not call:

- sat;
- real;
- ceval;
- phi.

### SB7 — Canonical counting

Constraint, NV and requirement-set counts are computed from
CKGGraph.objectives.

Graph node and edge counts are computed separately from CKGGraph.G.

### SB8 — Phi naming

Future evaluation outputs must distinguish:

- phi_unweighted;
- phi_weighted.

## E2.1 boundary

E2.1 may:

- generate a canonical objectives YAML document;
- load it with bootstrap_objectives();
- inspect CKGGraph.objectives;
- inspect CKGGraph.G;
- generate a canonical manifest;
- validate structural invariants.

E2.1 may not:

- execute SAT;
- execute Real;
- execute Ceval;
- execute phi;
- produce performance or decision claims.
