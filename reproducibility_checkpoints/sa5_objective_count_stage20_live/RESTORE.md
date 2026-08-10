# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 9

Reason: timing_rep_016_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15,16
```

Archive SHA-256:

```
4b70813780398b35d9641ebacf7cdd5ab8743f4ccc0259f3efd637e96ad59345
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "4b70813780398b35d9641ebacf7cdd5ab8743f4ccc0259f3efd637e96ad59345  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
