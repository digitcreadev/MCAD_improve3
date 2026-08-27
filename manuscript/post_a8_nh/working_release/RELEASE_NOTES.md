# MCAD V8.7.6 — Release Notes

**Release ID:** `MCAD-V8.7.6-A8-20260818T234700Z`  
**Scientific predecessor:** A7 candidate package  
**A7 candidate SHA-256:** `19c61f0bdf10bd22d522e359a54f56e97f686f90ed825ef789effa43141d32ea`

## Release purpose
A8 freezes the A7 scientific candidate as an immutable reproducibility release. It does not introduce a new experiment, observation, comparator, theorem, result, bibliographic claim, or manuscript-content change.

## A8-only changes
- deterministic PDF build through `SOURCE_DATE_EPOCH=1787096820`, `FORCE_SOURCE_DATE=1`, `TZ=UTC`, and a fixed locale;
- regenerated resource manifests and SHA-256 inventory;
- release provenance, build-environment record, immutability policy, and reproducibility report;
- exact source/PDF submission package;
- archival ZIP/TAR.GZ generated deterministically.

## Scientific preservation
The `data/`, `figure_sources/`, `figures/`, `literature/`, `results/`, `supplement/`, and `tables/` trees are byte-identical to A7. The EN/FR LaTeX sources are byte-identical to A7. Final PDFs differ at byte level from A7 only because A8 fixes their PDF timestamp/ID deterministically; raster comparison is pixel-identical on all 19 EN and 21 FR pages.

## Post-freeze rule
A9 audits this immutable release. It must not silently mutate this release. If A9 identifies a correction that changes released bytes, the correction must be issued as a superseding release with a new release ID and new checksums.
