# MCAD V8.7.6 — Immutable Reproducibility Release

This directory is the frozen scientific release of **MCAD V8.7.6** after A7 claim consolidation and A8 reproducibility hardening.

A8 introduces **no new experiment, numerical observation, comparator implementation, theorem, scientific claim, or manuscript-content change**. It freezes the A7 scientific candidate, makes the PDF build byte-reproducible through a fixed `SOURCE_DATE_EPOCH`, regenerates manifests/checksums, records provenance and release notes, and creates an exact submission package.

Build both manuscripts with:

```bash
./BUILD.sh
```

The default deterministic build timestamp is `2026-08-18T23:47:00Z` (`SOURCE_DATE_EPOCH=1787096820`). A caller may override `SOURCE_DATE_EPOCH`, but exact release hashes correspond to the default value.

See `RELEASE_NOTES.md`, `traceability/A8_REPRODUCIBILITY_REPORT.md`, `traceability/PROVENANCE_A8.json`, and `traceability/IMMUTABILITY_POLICY.md`.
