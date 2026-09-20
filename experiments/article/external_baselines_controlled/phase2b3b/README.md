# Phase 2B-3B observation-frame and mapping freeze

This isolated phase defines a deterministic observation frame and data-only Delian mapping descriptors. It performs no baseline, database, container, network, subprocess, benchmark, scoring, threshold, or policy execution.

## Scope

- `projection.py` validates and constructs pre-result and post-result frames.
- `delian_mapping.py` returns immutable-in-practice JSON-compatible descriptor data.
- `observation_frame.schema.json` freezes the interchange contract.
- `mapping_registry.json` records Delian provenance and explicitly deferred methods.
- `fixtures/` contains synthetic contract examples only.

Run only the focused tests described in the preregistration. A later preregistered phase is required before any native baseline execution.
