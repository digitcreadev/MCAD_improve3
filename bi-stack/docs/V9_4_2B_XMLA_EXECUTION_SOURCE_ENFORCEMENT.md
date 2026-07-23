# V9.4.2b — XMLA Execution Source Enforcement

## Purpose

This patch connects the main UI execution path (`/bi/execute`) to the hybrid execution gateway and makes the data-warehouse selection explicit and auditable.

The UI now lets the user choose between:

- `foodmart` — **FoodMart via XMLA/eMondrian**
- `foodmart_sql_direct` — **FoodMart via Direct BI**

## Enforced behavior

1. `/bi/execute` still calls MCAD `/eval` before any physical execution.
2. If MCAD returns `BLOCK`, no physical execution is performed.
3. If MCAD returns `ALLOW`, `/bi/execute` calls `get_gateway().execute(...)`.
4. The gateway dispatches by `dw_id`:
   - `foodmart` -> `xmla_mondrian_adapter`
   - `foodmart_sql_direct` -> `foodmart_direct_adapter`
5. Silent fallback is disabled by default. SQL Direct fallback is attempted only when the request explicitly sends `allow_fallback=true`.
6. The UI displays the selected execution path instead of the old fixed `BI direct` label.

## Files changed

- `bi-stack/mcad-proxy/app.py`
- `bi-stack/mcad-proxy/session_ui.html`
- `bi-stack/mcad-proxy/datawarehouses.yaml`
- `bi-stack/mcad-proxy/execution/gateway.py`
- `bi-stack/mcad-proxy/execution/registry.py`
- `bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py`
- `bi-stack/scripts/check_foodmart_xmla_regression.sh`

## Validation commands

```bash
PYTHONPATH=$PWD/bi-stack/mcad-proxy python -m py_compile   bi-stack/mcad-proxy/execution/adapters/base.py   bi-stack/mcad-proxy/execution/adapters/foodmart_direct_adapter.py   bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py   bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py   bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py   bi-stack/mcad-proxy/execution/registry.py   bi-stack/mcad-proxy/execution/gateway.py   bi-stack/mcad-proxy/app.py
```

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d emondrian pivot4j mcad-api mcad-proxy
bash bi-stack/scripts/check_foodmart_xmla_regression.sh . live
```

## Expected UI demonstration

1. Create a fresh session with objective `O_REAL_BEER_WA_MONTH`.
2. Choose `FoodMart via XMLA/eMondrian`.
3. Run Q1. The result metadata should show XMLA/eMondrian execution.
4. Create another fresh session or switch DW to `FoodMart via Direct BI`.
5. Run the same Q1. The result metadata should show Direct BI execution.
