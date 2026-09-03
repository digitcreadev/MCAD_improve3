# R3-E14 D8-A2 - failed-attempt audit freeze

D8 V2 invoked run-primary but failed after the seven-template non-measured warmup and before the first measured arm timer.

Frozen classification:
- arm receipts: 0
- candidate traces: 0
- output files: 0
- primary summary: absent
- first measured arm timer: not reached
- measurement result: not produced
- failure: Docker Compose interpolation environment was not bound before the first MCAD API restart

The failed D8 V2 directory is preserved and is not authorized for resume, continuation, or output reuse.

A read-only Compose binding preflight proves that the exact existing image references plus the SQL password sourced from the exact existing SQL container make `docker compose config -q` succeed. The SQL password value is never persisted, printed, hashed, or committed.

This freeze itself performs no measurement, HTTP request, XMLA query, container restart/recreate, image build/pull/tag, or effect analysis.
