# R3-E14 D3 physical-MDX compatibility repair freeze

This directory freezes the post-failure D1 diagnosis and the D2 repair design/authorization.

Scientific boundary:

- the failed E14 V1 attempt is preserved;
- it produced zero measured arm-run receipts and no primary summary;
- the root cause is a cross-backend physical-MDX normalizer coverage gap;
- the repair is implemented only through two NEW R3-E14 modules;
- historical adapter, E11 executor, logical MDX templates, and eMondrian schema are not modified;
- no HTTP/XMLA/SQL request is executed by D3;
- no measurement, effect analysis, non-measured XMLA preflight, or E14 rerun is authorized by D3.

The next station requires a separate authorization before any seven-template non-measured XMLA compatibility preflight.
