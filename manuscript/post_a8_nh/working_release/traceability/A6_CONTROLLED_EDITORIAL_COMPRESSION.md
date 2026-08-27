# A6 — Controlled Editorial Compression

**A6-GATE: PASS**

A6 compresses the A-R2 V8.7.6 candidate while preserving the frozen scientific content. No new experiment, observation, theorem, baseline, external comparison, or validation claim is introduced.

## Measured compression
- EN: 14856 → 13810 extracted words, a **7.041%** reduction; **20 → 19 pages**.
- FR: 17470 → 16454 extracted words, a **5.816%** reduction; **22 → 21 pages**.

Compression targets repeated framing and recap prose in the abstract/introduction, selected architecture/evaluation explanations, Results Synthesis, Discussion/Future Directions, and Conclusion. It does not remove the evidence tables, figures, appendices, or formal propositions.

## Preservation results
- All **39 citation keys** remain used in both manuscripts.
- All main labels, cross-references, figure/table inputs, **10 figures**, and **10 tables** are preserved.
- The complete MCAD formalization section is byte-identical to A-R2 in both languages.
- `data/`, `figures/`, `figure_sources/`, `tables/`, `supplement/`, `literature/`, and `results/` are byte-identical to A-R2.
- FoodMart trace-retention wording, controlled-oracle scope, direct-comparison limitation, human-utility boundary, 118000 timing count, structural counts, and policy/contribution separation remain explicit.

## Build and visual closure
The compressed candidate compiles to **19 pages EN** and **21 pages FR**, versus 20 and 22 in A-R2. A fresh extraction of the candidate archive rebuilds successfully to the same page counts. Full contact sheets were inspected with no clipping, overlap, missing figure/table, broken glyph, or bibliography-balance regression.

## Scientific interpretation
A6 is editorial compression only. Historical results, inference units, claim boundaries, and the distinction among verification, business validation, user validation, and field validation are not upgraded or reinterpreted.
