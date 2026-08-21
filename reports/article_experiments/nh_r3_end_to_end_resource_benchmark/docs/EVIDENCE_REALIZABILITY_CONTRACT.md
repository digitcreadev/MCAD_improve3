# Evidence-realizability contract

The scientific exposition separates five concepts:

1. semantic admissibility before the non-vacuity check;
2. evidence realizability/non-vacuity (NOVC/NVAC);
3. evidence actually acquired by the session;
4. contribution to objective-relative computability;
5. operational action.

The current canonical formal SAT implementation exposes `nvac_ok` as one clause
of the overall gate. R3-A2 does not change that decision behavior.

For reporting/instrumentation, expose:
- `semantic_admissibility_pre_nvac`;
- `evidence_realizability_nvac`;
- existing overall gate result.

A successful probe may establish availability/non-vacuity. It does not by
itself mean that the full candidate result was acquired into cumulative session
evidence.

Any physical probe cost is counted in R3.
