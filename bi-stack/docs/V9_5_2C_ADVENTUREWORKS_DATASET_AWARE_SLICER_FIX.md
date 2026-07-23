# MCAD V9.5.2c — AdventureWorks Dataset-Aware Slicer Fix

## Problem

After V9.5.2b, the AdventureWorks objective and scenario import correctly and the static validator matches the three ALLOW queries to their target constraints. However, the live runner can still return:

```text
BLOCK_SLICER_MISMATCH
physical_execution=false
```

for the AdventureWorks ALLOW queries.

The cause is that the formal `slc_ok` clause still applies the historical FoodMart known-member dictionary to generic level names such as `Product.Product Category`. Therefore, AdventureWorks members such as `Bikes` are incorrectly rejected because they are not FoodMart category members.

## Fix

V9.5.2c makes `slc_ok` dataset-aware:

- FoodMart keeps the original FoodMart member dictionary.
- AdventureWorksDW uses an AdventureWorks-specific member dictionary:
  - `Product.Product Category`: `Bikes`, `Accessories`, `Clothing`, `Components`
  - `Sales Territory.Sales Territory Group`: `Europe`, `North America`, `Pacific`
  - `Date.Calendar Year`: AdventureWorksDW demo years
- The eval request context `dw_id` is copied into `query_spec` before formal SAT.
- The formal SAT call receives `context=context`.
- NVAC probe payload/cache include `dw_id` and `dataset`.

## Apply

```bash
cp /mnt/data/mcad_v9_5_2c_adventureworks_dataset_aware_slicer_fix_tree/bi-stack/scripts/apply_adventureworks_dataset_aware_slicer_fix.py \
   bi-stack/scripts/apply_adventureworks_dataset_aware_slicer_fix.py
cp /mnt/data/mcad_v9_5_2c_adventureworks_dataset_aware_slicer_fix_tree/bi-stack/scripts/check_adventureworks_dataset_aware_slicer_fix.sh \
   bi-stack/scripts/check_adventureworks_dataset_aware_slicer_fix.sh
cp /mnt/data/mcad_v9_5_2c_adventureworks_dataset_aware_slicer_fix_tree/bi-stack/docs/V9_5_2C_ADVENTUREWORKS_DATASET_AWARE_SLICER_FIX.md \
   bi-stack/docs/V9_5_2C_ADVENTUREWORKS_DATASET_AWARE_SLICER_FIX.md
chmod +x bi-stack/scripts/apply_adventureworks_dataset_aware_slicer_fix.py
chmod +x bi-stack/scripts/check_adventureworks_dataset_aware_slicer_fix.sh
python bi-stack/scripts/apply_adventureworks_dataset_aware_slicer_fix.py .
bash bi-stack/scripts/check_adventureworks_dataset_aware_slicer_fix.sh .
```

## Rebuild

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-api
docker compose -f bi-stack/docker-compose.yml up -d adventureworks-sqlserver mcad-api mcad-proxy
```

## Validate

```bash
bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .
bash bi-stack/scripts/run_adventureworks_demo_validation.sh .
```

Expected result:

```json
{
  "overall_status": "PASS",
  "passed_steps": 6,
  "total_steps": 6,
  "physical_allow_count": 3,
  "block_no_execution_count": 3
}
```
