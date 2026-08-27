# A8 Decision Log Addendum

## D-A8-001 — A7 is the scientific content baseline
A8 does not alter manuscript claims, data, figures, tables, bibliography, or formal supplements inherited from A7.

## D-A8-002 — Build reproducibility is hardened rather than merely visually checked
A fixed `SOURCE_DATE_EPOCH`, UTC, forced source date, and fixed locale are part of the release build contract.

## D-A8-003 — PDF bytes may differ from A7 without scientific/render change
A8 intentionally regenerates PDF metadata/IDs deterministically. All rasterized pages remain pixel-identical to A7.

## D-A8-004 — A9 may audit but may not silently mutate A8
Any post-A8 correction that changes bytes creates a superseding release with a new identifier and checksum set.
