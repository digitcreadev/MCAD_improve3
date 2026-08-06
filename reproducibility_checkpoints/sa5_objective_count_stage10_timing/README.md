# SA5 objective-count Stage-10 timing checkpoints

This directory is a detached, repository-tracked persistence surface for the
SA5 objective-count Stage-10 timing campaign.

Source branch: `paper/phase3-controlled-execution`
Source commit: `dec3785432366fb64b68123419ac31f640476313`

## Scientific controls

- Replication files are copied only after structural validation.
- Validation reads structural CSV columns only:
  `cell_id`, `phase`, `phase_round`, and `factor_level`.
- Timing-value columns are not interpreted.
- Precision analysis, bootstrap analysis, and manuscript modification remain
  outside this checkpoint process.
- Each completed replication is committed and pushed separately on
  `evidence/sa5-objective-count-stage10-timing-checkpoints-20260806`.

## Recovery

A new clone can check out `evidence/sa5-objective-count-stage10-timing-checkpoints-20260806`. The repository history,
planning contract, execution specifications, detached control-plane metadata,
environment inventory, and every checkpointed replication will be available
under this directory.

The active scientific branch is deliberately not advanced while the timing
runner is operating. This avoids invalidating the exact-HEAD resume gate.
