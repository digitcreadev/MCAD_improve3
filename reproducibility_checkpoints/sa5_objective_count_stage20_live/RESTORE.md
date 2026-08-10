# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 10

Reason: timing_rep_017_validated_complete

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10,11,12,13,14,15,16,17
```

Archive SHA-256:

```
b95c6009ee132aaf325dec205f2eb4dd3b9eb73b5f0dc269289a5fc1c99ad6cd
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "b95c6009ee132aaf325dec205f2eb4dd3b9eb73b5f0dc269289a5fc1c99ad6cd  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
