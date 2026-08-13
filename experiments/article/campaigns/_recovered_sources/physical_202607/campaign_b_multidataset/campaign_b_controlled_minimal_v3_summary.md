# Campaign B controlled minimal V3

## Verdict

OK: `True`

## Summary

- Scenario count: 3
- Query count: 18
- ALLOW count: 7
- BLOCK count: 11
- Physical ALLOW executions: 7
- BLOCK without physical execution: 11
- Live B CKG events after run: 7
- Locked A CKG events: 2266

## Datasets / backends

- FoodMart: XMLA / Mondrian
- AdventureWorksDW: SQL Server Direct
- SteelWheels: SQL Server Direct

## Interpretation

Controlled Campaign B minimal evidence: MCAD decisions match expected outcomes; ALLOW queries are physically executed; BLOCK queries are stopped before physical execution; live B CKG receives exactly the 7 useful ALLOW events; locked Campaign A snapshot remains unchanged.

## Files

- `foodmart_q1_q6_check.json`
- `adventureworks_sales_margin_territory_q1_q6_check.json`
- `steelwheels_emea_classic_cars_q1_q6_check.json`
- `campaign_b_controlled_minimal_v3_manifest.json`
- `campaign_b_controlled_minimal_v3_summary.csv`
