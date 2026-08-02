# Virtual-node-count Stage-10 preregistration preflight

- Status: `preflight_complete_parameter_freeze_pending`
- Source branch: `paper/phase3-controlled-execution`
- Source commit: `6132923eb211b14109e2bda851948da7ddbe2220`
- Historical prefix valid: `true`
- Historical functional rerun required: `false`
- Historical replications: `rep_000`, `rep_001`
- New functional replications proposed: `rep_002` through `rep_009`
- Formal timing replications proposed: `rep_000` through `rep_009`
- Stage-20 policy: conditional only
- Functional execution authorized: `false`
- Timing execution authorized: `false`

## Proposed Stage-10 structure

- Factor: `virtual_node_count`
- Levels: `6, 12, 24`
- Fixed constraint count: `4`
- Structural replications: `10`
- Expected structural instances: `30`

## Historical prefix validation

- `rep_000`: seed `101`, levels `[6, 12, 24]`, valid `true`
- `rep_001`: seed `202`, levels `[6, 12, 24]`, valid `true`

## Parameters still requiring an explicit freeze

- Candidate evidence exists for all required parameters; values still require contract-level confirmation.

## Scientific gate

No new functional execution or timing execution is authorized by this preflight. The next step is to freeze the exact timing parameters in a versioned Stage-10 preregistration contract.
