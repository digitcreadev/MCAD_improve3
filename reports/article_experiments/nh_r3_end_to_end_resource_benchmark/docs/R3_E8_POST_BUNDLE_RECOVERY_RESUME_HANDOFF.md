# R3-E8 post-bundle recovery resume handoff

## Authoritative pre-bundle checkpoint

R3-E7 is frozen at `18f6c02c351c7c257c5f108f3dafb972095eeb14`. R3-E8 closes the currently authorized bundle-independent experimental lane. This handoff does not authorize runtime materialization, backend I/O, measured execution, or real inference.

## Old-Codespace bundle authority

Source directory on the old `benabib2` Codespace:

`/workspaces/MCAD_R3E_CODESPACE_MIGRATION_BUNDLE_20260824`

Critical artifacts:

- `AdventureWorksDW2022.bak`
  - SHA-256: `ac4a39502645c31f114331be28ce671ac5f70b0645f2aa59d8dccfbaae081c05`
  - bytes: `101834752`
- `exact_runtime_images.tar`
  - SHA-256: `22eba9990c871c0fb719757d0310d2e1609f4d9bddcb0b0665f35c1f8f02a7fd`
  - bytes: `794181632`
- `MCAD_improve3_branch.bundle`
  - SHA-256: `99d27dd4dcba9768471dff97d6b510a871a138ff08e228d9a93236723e03dead`
  - no longer critical for Git recovery because the branch already migrated and advanced on `benabib03`

Do not delete the old Codespace before these artifacts are recovered and re-verified in a durable location and on the new Codespace.

## Exact image identities expected after authorized load

- SQL Server: `sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89`
- MCAD API: `sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840`
- MCAD proxy: `sha256:2494827f7dda2769fcd80e1659bbb2520b0aafe52fdefdc79e6fff07db0fe6b4`

## eMondrian authority already frozen independently of the bundle

- release tag: `v9.3.0.6`
- tag commit: `d2006c162fcc6c4e7ec90a0c03485056696134ad`
- WAR SHA-256: `100895f17acd4e4d3e3af58c2fbd442d95ca71fb969169d4c1a66acb974c52db`
- Tomcat linux/amd64 digest: `sha256:81be7f8d435228148a6419d5e967e6c31f094ec3a492055b42c66d2bb775627c`
- MSSQL JDBC SHA-256: `3b1a70145dbaff98daa70022791e15becfb2b9534cc9e8cfaa1bdba6a3edeb8e`
- WEB-INF manifest SHA-256: `cb2b90d9627202df6063cb61037b161de231d9f91630b835dd514f141f8abb50`

This defines a new reproducible R3-only eMondrian runtime. It does not authorize a claim of byte identity with the historical eMondrian image.

## Resume sequence after the old Codespace can be accessed

1. Start the old Codespace only for artifact recovery. Do not start historical services or benchmarks.
2. Run `sha256sum -c SHA256SUMS.txt` in the migration-bundle directory and separately verify the critical artifact hashes above.
3. Transfer the bundle to a durable local copy and then to the `benabib03` Codespace.
4. Run `sha256sum -c SHA256SUMS.txt` again on the destination. Stop on any mismatch.
5. Do **not** run `docker load` yet.
6. Run only the new-host E2 read-only revalidation: planned ports, absence of `mcad-r3e-xmla1` objects, free disk, credential presence without printing values, seed/bundle hashes, and eMondrian exact local discovery.
7. Freeze a distinct materialization-authorization checkpoint that binds the verified bundle, new-host E2 facts, and the already frozen E3C-E7 authorities.
8. Only after that authorization: load exact SQL/API/proxy images, verify image IDs, build the pinned R3-only eMondrian image, restore AdventureWorks, and create the isolated runtime.
9. Run mechanical XMLA validation. Do not rerun the historical XMLA Q1-Q6 evidence.
10. Only after an explicit measured-execution authorization, run the frozen 300-session / 900-arm R3-E cohort.
11. Freeze integrity before any real inference. The E7 engine currently has no measured-data CLI by design.
12. After a separate analysis authorization, analyze/freeze R3-E, then perform R3-F and continue to NH-R4.

## Prohibited shortcuts

Do not replace missing historical SQL/API/proxy images with substitutes, do not use `latest`, do not rebuild historical artifacts, do not recompute D4, do not rerun SQL Direct, and do not infer or fabricate pending XMLA results.
