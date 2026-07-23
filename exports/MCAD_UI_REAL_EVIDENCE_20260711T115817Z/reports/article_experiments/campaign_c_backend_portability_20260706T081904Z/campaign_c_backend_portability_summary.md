# Campaign C — Backend Portability Validation

## Verdict

PASS: True

## Scope

- Dataset: AdventureWorksDW
- Objective: O_AW_EUROPE_BIKES_2013_MONTH_REGION_SALES_QUANTITY
- Comparison: SQL Server Direct vs XMLA/eMondrian
- Isolation: each backend run starts from an empty live CKG.

## Results

| Backend | Queries | ALLOW | BLOCK | Physical ALLOW | BLOCK without execution | CKG events |
|---|---:|---:|---:|---:|---:|---:|
| SQL Server Direct | 6 | 2 | 4 | 2 | 4 | 2 |
| XMLA/eMondrian | 6 | 2 | 4 | 2 | 4 | 2 |

## Portability checks

- Same query IDs: True
- Same expected sequence: True
- Same decision sequence: True
- Same reason sequence: True
- Same physical execution policy: True
- Isolated CKG updates: True

## Locked snapshots

- Campaign A locked events: 2266
- Campaign B locked events: 7

## Interpretation

Controlled Campaign C validates backend portability: for the same AdventureWorksDW objective and the same analytical query sequence, MCAD returns the same ALLOW/BLOCK decisions under SQL Server Direct and XMLA/eMondrian. ALLOW queries are physically executed in both paths, BLOCK queries are stopped before physical execution, and each isolated backend run creates exactly two useful CKG events.
