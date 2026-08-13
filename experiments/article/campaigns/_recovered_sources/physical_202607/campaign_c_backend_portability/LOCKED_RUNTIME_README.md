# Locked runtime — Campaign C backend portability

This locked runtime captures the controlled Campaign C validation.

Scope:
- Dataset: AdventureWorksDW
- Objective: O_AW_EUROPE_BIKES_2013_MONTH_REGION_SALES_QUANTITY
- Comparison: SQL Server Direct vs XMLA/eMondrian
- Isolation rule: each backend run starts from an empty live CKG.

Expected result:
- SQL Direct: 6 queries, 2 ALLOW physically executed, 4 BLOCK stopped before physical execution, 2 useful CKG events.
- XMLA/eMondrian: 6 queries, 2 ALLOW physically executed, 4 BLOCK stopped before physical execution, 2 useful CKG events.
- Portability verdict: same query sequence, same expected decisions, same MCAD decisions, same reason sequence, same physical execution policy.
