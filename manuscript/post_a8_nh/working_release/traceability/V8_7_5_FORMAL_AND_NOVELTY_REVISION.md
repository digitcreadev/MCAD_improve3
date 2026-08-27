# V8_7_5 formal and novelty revision

Scientific data are frozen. No experiment, session, backend execution, or timing run was added.

## Added close prior work
- Francia, Golfarelli, Marcel, Rizzi, Vassiliadis, “Assess Queries for Interactive Analysis of Data Cubes,” EDBT 2021, pp. 121–132, DOI 10.5441/002/edbt.2021.12.
- The manuscript distinguishes benchmark-based assessment of observed versus expected performance from MCAD's support-completion / strategic-computability semantics.
- A dedicated row was added to the comparative matrix.

## Session accumulation ambiguity resolved
Two cumulative notions are now explicit:
- `C_Q^{<=t}`: union of constraints completed by individual queries;
- `C_E^{<=t}`: constraints whose sufficient supports are complete in cumulative acquired evidence `E_t`.

`C_E^{<=t}` is the general session semantics. The published campaigns satisfy the single-query completion condition confirmed for the evaluated protocols, so `C_Q^{<=t} = C_E^{<=t}` at every reported step. Therefore all published `phi^{<=t}` and `Delta phi_t` values remain unchanged. A new proposition proves the equivalence under this condition and shows why the inclusion can be strict in the general multi-query support-completion case.

## Editorial corrections
- English title standardized to “Decision-Analysis Sessions”.
- IEEE paragraph-heading punctuation fixed by removing terminal periods inside `\\paragraph*{...}` headings.
- Contribution list condensed to four major contributions aligned with the conceptual hierarchy figure.
