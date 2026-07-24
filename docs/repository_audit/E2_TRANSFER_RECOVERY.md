# E2 repository-transfer recovery

## Context

The MCAD repository was transferred to the `digitcreadev` GitHub account
through a content-level migration that did not preserve the original Git
history, remote branches, pull requests, or original commit objects.

## Original validated E2 references

The following commit identifiers belonged to the previous repository history:

- `6d39b18` — E2.2 controlled-family implementation and contract
- `888debc` — E2.2 deterministic freeze bundle

These commit objects are not present in the transferred repository and are
recorded here solely as provenance references.

## Recovered scientific content

The transferred working tree contains:

- the E2.1 structural generator;
- the E2.2 controlled-family implementation;
- the E2.2 contract and validation code;
- the canonical controlled campaigns;
- the deterministic E2.2 freeze bundle;
- the deterministic archive and its external SHA-256 checksum.

## Recovery verification

Before recommitting the freeze bundle, the following checks were performed:

- E2.2 contract validation: PASS;
- E2.1 and E2.2 test suites: PASS (`23 passed`);
- internal `SHA256SUMS` verification: PASS;
- deterministic archive checksum verification: PASS.

The recovery commit does not claim to reconstruct the original Git commit
graph. It restores version-controlled preservation and records the provenance
of the transferred E2 artifacts.
