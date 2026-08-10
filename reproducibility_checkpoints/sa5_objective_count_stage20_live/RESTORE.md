# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 12

Reason: timing_rep_018_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15,16,17,18
```

Archive SHA-256:

```
f9a3bb52730b6a998e6ea0837d92be9ee659415753dcfd9495fe9bfc4ad4a585
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "f9a3bb52730b6a998e6ea0837d92be9ee659415753dcfd9495fe9bfc4ad4a585  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
