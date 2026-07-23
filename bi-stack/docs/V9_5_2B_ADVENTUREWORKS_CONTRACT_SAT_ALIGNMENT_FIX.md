# V9.5.2b — AdventureWorks Contract/SAT Alignment Fix

This fix addresses the first live AdventureWorks validation result after V9.5.2a:

- objective import succeeds;
- scenario import is accepted, but ALLOW queries produce static warnings;
- live validation passes only BLOCK cases, with `physical_allow_count=0`.

Root cause: the imported AdventureWorks objective is normalized into `constraints[].virtual_nodes[]`. The proxy scenario validator only matched top-level `measure/grain/slicers`, while the formal SAT non-vacuity probe still used a FoodMart-style probe measure and did not explicitly pass `dw_id` to the probe route.

## Apply

```bash
cp /mnt/data/mcad_v9_5_2b_adventureworks_contract_sat_alignment_fix_tree/bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py \
   bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py
cp /mnt/data/mcad_v9_5_2b_adventureworks_contract_sat_alignment_fix_tree/bi-stack/scripts/check_adventureworks_contract_sat_alignment_fix.sh \
   bi-stack/scripts/check_adventureworks_contract_sat_alignment_fix.sh
chmod +x bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py
chmod +x bi-stack/scripts/check_adventureworks_contract_sat_alignment_fix.sh
python bi-stack/scripts/apply_adventureworks_contract_sat_alignment_fix.py .
bash bi-stack/scripts/check_adventureworks_contract_sat_alignment_fix.sh .
```

Then rebuild both API and proxy:

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-api mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d adventureworks-sqlserver mcad-api mcad-proxy
```

Re-import and validate:

```bash
bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .
bash bi-stack/scripts/run_adventureworks_demo_validation.sh .
```
