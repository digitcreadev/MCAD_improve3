# A7 - Existing-ablation claim consolidation

A7 changes interpretation wording only. Existing robustness data, scenario-family aggregates, figures, formal proofs, bibliography, and all other frozen evidence remain unchanged from A6.

Canonical interpretation:
1. Naive, measure-overlap, and matched-random are **internal diagnostic reference policies**, not reimplementations of neighboring published systems.
2. The three targeted ablations manipulate only `SAT`, `Real`, and `C_eval`. Their observed degradations provide **component-sensitivity evidence under the controlled benchmark reference specification**.
3. The ablations do not prove that every MCAD component is necessary in every setting, do not establish human utility, and do not establish external superiority.
4. The no-`Real` and relaxed-`C_eval` variants have identical aggregate false-ALLOW and non-contributive-execution rates in this protocol; separate aggregate effect magnitudes are therefore not identified by this benchmark.
5. No historical result is recalculated or reinterpreted as external ground truth.
