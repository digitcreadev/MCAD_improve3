# MCAD Sensitivity Generator — Phase E1 Design Specification

## 1. Status

This document specifies the sensitivity-analysis generator before its
implementation.

No experimental result may be produced or interpreted from this
document alone.

The implementation phase is authorised only after all design
invariants and validation tests pass.

## 2. Scientific objective

The sensitivity campaign evaluates how MCAD behaviour changes when a
single structural or workload factor is varied while designated
control variables remain fixed.

The campaign is distinct from:

- the controlled UI demonstration;
- Campaign A, which validates depth over locked FoodMart sessions;
- Campaign B, which validates controlled multidataset behaviour;
- Campaign C, which validates backend portability;
- the policy and ablation benchmark;
- the existing coupled scalability benchmark.

## 3. Core causal principle

For every experimental axis, one primary factor is varied.

All other controlled factors must:

1. remain equal to their configured target values; or
2. be explicitly measured and documented when exact constancy is
   structurally impossible.

A point that does not realise its requested controls must fail and
must not be silently included in the result set.

## 4. Production semantics to reuse

The generator must use the current production implementations of:

- CKGGraph;
- SAT;
- Real;
- Ceval;
- phi;
- objective and constraint representations;
- requirement sets;
- virtual nodes.

The generator must not reimplement simplified versions of these
semantics.

The existing build_scaled_ckg function may be used for comparison or
legacy scalability checks, but not as the principal generator for
factor-isolated sensitivity experiments.

## 5. Experimental unit

One experimental unit is:

- one generated CKG instance;
- one selected objective;
- one generated workload;
- one seed;
- one value of the varied factor;
- one repetition.

Every unit must have a unique deterministic instance identifier.

## 6. Independent factors

### F1 — Objective count

Primary variable:

    n_objectives

Controls:

- constraints per objective;
- virtual nodes per objective;
- requirement-set structure;
- workload length;
- noise ratio;
- contribution density.

Candidate levels:

    1, 2, 5, 10, 20, 50

### F2 — Constraint count per selected objective

Primary variable:

    n_constraints

Controls:

- objective count;
- virtual nodes per constraint;
- requirement-set complexity;
- contribution density;
- workload length;
- noise ratio.

Candidate levels:

    2, 4, 8, 16, 32

Constraints must be semantically distinct. Merely duplicating the
same constraint under new identifiers is forbidden.

### F3 — Virtual-node count

Primary variable:

    n_virtual_nodes

Controls:

- objective count;
- constraint count;
- contribution density;
- workload length;
- noise composition.

Candidate levels:

    8, 16, 32, 64, 128, 256, 512

The design must distinguish:

- useful virtual nodes;
- irrelevant but valid virtual nodes;
- virtual nodes referenced by requirement sets.

### F4 — Contribution-support density

The provisional realised density is:

    density =
        number of realised requirement-set-to-NV membership links
        /
        maximum possible membership links under the generated model

The final denominator must be confirmed against the production
requirement-set semantics.

Candidate levels:

    0.10, 0.25, 0.50, 0.75, 1.00

Requested density and realised density must both be recorded.

### F5 — Non-contributive workload noise

Primary variable:

    noise_ratio =
        number of oracle-non-contributive queries
        /
        total number of queries

Candidate levels:

    0.00, 0.10, 0.25, 0.40, 0.60

Noise must be stratified across at least the following classes:

- wrong measure;
- wrong context or slicer;
- insufficient grain;
- invalid aggregation;
- invalid unit;
- invalid temporal window;
- missing cube;
- redundant already-covered contribution.

A sensitivity point must record both requested and realised noise
ratios and the realised class distribution.

## 7. Controlled variables

Unless explicitly varied, the following values must remain fixed
within one experimental axis:

- selected dataset or logical cube;
- objective count;
- constraint count;
- useful NV count;
- irrelevant NV count;
- requirement-set complexity;
- contribution density;
- workload length;
- noise ratio;
- noise-class distribution;
- policy;
- code revision;
- generator revision;
- random seed family;
- machine and Python environment.

## 8. Independent oracle

The oracle must be generated from the ground-truth construction before
calling MCAD.

The oracle must not depend on:

- SAT output;
- Real output;
- Ceval output;
- phi output;
- MCAD ALLOW or BLOCK decisions.

For each query, the generator must provide:

- oracle_allow;
- oracle_ceval;
- oracle_contribution;
- oracle_noise_class;
- oracle_target_constraints.

## 9. Required generated-instance manifest

Each generated instance must record:

- instance_id;
- axis;
- requested_factor_value;
- realised_factor_value;
- seed;
- repetition;
- objective_count;
- selected_objective_id;
- selected_objective_constraint_count;
- total_constraint_count;
- useful_virtual_node_count;
- irrelevant_virtual_node_count;
- total_virtual_node_count;
- requirement_set_count;
- requirement_membership_link_count;
- realised_density;
- workload_length;
- non_contributive_query_count;
- realised_noise_ratio;
- realised_noise_class_counts;
- graph_node_count;
- graph_edge_count;
- generator_version;
- code_revision;
- configuration_digest;
- instance_digest.

## 10. Decision metrics

Using the oracle as ground truth:

- true_allow;
- false_allow;
- true_block;
- false_block;
- false_allow_rate;
- false_block_rate;
- precision;
- recall;
- F1;
- specificity;
- balanced accuracy;
- Matthews correlation coefficient.

Degenerate denominators must be reported as missing values, not zero.

## 11. Goal-progress metrics

- phi_final;
- AUC of phi over session steps;
- reach_rate_0_8;
- reach_rate_0_9;
- conditional time to 0.8;
- conditional time to 0.9;
- executed non-contributive query rate.

Conditional threshold times must never be reported without their reach
rates.

## 12. Runtime and storage metrics

- graph construction time;
- cold decision latency;
- warm decision latency;
- p50, p95 and p99 latency;
- peak Python memory;
- snapshot time;
- snapshot size;
- graph node and edge counts.

Missing warm samples must remain missing and must not be converted to
zero.

## 13. Design invariants

### I1 — Identifier uniqueness

All objective, constraint, requirement-set and virtual-node
identifiers are unique.

### I2 — Reference integrity

Every referenced virtual node and constraint exists.

### I3 — Objective validity

Every generated objective has at least one valid constraint and one
valid support structure.

### I4 — Oracle independence

No production MCAD output is used to construct the oracle.

### I5 — Factor isolation

For a given axis, only the declared factor changes outside documented
tolerances.

### I6 — Requested/realised agreement

Every realised factor value falls within its declared tolerance.

### I7 — Determinism

The same configuration and seed produce byte-equivalent canonical
instance manifests.

### I8 — Seed variation

At least two distinct seeds produce distinct instances when a random
degree of freedom exists.

### I9 — No silent invalid point

Any failed invariant aborts the experimental point.

### I10 — Production evaluation

SAT, Real, Ceval and phi are called from the production implementation.

## 14. Validation gates

### Gate E1-A — Design specification

The design configuration and schema are structurally valid.

### Gate E1-B — Factor matrix

Each axis varies one declared primary factor and explicitly fixes all
controls.

### Gate E1-C — Metric contract

Every reported metric has a defined formula and missing-value policy.

### Gate E1-D — Implementation readiness

The design validator passes before generator implementation begins.

### Gate E2-A — Generator unit tests

The implementation must validate deterministic generation, factor
isolation, oracle independence and reference integrity.

### Gate E2-B — Smoke sensitivity campaign

A small falsifiable grid must pass before the full campaign.

### Gate E2-C — Full campaign

The full campaign is executed only after all prior gates pass.

## 15. Publication limits

The sensitivity campaign may support claims about controlled synthetic
variation of CKG and workload properties.

It must not be presented as:

- a substitute for physical backend execution;
- a user study;
- evidence about arbitrary real-world organisations;
- proof of unlimited scalability;
- evidence for factors not explicitly varied.
