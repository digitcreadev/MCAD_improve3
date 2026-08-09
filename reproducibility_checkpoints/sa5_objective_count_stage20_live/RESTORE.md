# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 7

Reason: timing_rep_014_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14
```

Archive SHA-256:

```
2b2c8e0975d2c3726fa1913e14608c11e69edc531debc72c9510058f2addeaf0
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "2b2c8e0975d2c3726fa1913e14608c11e69edc531debc72c9510058f2addeaf0  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
