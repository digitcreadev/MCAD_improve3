# Measurement protocol

## Arms
1. `UNGATED_EXECUTE_ADMISSIBLE`: practical break-even comparator.
2. `PERMISSIVE_GATED`: runs the same semantic gate/probes as treatment but
   executes every admissible full query.
3. `SAFE_PRUNING`: same gate/probes, but suppresses only R1-proven safe-prunable
   full backend queries.

The primary causal comparison is `SAFE_PRUNING` vs `PERMISSIVE_GATED`.
The ungated arm is secondary and answers whether the complete deployment
overhead breaks even against no strategic gate.

## Primary physical metrics
- full backend executions;
- all backend requests, including gate/NVAC probes;
- client wall-clock time;
- SQL Server cgroup CPU usage delta (`cpu.stat`);
- SQL Server cgroup I/O read/write byte deltas (`io.stat`);
- response bytes;
- `time_to_analytical_objective_completion_ms`.

## Analytical-completion timing contract
`time_to_analytical_objective_completion_ms` starts immediately before the
first candidate-policy evaluation of the measured session, after prescribed
backend readiness and warm-up.

It stops at the first state where:

`C_E^{<=t}(O) = O_req`.

It includes MCAD gate reasoning, NOVC/NVAC probes, full backend executions, and
attributable client/backend waiting before completion.

It excludes container startup, database restore, one-time environment
preparation, and all human/organizational decision time.

It is **not** time-to-decision.

## Semantic gate instrumentation
For reporting clarity, R3 distinguishes conceptually:
- `semantic_admissibility_pre_nvac`: conjunction of the non-NVAC semantic clauses;
- `evidence_realizability_nvac`: non-vacuity/realizability result;
- existing overall gate result: unchanged conjunction used by the implementation.

This is a reporting/contract refinement. It does not relabel frozen NH-R1/NH-R2
rows and does not alter the deterministic binding.

## Secondary metrics
When available after backend startup:
- SQL Server `STATISTICS IO` logical/physical/read-ahead reads;
- SQL Server `STATISTICS TIME` CPU and elapsed milliseconds;
- memory-current sampling / memory-time;
- eMondrian cgroup CPU and I/O for the XMLA replication path.

## Cache/order control
Primary runs use a fixed warm-up followed by paired blocks with randomized arm
order under a frozen seed. Cold-start behavior is a sensitivity analysis, not
the primary estimate.

## Gate overhead rule
Any resource consumed by semantic evaluation or a backend/NVAC probe belongs to
the treatment cost. We never infer resource saving merely from the absence of a
full-query execution.

`PRUNE != zero backend interaction`.

## Held-out discipline
Dev pilot = instrumentation only. Validation may fix measurement mechanics but
not optimize effect sizes. Confirmatory test binding and inclusion are frozen
before test execution.
