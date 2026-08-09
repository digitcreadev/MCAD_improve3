# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 2

Reason: timing_rep_011_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11
```

Archive SHA-256:

```
002289c13fb124aad093a1ce3f5106794d3d5a9a62ff84c0c2ed214d1ab69085
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "002289c13fb124aad093a1ce3f5106794d3d5a9a62ff84c0c2ed214d1ab69085  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
