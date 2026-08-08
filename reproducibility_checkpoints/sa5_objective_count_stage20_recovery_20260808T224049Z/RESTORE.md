# SA5 objective_count Stage-20 recovery checkpoint

Canonical source:

```
branch=paper/phase3-controlled-execution
head=fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Recovered scientific state:

- functional replications 010..019: complete
- timing replication 010: complete
- timing replication 011: interrupted by Codespace restart
- Stage-20 precision bootstrap: not started
- Stage-10 rerun: forbidden

## Reconstruct archive

```bash
cd "reproducibility_checkpoints/sa5_objective_count_stage20_recovery_20260808T224049Z"

cat chunks/sa5_stage20_runtime_recovery.tar.gz.part*   > /tmp/sa5_stage20_runtime_recovery.tar.gz

sha256sum /tmp/sa5_stage20_runtime_recovery.tar.gz
# Expected:
# 77108d696272d2a9ccca91ce165cc43609036e2298c12dc1f2dd824bdf8d333d

tar -tzf /tmp/sa5_stage20_runtime_recovery.tar.gz >/dev/null
```

## Restore runtime

From a checkout of canonical commit:

```bash
cd /workspaces/MCAD_improve3

tar -xzf   /tmp/sa5_stage20_runtime_recovery.tar.gz   -C /workspaces/MCAD_improve3

cp   "reproducibility_checkpoints/sa5_objective_count_stage20_recovery_20260808T224049Z/execute_sa5_stage20_once_v3.py"   /workspaces/execute_sa5_stage20_once_v3.py
```

Do not execute the precision analyzer independently.
Resume only with the exact SA5 environment and the controller's
`--reuse-successful` timing path.
