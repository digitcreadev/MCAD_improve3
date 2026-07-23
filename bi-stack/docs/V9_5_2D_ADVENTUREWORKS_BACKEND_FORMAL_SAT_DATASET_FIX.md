# MCAD V9.5.2d — AdventureWorks Backend Formal SAT Dataset Fix

## Purpose

V9.5.2c patched only the `bi-stack/mcad-api/app.py` side in some deployments. However, the Docker compose configuration mounts the canonical backend into `mcad-api` with:

```yaml
../backend:/app/backend:ro
```

Therefore, the actual `slc_ok` and `nvac_ok` logic used at runtime is `backend/mcad/formal_sat.py`. V9.5.2d patches that canonical file directly.

## Fixes

- Adds dataset-aware known-member dictionaries to `backend/mcad/formal_sat.py`.
- Keeps FoodMart member validation unchanged.
- Adds AdventureWorksDW valid members such as `Bikes`, `Accessories`, `Europe`, `2013`.
- Ensures `slc_ok` uses the dataset-specific dictionary.
- Ensures `nvac_ok` uses the dataset-specific dictionary.
- Forwards `dw_id` and `dataset` to the NVAC probe.
- Preserves `dw_id` and `dataset` at the formal SAT entry point.

## Expected Result

The AdventureWorks validation pack should progress from:

```json
{"overall_status":"FAIL","passed_steps":3,"total_steps":6,"physical_allow_count":0}
```

to:

```json
{"overall_status":"PASS","passed_steps":6,"total_steps":6,"physical_allow_count":3,"block_no_execution_count":3}
```
