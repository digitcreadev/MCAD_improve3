# A8 Immutability Policy

1. `MCAD-V8.7.6-A8-20260818T234700Z` is content-addressed by the SHA-256 manifests produced at A8.
2. No file in the frozen release may be overwritten in place after publication/archival.
3. A9 is an audit of the frozen release, not an in-place editing stage.
4. Any correction requiring a byte change creates a superseding release (for example `V8.7.6-r1`) and must cite the superseded release and its hashes.
5. Historical experimental observations remain immutable; re-aggregation may be added only as a separately identified derived artifact.
6. Rebuilding with the release-default `SOURCE_DATE_EPOCH=1787096820` must reproduce the final EN/FR PDFs byte-for-byte in the recorded build environment.
