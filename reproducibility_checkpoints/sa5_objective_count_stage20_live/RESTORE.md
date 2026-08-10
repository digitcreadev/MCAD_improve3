# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 8

Reason: timing_rep_015_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15
```

Archive SHA-256:

```
8466a01253f2fda0edb1a8022cde0656a021c2debefefe2b8c1c1f077e9965dc
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "8466a01253f2fda0edb1a8022cde0656a021c2debefefe2b8c1c1f077e9965dc  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
