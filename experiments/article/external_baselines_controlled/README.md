# Controlled external-baseline adapters (Phase 2B-3A)

This isolated package defines contracts and provenance-only adapter skeletons for
external methods considered alongside MCAD.  It produces **no benchmark
measurements** and makes no claim of experimental superiority, runtime
integration, or equivalence to MCAD's `ALLOW`/`BLOCK` decisions.

The Delian adapters only package caller-supplied native outputs.  They do not
start a database or execute a query.  Djedaini/IDEB is structurally blocked and
ASSESS is supported only by its frozen build/test-compilation evidence; both are
non-executable status stubs.  In every result,
`normalized_binary_decision` is unconditionally `null`.

## Layout

* `registry.yaml` is a JSON-compatible YAML registry of the four frozen adapter
  entries. `source_repository` and `source_ref` pin the audited code checkout;
  `publication_reference` separately retains its DOI (and the ASSESS release).
  Keeping it in the JSON subset avoids adding a YAML runtime dependency.
* `contract.schema.json` describes both registry entries and result envelopes.
* `adapters/` contains side-effect-free result builders and blocked stubs.
* `provenance/a9_freeze_reference.json` pins the closed A9 evidence digest.
* `tests/` checks the contract and scientific guardrails without network,
  database, Docker, or workload execution.

Run only the scoped checks with:

```bash
python -m pytest -q experiments/article/external_baselines_controlled/tests
```
