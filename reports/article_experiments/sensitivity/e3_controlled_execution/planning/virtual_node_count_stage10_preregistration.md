# Virtual-node-count Stage-10 preregistration

## Status

- Contract status: `preregistered`
- Source commit: `6132923eb211b14109e2bda851948da7ddbe2220`
- Factor: `virtual_node_count`
- Levels: `6`, `12`, `24`
- Fixed constraint count: `4`
- Stage-10 replications: `10`
- Expected structural instances: `30`

## Historical functional prefix

`rep_000` and `rep_001` are validated historical results.

- reuse required: `true`
- rerun required: `false`
- rerun authorized: `false`

Only `rep_002` through `rep_009` may eventually require new
functional execution, after generation and workload audits pass.

## Timing protocol

- warmups per cell: `10`
- measurements per cell: `100`
- order seed: `20260728 + replication_index`
- formal timing replications: `rep_000` through `rep_009`
- expected timing cells: `60`
- expected warmup observations: `600`
- expected measurement observations: `6000`
- reuse successful outputs: `true`

Timing execution is not authorized by this contract alone.

## Precision protocol

- bootstrap repetitions: `10000`
- bootstrap seed base: `20260728`
- confidence level: `0.95`
- median relative half-width target: `0.10`
- p95 relative half-width target: `0.15`
- bootstrap unit: structural seed cluster
- all cells must pass

## Extension rule

Stage 20 is permitted only if at least one preregistered Stage-10
precision cell fails. Stage 30 is outside this contract and requires
a formal amendment.

## Current authorization

- Stage-10 structural generation: `authorized`
- historical functional prefix reuse: `authorized`
- historical functional rerun: `not authorized`
- new functional execution: `not authorized`
- formal timing execution: `not authorized`
- Stage-20 execution: `not authorized`
- latency claim: `not authorized`

## Next stage

Generate and audit the Stage-10 structural campaign without executing
the new functional replications.
