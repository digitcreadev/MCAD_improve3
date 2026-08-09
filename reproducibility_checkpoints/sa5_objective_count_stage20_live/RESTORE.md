# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 3

Reason: timing_rep_012_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12
```

Archive SHA-256:

```
b04a1321d5c3f44ca43682f1df0386bdb83db9b598e8ba56205d1b65f09b53fb
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "b04a1321d5c3f44ca43682f1df0386bdb83db9b598e8ba56205d1b65f09b53fb  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
