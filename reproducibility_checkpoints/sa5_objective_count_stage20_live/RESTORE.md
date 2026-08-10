# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 13

Reason: timing_rep_019_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15,16,17,18,19
```

Archive SHA-256:

```
9216b0e7b4a06e75e4a0fa2e310afa7ef538229a342000aa27fc96239ca5c866
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "9216b0e7b4a06e75e4a0fa2e310afa7ef538229a342000aa27fc96239ca5c866  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
