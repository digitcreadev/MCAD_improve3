# MCAD Sensitivity Analysis — E2.2 Controlled Experimental Families

## 1. Purpose

E2.2 constructs controlled families of synthetic structural instances by
delegating every individual instance to the validated E2.1 structural
generator.

E2.2 does not evaluate MCAD decisions and must not call:

- `sat`
- `real`
- `ceval`
- `phi`

E2.2 is an experimental-design layer, not an evaluation layer.

## 2. Supported factors

The first E2.2 version supports only factors already exposed by E2.1:

1. `constraint_count`
2. `virtual_node_count`

The following factors are explicitly outside this version:

- objective count;
- requirement-membership density below 1.0;
- structural noise;
- invalid-reference injection;
- semantic perturbation.

Those factors require a separately validated extension of E2.1.

## 3. OFAT principle

Each family follows the one-factor-at-a-time principle.

For a `constraint_count` family:

- `n_constraints` varies over the declared levels;
- `n_virtual_nodes` remains equal to the baseline;
- the generator version remains fixed;
- the objective template remains fixed;
- the set of replication seeds remains fixed.

For a `virtual_node_count` family:

- `n_virtual_nodes` varies over the declared levels;
- `n_constraints` remains equal to the baseline;
- the generator version remains fixed;
- the objective template remains fixed;
- the set of replication seeds remains fixed.

## 4. Replications

A family may contain multiple deterministic replications.

Each experimental condition is identified by:

- family identifier;
- varied factor;
- factor level;
- replication index;
- seed;
- objective identifier.

The same campaign specification must reproduce the same generated instance
digests.

## 5. Required outputs

An E2.2 campaign must write:

- `campaign_spec.json`
- `campaign_manifest.json`
- `instances.csv`
- one directory per generated instance;
- the E2.1 `manifest.json` and `objectives.yaml` in every instance directory.

## 6. Campaign invariants

The campaign validator must verify:

- every requested condition was generated exactly once;
- factor levels are non-empty, positive and unique;
- seeds are non-empty and unique;
- only one structural factor varies inside a family;
- non-varied structural dimensions equal their baseline values;
- all instance manifests report the E2.1 generator version;
- all instance directories exist;
- all instance digests are present;
- the campaign digest is deterministic;
- no production evaluation method is invoked.

## 7. Naming

Instance objective identifiers must be deterministic and derived from:

- campaign identifier;
- factor name;
- factor level;
- replication index.

Filesystem names must be stable and must not depend on wall-clock time.

## 8. Boundary with later phases

E2.2 generates controlled structural families.

It does not:

- execute query plans;
- calculate SAT, Real, Ceval or phi;
- aggregate performance measurements;
- generate publication figures;
- make statistical claims.

Those operations belong to later experimental phases.
