# V9.4.2 — Hybrid BI Gateway Registry

## Purpose

This step adopts the hybrid BI execution strategy for MCAD demonstrations:

1. **XMLA/eMondrian is the priority path** for real MDX/OLAP demonstrations.
2. **SQL Direct is the fallback/secondary path** for robustness and portability.
3. The registry covers three datasets: **FoodMart**, **AdventureWorksDW**, and **SteelWheels / Pentaho SampleData**.

This version is a gateway/registry consolidation step. It does not yet claim that every registered backend is fully executable. It explicitly marks non-integrated backends as disabled/experimental so the system does not fake physical execution.

## Execution principle

The MCAD control rule is unchanged:

```text
/query from UI
→ mcad-proxy
→ mcad-api /eval
→ MCAD decision ALLOW/BLOCK
→ if BLOCK: no physical execution
→ if ALLOW: execution gateway selects XMLA or SQL Direct adapter
```

No XMLA or SQL request is sent to a data warehouse before MCAD returns `ALLOW`.

## Registered data warehouses/adapters

| DW id | Dataset | Adapter | Role | Enabled in V9.4.2 |
|---|---|---|---|---|
| `foodmart` | FoodMart | XMLA/eMondrian | Priority MDX path | yes |
| `foodmart_sql_direct` | FoodMart | SQL Direct | fallback/secondary | yes |
| `adventureworks_xmla` | AdventureWorksDW | XMLA/eMondrian | experimental path | no |
| `adventureworks_sql_direct` | AdventureWorksDW | SQL Direct | planned fallback/secondary | no |
| `steelwheels_xmla` | SteelWheels / Pentaho SampleData | XMLA/eMondrian | third reputed dataset candidate | no |
| `steelwheels_sql_direct` | SteelWheels / Pentaho SampleData | SQL Direct | planned fallback/secondary | no |

## Why disabled entries are still registered

AdventureWorksDW and SteelWheels are registered now to stabilize the public gateway contract and the UI dropdown, but they remain disabled until their real catalog/schema/connection is installed. This avoids the misleading claim that execution is implemented when it is not.

## XMLA path

For enabled XMLA backends, the adapter builds an XMLA `Execute` SOAP envelope and sends the MDX query to the configured eMondrian endpoint. It then records:

```json
{
  "physical_execution": true,
  "execution_mode": "real",
  "adapter_family": "xmla_mondrian",
  "logical_query_language": "mdx",
  "physical_query_language": "xmla_mdx",
  "status_code": 200,
  "elapsed_ms": 0,
  "response_digest": "..."
}
```

If XMLA execution fails and the registry entry declares a fallback DW, the gateway may try the fallback adapter **after MCAD has already allowed the query**.

## SQL Direct fallback path

FoodMart SQL Direct remains available through `foodmart_sql_direct`. It preserves the previous V9.3/V9.4 direct path and marks the result as a real direct execution summary.

AdventureWorksDW and SteelWheels SQL Direct are registered but intentionally unavailable until their physical connection and semantic mappings are implemented.

## Validation commands

From the repository root:

```bash
PYTHONPATH=$PWD/bi-stack/mcad-proxy python -m py_compile \
  bi-stack/mcad-proxy/execution/adapters/base.py \
  bi-stack/mcad-proxy/execution/adapters/foodmart_direct_adapter.py \
  bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py \
  bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py \
  bi-stack/mcad-proxy/execution/adapters/steelwheels_direct_adapter.py \
  bi-stack/mcad-proxy/execution/registry.py \
  bi-stack/mcad-proxy/execution/gateway.py \
  bi-stack/mcad-proxy/app.py
```

After Docker rebuild:

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d mcad-proxy

curl -s http://127.0.0.1:9000/mcad/datawarehouses | python -m json.tool
curl -s http://127.0.0.1:9000/mcad/datawarehouses/health | python -m json.tool
curl -s http://127.0.0.1:9000/mcad/datawarehouses/foodmart/metadata | python -m json.tool
curl -s http://127.0.0.1:9000/mcad/datawarehouses/foodmart_sql_direct/metadata | python -m json.tool
```

## Next steps

Recommended sequence after V9.4.2:

```text
V9.4.3 — Harden FoodMart XMLA/eMondrian Real Adapter
V9.4.4 — Add SteelWheels XMLA catalog/schema integration
V9.4.5 — Add AdventureWorksDW SQL Direct real execution
V9.4.6 — Optional AdventureWorks XMLA experiment
V9.5.0 — Multi-DW Real Demonstration Campaign
```
