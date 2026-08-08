# SA5 objective-count Stage-10 precision analyzer factor-label amendment

Status: preregistered before analyzer compatibility patch.

## Diagnosis

The frozen analyzer contains exactly one hard-coded cell-result
factor label: `constraint_count`, in `analyze_precision`.

This is classified as an output-metadata compatibility defect.
No scientific algorithm defect is being asserted.

## Preregistered minimal patch

The patch MUST:

1. add keyword-only `factor: str = "constraint_count"` to
   `analyze_precision`;
2. add CLI `--factor` with default `constraint_count`;
3. pass `factor=args.factor` at the call site;
4. replace the hard-coded cell-result label with the supplied factor;
5. invoke SA5 later with explicit `--factor objective_count`.

The patch MUST NOT alter measurement handling, cluster grouping,
bootstrap mechanics, seeds, thresholds, statistical calculations,
decision rules, or the materialized SA5 precision inputs.

The default remains `constraint_count` for historical
backward compatibility.

## Sequencing

This amendment must be merged before the analyzer is modified.
The analyzer patch must then be merged before any precision-analysis
authorization. Precision/bootstrap execution remains unauthorized.
