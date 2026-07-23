# MCAD V9.5.2a — AdventureWorks Import Validation Fix

## Purpose

V9.5.2a fixes the AdventureWorks objective import failure observed after V9.5.1/V9.5.2.
The previous objective JSON contained each virtual node twice inside a constraint:

- once as `virtual_node`, and
- once again inside `virtual_nodes[].id`.

The canonical import validator treats this as a duplicate virtual-node binding and rejects the payload with HTTP 400.

## Fix

The corrected objective keeps `virtual_nodes[]` as the authoritative binding and removes the duplicate top-level `virtual_node` key from each constraint.

The import script now also performs this sequence explicitly:

1. `POST /mcad/objectives/validate`
2. `POST /mcad/objectives/import`
3. `POST /bi/scenarios/validate`
4. `POST /bi/scenarios/import`
5. `POST /mcad/session/new`

If an HTTP 400 occurs, the response body is printed instead of hiding the real validation report behind a generic `HTTP Error 400`.

## Validation

```bash
bash bi-stack/scripts/check_adventureworks_import_validation_fix.sh .
bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .
bash bi-stack/scripts/run_adventureworks_demo_validation.sh .
```

Expected live result after SQL Server + AdventureWorksDW restoration:

```json
{
  "overall_status": "PASS",
  "passed_steps": 6,
  "total_steps": 6
}
```

The runner remains dynamic: if the AdventureWorks scenario contains more or fewer queries, `total_steps` follows the JSON scenario length.
