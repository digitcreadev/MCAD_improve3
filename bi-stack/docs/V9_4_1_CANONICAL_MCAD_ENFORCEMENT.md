# V9.4.1 — Canonical MCAD Enforcement

## Purpose

This patch consolidates the formal SAT(QP) layer used by the BI stack into the canonical backend package.

The architectural rule is:

```text
/backend defines MCAD.
/bi-stack consumes MCAD.
/bi-stack must not redefine ALLOW/BLOCK or SAT(QP) locally.
```

## Main change

The formal SAT(QP) functions that were previously embedded in:

```text
bi-stack/mcad-api/app.py
```

are now centralized in:

```text
backend/mcad/formal_sat.py
```

The BI API now imports the canonical backend function:

```python
from mcad.formal_sat import evaluate_sat_formal_clauses as _evaluate_sat_formal_clauses
```

## What remains in bi-stack

`/bi-stack` still owns integration duties:

- UI and scenario runner;
- `mcad-proxy`;
- Docker services;
- BI execution adapters;
- bounded `/bi/nvac-probe` endpoint;
- result display and report export.

## What moves to backend

`/backend` owns the formal MCAD model:

- `SAT(QP)` clauses;
- `grain_ok`, `agg_ok`, `unit_ok`, `slc_ok`, `time_ok`, `nvac_ok`;
- formal evidence contract;
- reason-code mapping for SAT failures.

## nvac_ok probe contract

The physical probe endpoint remains in the proxy:

```text
POST /bi/nvac-probe
```

It is not an analytical user execution path. It is a bounded non-vacuity probe used only by the canonical formal SAT layer when static evidence is insufficient. It must not update the CKG and must not be called by the UI Run buttons.

## Validation

Run:

```bash
PYTHONPATH=$PWD/backend python -m py_compile backend/mcad/formal_sat.py
PYTHONPATH=$PWD/backend python -m py_compile bi-stack/mcad-api/app.py
PYTHONPATH=$PWD/backend pytest -q backend/tests/test_formal_sat_canonical.py
```

Expected result:

```text
3 passed
```

## Scientific significance

This change strengthens the article/soutenance position:

```text
The BI demonstrator uses the same canonical MCAD formal layer as the backend scientific core. The proxy and adapters execute only after MCAD evaluation; they do not decide ALLOW/BLOCK independently.
```
