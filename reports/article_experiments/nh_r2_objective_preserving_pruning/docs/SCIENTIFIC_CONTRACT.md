# NH-R2 scientific contract

Primary question: does `SAFE_PRUNING` remove only strategically dispensable candidates while preserving the final computability of the active objective relative to permissive execution?

Primary gate, for every session: `Comp(E_final_SAFE) == Comp(E_final_PERMISSIVE)` and zero pruned `IMMEDIATE_CONTRIBUTOR` or `DEFERRED_SUPPORT_CONTRIBUTOR`.

Policies: `PERMISSIVE`, frozen-R1 `SAFE_PRUNING`, and historical `STRICT_IMMEDIATE`. Invalid/unverified semantic contracts fail open for pruning policies.

R2 can report semantic classification, pruning ratio, sequence compression, useful-execution density, objective preservation, strict-immediate completion loss, and replay-manifest counts. R2 cannot claim CPU, memory, I/O, bytes, end-to-end acceleration, throughput or net resource savings; these require NH-R3 paired backend replay.
