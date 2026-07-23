# V9.5.2e — AdventureWorks NVAC Probe Wiring Fix

## Problem

After V9.5.2d, the AdventureWorks objective and scenario validate correctly and `slc_ok` is no longer the blocker. However, live evaluation still blocks the three expected ALLOW queries with `nvac_ok=false` and `hybrid_probe_unavailable_strict_false`.

The session report shows that static SAT clauses such as `grain_ok`, `agg_ok`, `unit_ok`, `slc_ok`, and `time_ok` pass, while `nvac_ok` fails because the bounded physical probe is unavailable. In Docker, this is most often caused by `mcad-api` targeting the wrong internal proxy port or not wiring the optional `nvac_probe` callback into canonical `backend/mcad/formal_sat.py`.

## Fix

This patch:

- sets the Docker-internal NVAC probe URL to `http://mcad-proxy:9000/bi/nvac-probe`;
- declares `MCAD_NVAC_MODE=hybrid` and `MCAD_NVAC_PROBE_URL` in `docker-compose.yml` for `mcad-api`;
- ensures `mcad-api` calls canonical formal SAT with `nvac_probe=_mcad_api_call_nvac_probe`;
- forwards `dw_id` and `dataset` in the probe payload and cache key;
- keeps `backend/mcad/formal_sat.py` pure: it receives a callback but performs no HTTP/BI I/O itself.

## Expected result

AdventureWorks validation should move from:

```json
{
  "overall_status": "FAIL",
  "passed_steps": 3,
  "total_steps": 6,
  "physical_allow_count": 0,
  "block_no_execution_count": 3
}
```

to:

```json
{
  "overall_status": "PASS",
  "passed_steps": 6,
  "total_steps": 6,
  "physical_allow_count": 3,
  "block_no_execution_count": 3
}
```

## Commands

```bash
python bi-stack/scripts/apply_adventureworks_nvac_probe_wiring_fix.py .
bash bi-stack/scripts/check_adventureworks_nvac_probe_wiring_fix.sh .

docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-api
docker compose -f bi-stack/docker-compose.yml up -d adventureworks-sqlserver mcad-api mcad-proxy

bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .
bash bi-stack/scripts/run_adventureworks_demo_validation.sh .
```

## Optional live probe smoke test

```bash
curl -s -X POST http://127.0.0.1:9000/bi/nvac-probe \
  -H 'Content-Type: application/json' \
  -d '{"dw_id":"adventureworks_sql_direct","dataset":"AdventureWorksDW","mdx":"SELECT {[Measures].[SalesAmount]} ON COLUMNS, CrossJoin([Date].[Calendar].[Month].Members, [Sales Territory].[Sales Territory].[Sales Territory Region].Members) ON ROWS FROM [Adventure Works DW] WHERE ([Product].[Product Category].[Bikes], [Sales Territory].[Sales Territory Group].[Europe], [Date].[Calendar Year].[2013])"}' \
  | python -m json.tool
```

Expected fields: `ok=true`, `non_empty=true`, `count > 0`, `dw_id=adventureworks_sql_direct`.
