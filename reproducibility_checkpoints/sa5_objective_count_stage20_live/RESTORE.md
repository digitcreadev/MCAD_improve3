# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 5

Reason: controller_failure_before_rep_014_completion

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
ba18e86e4e2bb133a8f30e7741be23278119f628557eef2f7cac436c86686697
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "ba18e86e4e2bb133a8f30e7741be23278119f628557eef2f7cac436c86686697  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
