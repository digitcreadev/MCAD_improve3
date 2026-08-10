# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 11

Reason: interrupted_rep_018_preserved_before_resume

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15,16,17
```

Archive SHA-256:

```
5d9ea683d09143cb5eb9e6cee537a31f208cc0769918d4310b80a538fc7e5903
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "5d9ea683d09143cb5eb9e6cee537a31f208cc0769918d4310b80a538fc7e5903  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
