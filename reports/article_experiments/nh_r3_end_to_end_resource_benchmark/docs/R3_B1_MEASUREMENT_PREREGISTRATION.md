# NH-R3-B1 measurement preregistration

This document freezes R3-B DEV measurement mechanics before implementation
of the measurement runner and before any measured backend query.

## Parent scientific state

- Git HEAD: `32624aa76d91f38086fe101771be139400140f1c`
- R3 binding SHA-256: `a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff`
- R3-A1 freeze SHA-256: `e5d8e6857a22962623aa483eeb92f60cb66aac1e8e98ea3f6a7e060558a42f16`
- R3-A2 freeze SHA-256: `51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a`

No NH-R1, NH-R2, R3-A1, or R3-A2 semantic decision is changed here.

## Frozen semantic authority

R3 actions are controlled exclusively by the frozen NH-R2/R3 binding.

A live MCAD gate result is measurement evidence for gate/NVAC overhead.
It is never allowed to reclassify a frozen R3 action.

## Exact analytical-completion boundary

For each arm, completion occurs at the first frozen candidate whose
post-action `phi_after >= 1.0`, i.e. the first state satisfying:

`C_E^{<=t}(O) = O_req`.

For all 20 DEV sessions, SAFE_PRUNING and PERMISSIVE have the same
completion candidate.

SAFE completion candidate actions:

- EXECUTE: 19
- EXECUTE_FAIL_OPEN: 1

Therefore no SAFE completion boundary depends on a physically pruned
completion candidate.

## Three arms

### UNGATED_EXECUTE_ADMISSIBLE

No MCAD gate or NVAC gate probe is run.
Every frozen admissible candidate is physically executed.
Frozen INADMISSIBLE candidates are not executed.

### PERMISSIVE_GATED

The measurement gate is evaluated for every candidate.
Any real NVAC probe produced by that gate is counted.
The live gate decision is logged but is non-authoritative.
Every frozen admissible candidate is physically executed.

### SAFE_PRUNING

The same measurement gate/probe sequence is run.
The live gate decision is logged but is non-authoritative.

A full query is executed only when frozen `operational_action` is
`EXECUTE` or `EXECUTE_FAIL_OPEN`.

Frozen `PRUNE` suppresses only the full candidate execution.
Probe cost remains treatment cost.

## Required runtime implementation

Before R3-B measurement, implementation must provide two isolated
measurement paths:

1. `/bi/r3/measurement/gate-only`
   - performs MCAD evaluation;
   - may trigger the real NVAC probe;
   - never performs the candidate full execution;
   - never applies a full-result CKG update.

2. `/bi/r3/measurement/full-execute`
   - bypasses MCAD evaluation;
   - executes only through `adventureworks_sql_direct`;
   - uses `adventureworks_direct`;
   - disables fallback;
   - never updates CKG.

This separation prevents the extra physical executions in PERMISSIVE_GATED
from changing the later semantic gate state.

## Cache and warm-up

AdventureWorks SQL Server remains running and warm during the primary pilot.

Before measurement, each unique frozen R3 MDX template is executed once
in lexicographic template-id order through backend-only execution.

Before every arm run, `mcad-api` is restarted outside the measured interval.
This clears its process-local NVAC cache.

A fresh MCAD session is created for each gated arm.

## Timing

`client_wall_ns` starts immediately before candidate 1 arm processing
and ends immediately after candidate 24 arm processing.

`time_to_analytical_objective_completion_ms` uses the same start and stops
immediately after all required gate/probe/full-query work for the frozen
completion candidate has finished.

Container startup, database restoration, warm-up, cgroup snapshots, and
human time are excluded.

## SQL Server resource attribution

Before and after each arm run, outside the wall timer:

- `/sys/fs/cgroup/cpu.stat` -> `usage_usec`;
- `/sys/fs/cgroup/io.stat` -> summed `rbytes` and `wbytes`.

A negative delta invalidates the arm run. It is never clamped.

## Backend-request accounting

`backend_request_count_including_gate_probes` equals:

- physical full-query executions;
- plus uncached physical NVAC SQL probes.

A cache hit is not a backend request.
The MCAD gate HTTP call itself is not counted as a backend request.

Physical response bytes from both full executions and uncached NVAC
probes are summed.

## Paired-block arm randomization

Seed SHA-256:

`2c5986a4c5846bd17802869bc2302ad8edad82dcf0b3d7d8b57096546b885f8f`

Schedule SHA-256:

`6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e`

Position balance:

- position 1: UNGATED_EXECUTE_ADMISSIBLE=7, PERMISSIVE_GATED=7, SAFE_PRUNING=6
- position 2: UNGATED_EXECUTE_ADMISSIBLE=6, PERMISSIVE_GATED=7, SAFE_PRUNING=7
- position 3: UNGATED_EXECUTE_ADMISSIBLE=7, PERMISSIVE_GATED=6, SAFE_PRUNING=7

The frozen schedule is stored in:

`config/r3_b1_arm_order_schedule.csv`

## Claim boundary

This is a DEV instrumentation pilot only.

No confirmatory resource-saving claim is authorized by this preregistration.

No measured R3-B query is authorized until the runtime implementation and
its non-measured preflight have been audited.
