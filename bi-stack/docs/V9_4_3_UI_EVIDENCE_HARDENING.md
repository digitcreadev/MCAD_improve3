# MCAD V9.4.3 — UI Evidence Hardening

## Purpose

V9.4.3 makes the BI demonstration evidence explicit in the proxy response and in the session UI.
It builds on V9.4.2b, where `/bi/execute` was already wired to the hybrid execution gateway and the UI could choose between:

- `foodmart` — FoodMart via XMLA/eMondrian;
- `foodmart_sql_direct` — FoodMart via Direct BI.

## Main change

Every `/bi/execute` response now carries a compact, reproducible evidence contract:

```json
{
  "contract_version": "mcad.execution_evidence.v1",
  "mcad_gate": {"allowed_by_mcad": true, "decision": "ALLOW"},
  "formal_metrics": {"sat": 1.0, "real": 1.0, "ceval": 0.5, "phi": 0.5, "delta_phi": 0.5},
  "execution": {
    "status": "EXECUTED",
    "physical_execution": true,
    "requested_dw_id": "foodmart",
    "selected_dw_id": "foodmart",
    "adapter_id": "xmla_mondrian",
    "execution_path": "xmla_mondrian",
    "physical_query_language": "xmla_mdx",
    "status_code": 200,
    "elapsed_ms": 120,
    "response_bytes": 12345,
    "response_digest": "...",
    "xmla_response_type": "ExecuteResponse"
  }
}
```

For a blocked query, the same contract is emitted with:

```json
{
  "mcad_gate": {"allowed_by_mcad": false},
  "execution": {"status": "MCAD_BLOCKED", "physical_execution": false, "attempted": false}
}
```

## Files changed

- `bi-stack/mcad-proxy/app.py`
  - Adds `LAST_EXECUTION_EVIDENCE`.
  - Adds `/mcad/evidence/current`.
  - Adds the `mcad.execution_evidence.v1` contract.
  - Includes `execution_evidence` in `/bi/execute` responses.
  - Stores evidence in `LAST_DECISION` for UI refresh and export.

- `bi-stack/mcad-proxy/session_ui.html`
  - Adds the `Execution Evidence` card in BI results, MCAD decision blocks, and overview.
  - Displays MCAD gate, physical execution, adapter, execution path, elapsed time, status code, bytes, digest, and XMLA response type.
  - Adds evidence to exported session JSON.

- `bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py`
  - Adds `xmla_response_type`, `xmla_valid_response`, `xmla_has_fault`, `response_digest`, and `result_digest`.

- `bi-stack/mcad-proxy/execution/adapters/foodmart_direct_adapter.py`
  - Adds aligned `status_code`, `elapsed_ms`, `response_bytes`, `response_digest`, `result_digest`, and `execution_path` fields for Direct BI.

- `bi-stack/scripts/check_ui_evidence_contract.sh`
  - Static verification script for V9.4.3 evidence wiring.

## Verification

```bash
PYTHONPATH=$PWD/bi-stack/mcad-proxy python -m py_compile \
  bi-stack/mcad-proxy/app.py \
  bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py \
  bi-stack/mcad-proxy/execution/adapters/foodmart_direct_adapter.py

bash bi-stack/scripts/check_ui_evidence_contract.sh .
```

Expected:

```text
Summary: fails=0
```

## Demonstration checklist

1. Start the stack.
2. Open `/mcad/session/ui`.
3. Create a session with `FoodMart via XMLA/eMondrian`.
4. Run Q1.
5. Check the `Execution Evidence` card:
   - `MCAD allowed = true`;
   - `Physical execution = true`;
   - `Execution path = xmla_mondrian` or `FoodMart via XMLA/eMondrian`;
   - `XMLA type = ExecuteResponse`;
   - `Digest` is present.
6. Create another session with `FoodMart via Direct BI` and run Q1.
7. Check the `Execution Evidence` card:
   - `Execution path = sql_direct` or `FoodMart via Direct BI`;
   - `Physical execution = true`;
   - `Digest` is present.

## Boundary

This patch does not change the article reproduction pipeline under `/backend`, `/campaign_runs`, or `scripts/reproduce_article_artifacts.sh`.
