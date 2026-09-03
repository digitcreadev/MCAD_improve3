# R3-E14 D9 raw measured evidence freeze

This is the byte-preserving freeze of the completed D8-A3 replacement primary-300 measurement.

Recovery provenance:
- D9-R0 published the base raw-freeze authorization and then failed on an over-escaped mechanical ordinal regex.
- D9-R1 was separately authorized, corrected the ordinal validation, and then failed because GNU tar positional option `--no-recursion` was placed after `-T -`.
- D9-R2A audited that failure read-only, preserved the eight-file R1 staging including its partial arm archive, prohibited reuse of that partial archive, and validated the corrected tar ordering with a non-scientific canary.
- D9-R2B was separately authorized and rebuilt the freeze from original D8-A3 sources into a completely fresh staging directory. No R1 staging file was deleted, overwritten, or reused as archive input.

Raw evidence frozen:
- 900 arm receipt JSON files in deterministic lossless tar/gzip archive parts;
- 900 candidate trace JSON files in deterministic lossless tar/gzip archive parts;
- one primary summary JSON;
- D8-A3 execution receipt;
- pre-execution Codespaces quota receipt;
- Compose binding receipt;
- complete D8-A3 run-primary console log.

RAW_SOURCE_SHA256SUMS authenticates all 1801 original files under the D8-A3 output directory. After archive creation, all 1800 archived JSON members are stream-hashed and compared byte-for-byte with that source manifest.

Scientific boundary:
- no measurement reexecution;
- no effect analysis;
- no interim effect look;
- no cross-arm comparison;
- no scientific inference;
- no scientific interpretation of primary-summary, arm-receipt, or candidate-trace values.

A separate D10 inference authorization is mandatory before any scientific effect analysis.
