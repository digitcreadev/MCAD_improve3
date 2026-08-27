# A8 Reproducibility Report

**Release ID:** `MCAD-V8.7.6-A8-20260818T234700Z`

## Input admission
- A7 candidate package hash: **PASS** (`19c61f0...d32ea`).
- A7 audit package hash: **PASS** (`d68e21d3...49b9`).
- A7 internal checksum verification: **PASS**.

## Scientific preservation
- EN/FR manuscript source bytes: unchanged from A7.
- `data/`, `figure_sources/`, `figures/`, `literature/`, `results/`, `supplement/`, `tables/`: unchanged from A7.
- New scientific observations: **0**.
- New experimental executions: **0**.

## Deterministic build
The release build fixes `SOURCE_DATE_EPOCH=1787096820`, enables `FORCE_SOURCE_DATE=1`, uses UTC, and fixes the locale. Two independent clean builds produced byte-identical PDFs:
- EN SHA-256: `34c5d20ee5bb2328b453c1d2029df98dd3eb5a20066d56bc94a221ac4e032a66` — 19 pages;
- FR SHA-256: `86f79d7b1944a71eac62c66588aa9de5e1bacf6d5ca0937e83bcd2a36692ccf0` — 21 pages.

## Visual preservation
Compared with A7, the rebuilt PDFs are pixel-identical after rasterization on all **19/19 EN** pages and **21/21 FR** pages. The PDF byte hashes differ from A7 only because A8 fixes PDF timestamps/IDs deterministically.

## Final LaTeX diagnostics
No unresolved citation/reference remains in the final `.log` files. Existing non-blocking typography diagnostics are preserved: the known ~3.60 pt `Overfull \hbox` and small output `Overfull \vbox` warnings do not produce visible clipping in the audited render.

## Rebuild command
```bash
./BUILD.sh
```

Exact release/submission archive hashes are recorded outside the content-addressed tree in `MCAD_A8_DELIVERABLE_SHA256SUMS.txt`.
