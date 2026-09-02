# R3-E12 mechanical checkpoint freeze (V4.2.1)

This directory freezes **mechanical/runtime evidence only** for R3-E12.

- Exact objective: `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`
- Runtime DW: `adventureworks_xmla`
- Adapter: `xmla_mondrian`
- Mechanical checkpoint: one session creation, one non-authoritative gate-only probe, one physical XMLA full-execute probe.
- Runtime objective materialization: PASS before any mechanical POST.
- Measured campaign: **not executed**.
- Measurement result: **not produced**.
- Effect analysis: **not performed**.
- E13: **not authorized by this freeze**.
- Scientific final freeze: **not performed**.

The authoritative objective seed remains the already tracked
`bi-stack/mcad-api-data/imported_objectives.json`; it is referenced by hash in
`FREEZE_MANIFEST.json` and is deliberately not duplicated here.

The external V4.2.1 receipt records the state *before repository publication*.
That historical fact is preserved byte-for-byte. This directory and its Git
commit constitute the subsequent mechanical publication event.
