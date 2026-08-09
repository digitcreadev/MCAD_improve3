# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: 1

Reason: interrupted_rep_011_preserved_before_resume

Canonical commit:

```
fd7d87e5658b63c0753a9686b43ec2e5e2d17344
```

Completed Stage-20 timing replications:

```
10
```

Archive SHA-256:

```
eb40a3fbbb8b2912e0378ae9a3f30eb7346ddac9559f36badf14aaf0dbaa6ae0
```

Reconstruct with:

```bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "eb40a3fbbb8b2912e0378ae9a3f30eb7346ddac9559f36badf14aaf0dbaa6ae0  /tmp/sa5_stage20_runtime_latest.tar.gz" \
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \
  -C /workspaces/MCAD_improve3
```

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
