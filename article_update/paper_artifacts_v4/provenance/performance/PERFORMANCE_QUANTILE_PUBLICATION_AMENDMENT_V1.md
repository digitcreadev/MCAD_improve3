# Performance quantile publication amendment

Date: 2026-08-14

Purpose: restore the p50/p95/p99 performance-evaluation structure used in
earlier manuscript versions without reusing their historical numerical values.

Rules:
- no scientific campaign rerun;
- no timing execution;
- no bootstrap rerun;
- p50/p95/p99 are deterministically derived from already-existing canonical
  wall_latency_ms observations for constraint_count, virtual_node_count and
  membership_density;
- p99 is descriptive only; no p99 confidence-interval/precision claim is made;
- objective_count Stage-30 absolute timing remains excluded because its
  terminal execution manifest states absolute_timing_magnitudes_interpreted=false;
- semantic-decision latency must never be conflated with backend SQL/XMLA latency;
- old V-1/V0/V1/V2 numbers are methodological/visual precedents only.
