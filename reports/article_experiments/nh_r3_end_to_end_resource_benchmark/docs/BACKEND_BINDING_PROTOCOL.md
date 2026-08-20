# Backend binding protocol

## Primary path
AdventureWorks SQL Server Direct (`adventureworks_sql_direct`,
`adventureworks_direct`) is the primary resource-attribution backend.

## Secondary path
AdventureWorks XMLA/eMondrian (`adventureworks_xmla`, `xmla_mondrian`) is a
secondary end-to-end confirmation after the direct-path protocol passes.

## Deterministic workload embedding
The frozen R2 symbolic query identifiers are embedded into a small fixed family
of real AdventureWorks MDX templates. Binding is a deterministic function of
`query_id`, `evidence_atoms`, and the archetype parsed from the frozen ID.

- `ATOM`, `REPEAT`, `RPT`: one of SalesAmount, TotalProductCost, GrossMargin,
  selected by SHA-256 of the frozen evidence-atom string so repeats of the same
  atom remain bound consistently.
- `PAIR`: two-measure SalesAmount + TotalProductCost query.
- `DIST`, `DST`: out-of-objective Accessories SalesAmount query.
- `MIX`: two-measure query in the out-of-objective Accessories category.
- `INAD`: year-grain query used only as an inadmissible control.

This mapping is frozen before resource measurements and never changes based on
latency, CPU, I/O, or observed effect size.

The mapping is an **experimental workload embedding**, not a claim that the
synthetic evidence atom has identical business semantics to the warehouse
measure.
