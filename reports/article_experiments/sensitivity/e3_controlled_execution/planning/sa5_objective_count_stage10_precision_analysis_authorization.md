# SA5 objective-count Stage-10 precision-analysis authorization

Status: authorization preregistered, pending merge.

This authorization fixes the exact factor-compatible analyzer,
materialized inputs, bootstrap protocol, precision targets and
decision rule for the single canonical SA5 precision execution.

The authorization is NOT effective before this authorization commit
is merged into `paper/phase3-controlled-execution`.

After merge, one canonical precision/bootstrap execution is authorized
with explicit factor `objective_count`.

No timing values were read or interpreted while creating this
authorization. No precision/bootstrap analysis has yet been performed.

Result interpretation, scientific freeze and manuscript integration
remain downstream steps governed by the preregistered precision gate.
