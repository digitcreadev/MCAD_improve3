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

## Primary metrics
- full backend executions;
- all backend requests, including gate/NVAC probes;
- client wall-clock time;
- SQL Server cgroup CPU usage delta (`cpu.stat`);
- SQL Server cgroup I/O read/write byte deltas (`io.stat`);
- response bytes;
- session time-to-objective.

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

## Held-out discipline
Dev pilot = instrumentation only. Validation may fix measurement mechanics but
not optimize effect sizes. Confirmatory test binding and inclusion are frozen
before test execution.
