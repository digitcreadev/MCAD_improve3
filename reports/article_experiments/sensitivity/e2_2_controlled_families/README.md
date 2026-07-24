# MCAD Sensitivity Analysis — E2.2 Freeze

## Frozen component

Controlled Experimental Families, version:

- `mcad-sensitivity-e2.2-v1`

Structural dependency:

- `mcad-sensitivity-e2.1-v1`

## Experimental design

The frozen implementation supports one-factor-at-a-time campaigns over:

- `constraint_count`
- `virtual_node_count`

The replication unit is the deterministic seed.

E2.2 does not invoke the production evaluation functions:

- `sat`
- `real`
- `ceval`
- `phi`

## Canonical campaigns

Two canonical campaigns are included:

1. Constraint-count family:
   - levels: `2, 4, 8`
   - seeds: `101, 202`
   - fixed virtual-node count: `12`

2. Virtual-node-count family:
   - levels: `6, 12, 24`
   - seeds: `101, 202`
   - fixed constraint count: `4`

Each campaign contains six generated E2.1 instances.

## Validated invariants

- Complete experimental matrix.
- Exactly one varied factor per family.
- Requested and realised structural counts agree.
- Membership density remains equal to `1.0`.
- Each condition has distinct configuration and instance digests.
- Source contract validation succeeds.
- E2.1 and E2.2 tests succeed.

## Contents

- `source_snapshot/`: frozen source and test files.
- `campaigns/`: canonical generated campaigns.
- `validation/`: validation logs, environment and summaries.
- `MANIFEST.json`: machine-readable freeze metadata.
- `INVENTORY.txt`: deterministic file inventory.
- `SHA256SUMS`: SHA-256 digest of every freeze file.
