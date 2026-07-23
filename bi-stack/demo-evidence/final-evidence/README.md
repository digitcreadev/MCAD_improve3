# MCAD AdventureWorksDW Real Execution Evidence

This evidence bundle validates the end-to-end MCAD gate over a real AdventureWorksDW SQL Server Direct backend.

## Validated behavior

- Objective: O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN
- Scenario: adventureworks_sales_margin_territory_q1_q6
- Data warehouse identifier: adventureworks_sql_direct
- Dataset: AdventureWorksDW
- Backend path: SQL Server Direct
- Adapter: adventureworks_direct

## Expected result

- 3 ALLOW queries physically executed through SQL Server Direct.
- 3 BLOCK queries stopped by MCAD before physical execution.
- Overall validation status: PASS 6/6.

## Interpretation

This bundle is real-execution evidence for the live BI integration path.
It complements the article benchmark campaign and does not replace the large-scale experimental benchmark.
