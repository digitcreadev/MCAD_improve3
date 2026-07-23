# BI Direct Migration Contract

The BI stack is migrated from an XMLA/eMondrian-centered architecture to a BI direct architecture.

The following behavior must remain valid after migration:

1. A user can create a new MCAD session.
2. The objective `O_REAL_BEER_WA_MONTH` and DW `foodmart` are supported.
3. The Q1-Q6 scenario must produce:
   - Q1: ALLOW
   - Q2: ALLOW
   - Q3: BLOCK
   - Q4: BLOCK
   - Q5: BLOCK
   - Q6: BLOCK
4. The objective graph must evolve after Q1 and Q2.
5. `completion_rate`, `calculability_rate_total`, and `calculability_rate_partial` must evolve.
6. `analytic_alignment_score` must reflect the sequence of ALLOW/BLOCK decisions.
7. The decision history must preserve:
   - decision,
   - reason code,
   - reason text,
   - phi,
   - delta phi,
   - useful contribution,
   - query text.

The migration must remove XMLA/eMondrian from the critical path without changing the backend article reproducibility pipeline.
