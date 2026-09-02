from __future__ import annotations

import asyncio
import time
from typing import Any

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

# Import the frozen R3-D measurement module from the exact historical proxy image.
# This registers the historical SQL-direct endpoints but does not alter them.
# E11 exposes separate /bi/r3/e11/... paths and reuses only audited accounting helpers.
import r3_measurement_app as frozen_r3

legacy = frozen_r3.legacy
app = frozen_r3.legacy.app

R3_E11_MEASUREMENT_CONTRACT = "mcad.nh_r3.e11.measurement_runtime.v1"
R3_E11_DW_ID = "adventureworks_xmla"
R3_E11_ADAPTER_ID = "xmla_mondrian"


def _fields(payload: dict[str, Any]) -> dict[str, Any]:
    query_text = str(payload.get("mdx") or payload.get("query") or "")
    if not query_text.strip():
        raise HTTPException(status_code=400, detail="R3-E11 measurement query is empty")

    requested_dw = str(payload.get("dw_id") or R3_E11_DW_ID)
    if requested_dw != R3_E11_DW_ID:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "R3_E11_FIXED_DW_REQUIRED",
                "required_dw_id": R3_E11_DW_ID,
                "requested_dw_id": requested_dw,
            },
        )

    return {
        "query_text": query_text,
        "query_type": str(payload.get("query_type") or "mdx"),
        "query_id": str(payload.get("query_id") or payload.get("id") or ""),
        "objective_id": str(payload.get("objective_id") or ""),
        "session_id": str(payload.get("session_id") or "") or None,
        "dw_id": R3_E11_DW_ID,
    }


def _eval_payload(fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    context = dict(payload.get("context") or {})
    context.update(
        {
            "dw_id": R3_E11_DW_ID,
            "requested_dw_id": R3_E11_DW_ID,
            "query_type": fields["query_type"],
            "query_id": fields["query_id"] or None,
            "allow_fallback": False,
            "execution_source_enforcement": True,
            "r3_e11_measurement_gate_only": True,
        }
    )
    out: dict[str, Any] = {"mdx": fields["query_text"], "context": context}
    if fields["session_id"]:
        out["session_id"] = fields["session_id"]
    if fields["objective_id"]:
        out["objective_id"] = fields["objective_id"]
    return out


@app.post("/bi/r3/e11/measurement/gate-only")
async def r3_e11_measurement_gate_only(req: Request):
    payload = await req.json()
    fields = _fields(payload)
    legacy._get_dw_config_or_400(R3_E11_DW_ID)
    eval_payload = _eval_payload(fields, payload)

    started_ns = time.perf_counter_ns()
    try:
        response = await asyncio.to_thread(
            requests.post,
            legacy.MCAD_EVAL_URL,
            json=eval_payload,
            timeout=legacy.MCAD_EVAL_TIMEOUT_S,
        )
    except Exception as exc:
        elapsed_ns = time.perf_counter_ns() - started_ns
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "contract_version": R3_E11_MEASUREMENT_CONTRACT,
                "mode": "gate_only",
                "dw_id": R3_E11_DW_ID,
                "query_id": fields["query_id"],
                "gate_elapsed_ms": elapsed_ns / 1_000_000.0,
                "full_candidate_execution_performed": False,
                "full_result_ckg_update_performed": False,
                "error": str(exc),
            },
        )

    elapsed_ns = time.perf_counter_ns() - started_ns
    if not response.ok:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "contract_version": R3_E11_MEASUREMENT_CONTRACT,
                "mode": "gate_only",
                "dw_id": R3_E11_DW_ID,
                "query_id": fields["query_id"],
                "gate_http_status": response.status_code,
                "gate_elapsed_ms": elapsed_ns / 1_000_000.0,
                "full_candidate_execution_performed": False,
                "full_result_ckg_update_performed": False,
                "error": (response.text or "")[:1000],
            },
        )

    decision = response.json()
    nvac = frozen_r3._r3_nvac_accounting(decision if isinstance(decision, dict) else {})
    return {
        "ok": True,
        "contract_version": R3_E11_MEASUREMENT_CONTRACT,
        "mode": "gate_only",
        "dw_id": R3_E11_DW_ID,
        "query_id": fields["query_id"],
        "session_id": fields["session_id"],
        "objective_id": fields["objective_id"],
        "gate_elapsed_ms": elapsed_ns / 1_000_000.0,
        "decision": decision,
        "nvac": nvac,
        "full_candidate_execution_performed": False,
        "full_result_ckg_update_performed": False,
        "frozen_action_authority": "NH_R2_R3_BINDING",
        "live_gate_action_authoritative": False,
    }


@app.post("/bi/r3/e11/measurement/full-execute")
async def r3_e11_measurement_full_execute(req: Request):
    payload = await req.json()
    fields = _fields(payload)
    if bool(payload.get("allow_fallback", False)):
        raise HTTPException(status_code=400, detail="R3-E11 full-execute forbids fallback")

    cfg = legacy._get_dw_config_or_400(R3_E11_DW_ID)
    if getattr(cfg, "enabled", True) is False:
        raise HTTPException(status_code=503, detail="AdventureWorks XMLA is disabled")

    started_ns = time.perf_counter_ns()
    result = await asyncio.to_thread(
        legacy.get_gateway().execute,
        fields["query_text"],
        query_type=fields["query_type"],
        dw_id=R3_E11_DW_ID,
        context={
            "allow_fallback": False,
            "session_id": fields["session_id"],
            "objective_id": fields["objective_id"],
            "query_id": fields["query_id"] or None,
            "r3_e11_measurement_full_execute": True,
            "xmla_timeout_s": 180,
        },
    )
    elapsed_ns = time.perf_counter_ns() - started_ns

    summary = result.raw_result_summary if isinstance(result.raw_result_summary, dict) else {}
    physical_execution = bool(summary.get("physical_execution")) and not bool(getattr(result, "error", None))
    adapter_id = getattr(result, "adapter_id", None)
    selected_dw = getattr(result, "dw_id", None)

    body = {
        "ok": physical_execution,
        "contract_version": R3_E11_MEASUREMENT_CONTRACT,
        "mode": "full_execute",
        "dw_id": selected_dw or R3_E11_DW_ID,
        "adapter_id": adapter_id,
        "query_id": fields["query_id"],
        "physical_execution": physical_execution,
        "backend_request_count": 1 if physical_execution else 0,
        "elapsed_ms": getattr(result, "elapsed_ms", None),
        "client_endpoint_elapsed_ms": elapsed_ns / 1_000_000.0,
        "response_bytes": getattr(result, "response_bytes", None),
        "response_digest": getattr(result, "response_digest", None),
        "result_digest": summary.get("result_digest") or getattr(result, "response_digest", None),
        "row_count": summary.get("row_count"),
        "xmla_valid_response": summary.get("xmla_valid_response"),
        "xmla_response_type": summary.get("xmla_response_type"),
        "xmla_has_fault": summary.get("xmla_has_fault"),
        "fallback_allowed": False,
        "fallback_used": bool(summary.get("fallback_used", False)),
        "mcad_eval_performed": False,
        "ckg_update_performed": False,
        "error": getattr(result, "error", None),
    }

    if adapter_id != R3_E11_ADAPTER_ID or (selected_dw and selected_dw != R3_E11_DW_ID):
        body["ok"] = False
        body["contract_violation"] = "unexpected_adapter_or_dw"
        return JSONResponse(status_code=502, content=body)

    if summary.get("xmla_valid_response") is not True or summary.get("xmla_has_fault") is True:
        body["ok"] = False
        body["contract_violation"] = "invalid_xmla_response"
        return JSONResponse(status_code=502, content=body)

    if getattr(result, "error", None):
        return JSONResponse(status_code=502, content=body)
    return body
