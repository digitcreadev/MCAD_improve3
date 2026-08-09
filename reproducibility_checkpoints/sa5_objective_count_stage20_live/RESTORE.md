# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 4

Reason: timing_rep_013_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13
```

Archive SHA-256:

```
d523b23612836cc806b927ed1a7ed67d404250ad3d3c3770cb536a6cf16d9e7f
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "d523b23612836cc806b927ed1a7ed67d404250ad3d3c3770cb536a6cf16d9e7f  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
