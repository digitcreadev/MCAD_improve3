from __future__ import annotations

import asyncio
import time
from typing import Any

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

import app as legacy


R3_MEASUREMENT_CONTRACT = "mcad.nh_r3.b2.measurement_runtime.v1.1"
R3_FIXED_DW_ID = "adventureworks_sql_direct"
R3_FIXED_ADAPTER_ID = "adventureworks_direct"


def _r3_query_fields(payload: dict[str, Any]) -> dict[str, Any]:
    query_text = str(payload.get("mdx") or payload.get("query") or "")
    if not query_text.strip():
        raise HTTPException(status_code=400, detail="R3 measurement query is empty")

    requested_dw = str(payload.get("dw_id") or R3_FIXED_DW_ID)
    if requested_dw != R3_FIXED_DW_ID:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "R3_FIXED_DW_REQUIRED",
                "required_dw_id": R3_FIXED_DW_ID,
                "requested_dw_id": requested_dw,
            },
        )

    return {
        "query_text": query_text,
        "query_type": str(payload.get("query_type") or "mdx"),
        "query_id": str(payload.get("query_id") or payload.get("id") or ""),
        "objective_id": str(payload.get("objective_id") or ""),
        "session_id": str(payload.get("session_id") or "") or None,
        "dw_id": R3_FIXED_DW_ID,
    }


def _r3_eval_payload(fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    context = dict(payload.get("context") or {})
    context.update(
        {
            "dw_id": R3_FIXED_DW_ID,
            "requested_dw_id": R3_FIXED_DW_ID,
            "query_type": fields["query_type"],
            "query_id": fields["query_id"] or None,
            "allow_fallback": False,
            "execution_source_enforcement": True,
            "r3_measurement_gate_only": True,
        }
    )

    out: dict[str, Any] = {
        "mdx": fields["query_text"],
        "context": context,
    }
    if fields["session_id"]:
        out["session_id"] = fields["session_id"]
    if fields["objective_id"]:
        out["objective_id"] = fields["objective_id"]
    return out


def _r3_get_path(value: Any, *keys: str) -> Any:
    cur = value
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _r3_canonical_nvac_evidence(decision: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return one canonical nvac_ok evidence object from a live /eval response.

    MCAD deliberately exposes the same formal SAT evidence in more than one
    representation (for example details.sat_evidence.nvac_ok and
    details.nvac_evidence).  Those are aliases of one probe event, not multiple
    backend requests.  R3 accounting therefore selects one canonical evidence
    path before counting physical work.
    """
    candidates = (
        (("details", "nvac_evidence"), "details.nvac_evidence"),
        (("nvac_evidence",), "nvac_evidence"),
        (("details", "sat_evidence", "nvac_ok"), "details.sat_evidence.nvac_ok"),
        (("sat_evidence", "nvac_ok"), "sat_evidence.nvac_ok"),
        (("details", "graph_update", "nvac_evidence"), "details.graph_update.nvac_evidence"),
        (("graph_update", "nvac_evidence"), "graph_update.nvac_evidence"),
    )
    for path, label in candidates:
        evidence = _r3_get_path(decision, *path)
        if isinstance(evidence, dict) and evidence:
            return evidence, label
    return decision if isinstance(decision, dict) else {}, "recursive_fallback"


def _r3_probe_records(value: Any):
    if isinstance(value, dict):
        if "probe_attempted" in value or "raw_probe_summary" in value:
            yield value
            return
        probe = value.get("probe")
        if isinstance(probe, dict):
            yield from _r3_probe_records(probe)
            return
        for nested in value.values():
            yield from _r3_probe_records(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _r3_probe_records(nested)


def _r3_probe_identity(rec: dict[str, Any]) -> tuple[Any, ...]:
    raw = rec.get("raw_probe_summary")
    raw = raw if isinstance(raw, dict) else {}
    return (
        bool(rec.get("probe_attempted")),
        bool(rec.get("cache_hit")),
        rec.get("probe_url"),
        rec.get("probe_query"),
        rec.get("probe_measure"),
        rec.get("elapsed_ms"),
        rec.get("non_empty"),
        rec.get("count"),
        raw.get("response_digest") or raw.get("result_digest"),
        raw.get("response_bytes"),
        raw.get("elapsed_ms"),
        raw.get("generated_sql"),
        raw.get("adapter_id"),
        raw.get("dw_id"),
        bool(raw.get("physical_execution")),
    )


def _r3_nvac_accounting(decision: dict[str, Any]) -> dict[str, Any]:
    evidence, evidence_source = _r3_canonical_nvac_evidence(decision)
    represented_records = list(_r3_probe_records(evidence))

    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for rec in represented_records:
        identity = _r3_probe_identity(rec)
        if identity in seen:
            continue
        seen.add(identity)
        records.append(rec)

    attempted = 0
    cache_hits = 0
    physical = 0
    response_bytes = 0
    physical_elapsed_ms = 0
    normalized: list[dict[str, Any]] = []

    for rec in records:
        probe_attempted = bool(rec.get("probe_attempted"))
        cache_hit = bool(rec.get("cache_hit"))
        raw = rec.get("raw_probe_summary")
        raw = raw if isinstance(raw, dict) else {}
        physical_execution = bool(raw.get("physical_execution"))
        physical_uncached = probe_attempted and not cache_hit and physical_execution

        if probe_attempted:
            attempted += 1
        if cache_hit:
            cache_hits += 1
        if physical_uncached:
            physical += 1
            try:
                response_bytes += int(raw.get("response_bytes") or 0)
            except (TypeError, ValueError):
                pass
            try:
                physical_elapsed_ms += int(raw.get("elapsed_ms") or rec.get("elapsed_ms") or 0)
            except (TypeError, ValueError):
                pass

        normalized.append(
            {
                "probe_attempted": probe_attempted,
                "cache_hit": cache_hit,
                "physical_execution": physical_execution,
                "physical_uncached": physical_uncached,
                "elapsed_ms": rec.get("elapsed_ms"),
                "probe_query": rec.get("probe_query"),
                "probe_measure": rec.get("probe_measure"),
                "response_bytes": raw.get("response_bytes"),
                "adapter_id": raw.get("adapter_id"),
                "dw_id": raw.get("dw_id"),
            }
        )

    return {
        "canonical_evidence_source": evidence_source,
        "represented_probe_record_count": len(represented_records),
        "probe_record_count": len(records),
        "duplicate_probe_representation_count": len(represented_records) - len(records),
        "probe_attempted_count": attempted,
        "cache_hit_count": cache_hits,
        "physical_uncached_probe_count": physical,
        "physical_uncached_probe_response_bytes": response_bytes,
        "physical_uncached_probe_elapsed_ms": physical_elapsed_ms,
        "backend_request_count_including_gate_probes": physical,
        "records": normalized,
    }


@legacy.app.post("/bi/r3/measurement/gate-only")
async def r3_measurement_gate_only(req: Request):
    """Evaluate the MCAD gate/NVAC path without executing the full candidate query.

    The returned live decision is measurement evidence only. The frozen NH-R2/R3
    binding remains authoritative for the experimental arm action.
    """
    payload = await req.json()
    fields = _r3_query_fields(payload)
    legacy._get_dw_config_or_400(R3_FIXED_DW_ID)
    eval_payload = _r3_eval_payload(fields, payload)

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
                "contract_version": R3_MEASUREMENT_CONTRACT,
                "mode": "gate_only",
                "dw_id": R3_FIXED_DW_ID,
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
                "contract_version": R3_MEASUREMENT_CONTRACT,
                "mode": "gate_only",
                "dw_id": R3_FIXED_DW_ID,
                "query_id": fields["query_id"],
                "gate_http_status": response.status_code,
                "gate_elapsed_ms": elapsed_ns / 1_000_000.0,
                "full_candidate_execution_performed": False,
                "full_result_ckg_update_performed": False,
                "error": (response.text or "")[:1000],
            },
        )

    decision = response.json()
    nvac = _r3_nvac_accounting(decision if isinstance(decision, dict) else {})
    return {
        "ok": True,
        "contract_version": R3_MEASUREMENT_CONTRACT,
        "mode": "gate_only",
        "dw_id": R3_FIXED_DW_ID,
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


@legacy.app.post("/bi/r3/measurement/full-execute")
async def r3_measurement_full_execute(req: Request):
    """Execute one frozen candidate through AdventureWorks SQL Direct only.

    This path deliberately performs no MCAD /eval call and no CKG update.
    """
    payload = await req.json()
    fields = _r3_query_fields(payload)
    if bool(payload.get("allow_fallback", False)):
        raise HTTPException(status_code=400, detail="R3 full-execute forbids fallback")

    cfg = legacy._get_dw_config_or_400(R3_FIXED_DW_ID)
    if getattr(cfg, "enabled", True) is False:
        raise HTTPException(status_code=503, detail="AdventureWorks SQL Direct is disabled")

    started_ns = time.perf_counter_ns()
    result = await asyncio.to_thread(
        legacy.get_gateway().execute,
        fields["query_text"],
        query_type=fields["query_type"],
        dw_id=R3_FIXED_DW_ID,
        context={
            "allow_fallback": False,
            "session_id": fields["session_id"],
            "objective_id": fields["objective_id"],
            "query_id": fields["query_id"] or None,
            "r3_measurement_full_execute": True,
        },
    )
    elapsed_ns = time.perf_counter_ns() - started_ns

    summary = result.raw_result_summary if isinstance(result.raw_result_summary, dict) else {}
    physical_execution = bool(summary.get("physical_execution")) and not bool(getattr(result, "error", None))
    adapter_id = getattr(result, "adapter_id", None)
    selected_dw = getattr(result, "dw_id", None)

    body = {
        "ok": physical_execution,
        "contract_version": R3_MEASUREMENT_CONTRACT,
        "mode": "full_execute",
        "dw_id": selected_dw or R3_FIXED_DW_ID,
        "adapter_id": adapter_id,
        "query_id": fields["query_id"],
        "physical_execution": physical_execution,
        "backend_request_count": 1 if physical_execution else 0,
        "elapsed_ms": getattr(result, "elapsed_ms", None),
        "client_endpoint_elapsed_ms": elapsed_ns / 1_000_000.0,
        "response_bytes": getattr(result, "response_bytes", None),
        "response_digest": getattr(result, "response_digest", None),
        "result_digest": summary.get("result_digest") or getattr(result, "response_digest", None),
        "generated_sql": summary.get("generated_sql"),
        "row_count": summary.get("row_count"),
        "fallback_allowed": False,
        "fallback_used": bool(summary.get("fallback_used", False)),
        "mcad_eval_performed": False,
        "ckg_update_performed": False,
        "error": getattr(result, "error", None),
    }

    if adapter_id != R3_FIXED_ADAPTER_ID or (selected_dw and selected_dw != R3_FIXED_DW_ID):
        body["ok"] = False
        body["contract_violation"] = "unexpected_adapter_or_dw"
        return JSONResponse(status_code=502, content=body)

    if getattr(result, "error", None):
        return JSONResponse(status_code=502, content=body)
    return body


app = legacy.app
