# A7 - Existing-ablation claim consolidation

**A7-GATE: PASS**

## Scope
A7 consolidates the interpretation of the already frozen controlled robustness benchmark. It adds no experiment, observation, comparator implementation, theorem, or numerical result.

## Canonical interpretation
The robustness benchmark contains three **internal diagnostic reference policies** (naive, measure overlap, matched random) and three **targeted ablations** manipulating only `SAT`, `Real`, and `C_eval`. The reference policies are not reimplementations of neighboring published systems.

Within the four exercised scenario families, each targeted manipulation degrades reference-aligned behavior in at least one family. The supported conclusion is therefore **component sensitivity / behavioral consequence under the controlled reference specification**, not universal component necessity.

Removing `SAT` gives aggregate mean false-ALLOW 0.041667 and non-contributive execution 0.125. Removing `Real` or relaxing `C_eval` gives 0.08125 and 0.1875. Because the no-`Real` and relaxed-`C_eval` variants have the same aggregate error rates in this protocol, A7 explicitly states that their separate aggregate effect magnitudes are **not identified** here.

## Manuscript and traceability consolidation
The new bounded wording is aligned across the abstract, contribution list, RQ4 wording, evaluation protocol, robustness subsection, results synthesis, limitations, conclusion, the RQ4 row of Table V, and `traceability/CLAIM_EVIDENCE_MAP.csv`. The old positive claim of joint/universal necessity is removed.

## Preservation
Frozen robustness CSVs and all other data are unchanged. Figures, figure sources, supplements, bibliography, and results are byte-identical to A6. The only table files intentionally changed are the EN/FR evaluation-scope matrices, to align the RQ4 claim boundary. Citation sets, labels, input/graphics structure, and the numeric-token multiset of both main manuscripts are preserved.

## Build and visual closure
Full rebuild: EN 19 pages; FR 21 pages. Critical pages were rendered and inspected, including the expanded RQ4 scope row and canonical ablation paragraph; no clipping or overlap was found. Bibliography balance remains intact.

## Gate conclusion
A7 closes the existing-ablation claim-consolidation station. The robustness evidence is now framed as controlled component-sensitivity evidence with explicit comparator and identifiability boundaries.

## Clean-archive verification
The final candidate ZIP was extracted into a fresh directory; every packaged SHA-256 entry verified successfully and the extracted package rebuilt to 19 EN pages and 21 FR pages.
