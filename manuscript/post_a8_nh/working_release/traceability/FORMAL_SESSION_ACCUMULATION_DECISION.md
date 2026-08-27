# Formal decision — session accumulation in V8_7_5

## Two cumulative notions

Query-wise complete-support accumulation:

`C_Q^{<=t}(O) = union_{i=1..t} C_eval(QP_i,O)`.

Evidence-wise session accumulation:

`C_E^{<=t}(O) = { c in C*(O) | exists R in R(c), R subseteq E_t }`.

The second definition is adopted as the general session semantics because it correctly handles a support completed by evidence acquired across several queries.

## Why the previous union remains valid for the evaluated MCAD sessions

Two conditions are sufficient:

1. support-acquisition consistency: a completed support credited to session coverage is actually acquired and retained;
2. single-query completion: every sufficient support that becomes complete is completed by one query rather than only by combining fragments from several queries.

The user confirmed the second condition for the current campaigns. Under both conditions, `C_Q^{<=t}(O) = C_E^{<=t}(O)`. Therefore the reported MCAD `phi^{<=t}` and `Delta phi_t` values do not change.

For policies that block a contributive query, the acquired state `E_t` remains authoritative; the raw union of query-level `C_eval` sets must not be used as a substitute for acquired evidence.
