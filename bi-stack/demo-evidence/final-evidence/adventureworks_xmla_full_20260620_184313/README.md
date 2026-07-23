# AdventureWorks XMLA full scenario evidence

Validated path:

MCAD /eval → mcad-proxy → XmlaMondrianAdapter → eMondrian XMLA → SQL Server AdventureWorksDW2022.

Observed result:

- Q1: ALLOW + real XMLA execution
- Q2: ALLOW + real XMLA execution
- Q3: ALLOW + real XMLA execution
- Q4: BLOCK + no main physical execution
- Q5: BLOCK + no main physical execution
- Q6: BLOCK + no main physical execution

Final result:

FULL_SCENARIO_PASS = True
