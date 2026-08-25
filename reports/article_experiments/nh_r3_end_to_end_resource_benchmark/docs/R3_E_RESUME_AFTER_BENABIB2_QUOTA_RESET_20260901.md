# R3-E recovery plan after benabib2 Codespaces quota reset

## Frozen rupture anchor

The scientific repository was migrated to `benabib03` before the old Codespace became inaccessible.

- Branch: `paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z`
- Frozen pre-migration E2 commit: `c7f727db7b5c67c161e6357bb2dde4f3cf313d62`
- Old account/Codespace: `benabib2` / `shiny pancake`
- Expected quota reset: 2026-09-01
- Old Codespace must not be deleted before bundle recovery.
- R3-D/D4/E0/E1/E2-old-host are frozen. No scientific rerun is authorized.

## Blocked local-only bundle

Expected path on the old Codespace:

`/workspaces/MCAD_R3E_CODESPACE_MIGRATION_BUNDLE_20260824`

Expected critical hashes:

- `AdventureWorksDW2022.bak`
  - bytes: `101834752`
  - SHA-256: `ac4a39502645c31f114331be28ce671ac5f70b0645f2aa59d8dccfbaae081c05`
- `exact_runtime_images.tar`
  - bytes: `794181632`
  - SHA-256: `22eba9990c871c0fb719757d0310d2e1609f4d9bddcb0b0665f35c1f8f02a7fd`
- `MCAD_improve3_branch.bundle`
  - SHA-256: `99d27dd4dcba9768471dff97d6b510a871a138ff08e228d9a93236723e03dead`

The image archive contains the exact frozen SQL Server, MCAD API and MCAD proxy images.
It contains no exact eMondrian AdventureWorks image because E2 found none on the old host.

## Resume sequence - do not skip or reorder

1. Reopen `shiny pancake` after quota renewal. Do not start Docker services and do not rerun any benchmark.
2. Verify the existing bundle before copying:

```bash
cd /workspaces/MCAD_R3E_CODESPACE_MIGRATION_BUNDLE_20260824
sha256sum -c SHA256SUMS.txt
sha256sum AdventureWorksDW2022.bak exact_runtime_images.tar MCAD_improve3_branch.bundle
```

3. Require the exact hashes recorded above. If any mismatch occurs: STOP.
4. Copy the bundle off the old Codespace to a durable local location. Prefer old Codespace -> local PC -> new Codespace. A private forwarded HTTP port is an acceptable fallback if GitHub CLI is unavailable.
5. In `benabib03`, copy the bundle to `/workspaces/` and run `sha256sum -c SHA256SUMS.txt`. Require all entries `OK`.
6. Do not run `docker load` yet.
7. Re-run only the host-specific E2 read-only preflight on the new Codespace:
   - planned ports;
   - absence of `mcad-r3e-xmla1` objects;
   - available disk;
   - credential material presence without printing values;
   - local exact eMondrian image discovery;
   - bundle/seed/image-archive presence and hashes.
8. Combine the verified bundle facts, the new-host E2 facts and the frozen eMondrian pinning decision into a new static materialization-authorization checkpoint.
9. Only after that checkpoint may `docker load`, SQL restore, isolated runtime creation or eMondrian materialization occur.
10. Validate the isolated XMLA path mechanically.
11. Only after mechanical validation may the frozen R3-E 300-session / 900-arm-run campaign begin.
12. Analyze/freeze R3-E, then perform R3-F and handoff to NH-R4.

## Absolute no-redo rules

- Never rerun R3-D SQL Direct.
- Never recompute D4 confirmatory inference.
- Never reuse the interrupted D3 partial 297-arm attempt.
- Never rerun historical XMLA Q1-Q6.
- Never substitute rebuilt SQL/API/proxy images for the blocked exact image archive.
- Never build eMondrian from `releases/latest`.
