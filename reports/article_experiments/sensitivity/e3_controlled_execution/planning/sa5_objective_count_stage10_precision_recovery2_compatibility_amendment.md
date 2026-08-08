# SA5 precision recovery #2 compatibility amendment

Two analyzer invocations terminated before measurement loading and before bootstrap.

This amendment resolves the complete known legacy timing-report pre-measurement contract through an analyzer-facing adapter. The analyzer, frozen observations, bootstrap algorithm, bootstrap parameters, thresholds, and decision rule remain unchanged.

`exactly_balanced_run_count=10` is a compatibility alias for exact sample-count balance established directly from the frozen precision observations: every one of the 10 structural clusters contains exactly 100 measurements for each of the 192 canonical factor-level/step cells. It is not the positional `all_cells_exactly_balanced` timing-manifest flag.

Recovery #2 remains ineligible until this amendment is merged and explicit operator confirmation is given. This PR performs no precision analysis or bootstrap.
