# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 6

Reason: interrupted_rep_014_preserved_before_resume

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
48b234fa2c41d59650effcae42d81061489c6223c4a6b82569e067c18a6379ef
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "48b234fa2c41d59650effcae42d81061489c6223c4a6b82569e067c18a6379ef  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
