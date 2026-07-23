# V9.4.1.1 — Pure SAT Canonicalization Boundary

## Purpose

This patch fixes the architectural boundary introduced by V9.4.1.

V9.4.1 moved the formal SAT(QP) checks from `bi-stack/mcad-api/app.py` to the backend module `backend/mcad/formal_sat.py`. That was correct conceptually, but the first implementation still allowed the backend SAT module to know the physical `/bi/nvac-probe` endpoint.

V9.4.1.1 makes the boundary explicit:

```text
/backend/mcad/formal_sat.py
  defines formal SAT(QP) and nvac_ok(QP) as pure backend logic.

/bi-stack/mcad-api/app.py
  may provide a bounded physical nvac_probe callback to the backend SAT function.

/bi-stack/mcad-proxy/app.py
  owns the physical /bi/nvac-probe endpoint and DW interaction.
```

## Main rule

`backend/mcad/formal_sat.py` must not import or call any physical BI dependency:

- no `requests`, `httpx`, `aiohttp`, `urllib`;
- no `FastAPI` route;
- no `execute_direct_query`;
- no `forward_xmla`;
- no `MCAD_NVAC_PROBE_URL`;
- no hard-coded `mcad-proxy` or `/bi/nvac-probe` URL.

## New backend contract

`evaluate_sat_formal_clauses` now exposes an optional callback:

```python
evaluate_sat_formal_clauses(
    query_spec,
    objective_id,
    mdx="",
    nvac_probe=None,
)
```

If static metadata proves `nvac_ok`, the callback is not needed. If static metadata is insufficient, the backend calls the optional callback when supplied. If no callback is supplied, uncertain non-vacuity remains unproven and is blocked conservatively.

## Integration-side callback

`bi-stack/mcad-api/app.py` now owns the HTTP call to `/bi/nvac-probe` through `_mcad_api_call_nvac_probe`. It passes this callback to the backend:

```python
formal_sat_eval = _evaluate_sat_formal_clauses(
    query_spec,
    objective_id,
    payload.mdx,
    nvac_probe=_mcad_api_call_nvac_probe,
)
```

This preserves the separation:

```text
/backend decides.
/bi-stack observes/probes physical reality when asked.
```

## Validation commands

```bash
grep -nE "requests|httpx|aiohttp|urllib|socket|subprocess|FastAPI|APIRouter|execute_direct_query|direct_executor|forward_xmla|xmla|emondrian|docker|psycopg2|pyodbc|sqlalchemy|duckdb|sqlite3|pymysql|MCAD_NVAC_PROBE_URL|nvac-probe" backend/mcad/formal_sat.py \
  || echo "OK: formal_sat.py has no physical BI dependency"

PYTHONPATH=$PWD/backend python - <<'PY'
from mcad.formal_sat import evaluate_sat_formal_clauses
import inspect
sig = inspect.signature(evaluate_sat_formal_clauses)
print(sig)
print("has_nvac_probe =", "nvac_probe" in sig.parameters)
PY

PYTHONPATH=$PWD/backend python -m py_compile backend/mcad/formal_sat.py
PYTHONPATH=$PWD/backend python -m py_compile bi-stack/mcad-api/app.py
PYTHONPATH=$PWD/backend pytest -q backend/tests/test_formal_sat_canonical.py
```

Expected:

```text
OK: formal_sat.py has no physical BI dependency
has_nvac_probe = True
5 passed
```
