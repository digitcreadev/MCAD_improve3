# SA4 — Controlled Membership-Density Family

## Mathematical definition

For every constraint \(c\):

- \(V_c\) is the set of virtual nodes declared by the constraint;
- \(R_c\) is its collection of requirement sets.

The realised membership density is:

\[
d =
rac{
  \sum_c \sum_{r \in R_c} |r|
}{
  \sum_c |R_c|\,|V_c|
}
\]

The denominator is calculated locally per constraint. It is not the
product of the global constraint count and the global virtual-node count.

## Canonical baseline

The SA4 baseline contains:

- 4 constraints;
- 24 virtual nodes in total;
- one requirement set per constraint;
- 4 requirement sets in total.

Consequently:

\[
M_{\max}=24
\]

The controlled density levels are:

| Density | Membership links |
|---:|---:|
| 25% | 6 |
| 50% | 12 |
| 75% | 18 |
| 100% | 24 |

## Controlled variation

Only requirement-set membership links may vary. Constraints, declared
virtual nodes, virtual-node attributes, KPI metadata, measures,
aggregators, units, grains and all non-membership semantics remain fixed
within a structural seed.

Membership sets must be deterministic, balanced across constraints and
nested across increasing density levels.

## Integrity requirements

Every generated instance must satisfy:

- no unknown membership reference;
- no duplicate member inside one requirement set;
- no empty requirement set;
- one requirement set per constraint;
- exact rational density;
- unchanged non-membership semantic digest;
- unchanged structural dimensions;
- balanced membership allocation, with a maximum difference of one link
  between constraints.

## Independent oracle

The independent oracle is implemented in:

`backend/harness/sensitivity_generator/oracles/membership_density_oracle.py`

It does not import the structural generator or the controlled-family
generator. It recalculates the density directly from `objectives.yaml`.

## Experimental staging

The first formal stage uses 10 structural seeds. Extension to 20 or 30
seeds is adaptive and uses the same cluster-level precision criteria as
the constraint-count family.

No instance generation, controlled execution, timing claim or scientific
freeze is authorized by this contract alone.

## Generator implementation

The density-controlled implementation is isolated from the historical
E2.1 and E2.2 generators:

- `membership_density_generator.py`;
- `families/membership_density_family.py`.

The historical `structural_generator.py` and `controlled_families.py`
remain byte-identical. The dedicated family generator emits integer
percentage levels and validates every replication through the independent
oracle.

Objective, constraint, KPI and virtual-node identifiers may depend on the
experimental condition. The independent oracle therefore normalizes these
technical identifiers while preserving KPI cardinality and all
non-membership semantic attributes.

The generator extension is implemented and tested. No canonical SA4
campaign has yet been generated.

## E3 compatibility

E3 compatibility is defined by factor-specific generator profiles rather
than by a global set of independently accepted versions.

The historical profiles remain accepted for `constraint_count` and
`virtual_node_count`. The dedicated density profile is accepted only for
`membership_density`. Cross-factor generator-version combinations are
rejected.

The E3 executor records the campaign generator version read from the
validated campaign manifest. The reset-safe timing harness remains
unchanged because it already delegates input discovery to the canonical
executor and treats factor levels as integers.

No canonical membership-density campaign has yet been generated or
executed.

## Membership-density common-workload auditor

The SA4 workload is stratified by structural replication. Each structural
seed receives one deterministic 24-step workload that is shared across its
25%, 50%, 75% and 100% density instances.

The auditor verifies the exact level matrix, fixed non-membership
semantics, identical semantic-node sets, identical query specifications,
exact membership counts and strictly nested membership edges. Workloads
must not be reused across structural seeds.

The auditor produces deterministic per-replication workload blueprints.
These blueprints are not yet canonical E3 workload specifications. No
canonical campaign or execution has been started.
