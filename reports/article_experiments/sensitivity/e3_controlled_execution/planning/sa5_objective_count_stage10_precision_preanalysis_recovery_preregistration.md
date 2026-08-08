# SA5 objective-count Stage-10 precision pre-analysis recovery

The first authorized analyzer invocation stopped before measurement
loading and before bootstrap execution.

Cause: analyzer-facing timing-report metadata status mismatch.

No raw precision intervals or reports were created.

Recovery preserves the frozen measurement observations, the original
timing report, the factor-compatible analyzer, all bootstrap parameters,
all precision thresholds, and the decision rule.

A separate analyzer-facing timing-report adapter changes exactly one
top-level metadata field:

`precision_input_materialization_ready`
→ `stage10_formal_timing_execution_success`

No timing measurement is changed.

Exactly one recovery invocation becomes eligible only after this
recovery preregistration is merged and after explicit operator
confirmation.
