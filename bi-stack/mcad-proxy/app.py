from __future__ import annotations

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import asyncio
import sys
import time
import subprocess
import threading
import zipfile
import requests
import hashlib
import re
import json
import csv
import io
from pathlib import Path
from lxml import etree
from xml.sax.saxutils import escape as xml_escape
from xmla_result_parser import summarize_xmla_response
from direct_executor import execute_direct_query
from direct_result_materializer import build_public_direct_result
from execution.gateway import get_gateway
from execution.registry import list_datawarehouses

app = FastAPI(title="MCAD Hybrid BI Gateway Proxy", version="2.2.0-v9.4.7")
STATIC_DIR = Path(__file__).with_name("static")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
UPSTREAM = os.getenv("UPSTREAM_XMLA", "http://emondrian:8080/emondrian/xmla")
MCAD_EVAL_URL = os.getenv("MCAD_EVAL_URL", "http://mcad-api:8000/eval")
MCAD_CKG_URL = os.getenv("MCAD_CKG_URL", "http://mcad-api:8000/ckg/update")
MCAD_API_BASE = os.getenv("MCAD_API_BASE", "http://mcad-api:8000")
MCAD_EVAL_TIMEOUT_S = float(os.getenv("MCAD_EVAL_TIMEOUT_S", "60"))
MCAD_CKG_TIMEOUT_S = float(os.getenv("MCAD_CKG_TIMEOUT_S", "30"))
MCAD_OBJECTIVE_ID_DEFAULT = os.getenv("MCAD_OBJECTIVE_ID_DEFAULT", "")
MCAD_DW_ID_DEFAULT = os.getenv("MCAD_DW_ID_DEFAULT", "foodmart")
PIVOT4J_URL = os.getenv("PIVOT4J_URL", "http://pivot4j:8080/pivot4j")

ACTIVE_CONTEXT: dict[str, str | None] = {
    "session_id": None,
    "objective_id": MCAD_OBJECTIVE_ID_DEFAULT or None,
    "dw_id": MCAD_DW_ID_DEFAULT,
}
LAST_DECISION: dict[str, object] = {}
LAST_EXECUTION_EVIDENCE: dict[str, object] = {}
GRAPH_SESSION_STATES: dict[str, dict[str, object]] = {}

PROXY_DATA_DIR = Path(os.getenv("MCAD_PROXY_DATA_DIR", "/app/data"))
_IMPORTED_SCENARIOS_FILE = PROXY_DATA_DIR / "imported_scenarios.json"
_EXECUTION_EVIDENCE_FILE = PROXY_DATA_DIR / "execution_evidence_archive.json"
DEMO_EVIDENCE_DIR = Path(os.getenv("MCAD_DEMO_EVIDENCE_DIR", "/app/demo-evidence"))
DEMO_RUN_TIMEOUT_S = int(os.getenv("MCAD_DEMO_RUN_TIMEOUT_S", "300"))
DEMO_RUN_LOCK = threading.Lock()
DEMO_RUN_STATE: dict[str, object] = {
    "running": False,
    "status": "IDLE",
    "run_id": None,
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
    "output_dir": None,
    "stdout_tail": "",
    "stderr_tail": "",
    "message": "No UI-triggered demo validation run yet.",
}

SOAP_FAULT = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Client</faultcode>
      <faultstring>{faultstring}</faultstring>
      <detail>
        <mcad:MCAD xmlns:mcad="urn:mcad">
          <mcad:decision>{decision}</mcad:decision>
          <mcad:phi>{phi}</mcad:phi>
          <mcad:threshold>{threshold}</mcad:threshold>
          <mcad:objective_id>{objective_id}</mcad:objective_id>
          <mcad:session_id>{session_id}</mcad:session_id>
          <mcad:step_index>{step_index}</mcad:step_index>
          <mcad:decision_reason_code>{decision_reason_code}</mcad:decision_reason_code>
          <mcad:decision_reason>{decision_reason}</mcad:decision_reason>
          <mcad:is_redundant>{is_redundant}</mcad:is_redundant>
          <mcad:has_marginal_gain>{has_marginal_gain}</mcad:has_marginal_gain>
          <mcad:explain>{explain}</mcad:explain>
        </mcad:MCAD>
      </detail>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>
"""


def mdx_fingerprint(mdx: str) -> str:
    return hashlib.sha256((mdx or "").encode("utf-8")).hexdigest()[:16]


_JSESSION_RE = re.compile(r"(?:^|;\s*)JSESSIONID=([^;]+)")


def extract_session_cookie(req: Request) -> str | None:
    cookie = req.headers.get("cookie") or ""
    m = _JSESSION_RE.search(cookie)
    if not m:
        return None
    js = m.group(1).strip()
    return js[:64] if js else None


def classify_xmla(xml_bytes: bytes) -> tuple[str, str | None]:
    try:
        root = etree.fromstring(xml_bytes)
        stmt_nodes = root.xpath("//*[local-name()='Statement']")
        if stmt_nodes:
            mdx = (stmt_nodes[0].text or "").strip()
            return ("EXECUTE", mdx if mdx else None)
        rt_nodes = root.xpath("//*[local-name()='RequestType']")
        if rt_nodes:
            rt = (rt_nodes[0].text or "").strip()
            return ("DISCOVER", rt if rt else None)
        return ("OTHER", None)
    except Exception:
        return ("OTHER", None)


def forward_xmla(body: bytes, content_type: str, timeout_s: int = 60) -> requests.Response:
    return requests.post(
        UPSTREAM,
        data=body,
        headers={"Content-Type": content_type or "text/xml"},
        timeout=timeout_s,
    )



def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _collect_id_values(value, key_hints: tuple[str, ...], active: bool = False) -> list[str]:
    """Collect string identifiers from nested MCAD payloads when keys look relevant."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_l = str(key).lower()
            child_active = active or any(hint in key_l for hint in key_hints)
            found.extend(_collect_id_values(nested, key_hints, child_active))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_collect_id_values(item, key_hints, active))
    elif active and value is not None:
        found.append(str(value))
    return found


def _parse_mdx_graph_features(mdx: str) -> dict[str, list[str]]:
    """Generic MDX feature fallback; query ids are not used for semantics."""
    text = mdx or ""
    measures = sorted(set(re.findall(r"\[Measures\]\.\[([^\]]+)\]", text, flags=re.IGNORECASE)))
    members: list[str] = []
    for match in re.finditer(r"\[([^\]]+)\](?:\.\[([^\]]+)\])+(?!\.)", text):
        raw = match.group(0)
        if raw.lower().startswith("[measures]"):
            continue
        members.append(raw.replace("[", "").replace("]", ""))
    slicers: list[str] = []
    where = re.search(r"WHERE\s*\((.*)\)\s*$", text, flags=re.IGNORECASE | re.DOTALL)
    if where:
        slicers = [
            m.replace("[", "").replace("]", "")
            for m in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\])+", where.group(1))
        ]
    return {
        "measures": measures,
        "grain": sorted(set(members)),
        "slicers": sorted(set(slicers)),
    }


def _classify_blocked_reasons(decision: dict, det: dict, graph_update: dict) -> list[str]:
    code = str(decision.get("decision_reason_code") or det.get("decision_reason_code") or "")
    text = " ".join([
        code,
        str(decision.get("decision_reason") or det.get("decision_reason") or ""),
        str(decision.get("explain") or ""),
    ]).lower()
    if graph_update.get("redundant") or re.search(r"redundant|delta[_ ]?phi|dphi|marginal", text):
        return ["redundant / Δφ = 0"]
    if re.search(r"slicer|slice|filter|where|time_window|window|region|state|country", text):
        return ["slicer mismatch"]
    if re.search(r"measure|kpi|metric|non.?target", text):
        return ["measure mismatch"]
    if re.search(r"grain|level|granular|group.?by|aggregation", text):
        return ["grain mismatch"]
    if "sat" in text or "satisf" in text:
        return ["SAT mismatch"]
    if "real" in text:
        return ["resource mismatch"]
    if "ceval" in text or "calcul" in text:
        return ["Ceval mismatch"]
    return [code or "blocked"]


def _normalize_graph_update(decision: dict, mdx: str) -> dict:
    """
    Normalize the MCAD decision payload into graph-update semantics.
    The mapping is generic and MCAD-result-driven; query_id is provenance only.
    """
    det = decision.get("details") if isinstance(decision.get("details"), dict) else {}

    delta_phi = det.get("delta_phi_t", det.get("delta_phi", decision.get("delta_phi")))
    try:
        delta_phi_num = float(delta_phi) if delta_phi is not None else None
    except (TypeError, ValueError):
        delta_phi_num = None

    useful_part = det.get("useful_part", decision.get("useful_part"))
    useful_constraint_ids = _collect_id_values(useful_part, ("constraint",))
    useful_resource_ids = _collect_id_values(useful_part, ("resource", "node_id"))

    graph_update = {
        "covered_constraints": sorted(set(
            _as_list(det.get("covered_constraints"))
            + _as_list(det.get("calculable_constraints_total"))
            + _as_list(det.get("newly_contributed_constraints_total"))
            + _as_list(decision.get("newly_contributed_constraints_total"))
            + useful_constraint_ids
        )),
        "partially_covered_constraints": sorted(set(
            _as_list(det.get("calculable_constraints_partial"))
            + _as_list(det.get("newly_contributed_constraints_partial"))
            + _as_list(decision.get("newly_contributed_constraints_partial"))
        )),
        "observed_resources": sorted(set(
            _as_list(det.get("observed_resources"))
            + _as_list(det.get("covered_resource_ids"))
            + _as_list(det.get("gained_resource_ids"))
            + _as_list(det.get("real_node_ids"))
            + useful_resource_ids
        )),
        "covered_resources": sorted(set(
            _as_list(det.get("explicitly_covered_resource_ids"))
            + _as_list(det.get("useful_resource_ids"))
        )),
        "blocked_resources": sorted(set(
            _as_list(det.get("blocked_resource_ids"))
            + _as_list(det.get("rejected_resource_ids"))
        )),
        "blocked_reasons": [],
        "redundant": bool(decision.get("is_redundant", det.get("is_redundant", False)))
        or (delta_phi_num == 0 and str(decision.get("decision", "")).upper() == "BLOCK"),
        "delta_phi": delta_phi_num,
        "decision": str(decision.get("decision") or "").upper(),
        "useful_part": useful_part,
    }

    if graph_update["decision"] == "BLOCK" or graph_update["redundant"]:
        graph_update["blocked_reasons"] = _classify_blocked_reasons(decision, det, graph_update)

    qspec = det.get("query_spec") if isinstance(det.get("query_spec"), dict) else {}
    graph_update["measures"] = _as_list(det.get("measures") or qspec.get("measures"))
    graph_update["slicers"] = det.get("slicers") or qspec.get("slicers") or {}
    graph_update["grain"] = _as_list(det.get("grain") or qspec.get("group_by"))
    graph_update["time_window"] = det.get("time_window") or {
        "start": qspec.get("window_start"),
        "end": qspec.get("window_end"),
    }

    graph_update["mdx_features"] = _parse_mdx_graph_features(mdx)
    if not graph_update["measures"]:
        graph_update["measures"] = graph_update["mdx_features"]["measures"]
    if not graph_update["grain"]:
        graph_update["grain"] = graph_update["mdx_features"]["grain"]
    if not graph_update["slicers"]:
        graph_update["slicers"] = graph_update["mdx_features"]["slicers"]

    return graph_update


# ---------------------------------------------------------------------------
# V8.2 graph-state contract for the Governance Cytoscape view.
# This contract is derived from MCAD evaluation outputs first. When the current
# prototype response is still incomplete, it uses a generic MDX feature fallback
# based on QP features, never on query ids or scenario order.
# ---------------------------------------------------------------------------

_OBJECTIVE_REQUIRED_CONSTRAINTS: dict[str, list[str]] = {
    "O_REAL_BEER_WA_MONTH": ["c_sales", "c_profit"],
}


def _norm_text(value) -> str:
    return str(value or "").strip().lower()


def _norm_id(value) -> str:
    txt = re.sub(r"[^a-z0-9]+", "_", _norm_text(value))
    return txt.strip("_")


def _graph_values_blob(*values) -> str:
    chunks: list[str] = []
    for v in values:
        if isinstance(v, dict):
            chunks.append(json.dumps(v, ensure_ascii=False))
        elif isinstance(v, (list, tuple, set)):
            chunks.extend(_graph_values_blob(x) for x in v)
        elif v is not None:
            chunks.append(str(v))
    return " ".join(chunks).lower()


def _canonical_constraint_id(value: str) -> str | None:
    t = _norm_id(value)
    raw = _norm_text(value)
    if not t and not raw:
        return None
    if any(x in t for x in ("c_sales", "sales_constraint", "store_sales", "sales", "revenue")):
        if "unit_sales" not in t:
            return "c_sales"
    if any(x in t for x in ("c_profit", "profit_constraint", "profit", "margin")):
        return "c_profit"
    return None


def _canonical_virtual_node_id(value: str) -> str | None:
    t = _norm_id(value)
    if any(x in t for x in ("n_c_sales", "nv_sales", "virtual_sales", "store_sales", "c_sales")) and "unit_sales" not in t:
        return "N_c_sales"
    if any(x in t for x in ("n_c_profit", "nv_profit", "virtual_profit", "profit", "c_profit")):
        return "N_c_profit"
    return None


def _canonicalize_constraints(values) -> list[str]:
    out: list[str] = []
    for v in _as_list(values):
        c = _canonical_constraint_id(v)
        out.append(c or str(v))
    return sorted(set(x for x in out if x))


def _canonicalize_virtual_nodes(values) -> list[str]:
    out: list[str] = []
    for v in _as_list(values):
        n = _canonical_virtual_node_id(v)
        out.append(n or str(v))
    return sorted(set(x for x in out if x))


def _infer_objective_constraint_from_qp_features(graph_update: dict, mdx: str) -> tuple[list[str], list[str]]:
    """Infer current prototype FoodMart objective coverage from QP features.

    This is a semantic QP-feature fallback, not a query-id mapping. It is used
    only when MCAD does not yet expose explicit Ceval/Real node identifiers.
    """
    decision = str(graph_update.get("decision") or "").upper()
    if decision == "BLOCK":
        return [], []

    blob = _graph_values_blob(
        graph_update.get("measures"),
        graph_update.get("grain"),
        graph_update.get("slicers"),
        graph_update.get("mdx_features"),
        mdx,
    )

    has_month = "month" in blob and "year" not in blob
    has_wa = re.search(r"\bwa\b|washington", blob) is not None
    has_beer = "beer and wine" in blob or ("beer" in blob and "wine" in blob)
    target_slice_ok = has_month and has_wa and has_beer

    covered: list[str] = []
    realized: list[str] = []
    if target_slice_ok and "store sales" in blob and "unit sales" not in blob:
        covered.append("c_sales")
        realized.append("N_c_sales")
    if target_slice_ok and "profit" in blob:
        covered.append("c_profit")
        realized.append("N_c_profit")
    return sorted(set(covered)), sorted(set(realized))


def _required_constraints_for_objective(objective_id: str | None) -> list[str]:
    return _OBJECTIVE_REQUIRED_CONSTRAINTS.get(str(objective_id or ""), ["c_sales", "c_profit"])


def _empty_graph_session_state(objective_id: str | None, session_id: str | None = None) -> dict[str, object]:
    required = _required_constraints_for_objective(objective_id)
    return {
        "session_id": session_id,
        "objective_id": objective_id,
        "required_constraints": required,
        "covered_constraints": [],
        "partially_covered_constraints": [],
        "pending_constraints": required,
        "realized_virtual_nodes": [],
        "objective_state": "pending",
        "session_phi": 0.0,
        "last_delta_phi": 0.0,
    }


def _merge_graph_session_state(session_id: str | None, objective_id: str | None, graph_update: dict) -> dict:
    key = str(session_id or "__no_session__")
    state = GRAPH_SESSION_STATES.setdefault(key, _empty_graph_session_state(objective_id, session_id))
    required = _required_constraints_for_objective(objective_id)
    state["session_id"] = session_id
    state["objective_id"] = objective_id
    state["required_constraints"] = required

    covered = set(_canonicalize_constraints(state.get("covered_constraints", [])))
    partial = set(_canonicalize_constraints(state.get("partially_covered_constraints", [])))
    realized = set(_canonicalize_virtual_nodes(state.get("realized_virtual_nodes", [])))

    # ALLOW updates can add coverage; BLOCK updates only preserve existing
    # coverage and expose explanations outside the main objective graph.
    if str(graph_update.get("decision") or "").upper() == "ALLOW":
        covered.update(_canonicalize_constraints(graph_update.get("covered_constraints", [])))
        partial.update(_canonicalize_constraints(graph_update.get("partially_covered_constraints", [])))
        realized.update(_canonicalize_virtual_nodes(graph_update.get("realized_virtual_nodes", [])))
        # observed_resources are provenance only; they must not realize N(c).
        realized.update(_canonicalize_virtual_nodes(graph_update.get("covered_resources", [])))

    # If a constraint is fully covered, it is no longer merely partial.
    partial.difference_update(covered)

    pending = [c for c in required if c not in covered]
    if required and all(c in covered for c in required):
        objective_state = "covered"
    elif covered or partial:
        objective_state = "partial"
    else:
        objective_state = "pending"

    session_phi = (len([c for c in required if c in covered]) / len(required)) if required else 0.0
    state.update({
        "covered_constraints": sorted(covered),
        "partially_covered_constraints": sorted(partial),
        "pending_constraints": pending,
        "realized_virtual_nodes": sorted(realized),
        "objective_state": objective_state,
        "session_phi": session_phi,
        "last_delta_phi": graph_update.get("delta_phi"),
    })
    return dict(state)


def _finalize_graph_update_contract(decision: dict, graph_update: dict, mdx: str, session_id: str | None, objective_id: str | None) -> dict:
    graph_update = dict(graph_update or {})
    graph_update["objective_id"] = objective_id
    graph_update["session_id"] = session_id

    explicit_covered = _canonicalize_constraints(graph_update.get("covered_constraints", []))
    explicit_partial = _canonicalize_constraints(graph_update.get("partially_covered_constraints", []))
    explicit_realized = _canonicalize_virtual_nodes(
        graph_update.get("realized_virtual_nodes", [])
        or graph_update.get("realized_nodes", [])
        or graph_update.get("real_node_ids", [])
    )

    if str(graph_update.get("decision") or decision.get("decision") or "").upper() == "BLOCK":
        explicit_covered = []
        explicit_partial = []
        explicit_realized = []
    elif not explicit_covered and not explicit_partial:
        inferred_covered, inferred_realized = _infer_objective_constraint_from_qp_features(graph_update, mdx)
        explicit_covered = inferred_covered
        explicit_realized = sorted(set(explicit_realized + inferred_realized))

    graph_update["covered_constraints"] = explicit_covered
    graph_update["partially_covered_constraints"] = explicit_partial
    graph_update["realized_virtual_nodes"] = explicit_realized

    session_state = _merge_graph_session_state(session_id, objective_id, graph_update)
    graph_update["required_constraints"] = session_state["required_constraints"]
    graph_update["cumulative_covered_constraints"] = session_state["covered_constraints"]
    graph_update["cumulative_partially_covered_constraints"] = session_state["partially_covered_constraints"]
    graph_update["pending_constraints"] = session_state["pending_constraints"]
    graph_update["cumulative_realized_virtual_nodes"] = session_state["realized_virtual_nodes"]
    graph_update["objective_state"] = session_state["objective_state"]
    graph_update["session_phi"] = session_state["session_phi"]
    graph_update["contract_version"] = "mcad.graph_update.v1"
    return graph_update


def _constraint_state(constraint_id: str, state: dict[str, object]) -> str:
    covered = set(_canonicalize_constraints(state.get("covered_constraints", [])))
    partial = set(_canonicalize_constraints(state.get("partially_covered_constraints", [])))
    if constraint_id in covered:
        return "covered"
    if constraint_id in partial:
        return "partial"
    return "pending"


def _virtual_node_state(node_id: str, constraint_id: str, state: dict[str, object]) -> str:
    realized = set(_canonicalize_virtual_nodes(state.get("realized_virtual_nodes", [])))
    if node_id in realized:
        return "realized"
    if _constraint_state(constraint_id, state) == "covered":
        return "realized"
    return "pending"


def _current_graph_session_state() -> dict[str, object]:
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    key = str(sid or "__no_session__")
    if key not in GRAPH_SESSION_STATES:
        GRAPH_SESSION_STATES[key] = _empty_graph_session_state(oid, sid)
    state = dict(GRAPH_SESSION_STATES[key])
    state["session_id"] = sid
    state["objective_id"] = oid
    state["required_constraints"] = _required_constraints_for_objective(oid)
    return state


def _build_graph_state_payload() -> dict[str, object]:
    """Return the canonical UI graph state for Cytoscape.

    This endpoint is intentionally graph-structure oriented: it exposes
    O -> C*(O) -> N(c) plus node states. Query ids and BLOCK reasons remain
    provenance/decision data and are not structural graph nodes.
    """
    state = _current_graph_session_state()
    sid = state.get("session_id")
    oid = state.get("objective_id")
    required = _canonicalize_constraints(state.get("required_constraints", [])) or ["c_sales", "c_profit"]
    covered = _canonicalize_constraints(state.get("covered_constraints", []))
    partial = _canonicalize_constraints(state.get("partially_covered_constraints", []))
    realized = _canonicalize_virtual_nodes(state.get("realized_virtual_nodes", []))
    pending = [c for c in required if c not in covered]
    objective_state = str(state.get("objective_state") or "pending")
    session_phi = float(state.get("session_phi") or 0.0)

    def node(nid: str, label: str, ntype: str, nstate: str, **extra: object) -> dict[str, object]:
        return {"id": nid, "label": label, "type": ntype, "state": nstate, **extra}

    nodes = [
        node(str(oid or "O_REAL_BEER_WA_MONTH"), "Objective O", "objective", objective_state,
             definition="Finite set of analytical constraints C*(O)."),
        node("c_sales", "Constraint c_sales", "constraint", _constraint_state("c_sales", state),
             definition="Store Sales calculability."),
        node("N_c_sales", "Virtual node N(c_sales)", "virtual_node", _virtual_node_state("N_c_sales", "c_sales", state),
             fact="Sales cube", measure="Store Sales", grain="Time.Month", slicers="WA / Beer & Wine"),
        node("c_profit", "Constraint c_profit", "constraint", _constraint_state("c_profit", state),
             definition="Profit calculability."),
        node("N_c_profit", "Virtual node N(c_profit)", "virtual_node", _virtual_node_state("N_c_profit", "c_profit", state),
             fact="Sales cube", measure="Profit", grain="Time.Month", slicers="WA / Beer & Wine"),
    ]
    edges = [
        {"id": "e_obj_sales", "source": str(oid or "O_REAL_BEER_WA_MONTH"), "target": "c_sales", "type": "HAS_CONSTRAINT"},
        {"id": "e_sales_nv", "source": "c_sales", "target": "N_c_sales", "type": "SUPPORTED_BY"},
        {"id": "e_obj_profit", "source": str(oid or "O_REAL_BEER_WA_MONTH"), "target": "c_profit", "type": "HAS_CONSTRAINT"},
        {"id": "e_profit_nv", "source": "c_profit", "target": "N_c_profit", "type": "SUPPORTED_BY"},
    ]
    graph_update = {
        "contract_version": "mcad.graph_update.v1",
        "source": "GET /mcad/graph/state",
        "session_id": sid,
        "objective_id": oid,
        "required_constraints": required,
        "cumulative_covered_constraints": covered,
        "cumulative_partially_covered_constraints": partial,
        "cumulative_realized_virtual_nodes": realized,
        "covered_constraints": covered,
        "partially_covered_constraints": partial,
        "realized_virtual_nodes": realized,
        "pending_constraints": pending,
        "objective_state": objective_state,
        "session_phi": session_phi,
        "last_delta_phi": state.get("last_delta_phi"),
    }
    return {
        "ok": True,
        "contract_version": "mcad.graph_state.v1",
        "session_id": sid,
        "objective_id": oid,
        "dw_id": ACTIVE_CONTEXT.get("dw_id"),
        "objective_state": objective_state,
        "session_phi": session_phi,
        "nodes": nodes,
        "edges": edges,
        "graph_update": graph_update,
        "last_decision": LAST_DECISION,
        "metrics": {
            "completion_rate": session_phi,
            "calculability_rate_total": session_phi,
            "calculability_rate_partial": 0.0 if objective_state == "covered" else session_phi,
            "analytic_alignment_score": session_phi,
        },
    }



def _fault_from_decision(decision: dict, session_id: str | None) -> str:
    det = decision.get("details") if isinstance(decision.get("details"), dict) else {}
    phi = float(decision.get("phi", 0.0) or 0.0)
    theta = float(decision.get("threshold", 0.0) or 0.0)
    objective_id = str(det.get("objective_id") or decision.get("objective_id") or ACTIVE_CONTEXT.get("objective_id") or "")
    step_index = str(det.get("step_index") or decision.get("step_index") or "")
    explain = str(decision.get("explain") or "")
    code = str(decision.get("decision_reason_code") or det.get("decision_reason_code") or "BLOCK_GENERIC")
    reason = str(decision.get("decision_reason") or det.get("decision_reason") or explain or "Blocked by MCAD")
    short = f"MCAD BLOCK [{code}]"
    return SOAP_FAULT.format(
        faultstring=xml_escape(short),
        decision=xml_escape(str(decision.get("decision", "BLOCK"))),
        phi=xml_escape(f"{phi:.6f}"),
        threshold=xml_escape(f"{theta:.6f}"),
        objective_id=xml_escape(objective_id),
        session_id=xml_escape(str(session_id or det.get("session_id") or ACTIVE_CONTEXT.get("session_id") or "")),
        step_index=xml_escape(step_index),
        decision_reason_code=xml_escape(code),
        decision_reason=xml_escape(reason),
        is_redundant=xml_escape(str(bool(decision.get("is_redundant", det.get("is_redundant", False)))).lower()),
        has_marginal_gain=xml_escape(str(bool(decision.get("has_marginal_gain", det.get("has_marginal_gain", False)))).lower()),
        explain=xml_escape(explain),
    )


def _coerce_int(value, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _coerce_float(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _result_summary_dict(direct_result, public_result) -> dict:
    if isinstance(public_result, dict):
        out = dict(public_result)
    else:
        out = {}
    raw = getattr(direct_result, "raw_result_summary", None) if direct_result is not None else None
    if isinstance(raw, dict):
        for key, value in raw.items():
            out.setdefault(key, value)
    return out


def _build_execution_evidence(
    *,
    decision: dict,
    direct_result,
    public_result,
    graph_update: dict,
    query_text: str,
    query_type: str,
    dw_id: str,
    query_id: str,
    payload: dict,
    eval_elapsed_ms: int | None = None,
) -> dict:
    """Build the UI/proof contract shown after each BI execution.

    This evidence object is deliberately compact: it records MCAD's gate, the
    selected physical execution source, and reproducibility digests without
    storing the full XMLA payload or full table result.
    """
    det = decision.get("details") if isinstance(decision.get("details"), dict) else {}
    summary = _result_summary_dict(direct_result, public_result)
    decision_kind = str(decision.get("decision") or "").upper()
    allowed = decision_kind == "ALLOW"
    status_code = _coerce_int(summary.get("status_code"), _coerce_int(getattr(direct_result, "status_code", None), None))
    error = summary.get("error") or getattr(direct_result, "error", None) if direct_result is not None else summary.get("error")
    physical_execution = bool(
        allowed
        and (direct_result is not None or bool(summary.get("physical_execution", False)))
        and summary.get("physical_execution", status_code is not None and int(status_code) < 400)
        and not error
    )
    response_digest = str(
        summary.get("response_digest")
        or summary.get("result_digest")
        or getattr(direct_result, "response_digest", "")
        or ""
    )
    response_bytes = _coerce_int(summary.get("response_bytes"), _coerce_int(getattr(direct_result, "response_bytes", None), None))
    elapsed_ms = _coerce_int(summary.get("elapsed_ms"), _coerce_int(getattr(direct_result, "elapsed_ms", None), None))
    adapter_id = str(summary.get("adapter_id") or getattr(direct_result, "adapter_id", "") or "")
    adapter_family = str(summary.get("adapter_family") or summary.get("execution_path") or adapter_id or "")
    backend_type = str(summary.get("backend_type") or getattr(direct_result, "backend_type", "") or "")
    selected_dw_id = str(summary.get("dw_id") or getattr(direct_result, "dw_id", "") or dw_id or "")
    row_count = summary.get("row_count")
    if row_count is None and isinstance(summary.get("rows"), list):
        row_count = len(summary.get("rows") or [])
    columns_count = None
    if isinstance(summary.get("columns"), list):
        columns_count = len(summary.get("columns") or [])
    return {
        "contract_version": "mcad.execution_evidence.v1",
        "generated_at_ms": int(time.time() * 1000),
        "query": {
            "query_id": query_id or payload.get("scenario_query_id") or None,
            "query_type": query_type,
            "query_digest": mdx_fingerprint(query_text),
            "execution_mode": payload.get("execution_mode") or payload.get("query_mode"),
            "scenario_instance_id": payload.get("scenario_instance_id"),
            "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
            "scenario_query_index": payload.get("scenario_query_index"),
            "scenario_query_id": payload.get("scenario_query_id") or query_id or None,
        },
        "mcad_gate": {
            "allowed_by_mcad": allowed,
            "decision": decision.get("decision"),
            "decision_reason_code": decision.get("decision_reason_code") or det.get("decision_reason_code"),
            "decision_reason": decision.get("decision_reason") or det.get("decision_reason"),
            "session_id": det.get("session_id") or ACTIVE_CONTEXT.get("session_id"),
            "objective_id": det.get("objective_id") or ACTIVE_CONTEXT.get("objective_id"),
            "step_index": det.get("step_index") or decision.get("step_index"),
            "eval_elapsed_ms": eval_elapsed_ms,
            "fail_closed": bool(decision.get("decision_reason_code") == "EVAL_UNREACHABLE" or decision.get("decision") == "BLOCK"),
        },
        "formal_metrics": {
            "sat": _coerce_float(decision.get("sat")),
            "real": _coerce_float(decision.get("real")),
            "ceval": _coerce_float(decision.get("ceval")),
            "phi": _coerce_float(decision.get("phi")),
            "delta_phi": _coerce_float(decision.get("delta_phi", decision.get("dphi", det.get("delta_phi_t")))),
            "threshold": _coerce_float(decision.get("threshold")),
        },
        "sat_clauses": det.get("sat_checks") or decision.get("sat_checks") or {},
        "execution": {
            "attempted": direct_result is not None,
            "physical_execution": physical_execution,
            "status": "EXECUTED" if physical_execution else ("MCAD_BLOCKED" if not allowed else "EXECUTION_FAILED"),
            "requested_dw_id": dw_id,
            "selected_dw_id": selected_dw_id,
            "adapter_id": adapter_id or None,
            "adapter_family": adapter_family or None,
            "backend_type": backend_type or None,
            "execution_path": summary.get("execution_path") or adapter_family or backend_type or None,
            "logical_query_language": summary.get("logical_query_language") or query_type,
            "physical_query_language": summary.get("physical_query_language"),
            "catalog": summary.get("catalog"),
            "cube": summary.get("cube"),
            "forwarded_to": summary.get("forwarded_to") or summary.get("xmla_url"),
            "xmla_response_type": summary.get("xmla_response_type") or summary.get("response_type"),
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "response_bytes": response_bytes,
            "response_digest": response_digest or None,
            "result_digest": response_digest or None,
            "row_count": row_count,
            "columns_count": columns_count,
            "fallback_used": bool(summary.get("fallback_used", False)),
            "demo_materialized": bool(summary.get("demo_materialized", False)),
            "error": error,
        },
        "graph_update_summary": {
            "covered_constraints": graph_update.get("covered_constraints") or graph_update.get("cumulative_covered_constraints"),
            "partially_covered_constraints": graph_update.get("partially_covered_constraints") or graph_update.get("cumulative_partially_covered_constraints"),
            "realized_virtual_nodes": graph_update.get("realized_virtual_nodes") or graph_update.get("cumulative_realized_virtual_nodes"),
            "delta_phi": graph_update.get("delta_phi"),
            "measures": graph_update.get("measures"),
            "grain": graph_update.get("grain"),
            "slicers": graph_update.get("slicers"),
        },
    }


def _load_session_ui_html() -> str:
    p = Path(__file__).with_name("session_ui.html")
    if p.exists():
        return p.read_text(encoding="utf-8")

def _selectable_datawarehouse_items(include_disabled: bool = False) -> list[dict]:
    """Return DWs intended for the user-facing selector.

    The registry may contain future/experimental DWs (AdventureWorksDW,
    SteelWheels, etc.) so they can be documented and health-checked, but they
    must not be selectable until their physical adapter/catalog is actually
    integrated. This prevents accidental sessions that appear to run FoodMart
    queries while the active DW id says AdventureWorks.
    """
    items = list_datawarehouses()
    if include_disabled:
        return items
    return [x for x in items if x.get("enabled", True) is not False]


def _get_dw_config_or_400(dw_id: str):
    try:
        return get_gateway().get_config(dw_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "code": "UNKNOWN_DW",
            "message": f"Unknown data warehouse: {dw_id}",
            "dw_id": dw_id,
            "error": str(exc),
        })


def _ensure_dw_enabled_or_400(dw_id: str):
    cfg = _get_dw_config_or_400(dw_id)
    if getattr(cfg, "enabled", True) is False:
        raise HTTPException(status_code=400, detail={
            "code": "DW_DISABLED",
            "message": (
                f"Data warehouse '{dw_id}' is registered but disabled/unimplemented. "
                "Use 'foodmart' for FoodMart via XMLA/eMondrian or "
                "'foodmart_sql_direct' for FoodMart via Direct BI."
            ),
            "dw_id": dw_id,
            "label": getattr(cfg, "label", dw_id),
            "enabled": False,
            "experimental": getattr(cfg, "experimental", None),
        })
    return cfg




def _compat_norm(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _dataset_key(value) -> str:
    """Canonical dataset key used for scenario/DW compatibility checks."""
    raw = str(value or "")
    key = _compat_norm(raw)
    if "foodmart" in key or key in {"food", "mart"}:
        return "foodmart"
    if "adventureworks" in key or "adventureworksdw" in key or key == "awdw":
        return "adventureworksdw"
    if "steelwheels" in key or "sampledata" in key or "pentaho" in key:
        return "steelwheels"
    return key


def _dw_dataset_key(dw_id: str | None) -> str:
    if not dw_id:
        return ""
    try:
        cfg = get_gateway().get_config(str(dw_id))
        return _dataset_key(getattr(cfg, "dataset", None) or getattr(cfg, "catalog", None) or dw_id)
    except Exception:
        return _dataset_key(dw_id)


def _dw_enabled_flag(dw_id: str | None) -> bool:
    if not dw_id:
        return False
    try:
        cfg = get_gateway().get_config(str(dw_id))
        return bool(getattr(cfg, "enabled", True) is not False)
    except Exception:
        return False


def _scenario_declared_dataset_key(sc: dict | None) -> str:
    if not isinstance(sc, dict):
        return ""
    for key in ("dataset", "dataset_id", "logical_dataset"):
        if sc.get(key):
            return _dataset_key(sc.get(key))
    dw = str(sc.get("dw_id") or sc.get("dw") or "").strip()
    if dw:
        return _dw_dataset_key(dw)
    # Defensive heuristic for legacy imported scenarios without a declared DW.
    blob = json.dumps({k: sc.get(k) for k in ("id", "scenario_id", "name", "description")}, ensure_ascii=False)
    return _dataset_key(blob)


def _scenario_compatibility(sc: dict | None, objective_id: str | None = None, dw_id: str | None = None) -> dict:
    """Return an explicit scenario/objective/DW compatibility report.

    Rules:
    - objective_id must match the active/session objective when both are known;
    - selected DW must be enabled;
    - scenario logical dataset must match the selected DW dataset;
    - FoodMart scenarios are therefore compatible with both foodmart XMLA and
      foodmart_sql_direct because both declare dataset=FoodMart.
    """
    sc = sc or {}
    errors: list[dict] = []
    warnings: list[dict] = []
    active_objective = str(objective_id or ACTIVE_CONTEXT.get("objective_id") or "").strip()
    active_dw = str(dw_id or ACTIVE_CONTEXT.get("dw_id") or "").strip()
    scenario_id = str(sc.get("id") or sc.get("scenario_id") or "").strip()
    scenario_objective = str(sc.get("objective_id") or sc.get("objective") or "").strip()
    scenario_dw = str(sc.get("dw_id") or sc.get("dw") or "").strip()
    scenario_dataset = _scenario_declared_dataset_key(sc)
    selected_dataset = _dw_dataset_key(active_dw)

    if active_objective and scenario_objective and scenario_objective != active_objective:
        errors.append({
            "code": "OBJECTIVE_MISMATCH",
            "message": f"Scenario objective '{scenario_objective}' is incompatible with active objective '{active_objective}'.",
            "scenario_objective_id": scenario_objective,
            "active_objective_id": active_objective,
        })
    elif not scenario_objective:
        warnings.append({"code": "SCENARIO_OBJECTIVE_MISSING", "message": "Scenario does not declare objective_id; active objective will be used."})

    if active_dw:
        try:
            cfg = get_gateway().get_config(active_dw)
            if getattr(cfg, "enabled", True) is False:
                errors.append({
                    "code": "DW_DISABLED",
                    "message": f"Selected data warehouse '{active_dw}' is disabled/unimplemented.",
                    "selected_dw_id": active_dw,
                    "selected_dw_label": getattr(cfg, "label", active_dw),
                })
        except Exception:
            errors.append({"code": "UNKNOWN_DW", "message": f"Selected data warehouse '{active_dw}' is not registered.", "selected_dw_id": active_dw})

    if scenario_dataset and selected_dataset and scenario_dataset != selected_dataset:
        errors.append({
            "code": "DATASET_MISMATCH",
            "message": f"Scenario dataset '{scenario_dataset}' is incompatible with selected DW dataset '{selected_dataset}'.",
            "scenario_dataset": scenario_dataset,
            "selected_dataset": selected_dataset,
            "scenario_dw_id": scenario_dw,
            "selected_dw_id": active_dw,
        })
    elif not scenario_dataset:
        warnings.append({"code": "SCENARIO_DATASET_UNKNOWN", "message": "Scenario dataset could not be inferred; compatibility is permissive."})

    return {
        "compatible": not errors,
        "scenario_id": scenario_id,
        "scenario_objective_id": scenario_objective or None,
        "active_objective_id": active_objective or None,
        "scenario_dw_id": scenario_dw or None,
        "selected_dw_id": active_dw or None,
        "scenario_dataset": scenario_dataset or None,
        "selected_dataset": selected_dataset or None,
        "errors": errors,
        "warnings": warnings,
        "reason_codes": [e.get("code") for e in errors],
    }


def _attach_scenario_compatibility(sc: dict, objective_id: str | None = None, dw_id: str | None = None) -> dict:
    out = dict(sc)
    compat = _scenario_compatibility(out, objective_id=objective_id, dw_id=dw_id)
    out["compatibility"] = compat
    out["compatible"] = bool(compat.get("compatible"))
    out["compatibility_errors"] = compat.get("errors", [])
    out["compatibility_warnings"] = compat.get("warnings", [])
    return out


def _scenario_compatibility_block_response(sc: dict | None, compat: dict, query_text: str, query_type: str, query_id: str, objective_id: str, dw_id: str, session_id: str | None, payload: dict) -> dict:
    reason = "; ".join(str(e.get("message") or e.get("code")) for e in compat.get("errors", [])) or "Scenario is incompatible with the active objective/DW."
    decision = {
        "decision": "BLOCK",
        "phi": 0.0,
        "threshold": 0.0,
        "sat": 1.0,
        "real": 0.0,
        "ceval": 0.0,
        "decision_reason_code": "BLOCK_SCENARIO_OBJECTIVE_DW_INCOMPATIBLE",
        "decision_reason": reason,
        "explain": reason,
        "details": {
            "session_id": session_id or ACTIVE_CONTEXT.get("session_id"),
            "objective_id": objective_id or ACTIVE_CONTEXT.get("objective_id"),
            "dw_id": dw_id,
            "scenario_compatibility": compat,
            "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
        },
    }
    graph_update = _finalize_graph_update_contract(decision, {}, query_text, session_id, objective_id)
    evidence = _build_execution_evidence(
        decision=decision,
        direct_result=None,
        public_result=None,
        graph_update=graph_update,
        query_text=query_text,
        query_type=query_type,
        dw_id=dw_id,
        query_id=query_id,
        payload=payload,
        eval_elapsed_ms=None,
    )
    LAST_EXECUTION_EVIDENCE.clear(); LAST_EXECUTION_EVIDENCE.update(evidence); _archive_execution_evidence(evidence)
    LAST_DECISION.clear(); LAST_DECISION.update({
        "decision": "BLOCK",
        "decision_reason_code": decision["decision_reason_code"],
        "decision_reason": reason,
        "objective_id": objective_id,
        "session_id": session_id,
        "dw_id": dw_id,
        "query_id": query_id,
        "phi": 0.0,
        "threshold": 0.0,
        "sat": 1.0,
        "real": 0.0,
        "ceval": 0.0,
        "details": decision["details"],
        "execution_evidence": evidence,
        "graph_update": graph_update,
        "ts_ms": int(time.time() * 1000),
    })
    return {
        "ok": True,
        "mode": "hybrid_bi_gateway",
        "gateway": "mcad.execution_gateway.v2.hybrid",
        "compatibility_guard": "scenario_objective_dw.v1",
        "scenario_compatibility": compat,
        "query_id": query_id,
        "dw_id": dw_id,
        "adapter_id": None,
        "execution_path": None,
        "decision": decision,
        "execution_evidence": evidence,
        "graph_update": graph_update,
        "direct_result": None,
        "active": ACTIVE_CONTEXT,
    }


def _disabled_dw_decision(dw_id: str, query_text: str, query_type: str, query_id: str, objective_id: str, session_id: str | None, payload: dict) -> dict:
    cfg = _get_dw_config_or_400(dw_id)
    reason = f"Data warehouse '{dw_id}' is disabled/unimplemented; no physical execution is allowed."
    decision = {
        "decision": "BLOCK",
        "phi": 0.0,
        "threshold": 0.0,
        "sat": 0.0,
        "real": 0.0,
        "ceval": 0.0,
        "decision_reason_code": "BLOCK_DISABLED_DW",
        "decision_reason": reason,
        "explain": reason,
        "details": {
            "session_id": session_id or ACTIVE_CONTEXT.get("session_id"),
            "objective_id": objective_id or ACTIVE_CONTEXT.get("objective_id"),
            "dw_id": dw_id,
        },
    }
    evidence = {
        "contract_version": "mcad.execution_evidence.v1",
        "generated_at_ms": int(time.time() * 1000),
        "query": {
            "query_id": query_id or payload.get("scenario_query_id") or None,
            "query_type": query_type,
            "query_digest": mdx_fingerprint(query_text),
            "execution_mode": payload.get("execution_mode") or payload.get("query_mode"),
            "scenario_instance_id": payload.get("scenario_instance_id"),
            "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
            "scenario_query_index": payload.get("scenario_query_index"),
            "scenario_query_id": payload.get("scenario_query_id") or query_id or None,
        },
        "mcad_gate": {
            "allowed_by_mcad": False,
            "decision": "BLOCK",
            "decision_reason_code": "BLOCK_DISABLED_DW",
            "decision_reason": reason,
            "session_id": session_id or ACTIVE_CONTEXT.get("session_id"),
            "objective_id": objective_id or ACTIVE_CONTEXT.get("objective_id"),
            "step_index": None,
            "eval_elapsed_ms": None,
            "fail_closed": True,
        },
        "formal_metrics": {"sat": 0.0, "real": 0.0, "ceval": 0.0, "phi": 0.0, "delta_phi": 0.0, "threshold": 0.0},
        "sat_clauses": {},
        "execution": {
            "attempted": False,
            "physical_execution": False,
            "status": "DW_DISABLED",
            "requested_dw_id": dw_id,
            "selected_dw_id": dw_id,
            "adapter_id": getattr(cfg, "adapter", None),
            "adapter_family": getattr(cfg, "backend_type", None),
            "backend_type": getattr(cfg, "backend_type", None),
            "execution_path": getattr(cfg, "backend_type", None),
            "logical_query_language": query_type,
            "physical_query_language": getattr(cfg, "physical_query_language", None),
            "catalog": getattr(cfg, "catalog", None),
            "cube": getattr(cfg, "cube", None),
            "status_code": None,
            "elapsed_ms": None,
            "response_bytes": None,
            "response_digest": None,
            "result_digest": None,
            "row_count": 0,
            "columns_count": 0,
            "error": reason,
        },
        "graph_update_summary": {},
    }
    LAST_DECISION.clear(); LAST_DECISION.update(decision)
    LAST_EXECUTION_EVIDENCE.clear(); LAST_EXECUTION_EVIDENCE.update(evidence)
    _archive_execution_evidence(evidence)
    return {
        "ok": True,
        "decision": decision,
        "direct_result": None,
        "bi_result": None,
        "execution_evidence": evidence,
        "execution_allowed_by_mcad": False,
        "physical_execution": False,
    }

# ---------------------------------------------------------------------------
# V9.4.3a — evidence propagation helpers
# ---------------------------------------------------------------------------
def _read_json_file(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8") or "null") or default
    except Exception as exc:
        print(f"unable to read JSON file {path}: {exc}")
    return default


def _write_json_file(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        print(f"unable to write JSON file {path}: {exc}")


def _evidence_session_id(ev: dict | None) -> str:
    if not isinstance(ev, dict):
        return ""
    gate = ev.get("mcad_gate") if isinstance(ev.get("mcad_gate"), dict) else {}
    return str(gate.get("session_id") or ev.get("session_id") or "")


def _evidence_step_index(ev: dict | None):
    if not isinstance(ev, dict):
        return None
    gate = ev.get("mcad_gate") if isinstance(ev.get("mcad_gate"), dict) else {}
    step = gate.get("step_index") or ev.get("step_index")
    try:
        return int(step)
    except Exception:
        return None


def _evidence_query_id(ev: dict | None) -> str:
    if not isinstance(ev, dict):
        return ""
    q = ev.get("query") if isinstance(ev.get("query"), dict) else {}
    return str(q.get("scenario_query_id") or q.get("query_id") or ev.get("query_id") or "")


def _evidence_query_digest(ev: dict | None) -> str:
    if not isinstance(ev, dict):
        return ""
    q = ev.get("query") if isinstance(ev.get("query"), dict) else {}
    return str(q.get("query_digest") or ev.get("query_digest") or "")




def _article_blocked_before_execution(ev: dict | None, exe: dict | None = None, gate: dict | None = None) -> bool:
    ev = ev or {}
    exe = exe or ev.get("execution") or {}
    gate = gate or ev.get("gate") or ev.get("mcad_gate") or {}

    if ev.get("blocked_before_execution") is not None:
        return bool(ev.get("blocked_before_execution"))

    if exe.get("blocked_before_execution") is not None:
        return bool(exe.get("blocked_before_execution"))

    decision = str(
        gate.get("decision")
        or ev.get("decision")
        or exe.get("decision")
        or ""
    ).upper()

    physical_execution = exe.get("physical_execution")
    execution_path = str(exe.get("execution_path") or exe.get("path") or "").lower()
    execution_status = str(exe.get("execution_status") or exe.get("status") or "").lower()

    if decision == "BLOCK" and physical_execution is False:
        return True

    if "not_executed" in execution_path or "not-executed" in execution_path:
        return True

    if "rejected" in execution_status or "blocked" in execution_status:
        return True

    return False

def _flatten_execution_evidence(ev: dict | None) -> dict:
    if not isinstance(ev, dict):
        return {}
    gate = ev.get("mcad_gate") if isinstance(ev.get("mcad_gate"), dict) else {}
    exe = ev.get("execution") if isinstance(ev.get("execution"), dict) else {}
    fm = ev.get("formal_metrics") if isinstance(ev.get("formal_metrics"), dict) else {}
    q = ev.get("query") if isinstance(ev.get("query"), dict) else {}
    return {
        "execution_status": exe.get("status"),
        "execution_path": exe.get("execution_path") or exe.get("adapter_family"),
        "adapter_id": exe.get("adapter_id") or exe.get("adapter_family"),
        "selected_dw_id": exe.get("selected_dw_id") or exe.get("requested_dw_id"),
        "requested_dw_id": exe.get("requested_dw_id"),
        "physical_execution": exe.get("physical_execution"),
        "blocked_before_execution": _article_blocked_before_execution(ev, exe, gate),
        "execution_attempted": exe.get("attempted"),
        "status_code": exe.get("status_code"),
        "elapsed_ms": exe.get("elapsed_ms"),
        "response_bytes": exe.get("response_bytes"),
        "response_digest": exe.get("response_digest") or exe.get("result_digest"),
        "result_digest": exe.get("result_digest") or exe.get("response_digest"),
        "xmla_response_type": exe.get("xmla_response_type"),
        "row_count": exe.get("row_count"),
        "columns_count": exe.get("columns_count"),
        "mcad_allowed": gate.get("allowed_by_mcad"),
        "mcad_decision": gate.get("decision"),
        "decision_reason_code": gate.get("decision_reason_code"),
        "decision_reason": gate.get("decision_reason"),
        "objective_id": gate.get("objective_id"),
        "session_id": gate.get("session_id"),
        "step_index": gate.get("step_index"),
        "query_id": q.get("query_id"),
        "scenario_query_id": q.get("scenario_query_id"),
        "query_digest": q.get("query_digest"),
        "sat": fm.get("sat"),
        "real": fm.get("real"),
        "ceval": fm.get("ceval"),
        "phi": fm.get("phi"),
        "delta_phi": fm.get("delta_phi"),
        "threshold": fm.get("threshold"),
    }


def _load_execution_evidence_store() -> dict:
    data = _read_json_file(_EXECUTION_EVIDENCE_FILE, {"version": "mcad.execution_evidence_archive.v1", "sessions": {}})
    if not isinstance(data, dict):
        data = {"version": "mcad.execution_evidence_archive.v1", "sessions": {}}
    data.setdefault("version", "mcad.execution_evidence_archive.v1")
    data.setdefault("sessions", {})
    return data


def _save_execution_evidence_store(data: dict) -> None:
    _write_json_file(_EXECUTION_EVIDENCE_FILE, data)


def _archive_execution_evidence(ev: dict | None) -> None:
    if not isinstance(ev, dict) or not ev:
        return
    sid = _evidence_session_id(ev) or str(ACTIVE_CONTEXT.get("session_id") or "")
    if not sid:
        return
    ev = json.loads(json.dumps(ev, ensure_ascii=False))  # detach mutable refs
    ev.setdefault("archive_recorded_at_ms", int(time.time() * 1000))
    ev["report_fields"] = _flatten_execution_evidence(ev)
    step = _evidence_step_index(ev)
    qid = _evidence_query_id(ev)
    qdig = _evidence_query_digest(ev)
    store = _load_execution_evidence_store()
    sessions = store.setdefault("sessions", {})
    items = sessions.setdefault(sid, [])
    replaced = False
    for i, old in enumerate(items):
        same_step = step is not None and _evidence_step_index(old) == step
        same_qid = qid and _evidence_query_id(old) == qid
        same_qdig = qdig and _evidence_query_digest(old) == qdig
        if same_step or (same_qid and same_qdig):
            items[i] = ev
            replaced = True
            break
    if not replaced:
        items.append(ev)
    items.sort(key=lambda x: (_evidence_step_index(x) if _evidence_step_index(x) is not None else 10**9, int(x.get("generated_at_ms") or 0)))
    store["updated_at_ms"] = int(time.time() * 1000)
    _save_execution_evidence_store(store)


def _clear_session_execution_evidence(sid: str | None) -> None:
    if not sid:
        return
    store = _load_execution_evidence_store()
    if isinstance(store.get("sessions"), dict) and str(sid) in store["sessions"]:
        store["sessions"][str(sid)] = []
        store["updated_at_ms"] = int(time.time() * 1000)
        _save_execution_evidence_store(store)


def _session_execution_evidence(sid: str | None) -> list[dict]:
    if not sid:
        return []
    store = _load_execution_evidence_store()
    items = (store.get("sessions") or {}).get(str(sid), [])
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def _latest_session_execution_evidence(sid: str | None) -> dict:
    items = _session_execution_evidence(sid)
    if not items:
        return {}
    return items[-1]


def _row_step_index(row: dict | None):
    if not isinstance(row, dict):
        return None
    for key in ("step_index", "step", "idx", "n"):
        try:
            if row.get(key) not in (None, ""):
                return int(row.get(key))
        except Exception:
            pass
    det = row.get("details") if isinstance(row.get("details"), dict) else {}
    try:
        if det.get("step_index") not in (None, ""):
            return int(det.get("step_index"))
    except Exception:
        pass
    return None


def _row_query_id(row: dict | None) -> str:
    if not isinstance(row, dict):
        return ""
    sc = row.get("scenario") if isinstance(row.get("scenario"), dict) else {}
    return str(sc.get("scenario_query_id") or row.get("scenario_query_id") or row.get("query_id") or row.get("id") or "")


def _row_query_digest(row: dict | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("query_digest") or row.get("query_fingerprint") or mdx_fingerprint(str(row.get("mdx") or row.get("query") or "")))


def _evidence_index(sid: str | None) -> dict:
    items = _session_execution_evidence(sid)
    by_step: dict[int, dict] = {}
    by_qid: dict[str, dict] = {}
    by_digest: dict[str, dict] = {}
    for ev in items:
        step = _evidence_step_index(ev)
        qid = _evidence_query_id(ev)
        qdig = _evidence_query_digest(ev)
        if step is not None:
            by_step[step] = ev
        if qid:
            by_qid[qid] = ev
        if qdig:
            by_digest[qdig] = ev
    return {"items": items, "by_step": by_step, "by_qid": by_qid, "by_digest": by_digest}


def _evidence_for_row(row: dict, idx: dict, ordinal: int | None = None) -> dict:
    step = _row_step_index(row)
    if step is not None and step in idx["by_step"]:
        return idx["by_step"][step]
    qid = _row_query_id(row)
    if qid and qid in idx["by_qid"]:
        return idx["by_qid"][qid]
    qdig = _row_query_digest(row)
    if qdig and qdig in idx["by_digest"]:
        return idx["by_digest"][qdig]
    if ordinal is not None and 0 <= ordinal < len(idx["items"]):
        return idx["items"][ordinal]
    return {}


def _enrich_rows_with_evidence(rows, sid: str | None):
    if not isinstance(rows, list):
        return rows
    idx = _evidence_index(sid)
    enriched = []
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict):
            enriched.append(row)
            continue
        ev = _evidence_for_row(row, idx, ordinal)
        out = dict(row)
        if ev:
            flat = _flatten_execution_evidence(ev)
            out["execution_evidence"] = ev
            out["execution_evidence_contract"] = ev.get("contract_version")
            for key, value in flat.items():
                if value is not None and out.get(key) in (None, ""):
                    out[key] = value
        enriched.append(out)
    return enriched


def _evidence_summary(sid: str | None) -> dict:
    items = _session_execution_evidence(sid)
    paths: dict[str, int] = {}
    adapters: dict[str, int] = {}
    physical = 0
    xmla = 0
    direct = 0
    digests = 0
    blocked = 0
    for ev in items:
        flat = _flatten_execution_evidence(ev)
        p = str(flat.get("execution_path") or "not_executed")
        a = str(flat.get("adapter_id") or "none")
        paths[p] = paths.get(p, 0) + 1
        adapters[a] = adapters.get(a, 0) + 1
        if flat.get("physical_execution") is True:
            physical += 1
        if "xmla" in p.lower() or "xmla" in a.lower():
            xmla += 1
        if "direct" in p.lower() or "direct" in a.lower() or "sql" in p.lower():
            direct += 1
        if flat.get("response_digest"):
            digests += 1
        if flat.get("execution_status") == "MCAD_BLOCKED":
            blocked += 1
    return {
        "contract_version": "mcad.execution_evidence_archive.v1",
        "evidence_rows": len(items),
        "physical_execution_count": physical,
        "mcad_blocked_count": blocked,
        "xmla_execution_count": xmla,
        "direct_bi_execution_count": direct,
        "digest_count": digests,
        "execution_paths": paths,
        "adapters": adapters,
    }


def _enrich_report_payload_with_evidence(report, sid: str | None):
    if not isinstance(report, dict):
        return report
    out = dict(report)
    if isinstance(out.get("rows"), list):
        out["rows"] = _enrich_rows_with_evidence(out.get("rows"), sid)
    if isinstance(out.get("trace"), list):
        out["trace"] = _enrich_rows_with_evidence(out.get("trace"), sid)
    summary = dict(out.get("summary") or {}) if isinstance(out.get("summary"), dict) else {}
    summary["execution_evidence_summary"] = _evidence_summary(sid)
    out["summary"] = summary
    out["execution_evidence_items"] = _session_execution_evidence(sid)
    return out


def _append_execution_evidence_markdown(markdown_text: str, sid: str | None, title: str = "Execution Evidence") -> str:
    items = _session_execution_evidence(sid)
    if not items:
        return markdown_text.rstrip() + f"\n\n## {title}\n\nNo execution evidence archived for this session.\n"
    lines = [markdown_text.rstrip(), "", f"## {title}", "", "| Step | Query | MCAD | Path | Adapter | Physical | HTTP | Elapsed ms | Rows | Digest |", "|---:|---|---|---|---|:---:|---:|---:|---:|---|"]
    for ev in items:
        f = _flatten_execution_evidence(ev)
        digest = str(f.get("response_digest") or "")
        if len(digest) > 18:
            digest = digest[:18] + "…"
        lines.append("| {step} | {qid} | {mcad} | {path} | {adapter} | {physical} | {status} | {elapsed} | {rows} | `{digest}` |".format(
            step=f.get("step_index") or "",
            qid=str(f.get("scenario_query_id") or f.get("query_id") or "").replace("|", "\\|"),
            mcad=str(f.get("mcad_decision") or "").replace("|", "\\|"),
            path=str(f.get("execution_path") or "not_executed").replace("|", "\\|"),
            adapter=str(f.get("adapter_id") or "—").replace("|", "\\|"),
            physical=str(bool(f.get("physical_execution"))).lower(),
            status=f.get("status_code") if f.get("status_code") is not None else "",
            elapsed=f.get("elapsed_ms") if f.get("elapsed_ms") is not None else "",
            rows=f.get("row_count") if f.get("row_count") is not None else "",
            digest=digest or "—",
        ))
    summary = _evidence_summary(sid)
    lines += ["", "### Evidence summary", "", "```json", json.dumps(summary, indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(lines)


def _enrich_csv_with_evidence(csv_text: str, sid: str | None) -> str:
    try:
        src = io.StringIO(csv_text)
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            return csv_text
        rows = list(reader)
        idx = _evidence_index(sid)
        evidence_fields = [
            "execution_status", "execution_path", "adapter_id", "selected_dw_id",
            "physical_execution", "blocked_before_execution", "status_code", "elapsed_ms", "response_bytes",
            "response_digest", "xmla_response_type", "row_count",
        ]
        fieldnames = list(reader.fieldnames)
        for f in evidence_fields:
            if f not in fieldnames:
                fieldnames.append(f)
        out_rows = []
        for ordinal, row in enumerate(rows):
            ev = _evidence_for_row(row, idx, ordinal)
            if ev:
                flat = _flatten_execution_evidence(ev)
                for f in evidence_fields:
                    row[f] = flat.get(f, "")
            out_rows.append(row)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
        return buf.getvalue()
    except Exception as exc:
        print("CSV evidence enrichment failed:", exc)
        return csv_text

    return "<html><body><h1>MCAD BI Decision Dashboard V7</h1></body></html>"


# V9.4.6 — Demo Evidence Viewer helpers
_DEMO_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _demo_evidence_root() -> Path:
    return DEMO_EVIDENCE_DIR


def _demo_runs_root() -> Path:
    return _demo_evidence_root() / "runs"


def _safe_demo_run_id(run_id: str | None) -> str:
    rid = str(run_id or "").strip()
    if not rid or not _DEMO_RUN_ID_RE.match(rid) or ".." in rid or "/" in rid or "\\" in rid:
        raise HTTPException(status_code=400, detail={"code": "INVALID_DEMO_RUN_ID", "message": f"Invalid demo evidence run id: {rid!r}"})
    return rid


def _demo_latest_run_id() -> str | None:
    root = _demo_evidence_root()
    latest_file = root / "latest_path.txt"
    if latest_file.exists():
        try:
            raw = latest_file.read_text(encoding="utf-8").strip()
            if raw:
                rid = Path(raw).name
                if rid and _DEMO_RUN_ID_RE.match(rid):
                    return rid
        except Exception:
            pass
    runs_root = _demo_runs_root()
    if not runs_root.exists():
        return None
    candidates = []
    for d in runs_root.iterdir():
        if d.is_dir() and (d / "dual_path_summary.json").exists():
            candidates.append(d)
    if not candidates:
        return None
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0].name


def _demo_run_dir(run_id: str | None = None) -> Path:
    rid = _safe_demo_run_id(run_id or _demo_latest_run_id())
    d = _demo_runs_root() / rid
    root_resolved = _demo_runs_root().resolve()
    try:
        resolved = d.resolve()
        if not str(resolved).startswith(str(root_resolved)):
            raise HTTPException(status_code=400, detail={"code": "INVALID_DEMO_RUN_PATH"})
    except FileNotFoundError:
        pass
    if not d.exists() or not d.is_dir():
        raise HTTPException(status_code=404, detail={"code": "DEMO_RUN_NOT_FOUND", "message": f"Demo evidence run not found: {rid}", "demo_evidence_dir": str(_demo_evidence_root())})
    return d


def _read_demo_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_parse_error": str(exc), "_path": str(path)}


def _read_demo_text(path: Path) -> str:
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "DEMO_ARTIFACT_NOT_FOUND", "path": str(path)})
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_demo_steps_csv(text: str) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(text or ""))
        return [dict(row) for row in reader]
    except Exception:
        return []


def _demo_run_payload(run_id: str | None = None, include_text: bool = False) -> dict:
    d = _demo_run_dir(run_id)
    rid = d.name
    summary = _read_demo_json(d / "dual_path_summary.json", {}) or {}
    csv_text = _read_demo_text(d / "dual_path_steps.csv") if (d / "dual_path_steps.csv").exists() else ""
    steps = _parse_demo_steps_csv(csv_text)
    md_path = d / "dual_path_summary.md"
    md_preview = ""
    if md_path.exists():
        md = _read_demo_text(md_path)
        md_preview = md[:4000]
    raw_dir = d / "raw"
    raw_files = sorted([x.name for x in raw_dir.glob("*.json")]) if raw_dir.exists() else []
    digest_files = sorted([x.name for x in d.glob("*_response_digest.txt")])
    payload = {
        "ok": True,
        "contract_version": "mcad.demo_evidence_viewer.v1",
        "run_id": rid,
        "is_latest": rid == _demo_latest_run_id(),
        "demo_evidence_dir": str(_demo_evidence_root()),
        "run_dir": str(d),
        "overall_status": summary.get("overall_status"),
        "passed_steps": summary.get("passed_steps"),
        "total_steps": summary.get("total_steps"),
        "generated_at": summary.get("generated_at"),
        "base_url": summary.get("base_url"),
        "summary": summary,
        "steps": steps,
        "raw_files": raw_files,
        "digest_files": digest_files,
        "artifacts": {
            "summary_json": "dual_path_summary.json",
            "summary_markdown": "dual_path_summary.md",
            "steps_csv": "dual_path_steps.csv",
        },
        "markdown_preview": md_preview,
    }
    if include_text:
        payload["markdown"] = _read_demo_text(md_path) if md_path.exists() else ""
        payload["csv"] = csv_text
    return payload


def _relay_get(path: str) -> dict:
    try:
        r = requests.get(f"{MCAD_API_BASE}{path}", timeout=10)
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MCAD_API_UNAVAILABLE",
                "message": "MCAD API is not reachable yet. Retry after the mcad-api service is ready.",
                "path": path,
                "mcad_api_base": MCAD_API_BASE,
                "error": str(e),
            },
        ) from e
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:1000]
        raise HTTPException(status_code=r.status_code, detail=detail)
    try:
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from MCAD API for {path}: {e}") from e


def _relay_post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{MCAD_API_BASE}{path}", json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MCAD_API_UNAVAILABLE",
                "message": "MCAD API is not reachable yet. Retry after the mcad-api service is ready.",
                "path": path,
                "mcad_api_base": MCAD_API_BASE,
                "payload_keys": sorted(list(payload.keys())) if isinstance(payload, dict) else [],
                "error": str(e),
            },
        ) from e
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:1000]
        raise HTTPException(status_code=r.status_code, detail=detail)
    try:
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from MCAD API for {path}: {e}") from e

DEFAULT_FOODMART_Q1_Q6_SCENARIOS = [
    {
        "id": "Q1_ALLOW_USEFUL",
        "query_id": "Q1_ALLOW_USEFUL",
        "label": "Q1 — ALLOW utile",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "ALLOW",
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
    },
    {
        "id": "Q2_ALLOW_COMPLEMENTARY",
        "query_id": "Q2_ALLOW_COMPLEMENTARY",
        "label": "Q2 — ALLOW complémentaire",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "ALLOW",
        "mdx": "SELECT {[Measures].[Profit]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
    },
    {
        "id": "Q3_BLOCK_OUT_OF_OBJECTIVE",
        "query_id": "Q3_BLOCK_OUT_OF_OBJECTIVE",
        "label": "Q3 — BLOCK hors objectif",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "BLOCK",
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[CA])",
    },
    {
        "id": "Q4_BLOCK_REDUNDANT",
        "query_id": "Q4_BLOCK_REDUNDANT",
        "label": "Q4 — BLOCK redondant",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "BLOCK",
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
    },
    {
        "id": "Q5_BLOCK_NON_TARGET_MEASURE",
        "query_id": "Q5_BLOCK_NON_TARGET_MEASURE",
        "label": "Q5 — BLOCK mesure non ciblée",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "BLOCK",
        "mdx": "SELECT {[Measures].[Unit Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
    },
    {
        "id": "Q6_BLOCK_BAD_GRAIN",
        "query_id": "Q6_BLOCK_BAD_GRAIN",
        "label": "Q6 — BLOCK grain non conforme",
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": "BLOCK",
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Year].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
    },
]


def _load_foodmart_q1_q6_scenarios() -> list[dict]:
    candidates = [
        Path("/app/direct-scenarios/foodmart_q1_q6.json"),
        Path(__file__).resolve().parents[1] / "direct-scenarios" / "foodmart_q1_q6.json",
        Path(__file__).resolve().parent / "direct-scenarios" / "foodmart_q1_q6.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception as e:
                print(f"Could not load direct scenario file {p}: {e}")
    return DEFAULT_FOODMART_Q1_Q6_SCENARIOS



@app.get("/mcad/demo-evidence/runs")
def mcad_demo_evidence_runs():
    root = _demo_runs_root()
    items = []
    if root.exists():
        for d in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True):
            summary = _read_demo_json(d / "dual_path_summary.json", {}) or {}
            items.append({
                "run_id": d.name,
                "mtime": int(d.stat().st_mtime),
                "overall_status": summary.get("overall_status"),
                "passed_steps": summary.get("passed_steps"),
                "total_steps": summary.get("total_steps"),
                "generated_at": summary.get("generated_at"),
                "has_markdown": (d / "dual_path_summary.md").exists(),
                "has_csv": (d / "dual_path_steps.csv").exists(),
            })
    return {"ok": True, "demo_evidence_dir": str(_demo_evidence_root()), "latest_run_id": _demo_latest_run_id(), "items": items}


@app.get("/mcad/demo-evidence/latest")
def mcad_demo_evidence_latest():
    rid = _demo_latest_run_id()
    if not rid:
        return {"ok": False, "code": "NO_DEMO_EVIDENCE_RUN", "message": "No dual-path demo evidence run has been found. Run: bash bi-stack/scripts/run_dual_path_demo_validation.sh .", "demo_evidence_dir": str(_demo_evidence_root()), "items": []}
    return _demo_run_payload(rid)


@app.get("/mcad/demo-evidence/runs/{run_id}")
def mcad_demo_evidence_run(run_id: str):
    return _demo_run_payload(run_id)


@app.get("/mcad/demo-evidence/latest/json")
def mcad_demo_evidence_latest_json():
    rid = _demo_latest_run_id()
    if not rid:
        raise HTTPException(status_code=404, detail={"code": "NO_DEMO_EVIDENCE_RUN"})
    d = _demo_run_dir(rid)
    return JSONResponse(_read_demo_json(d / "dual_path_summary.json", {}) or {})


@app.get("/mcad/demo-evidence/runs/{run_id}/json")
def mcad_demo_evidence_run_json(run_id: str):
    d = _demo_run_dir(run_id)
    return JSONResponse(_read_demo_json(d / "dual_path_summary.json", {}) or {})


@app.get("/mcad/demo-evidence/latest/markdown")
def mcad_demo_evidence_latest_markdown():
    rid = _demo_latest_run_id()
    if not rid:
        raise HTTPException(status_code=404, detail={"code": "NO_DEMO_EVIDENCE_RUN"})
    return Response(content=_read_demo_text(_demo_run_dir(rid) / "dual_path_summary.md"), media_type="text/markdown; charset=utf-8")


@app.get("/mcad/demo-evidence/runs/{run_id}/markdown")
def mcad_demo_evidence_run_markdown(run_id: str):
    return Response(content=_read_demo_text(_demo_run_dir(run_id) / "dual_path_summary.md"), media_type="text/markdown; charset=utf-8")


@app.get("/mcad/demo-evidence/latest/csv")
def mcad_demo_evidence_latest_csv():
    rid = _demo_latest_run_id()
    if not rid:
        raise HTTPException(status_code=404, detail={"code": "NO_DEMO_EVIDENCE_RUN"})
    return Response(content=_read_demo_text(_demo_run_dir(rid) / "dual_path_steps.csv"), media_type="text/csv; charset=utf-8")


@app.get("/mcad/demo-evidence/runs/{run_id}/csv")
def mcad_demo_evidence_run_csv(run_id: str):
    return Response(content=_read_demo_text(_demo_run_dir(run_id) / "dual_path_steps.csv"), media_type="text/csv; charset=utf-8")


# V9.4.7 — One-click demo validation runner + bundle export

def _demo_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _demo_runner_script() -> Path:
    candidates = [
        Path("/app/scripts/run_dual_path_demo_validation.py"),
        Path(__file__).resolve().parent / "scripts" / "run_dual_path_demo_validation.py",
        Path(__file__).resolve().parents[1] / "scripts" / "run_dual_path_demo_validation.py" if len(Path(__file__).resolve().parents) > 1 else Path("missing"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise HTTPException(
        status_code=500,
        detail={
            "code": "DEMO_RUNNER_SCRIPT_NOT_FOUND",
            "message": "run_dual_path_demo_validation.py was not found inside the proxy container. Ensure ./scripts is mounted to /app/scripts.",
            "candidates": [str(c) for c in candidates],
        },
    )


def _demo_status_snapshot() -> dict:
    with DEMO_RUN_LOCK:
        snap = dict(DEMO_RUN_STATE)
    latest = _demo_latest_run_id()
    snap["latest_run_id"] = latest
    if latest:
        try:
            snap["latest_summary"] = _demo_run_payload(latest)
        except Exception as exc:
            snap["latest_summary_error"] = str(exc)
    return {"ok": True, "contract_version": "mcad.demo_runner_status.v1", "state": snap}


def _update_demo_run_state(**kw) -> None:
    with DEMO_RUN_LOCK:
        DEMO_RUN_STATE.update(kw)


def _tail_text(text: str, limit: int = 6000) -> str:
    text = text or ""
    return text[-limit:] if len(text) > limit else text


def _run_demo_validation_worker(run_id: str, output_dir: str, base_url: str, retry_attempts: int, retry_sleep_s: float) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stdout_text = ""
    stderr_text = ""
    exit_code = None
    status = "FAIL"
    try:
        script = _demo_runner_script()
        env = os.environ.copy()
        env["MCAD_PROXY_BASE"] = base_url
        env["MCAD_DEMO_RETRY_ATTEMPTS"] = str(retry_attempts)
        env["MCAD_DEMO_RETRY_SLEEP_S"] = str(retry_sleep_s)
        env["MCAD_DEMO_EVIDENCE_DIR"] = str(_demo_evidence_root())
        repo_root = "/app" if Path("/app").exists() else str(Path(__file__).resolve().parents[1])
        cmd = [sys.executable, str(script), repo_root, "--base-url", base_url, "--output-dir", str(out)]
        _update_demo_run_state(message="Dual-path validation is running.", command=" ".join(cmd))
        proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=DEMO_RUN_TIMEOUT_S)
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        exit_code = proc.returncode
        (out / "ui_run_stdout.log").write_text(stdout_text, encoding="utf-8")
        (out / "ui_run_stderr.log").write_text(stderr_text, encoding="utf-8")
        latest_file = _demo_evidence_root() / "latest_path.txt"
        latest_file.parent.mkdir(parents=True, exist_ok=True)
        latest_file.write_text(str(out) + "\n", encoding="utf-8")
        summary = _read_demo_json(out / "dual_path_summary.json", {}) or {}
        status = "PASS" if exit_code == 0 and str(summary.get("overall_status") or "").upper() == "PASS" else "FAIL"
        _update_demo_run_state(
            running=False,
            status=status,
            run_id=run_id,
            finished_at=_demo_now_iso(),
            exit_code=exit_code,
            output_dir=str(out),
            stdout_tail=_tail_text(stdout_text),
            stderr_tail=_tail_text(stderr_text),
            message=f"Dual-path validation finished with {status}.",
            summary=summary,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        (out / "ui_run_stdout.log").write_text(stdout_text if isinstance(stdout_text, str) else str(stdout_text), encoding="utf-8")
        (out / "ui_run_stderr.log").write_text(stderr_text if isinstance(stderr_text, str) else str(stderr_text), encoding="utf-8")
        _update_demo_run_state(
            running=False,
            status="TIMEOUT",
            run_id=run_id,
            finished_at=_demo_now_iso(),
            exit_code=None,
            output_dir=str(out),
            stdout_tail=_tail_text(str(stdout_text)),
            stderr_tail=_tail_text(str(stderr_text)),
            message=f"Dual-path validation timed out after {DEMO_RUN_TIMEOUT_S}s.",
        )
    except Exception as exc:
        _update_demo_run_state(
            running=False,
            status="ERROR",
            run_id=run_id,
            finished_at=_demo_now_iso(),
            exit_code=exit_code,
            output_dir=str(out),
            stdout_tail=_tail_text(stdout_text),
            stderr_tail=_tail_text(stderr_text + "\n" + str(exc)),
            message=f"Dual-path validation failed before completion: {exc}",
        )


@app.post("/mcad/demo-evidence/run")
async def mcad_demo_evidence_run_start(req: Request):
    payload = {}
    try:
        payload = await req.json()
    except Exception:
        payload = {}
    with DEMO_RUN_LOCK:
        if DEMO_RUN_STATE.get("running"):
            return JSONResponse(status_code=409, content={"ok": False, "code": "DEMO_RUN_ALREADY_RUNNING", "state": dict(DEMO_RUN_STATE)})
        run_id = time.strftime("%Y%m%d_%H%M%S")
        output_dir = _demo_runs_root() / run_id
        retry_attempts = int(payload.get("retry_attempts") or os.getenv("MCAD_DEMO_RETRY_ATTEMPTS", "24"))
        retry_sleep_s = float(payload.get("retry_sleep_s") or os.getenv("MCAD_DEMO_RETRY_SLEEP_S", "1.0"))
        base_url = str(payload.get("base_url") or "http://127.0.0.1:9000")
        DEMO_RUN_STATE.update({
            "running": True,
            "status": "RUNNING",
            "run_id": run_id,
            "started_at": _demo_now_iso(),
            "finished_at": None,
            "exit_code": None,
            "output_dir": str(output_dir),
            "stdout_tail": "",
            "stderr_tail": "",
            "message": "Dual-path validation started from UI.",
        })
    th = threading.Thread(target=_run_demo_validation_worker, args=(run_id, str(output_dir), base_url, retry_attempts, retry_sleep_s), daemon=True)
    th.start()
    return {"ok": True, "started": True, "run_id": run_id, "status": "RUNNING", "output_dir": str(output_dir), "retry_attempts": retry_attempts, "retry_sleep_s": retry_sleep_s}


@app.get("/mcad/demo-evidence/run/status")
def mcad_demo_evidence_run_status():
    return _demo_status_snapshot()


def _build_demo_bundle(run_id: str | None = None) -> Path:
    d = _demo_run_dir(run_id or _demo_latest_run_id())
    rid = d.name
    bundle_dir = _demo_evidence_root() / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle = bundle_dir / f"mcad_demo_evidence_{rid}.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for child in sorted(d.rglob("*")):
            if child.is_file():
                zf.write(child, arcname=str(Path(rid) / child.relative_to(d)))
    return bundle


@app.get("/mcad/demo-evidence/latest/bundle.zip")
def mcad_demo_evidence_latest_bundle():
    rid = _demo_latest_run_id()
    if not rid:
        raise HTTPException(status_code=404, detail={"code": "NO_DEMO_EVIDENCE_RUN"})
    bundle = _build_demo_bundle(rid)
    return FileResponse(path=str(bundle), media_type="application/zip", filename=bundle.name)


@app.get("/mcad/demo-evidence/runs/{run_id}/bundle.zip")
def mcad_demo_evidence_run_bundle(run_id: str):
    rid = _safe_demo_run_id(run_id)
    bundle = _build_demo_bundle(rid)
    return FileResponse(path=str(bundle), media_type="application/zip", filename=bundle.name)


@app.get("/health")
def health():
    gateway_health = {}
    try:
        gateway_health = get_gateway().health()
    except Exception as exc:
        gateway_health = {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "service": "mcad-proxy",
        "mode": "hybrid_bi_gateway",
        "gateway": "mcad.execution_gateway.v2.hybrid",
        "upstream": UPSTREAM,
        "mcad_eval": MCAD_EVAL_URL,
        "mcad_ckg": MCAD_CKG_URL,
        "active_context": ACTIVE_CONTEXT,
        "last_decision": LAST_DECISION,
        "dw_gateway_health": gateway_health,
        "demo_evidence": {"dir": str(_demo_evidence_root()), "latest_run_id": _demo_latest_run_id()},
    }


@app.get("/mcad/objectives")
def mcad_objectives():
    data = _relay_get("/objectives")
    return {"ok": True, "items": data if isinstance(data, list) else data.get("items", [])}


@app.post("/mcad/objectives/validate")
async def mcad_objectives_validate(req: Request):
    payload = await req.json()
    return _relay_post("/objectives/validate", payload)


@app.post("/mcad/objectives/import")
async def mcad_objectives_import(req: Request):
    payload = await req.json()
    return _relay_post("/objectives/import", payload)


@app.get("/mcad/objectives/{objective_id}")
def mcad_objective_detail(objective_id: str):
    return _relay_get(f"/objectives/{objective_id}")

@app.delete("/mcad/objectives/{objective_id}")
def mcad_objective_delete(objective_id: str):
    r = requests.delete(f"{MCAD_API_BASE}/objectives/{objective_id}", timeout=20)
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:1000]
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()

@app.get("/mcad/sessions")
def mcad_sessions():
    data = _relay_get("/sessions")
    return {"ok": True, "items": data if isinstance(data, list) else data.get("items", [])}


# MCAD_UI_V948_SESSION_DELETE_PROXY
@app.delete("/mcad/sessions/{session_id}")
def mcad_session_delete(session_id: str):
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")

    r = requests.delete(f"{MCAD_API_BASE}/sessions/{sid}", timeout=60)
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:2000]
        raise HTTPException(status_code=r.status_code, detail=detail)

    api_delete = r.json()
    try:
        evidence_result = _clear_session_execution_evidence(sid) or {}
    except Exception as exc:
        evidence_result = {"cleared": False, "error": str(exc)}

    GRAPH_SESSION_STATES.pop(sid, None)
    deleted_active = str(ACTIVE_CONTEXT.get("session_id") or "") == sid
    if deleted_active:
        ACTIVE_CONTEXT["session_id"] = None
        ACTIVE_CONTEXT["objective_id"] = None
        ACTIVE_CONTEXT["dw_id"] = None
        LAST_DECISION.clear()
        LAST_EXECUTION_EVIDENCE.clear()

    return {
        "ok": True,
        "deleted_session_id": sid,
        "deleted_active_session": deleted_active,
        "api_delete": api_delete,
        "proxy_execution_evidence": evidence_result,
        "active": ACTIVE_CONTEXT,
    }



@app.get("/mcad/datawarehouses")
def mcad_datawarehouses(include_disabled: bool = False):
    """Return DWs that are safe to select in the UI.

    Disabled future integrations remain available through health/metadata routes
    when requested with include_disabled=true, but the default selector now shows
    only executable options: FoodMart via XMLA/eMondrian and FoodMart via Direct BI.
    """
    return {
        "ok": True,
        "gateway": "mcad.execution_gateway.v2.hybrid",
        "items": _selectable_datawarehouse_items(include_disabled=include_disabled),
        "include_disabled": include_disabled,
    }


@app.get("/mcad/datawarehouses/health")
def mcad_datawarehouses_health():
    return get_gateway().health()


@app.get("/mcad/datawarehouses/{dw_id}/health")
def mcad_datawarehouse_health(dw_id: str):
    return get_gateway().health_one(dw_id)


@app.get("/mcad/datawarehouses/{dw_id}/metadata")
def mcad_datawarehouse_metadata(dw_id: str):
    return get_gateway().metadata(dw_id)


@app.get("/mcad/session/current")
def mcad_session_current():
    return {"ok": True, "active": ACTIVE_CONTEXT, "last_decision": LAST_DECISION, "execution_evidence": LAST_EXECUTION_EVIDENCE}


@app.get("/mcad/evidence/current")
def mcad_evidence_current():
    sid = str(ACTIVE_CONTEXT.get("session_id") or "")
    current = dict(LAST_EXECUTION_EVIDENCE) if isinstance(LAST_EXECUTION_EVIDENCE, dict) else {}
    if sid and _evidence_session_id(current) != sid:
        current = _latest_session_execution_evidence(sid)
    return {
        "ok": True,
        "active": ACTIVE_CONTEXT,
        "last_decision": LAST_DECISION if str(LAST_DECISION.get("session_id") or (LAST_DECISION.get("details") or {}).get("session_id") or sid) == sid else {},
        "execution_evidence": current or {},
        "items": _session_execution_evidence(sid),
        "summary": _evidence_summary(sid),
    }


@app.get("/mcad/evidence/current/archive")
def mcad_evidence_current_archive():
    sid = str(ACTIVE_CONTEXT.get("session_id") or "")
    return {"ok": True, "session_id": sid or None, "items": _session_execution_evidence(sid), "summary": _evidence_summary(sid)}



def _session_guard_dataset_key(value: object) -> str:
    s = str(value or "").lower()
    if "steelwheels" in s or "steel wheels" in s or "sampledata" in s or "pentaho" in s:
        return "steelwheels"
    if "adventureworksdw" in s or "adventureworks" in s or "adventure works" in s or "o_aw_" in s:
        return "adventureworksdw"
    if "foodmart" in s or "food mart" in s or "o_real_beer" in s or "beer and wine" in s or "unit sales" in s:
        return "foodmart"
    return ""


def _session_guard_objective_payload(objective_id: str) -> dict:
    objective_id = str(objective_id or "").strip()
    if not objective_id:
        return {}
    try:
        r = requests.get(f"{MCAD_API_BASE}/objectives/{objective_id}", timeout=20)
        if not r.ok:
            return {}
        data = r.json()
        if isinstance(data, dict):
            for key in ("objective", "item", "data"):
                if isinstance(data.get(key), dict):
                    return data[key]
            return data
    except Exception:
        return {}
    return {}


def _session_guard_objective_dataset(objective_id: str, objective: dict | None = None) -> str:
    known = {
        "O_REAL_BEER_WA_MONTH": "foodmart",
        "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN": "adventureworksdw",
        "O_STEELWHEELS_EMEA_CLASSIC_CARS_MONTH_SALES_QUANTITY": "steelwheels",
    }
    oid = str(objective_id or "").strip()
    if oid in known:
        return known[oid]

    pieces = [oid]
    obj = objective if isinstance(objective, dict) else {}
    for key in ("dataset", "dw_id", "datawarehouse_id", "catalog", "cube", "id", "objective_id", "name", "label", "description"):
        val = obj.get(key)
        if val is not None:
            pieces.append(str(val))

    constraints = obj.get("constraints") or obj.get("items") or []
    if isinstance(constraints, dict):
        constraints = list(constraints.values())
    if isinstance(constraints, list):
        for c in constraints:
            if isinstance(c, dict):
                for key in ("dataset", "dw_id", "catalog", "cube", "id", "name", "label", "measure", "measure_name", "dimension", "level"):
                    val = c.get(key)
                    if val is not None:
                        pieces.append(str(val))

    return _session_guard_dataset_key(" ".join(pieces))


def _assert_session_objective_dw_compatible(objective_id: str, dw_id: str) -> None:
    objective_id = str(objective_id or "").strip()
    dw_id = str(dw_id or "").strip()
    if not objective_id or not dw_id:
        return

    cfg = _get_dw_config_or_400(dw_id)
    dw_dataset = _session_guard_dataset_key(
        " ".join(str(x or "") for x in [
            getattr(cfg, "dataset", None),
            getattr(cfg, "catalog", None),
            getattr(cfg, "cube", None),
            getattr(cfg, "id", None),
            getattr(cfg, "label", None),
        ])
    )

    objective = _session_guard_objective_payload(objective_id)
    objective_dataset = _session_guard_objective_dataset(objective_id, objective)

    if objective_dataset and dw_dataset and objective_dataset != dw_dataset:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "code": "OBJECTIVE_DW_DATASET_MISMATCH",
                "message": (
                    f"Objective '{objective_id}' targets dataset '{objective_dataset}', "
                    f"but selected data warehouse '{dw_id}' targets dataset '{dw_dataset}'."
                ),
                "objective_id": objective_id,
                "dw_id": dw_id,
                "objective_dataset": objective_dataset,
                "dw_dataset": dw_dataset,
            },
        )


@app.post("/mcad/session/new")
async def mcad_session_new(req: Request):
    payload = await req.json()
    _assert_session_objective_dw_compatible(
        str(payload.get("objective_id") or MCAD_OBJECTIVE_ID_DEFAULT or ""),
        str(payload.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart"),
    )
    objective_id = str(payload.get("objective_id") or MCAD_OBJECTIVE_ID_DEFAULT or "")
    dw_id = str(payload.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart")
    _ensure_dw_enabled_or_400(dw_id)
    session_resp = _relay_post("/sessions/create", {"objective_id": objective_id, "dw_id": dw_id})
    session = session_resp.get("session", session_resp)
    ACTIVE_CONTEXT["session_id"] = str(session.get("session_id") or "") or None
    ACTIVE_CONTEXT["objective_id"] = str(session.get("objective_id") or objective_id) or None
    ACTIVE_CONTEXT["dw_id"] = str(session.get("dw_id") or dw_id) or None
    LAST_DECISION.clear()
    LAST_EXECUTION_EVIDENCE.clear()
    # Ensure a newly created logical session does not inherit stale persisted
    # decision evidence from an earlier API run that reused the same id (S_0001, ...).
    try:
        if ACTIVE_CONTEXT.get("session_id"):
            _relay_post(f"/sessions/{ACTIVE_CONTEXT.get('session_id')}/trace/reset", {})
    except Exception as e:
        print("session trace reset after create failed:", e)
    GRAPH_SESSION_STATES[str(ACTIVE_CONTEXT.get("session_id") or "__no_session__")] = _empty_graph_session_state(ACTIVE_CONTEXT.get("objective_id"), ACTIVE_CONTEXT.get("session_id"))
    return {"ok": True, "active": ACTIVE_CONTEXT, "session": session}


@app.post("/mcad/session/resume")
async def mcad_session_resume(req: Request):
    payload = await req.json()
    session_id = str(payload.get("session_id") or "")
    resp = _relay_get(f"/sessions/{session_id}")
    session = resp.get("session", resp)
    ACTIVE_CONTEXT["session_id"] = str(session.get("session_id") or session_id) or None
    ACTIVE_CONTEXT["objective_id"] = str(session.get("objective_id") or "") or None
    ACTIVE_CONTEXT["dw_id"] = str(session.get("dw_id") or MCAD_DW_ID_DEFAULT) or None
    LAST_DECISION.clear()
    LAST_EXECUTION_EVIDENCE.clear()
    GRAPH_SESSION_STATES.setdefault(str(ACTIVE_CONTEXT.get("session_id") or "__no_session__"), _empty_graph_session_state(ACTIVE_CONTEXT.get("objective_id"), ACTIVE_CONTEXT.get("session_id")))
    return {"ok": True, "active": ACTIVE_CONTEXT, "session": session}


@app.get("/mcad/session/ui", response_class=HTMLResponse)
def mcad_session_ui():
    return HTMLResponse(_load_session_ui_html())

@app.head("/mcad/session/ui")
def mcad_session_ui_head():
    return HTMLResponse("")


@app.post("/mcad/session/current/trace/reset")
def mcad_current_session_trace_reset():
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {"ok": False, "error": "No active session."}
    reset = _relay_post(f"/sessions/{sid}/trace/reset", {})
    LAST_DECISION.clear()
    LAST_EXECUTION_EVIDENCE.clear()
    _clear_session_execution_evidence(str(sid))
    GRAPH_SESSION_STATES[str(sid)] = _empty_graph_session_state(oid, sid)
    return {"ok": True, "session_id": sid, "objective_id": oid, "reset": reset.get("reset", reset), "execution_evidence_cleared": True}


@app.get("/mcad/history/current")
def mcad_history_current():
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {"ok": True, "session_id": None, "objective_id": oid, "items": []}
    data = _relay_get(f"/sessions/{sid}/history")
    items = _enrich_rows_with_evidence(data.get("items", []), str(sid))
    return {"ok": True, "session_id": sid, "objective_id": oid, "items": items, "execution_evidence_summary": _evidence_summary(str(sid))}


@app.get("/mcad/decision-details/archive/status")
def mcad_decision_details_archive_status():
    return _relay_get("/decision-details/archive/status")


@app.get("/mcad/decision-details/current")
def mcad_decision_details_current():
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {"ok": True, "session_id": None, "objective_id": oid, "items": []}
    data = _relay_get(f"/sessions/{sid}/decision-details")
    items = _enrich_rows_with_evidence(data.get("items", []), str(sid))
    return {"ok": True, "session_id": sid, "objective_id": oid, "items": items, "execution_evidence_summary": _evidence_summary(str(sid))}


@app.get("/mcad/decision-details/current/{step_index}")
def mcad_decision_detail_current(step_index: int):
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    try:
        data = _relay_get(f"/sessions/{sid}/decision-details/{step_index}")
        item = data.get("item", data)
        if isinstance(item, dict):
            ev = _evidence_index(str(sid))["by_step"].get(int(step_index))
            if ev:
                item = dict(item)
                item["execution_evidence"] = ev
                for key, value in _flatten_execution_evidence(ev).items():
                    item.setdefault(key, value)
        return {"ok": True, "session_id": sid, "objective_id": oid, "item": item}
    except HTTPException as e:
        # UI fallback: return a structured placeholder instead of an internal
        # server error. This is especially useful for executions created before
        # the V8.9 archive existed, or when the backend evidence file was reset.
        if LAST_DECISION and int(step_index) == int((LAST_DECISION.get("details") or {}).get("step_index") or LAST_DECISION.get("step_index") or -1):
            det = LAST_DECISION.get("details") if isinstance(LAST_DECISION.get("details"), dict) else {}
            item = {
                "session_id": sid,
                "step_index": int(step_index),
                "objective_id": oid,
                "decision": LAST_DECISION,
                "decision_summary": {
                    "decision": LAST_DECISION.get("decision"),
                    "decision_reason_code": LAST_DECISION.get("decision_reason_code"),
                    "decision_reason": LAST_DECISION.get("decision_reason"),
                    "phi": LAST_DECISION.get("phi"),
                    "delta_phi_t": det.get("delta_phi_t"),
                    "sat": LAST_DECISION.get("sat"),
                    "real": LAST_DECISION.get("real"),
                    "ceval": LAST_DECISION.get("ceval"),
                },
                "sat_checks": det.get("sat_checks") or (det.get("graph_update") or {}).get("sat_checks") or {},
                "sat_evidence": det.get("sat_evidence") or {},
                "nvac_evidence": det.get("nvac_evidence") or (det.get("graph_update") or {}).get("nvac_evidence") or {},
                "query_spec": det.get("query_spec") or {},
                "graph_update": det.get("graph_update") or LAST_DECISION.get("graph_update") or {},
                "archive_fallback": True,
                "archive_note": f"Backend detail archive unavailable: {e.detail}",
            }
            ev = _evidence_index(str(sid))["by_step"].get(int(step_index))
            if ev:
                item["execution_evidence"] = ev
                for key, value in _flatten_execution_evidence(ev).items():
                    item.setdefault(key, value)
            return {"ok": True, "session_id": sid, "objective_id": oid, "item": item}
        raise e


@app.get("/mcad/decision-details/current/{step_index}/explainability")
def mcad_decision_detail_current_explainability(step_index: int):
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    data = _relay_get(f"/sessions/{sid}/decision-details/{step_index}/explainability")
    return {"ok": True, "session_id": sid, "objective_id": oid, "formal_explanation": data.get("formal_explanation", {})}


@app.get("/mcad/decision-details/current/{step_index}/markdown")
def mcad_decision_detail_current_markdown(step_index: int):
    sid = ACTIVE_CONTEXT.get("session_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    r = requests.get(f"{MCAD_API_BASE}/sessions/{sid}/decision-details/{step_index}/markdown", timeout=20)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text[:1000])
    return Response(content=_append_execution_evidence_markdown(r.text, str(sid), "Execution Evidence"), media_type="text/markdown; charset=utf-8")




@app.get("/mcad/reports/current/session")
def mcad_current_session_report(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {"ok": True, "session_id": None, "objective_id": oid, "report": {"summary": {"total_queries": 0}, "rows": []}}
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    data = _relay_get(f"/sessions/{sid}/report{suffix}")
    report = _enrich_report_payload_with_evidence(data.get("report", data), str(sid))
    if isinstance(report, dict):
        report.setdefault("contract_version", "mcad.session_report.v1")
    return {"ok": True, "session_id": sid, "objective_id": oid, "report": report, "execution_evidence_summary": _evidence_summary(str(sid))}


@app.get("/mcad/reports/current/session/markdown")
def mcad_current_session_report_markdown(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    r = requests.get(f"{MCAD_API_BASE}/sessions/{sid}/report/markdown{suffix}", timeout=30)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text[:1000])
    return Response(content=_append_execution_evidence_markdown(r.text, str(sid), "Execution Evidence for Metrics"), media_type="text/markdown; charset=utf-8")


@app.get("/mcad/reports/current/session/csv")
def mcad_current_session_report_csv(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    r = requests.get(f"{MCAD_API_BASE}/sessions/{sid}/report/csv{suffix}", timeout=30)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text[:1000])
    return Response(content=_enrich_csv_with_evidence(r.text, str(sid)), media_type="text/csv; charset=utf-8")


@app.get("/mcad/metrics/current/session")
def mcad_current_session_metrics(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {"ok": True, "session_id": None, "objective_id": oid, "metrics": {"summary": {"total_queries": 0}, "trace": []}}
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    data = _relay_get(f"/sessions/{sid}/metrics{suffix}")
    metrics = _enrich_report_payload_with_evidence(data.get("metrics", data), str(sid))
    if isinstance(metrics, dict):
        metrics.setdefault("contract_version", "mcad.experimental_metrics.v1")
    return {"ok": True, "session_id": sid, "objective_id": oid, "metrics": metrics, "execution_evidence_summary": _evidence_summary(str(sid))}


@app.get("/mcad/metrics/current/session/markdown")
def mcad_current_session_metrics_markdown(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    r = requests.get(f"{MCAD_API_BASE}/sessions/{sid}/metrics/markdown{suffix}", timeout=30)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text[:1000])
    return Response(content=r.text, media_type="text/markdown; charset=utf-8")


@app.get("/mcad/metrics/current/session/csv")
def mcad_current_session_metrics_csv(req: Request):
    sid = ACTIVE_CONTEXT.get("session_id")
    if not sid:
        raise HTTPException(status_code=404, detail="No active session")
    qs = req.url.query
    suffix = ("?" + qs) if qs else ""
    r = requests.get(f"{MCAD_API_BASE}/sessions/{sid}/metrics/csv{suffix}", timeout=30)
    if not r.ok:
        raise HTTPException(status_code=r.status_code, detail=r.text[:1000])
    return Response(content=_enrich_csv_with_evidence(r.text, str(sid)), media_type="text/csv; charset=utf-8")


@app.get("/mcad/graph/state")
@app.get("/mcad/graph/state/current")
def mcad_graph_state():
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return _build_graph_state_payload()
    try:
        data = _relay_get(f"/sessions/{sid}/graph/state")
        if not data.get("last_decision"):
            data["last_decision"] = LAST_DECISION
        return data
    except Exception as exc:
        fallback = _build_graph_state_payload()
        fallback["relay_error"] = str(exc)
        return fallback


@app.get("/mcad/graph/current")
def mcad_graph_current():
    sid = ACTIVE_CONTEXT.get("session_id")
    oid = ACTIVE_CONTEXT.get("objective_id")
    if not sid:
        return {
            "ok": True,
            "session_id": None,
            "objective_id": oid,
            "graph": {"nodes": [], "edges": []},
            "metrics": {
                "completion_rate": 0.0,
                "calculability_rate_total": 0.0,
                "calculability_rate_partial": 0.0,
                "analytic_alignment_score": 0.0,
                "allow_rate": 0.0,
                "allow_count": 0,
                "block_count": 0,
            },
        }
    data = _relay_get(f"/sessions/{sid}/graph")
    return {
        "ok": True,
        "session_id": sid,
        "objective_id": data.get("objective_id", oid),
        "dw_id": data.get("dw_id"),
        "graph": data.get("graph", {"nodes": [], "edges": []}),
        "metrics": data.get("metrics", {}),
    }





def _scenario_file_candidates() -> list[Path]:
    roots = [
        Path("/app/direct-scenarios"),
        Path(__file__).resolve().parents[1] / "direct-scenarios",
        Path("bi-stack/direct-scenarios"),
    ]
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for f in sorted(root.glob("*.json")):
            key = str(f.resolve())
            if key not in seen:
                files.append(f)
                seen.add(key)
    return files


def _normalize_scenario(raw, scenario_id: str) -> dict:
    if isinstance(raw, list):
        queries = raw
        return {
            "id": scenario_id,
            "name": scenario_id,
            "description": "",
            "objective_id": queries[0].get("objective_id", "") if queries else "",
            "dw_id": queries[0].get("dw_id", "foodmart") if queries else "foodmart",
            "queries": queries,
        }

    if isinstance(raw, dict):
        queries = raw.get("queries") or raw.get("items") or []
        objective_id = raw.get("objective_id") or (queries[0].get("objective_id", "") if queries else "")
        dw_id = raw.get("dw_id") or (queries[0].get("dw_id", "foodmart") if queries else "foodmart")

        normalized = {
            "id": raw.get("id") or scenario_id,
            "name": raw.get("name") or raw.get("label") or scenario_id,
            "description": raw.get("description") or "",
            "objective_id": objective_id,
            "dw_id": dw_id,
            "dataset": raw.get("dataset") or raw.get("dataset_id") or raw.get("logical_dataset") or (_dw_dataset_key(dw_id) if dw_id else ""),
            "queries": queries,
        }

        for i, q in enumerate(normalized["queries"], start=1):
            q.setdefault("query_id", q.get("id") or q.get("name") or f"Q{i}")
            q.setdefault("id", q.get("query_id"))
            q.setdefault("objective_id", objective_id)
            q.setdefault("dw_id", dw_id)
            q.setdefault("dataset", normalized.get("dataset") or (_dw_dataset_key(dw_id) if dw_id else ""))
            q.setdefault("query_type", q.get("query_type") or "mdx")

        return normalized

    return {
        "id": scenario_id,
        "name": scenario_id,
        "description": "Invalid scenario format",
        "objective_id": "",
        "dw_id": "foodmart",
        "queries": [],
    }


def _default_foodmart_q1_q6_scenario() -> dict:
    scenario = _normalize_scenario(_load_foodmart_q1_q6_scenarios(), "foodmart_q1_q6")
    scenario["id"] = "foodmart_q1_q6"
    scenario["name"] = "FoodMart Q1-Q6 MCAD validation"
    scenario["label"] = "FoodMart Q1-Q6 MCAD validation"
    scenario["description"] = "Six FoodMart MDX queries validating ALLOW/BLOCK behavior for O_REAL_BEER_WA_MONTH."
    scenario["objective_id"] = "O_REAL_BEER_WA_MONTH"
    scenario["dw_id"] = "foodmart"
    scenario["dataset"] = "FoodMart"
    for q in scenario.get("queries", []):
        if isinstance(q, dict):
            q.setdefault("dataset", "FoodMart")
    return scenario


def _load_imported_scenarios_raw() -> list[dict]:
    try:
        if _IMPORTED_SCENARIOS_FILE.exists():
            data = json.loads(_IMPORTED_SCENARIOS_FILE.read_text(encoding="utf-8") or "{}")
            if isinstance(data, dict) and isinstance(data.get("scenarios"), list):
                return [x for x in data.get("scenarios") if isinstance(x, dict)]
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _write_imported_scenarios_raw(items: list[dict]) -> None:
    by_id: dict[str, dict] = {}
    for raw in items:
        sid = str(raw.get("id") or raw.get("scenario_id") or "").strip()
        if sid:
            by_id[sid] = raw
    _IMPORTED_SCENARIOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _IMPORTED_SCENARIOS_FILE.write_text(json.dumps({"scenarios": list(by_id.values())}, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_scenarios_payload(payload) -> list[dict]:
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("scenarios"), list):
        raw_items = payload.get("scenarios") or []
    elif isinstance(payload, dict) and isinstance(payload.get("queries"), list):
        raw_items = [payload]
    else:
        raise HTTPException(status_code=400, detail="JSON must be a scenario object, a list, or {'scenarios': [...]}.")
    out: list[dict] = []
    for idx, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or raw.get("scenario_id") or raw.get("name") or f"scenario_{idx}").strip()
        if not sid:
            continue
        out.append(_normalize_scenario({**raw, "id": sid}, sid))
    return out


def _load_imported_scenario_by_id(scenario_id: str) -> dict | None:
    for raw in _load_imported_scenarios_raw():
        scenario = _normalize_scenario(raw, str(raw.get("id") or raw.get("scenario_id") or "imported"))
        if str(scenario.get("id")) == str(scenario_id) or str(scenario.get("scenario_id")) == str(scenario_id):
            return scenario
    return None


def _load_scenario_by_id(scenario_id: str) -> dict | None:
    imported = _load_imported_scenario_by_id(scenario_id)
    if imported is not None:
        return imported
    safe_id = scenario_id.replace("/", "").replace("\\", "")
    for f in _scenario_file_candidates():
        if f.stem == safe_id:
            raw = json.loads(f.read_text(encoding="utf-8"))
            return _normalize_scenario(raw, f.stem)
    if safe_id == "foodmart_q1_q6":
        return _default_foodmart_q1_q6_scenario()
    return None



# -------------------------
# Scenario import validation helpers (V8.7)
# -------------------------

def _scenario_existing_ids() -> set[str]:
    ids: set[str] = set()
    default = _default_foodmart_q1_q6_scenario()
    ids.add(str(default.get("id")))
    for raw in _load_imported_scenarios_raw():
        sid = str(raw.get("id") or raw.get("scenario_id") or "").strip()
        if sid:
            ids.add(sid)
    for f in _scenario_file_candidates():
        ids.add(f.stem)
    return ids


def _v87_norm(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _v87_as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _v87_bracket_parts(chain: str) -> list[str]:
    return [p.strip() for p in re.findall(r"\[([^\]]+)\]", chain or "") if p.strip()]


def _v87_level_name(parts: list[str]) -> str | None:
    if len(parts) < 2:
        return None
    return f"{parts[0]}.{parts[-1]}"


def _v87_mdx_features(mdx: str) -> dict:
    text = mdx or ""
    measures = sorted(set(re.findall(r"\[Measures\]\.\[([^\]]+)\]", text, flags=re.I)))
    group_by: list[str] = []
    slicers: dict[str, str] = {}

    row_exprs = re.findall(r"(?is)(.*?)(?:ON\s+ROWS)", text)
    if row_exprs:
        row_expr = row_exprs[-1]
        if "ON COLUMNS" in row_expr.upper():
            row_expr = re.split(r"(?is)ON\s+COLUMNS\s*,", row_expr)[-1]
        for chain in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\])+\s*(?:\.Members)?", row_expr, flags=re.I):
            if chain.lower().startswith("[measures]"):
                continue
            if ".members" not in chain.lower():
                continue
            level = _v87_level_name(_v87_bracket_parts(chain))
            if level:
                group_by.append(level)

    where_match = re.search(r"(?is)\bWHERE\s*\((.*)\)\s*$", text)
    if where_match:
        where_expr = where_match.group(1)
        for chain in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\])+", where_expr):
            if chain.lower().startswith("[measures]"):
                continue
            parts = _v87_bracket_parts(chain)
            if len(parts) >= 2:
                key_parts = parts[:-1]
                key = f"{key_parts[0]}.{key_parts[-1]}" if len(key_parts) >= 2 else key_parts[0]
                slicers[key] = parts[-1]

    return {"measures": measures, "group_by": sorted(set(group_by)), "slicers": slicers}


def _v87_objective_from_payload(payload, objective_id: str) -> dict | None:
    if isinstance(payload, dict):
        for obj in payload.get("objectives") or []:
            if isinstance(obj, dict) and str(obj.get("id") or obj.get("objective_id")) == str(objective_id):
                return obj
    return None


def _v87_fetch_objective(objective_id: str, payload=None) -> dict | None:
    tmp = _v87_objective_from_payload(payload, objective_id)
    if tmp:
        return tmp
    try:
        r = requests.get(f"{MCAD_API_BASE}/objectives/{objective_id}", timeout=20)
        if r.ok:
            data = r.json()
            return data.get("objective") or data
    except Exception:
        return None
    return None


def _v87_constraint_list(objective: dict | None) -> list[dict]:
    """Return scenario-validation constraints, flattening imported virtual_nodes.

    Imported objectives are normalized by mcad-api into constraints whose
    operational contract is stored under virtual_nodes[]. Earlier proxy-side
    scenario validation inspected only top-level measure/grain/slicers fields,
    so AdventureWorks ALLOW queries were accepted with warnings and appeared as
    non-matching even though the imported objective was valid.
    """
    if not isinstance(objective, dict):
        return []
    out: list[dict] = []
    for c in objective.get("constraints") or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        base = dict(c)
        vnodes = c.get("virtual_nodes") if isinstance(c.get("virtual_nodes"), list) else []
        if vnodes:
            for vn in vnodes:
                if not isinstance(vn, dict):
                    continue
                item = dict(base)
                item["id"] = cid
                item["virtual_node_id"] = vn.get("id") or c.get("virtual_node") or c.get("virtual_node_id")
                item["measure"] = vn.get("measure") or c.get("measure") or c.get("metric") or ""
                item["metric"] = item.get("measure")
                item["grain"] = vn.get("grain") or c.get("grain") or c.get("group_by") or []
                item["group_by"] = item.get("grain")
                item["slicers"] = vn.get("slicers") if isinstance(vn.get("slicers"), dict) else (c.get("slicers") if isinstance(c.get("slicers"), dict) else {})
                item["aggregator"] = vn.get("aggregator") or c.get("aggregator") or ""
                item["unit"] = vn.get("unit") or c.get("unit") or ""
                item["fact"] = vn.get("fact") or c.get("fact") or ""
                out.append(item)
        else:
            out.append(base)
    return out

def _v87_feature_has_measure(features: dict, measure: str) -> bool:
    req = _v87_norm(measure)
    measures = {_v87_norm(m) for m in _v87_as_list(features.get("measures"))}
    return bool(req) and (req in measures or req in _v87_norm(features.get("mdx")))


def _v87_feature_has_grain(features: dict, grain) -> bool:
    required = _v87_as_list(grain)
    group_tokens = {_v87_norm(g) for g in _v87_as_list(features.get("group_by"))}
    group_last = {_v87_norm(str(g).split(".")[-1]) for g in _v87_as_list(features.get("group_by"))}
    for g in required:
        gt = _v87_norm(g)
        gl = _v87_norm(str(g).split(".")[-1])
        if gt not in group_tokens and gl not in group_last:
            return False
    return True


def _v87_feature_contains_value(features: dict, value) -> bool:
    """Exact MDX member-value matching for slicers.

    V8.7 used substring matching, which made CA match words such as
    Product Category and produced false positives/false negatives in scenario
    validation. Here a slicer value is matched as an actual MDX bracket token
    or as an exact normalized slicer value.
    """
    val = _v87_norm(value)
    if not val:
        return True
    tokens: set[str] = set()
    slicers = features.get("slicers") or {}
    if isinstance(slicers, dict):
        for k, v in slicers.items():
            tokens.add(_v87_norm(k))
            tokens.add(_v87_norm(str(k).split(".")[-1]))
            tokens.add(_v87_norm(v))
    mdx = str(features.get("mdx") or "")
    for token in re.findall(r"\[([^\]]+)\]", mdx):
        tokens.add(_v87_norm(token))
    return val in tokens


def _v87_feature_has_slicers(features: dict, slicers: dict) -> bool:
    if not isinstance(slicers, dict) or not slicers:
        return True
    group_tokens = {_v87_norm(g) for g in _v87_as_list(features.get("group_by"))}
    group_last = {_v87_norm(str(g).split(".")[-1]) for g in _v87_as_list(features.get("group_by"))}
    for key, value in slicers.items():
        if _v87_feature_contains_value(features, value):
            continue
        kt = _v87_norm(key)
        kl = _v87_norm(str(key).split(".")[-1])
        if kt in group_tokens or kl in group_last:
            continue
        return False
    return True


def _v87_matching_constraints(mdx: str, objective: dict | None) -> list[str]:
    features = _v87_mdx_features(mdx)
    features["mdx"] = mdx
    matches: list[str] = []
    for c in _v87_constraint_list(objective):
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        if not _v87_feature_has_measure(features, str(c.get("measure") or c.get("metric") or "")):
            continue
        if not _v87_feature_has_grain(features, c.get("grain") or c.get("group_by") or []):
            continue
        if not _v87_feature_has_slicers(features, c.get("slicers") if isinstance(c.get("slicers"), dict) else {}):
            continue
        matches.append(cid)

    # Specificity: keep only the most detailed matching constraints.
    if len(matches) > 1:
        constraints_by_id = {str(c.get("id")): c for c in _v87_constraint_list(objective)}
        max_grain = max(len(_v87_as_list((constraints_by_id.get(mid) or {}).get("grain"))) for mid in matches)
        matches = [mid for mid in matches if len(_v87_as_list((constraints_by_id.get(mid) or {}).get("grain"))) == max_grain]
    return sorted(set(matches))


def _validate_scenarios_payload(payload, *, check_unique: bool = True) -> dict:
    try:
        scenarios = _extract_scenarios_payload(payload)
    except HTTPException as e:
        return {"ok": False, "status": "refused", "kind": "scenarios", "errors": [str(e.detail)], "warnings": [], "items": []}

    existing = _scenario_existing_ids()
    seen: set[str] = set()
    errors: list[str] = []
    warnings: list[str] = []
    items: list[dict] = []

    for sc in scenarios:
        sid = str(sc.get("id") or sc.get("scenario_id") or "").strip()
        item_errors: list[str] = []
        item_warnings: list[str] = []
        if not sid:
            item_errors.append("scenario id is required")
        elif check_unique and sid in existing:
            item_warnings.append(f"scenario id already exists and will be replaced on import: {sid}")
        if sid in seen:
            item_errors.append(f"scenario id duplicated inside payload: {sid}")
        seen.add(sid)

        if not str(sc.get("name") or "").strip():
            item_warnings.append("name is missing; id will be used")
        oid = str(sc.get("objective_id") or "").strip()
        if not oid:
            item_errors.append("objective_id is required")
            objective = None
        else:
            objective = _v87_fetch_objective(oid, payload)
            if objective is None:
                item_errors.append(f"objective_id does not exist or is not imported yet: {oid}")

        sc_dw = str(sc.get("dw_id") or "").strip()
        if not sc_dw:
            item_warnings.append("dw_id is missing; foodmart/default may be used")
        else:
            try:
                cfg = get_gateway().get_config(sc_dw)
                if getattr(cfg, "enabled", True) is False:
                    item_errors.append(f"dw_id is registered but disabled/unimplemented: {sc_dw}")
            except Exception:
                item_errors.append(f"dw_id is not registered: {sc_dw}")

        queries = sc.get("queries") or []
        if not isinstance(queries, list) or not queries:
            item_errors.append("queries must be a non-empty list")
            queries = []

        qids: set[str] = set()
        query_reports: list[dict] = []
        seen_matching_constraints: set[str] = set()
        for i, q in enumerate(queries):
            q_errors: list[str] = []
            q_warnings: list[str] = []
            if not isinstance(q, dict):
                q_errors.append("query must be an object")
                qid = f"Q{i+1}"
                mdx = ""
            else:
                qid = str(q.get("id") or q.get("query_id") or f"Q{i+1}").strip()
                mdx = str(q.get("mdx") or q.get("query") or q.get("text") or "").strip()
            if not qid:
                q_errors.append(f"queries[{i}].id is required")
            elif qid in qids:
                q_errors.append(f"query id duplicated: {qid}")
            qids.add(qid)
            if isinstance(q, dict) and not str(q.get("label") or q.get("name") or "").strip():
                q_warnings.append(f"{qid}: label is missing")
            if not mdx:
                q_errors.append(f"{qid}: mdx is required and must be non-empty")
            expected = str((q or {}).get("expected_decision") or "").upper() if isinstance(q, dict) else ""
            if expected and expected not in {"ALLOW", "BLOCK"}:
                q_errors.append(f"{qid}: expected_decision must be ALLOW or BLOCK")
            matches = _v87_matching_constraints(mdx, objective) if mdx and objective else []
            match_set = set(matches)
            redundant_match = bool(match_set) and match_set.issubset(seen_matching_constraints)
            if not matches:
                if expected == "ALLOW":
                    q_warnings.append(f"{qid}: expected ALLOW, but no matching objective constraint was found")
                # expected BLOCK with no match is coherent: no warning.
            elif expected == "BLOCK":
                if redundant_match:
                    pass  # coherent runtime BLOCK: static match exists but it is already covered earlier in the scenario.
                else:
                    q_warnings.append(f"{qid}: expected BLOCK, but it can cover {', '.join(matches)}")
            elif expected == "ALLOW":
                seen_matching_constraints.update(match_set)
            elif matches:
                seen_matching_constraints.update(match_set)
            query_reports.append({"id": qid, "ok": not q_errors, "errors": q_errors, "warnings": q_warnings, "matching_constraints": matches, "redundant_static_match": redundant_match})
            item_errors.extend(q_errors)
            item_warnings.extend(q_warnings)

        items.append({"id": sid, "ok": not item_errors, "errors": item_errors, "warnings": item_warnings, "query_reports": query_reports})
        errors.extend([f"{sid}: {e}" for e in item_errors])
        warnings.extend([f"{sid}: {w}" for w in item_warnings])

    status = "accepted" if not errors and not warnings else ("accepted_with_warnings" if not errors else "refused")
    return {
        "ok": not errors,
        "status": status,
        "kind": "scenarios",
        "accepted_count": len(scenarios) if not errors else 0,
        "errors": errors,
        "warnings": warnings,
        "items": items,
        "scenarios": scenarios,
    }


@app.get("/bi/scenarios")
def bi_scenarios(include_incompatible: bool = False):
    scenarios: dict[str, dict] = {}

    default = _default_foodmart_q1_q6_scenario()
    scenarios[default["id"]] = default

    for f in _scenario_file_candidates():
        try:
            scenario = _normalize_scenario(json.loads(f.read_text(encoding="utf-8")), f.stem)
            scenarios[scenario["id"]] = scenario
        except Exception as e:
            scenarios[f.stem] = {
                "id": f.stem,
                "name": f.stem,
                "label": f.stem,
                "description": f"Failed to load scenario: {e}",
                "objective_id": "",
                "dw_id": "foodmart",
                "dataset": "FoodMart",
                "queries": [],
                "error": str(e),
            }

    for raw in _load_imported_scenarios_raw():
        try:
            scenario = _normalize_scenario(raw, str(raw.get("id") or raw.get("scenario_id") or "imported"))
            scenarios[scenario["id"]] = scenario
        except Exception:
            continue

    active_objective = str(ACTIVE_CONTEXT.get("objective_id") or "").strip()
    active_dw = str(ACTIVE_CONTEXT.get("dw_id") or "").strip()
    items = []
    hidden_count = 0
    for scenario in scenarios.values():
        scenario = _attach_scenario_compatibility(scenario, active_objective, active_dw)
        if active_objective and active_dw and not scenario.get("compatible") and not include_incompatible:
            hidden_count += 1
            continue
        items.append({
            "id": scenario["id"],
            "name": scenario.get("name") or scenario.get("label") or scenario["id"],
            "label": scenario.get("label") or scenario.get("name") or scenario["id"],
            "description": scenario.get("description") or "",
            "objective_id": scenario.get("objective_id"),
            "dw_id": scenario.get("dw_id"),
            "dataset": scenario.get("dataset"),
            "query_count": len(scenario.get("queries", [])),
            "compatible": scenario.get("compatible"),
            "compatibility": scenario.get("compatibility"),
            "compatibility_errors": scenario.get("compatibility_errors", []),
            "compatibility_warnings": scenario.get("compatibility_warnings", []),
        })

    return {
        "ok": True,
        "compatibility_guard": "scenario_objective_dw.v1",
        "active": ACTIVE_CONTEXT,
        "include_incompatible": include_incompatible,
        "hidden_incompatible_count": hidden_count,
        "items": items,
    }


@app.get("/bi/scenarios/{scenario_id}")
def bi_scenario_get(scenario_id: str):
    scenario = _load_scenario_by_id(scenario_id)
    if scenario is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": f"Scenario not found: {scenario_id}"},
        )
    scenario = _attach_scenario_compatibility(scenario, ACTIVE_CONTEXT.get("objective_id"), ACTIVE_CONTEXT.get("dw_id"))
    return {"ok": True, "scenario": scenario, "items": scenario.get("queries", []), "compatibility": scenario.get("compatibility")}


@app.post("/bi/scenarios/validate")
async def bi_scenarios_validate(req: Request):
    payload = await req.json()
    return _validate_scenarios_payload(payload, check_unique=True)


@app.post("/bi/scenarios/import")
async def bi_scenarios_import(req: Request):
    payload = await req.json()
    report = _validate_scenarios_payload(payload, check_unique=True)
    if not report.get("ok"):
        raise HTTPException(status_code=400, detail=report)
    imported = report.get("scenarios") or []
    existing = _load_imported_scenarios_raw()
    by_id = {str(x.get("id") or x.get("scenario_id")): x for x in existing if x.get("id") or x.get("scenario_id")}
    for sc in imported:
        by_id[str(sc["id"])] = sc
    _write_imported_scenarios_raw(list(by_id.values()))
    return {
        "ok": True,
        "status": report.get("status", "accepted"),
        "imported_count": len(imported),
        "scenario_ids": [x["id"] for x in imported],
        "warnings": report.get("warnings", []),
        "report": report,
    }


@app.delete("/bi/scenarios/{scenario_id}")
def bi_scenario_delete(scenario_id: str):
    existing = _load_imported_scenarios_raw()
    remaining = [x for x in existing if str(x.get("id") or x.get("scenario_id")) != str(scenario_id)]
    if len(remaining) == len(existing):
        return JSONResponse(status_code=404, content={"ok": False, "error": f"Imported scenario not found or not removable: {scenario_id}"})
    _write_imported_scenarios_raw(remaining)
    return {"ok": True, "deleted_scenario_id": scenario_id, "remaining_imported_count": len(remaining)}


# ---------------------------------------------------------------------------
# V8.8.1 lightweight FoodMart probe for nvac_ok(QP)
# ---------------------------------------------------------------------------

def _probe_parse_cube(mdx: str) -> str:
    m = re.search(r"FROM\s+\[([^\]]+)\]", mdx or "", flags=re.I)
    return m.group(1) if m else "Sales"


def _probe_extract_where(mdx: str) -> str:
    m = re.search(r"(?is)\bWHERE\s*\((.*)\)\s*$", mdx or "")
    return (m.group(1).strip() if m else "")


def _probe_build_query(mdx: str, cube: str | None = None) -> tuple[str, str]:
    cube_name = cube or _probe_parse_cube(mdx) or "Sales"
    where_expr = _probe_extract_where(mdx)
    # FoodMart uses Unit Sales as a safe presence measure. AdventureWorksDW
    # does not expose Unit Sales; use SalesAmount so the lightweight probe can
    # prove nvac_ok on the real SQL Server adapter without fabricating rows.
    cube_l = str(cube_name or "").lower()
    mdx_l = str(mdx or "").lower()
    if "adventure" in cube_l or "adventure" in mdx_l:
        measure = "SalesAmount"
    else:
        measure = "Unit Sales"
    query = f"SELECT {{[Measures].[{measure}]}} ON COLUMNS FROM [{cube_name}]"
    if where_expr:
        query += f" WHERE ({where_expr})"
    return query, measure

def _probe_numeric_values(value) -> list[float]:
    vals: list[float] = []
    if isinstance(value, dict):
        for v in value.values():
            vals.extend(_probe_numeric_values(v))
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            vals.extend(_probe_numeric_values(v))
    else:
        try:
            if isinstance(value, str):
                txt = value.strip().replace(",", "")
                if not txt or len(txt) > 64:
                    return vals
                vals.append(float(txt))
            elif value is not None:
                vals.append(float(value))
        except Exception:
            pass
    return vals


def _probe_count_from_summary(summary: dict) -> tuple[int | None, bool | None]:
    if not isinstance(summary, dict):
        return None, None
    for key in ("row_count", "rows_count", "cell_count", "cells_count", "rows", "count"):
        val = summary.get(key)
        if isinstance(val, int):
            return val, val > 0
        if isinstance(val, list):
            return len(val), len(val) > 0
    nums = [x for x in _probe_numeric_values(summary) if x is not None]
    if nums:
        positive = any(abs(x) > 0 for x in nums)
        # Count is a lower-bound/proxy, not a business measure.
        return int(max(nums)) if positive else 0, positive
    return None, None


@app.post("/bi/nvac-probe")
async def bi_nvac_probe(req: Request):
    """Execute a bounded lightweight FoodMart probe for nvac_ok(QP).

    This endpoint intentionally bypasses MCAD /eval and never updates the CKG.
    It is only used by mcad-api to decide whether an uncertain subspace is
    non-empty before the main analytical query is allowed.
    """
    payload = await req.json()
    mdx = str(payload.get("mdx") or "")
    cube = str(payload.get("cube") or _probe_parse_cube(mdx) or "Sales")
    query, measure = _probe_build_query(mdx, cube)
    try:
        started = time.time()
        dw_id = str(payload.get("dw_id") or ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart")
        direct_result = get_gateway().execute(query, query_type="mdx", dw_id=dw_id, context={"probe": True})
        elapsed_ms = int((time.time() - started) * 1000) if not getattr(direct_result, "elapsed_ms", None) else int(direct_result.elapsed_ms)
        summary = direct_result.raw_result_summary if isinstance(direct_result.raw_result_summary, dict) else {}
        count, non_empty = _probe_count_from_summary(summary)
        if non_empty is None:
            non_empty = bool(getattr(direct_result, "status_code", 500) < 400 and summary and not getattr(direct_result, "error", None))
            count = 1 if non_empty else 0
        return {
            "ok": True,
            "dw_id": dw_id,
            "adapter_id": getattr(direct_result, "adapter_id", None),
            "non_empty": bool(non_empty),
            "count": int(count or 0),
            "probe_query": query,
            "probe_measure": measure,
            "elapsed_ms": elapsed_ms,
            "status_code": getattr(direct_result, "status_code", None),
            "summary": summary,
        }
    except Exception as exc:
        return JSONResponse(status_code=502, content={
            "ok": False,
            "non_empty": None,
            "count": None,
            "probe_query": query,
            "probe_measure": measure,
            "error": str(exc),
        })


@app.post("/bi/execute")
async def bi_execute(req: Request):
    payload = await req.json()

    query_text = str(payload.get("mdx") or payload.get("query") or "")
    query_type = str(payload.get("query_type") or "mdx")
    query_id = str(payload.get("query_id") or payload.get("id") or payload.get("queryId") or "")
    objective_id = str(payload.get("objective_id") or ACTIVE_CONTEXT.get("objective_id") or MCAD_OBJECTIVE_ID_DEFAULT or "")
    session_id = str(payload.get("session_id") or ACTIVE_CONTEXT.get("session_id") or "") or None
    dw_id = str(payload.get("dw_id") or ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart")

    try:
        cfg_for_request = _get_dw_config_or_400(dw_id)
        if getattr(cfg_for_request, "enabled", True) is False:
            return _disabled_dw_decision(dw_id, query_text, query_type, query_id, objective_id, session_id, payload)
    except HTTPException:
        raise

    source_scenario_id = str(payload.get("source_scenario_id") or payload.get("scenario_id") or "").strip()
    if source_scenario_id:
        scenario = _load_scenario_by_id(source_scenario_id)
        if scenario is not None:
            compat = _scenario_compatibility(scenario, objective_id=objective_id, dw_id=dw_id)
            if not compat.get("compatible", False):
                return _scenario_compatibility_block_response(scenario, compat, query_text, query_type, query_id, objective_id, dw_id, session_id, payload)

    decision: dict = {
        "decision": "BLOCK",
        "phi": 0.0,
        "threshold": 0.0,
        "sat": 0.0,
        "real": 0.0,
        "ceval": 0.0,
        "decision_reason_code": "EVAL_UNREACHABLE",
        "decision_reason": "MCAD /eval unavailable or failed.",
        "explain": "BLOCK because MCAD /eval failed; fail-open disabled.",
        "details": {},
    }

    eval_elapsed_ms = None

    try:
        eval_payload: dict = {
            "mdx": query_text,
            "context": {
                "dw_id": dw_id,
                "bi_mode": "hybrid_gateway",
                "query_type": query_type,
                "query_id": query_id or None,
                "execution_source_enforcement": True,
                "requested_dw_id": dw_id,
                "allow_fallback": bool(payload.get("allow_fallback", False)),
                "execution_mode": payload.get("execution_mode") or payload.get("query_mode"),
                "scenario_instance_id": payload.get("scenario_instance_id"),
                "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
                "scenario_name": payload.get("scenario_name"),
                "scenario_source": payload.get("scenario_source"),
                "scenario_query_index": payload.get("scenario_query_index"),
                "scenario_query_id": payload.get("scenario_query_id") or query_id or None,
            },
        }
        if session_id:
            eval_payload["session_id"] = session_id
        if objective_id:
            eval_payload["objective_id"] = objective_id

        eval_started = time.time()
        er = await asyncio.to_thread(requests.post, MCAD_EVAL_URL, json=eval_payload, timeout=MCAD_EVAL_TIMEOUT_S)
        eval_elapsed_ms = int((time.time() - eval_started) * 1000)
        if er.ok:
            decision = er.json()
        else:
            decision["decision_reason"] = f"HTTP {er.status_code}: {(er.text or '')[:300]}"
            print("MCAD-EVAL HTTP error:", er.status_code, (er.text or "")[:300])
    except Exception as e:
        decision["decision_reason"] = str(e)
        print("MCAD-EVAL exception:", e)

    det = decision.get("details") if isinstance(decision.get("details"), dict) else {}
    graph_update = dict(det.get("graph_update") or {}) if isinstance(det.get("graph_update"), dict) else _normalize_graph_update(decision, query_text)
    # Keep proxy-side metadata useful for the UI, but do not let observations become coverage.
    if not graph_update.get("measures") or not graph_update.get("grain") or not graph_update.get("slicers"):
        enriched = _normalize_graph_update(decision, query_text)
        for k in ("measures", "grain", "slicers", "time_window", "mdx_features", "blocked_reasons", "redundant", "delta_phi"):
            graph_update.setdefault(k, enriched.get(k))
    graph_update = _finalize_graph_update_contract(decision, graph_update, query_text, session_id, objective_id)
    decision["graph_update"] = graph_update
    ACTIVE_CONTEXT["session_id"] = str(det.get("session_id") or session_id or ACTIVE_CONTEXT.get("session_id") or "") or None
    ACTIVE_CONTEXT["objective_id"] = str(det.get("objective_id") or objective_id or ACTIVE_CONTEXT.get("objective_id") or "") or None
    ACTIVE_CONTEXT["dw_id"] = dw_id

    direct_result = None
    public_direct_result = None

    if str(decision.get("decision", "")).upper() == "ALLOW":
        try:
            direct_result = get_gateway().execute(
                query_text,
                query_type=query_type,
                dw_id=dw_id,
                context={
                    "session_id": session_id,
                    "objective_id": objective_id,
                    "query_id": query_id or None,
                    "execution_mode": payload.get("execution_mode") or payload.get("query_mode"),
                    "scenario_instance_id": payload.get("scenario_instance_id"),
                    "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
                    "allow_fallback": bool(payload.get("allow_fallback", False)),
                    "execution_source_enforcement": True,
                },
            )
            public_direct_result = build_public_direct_result(
                query_text,
                direct_result.raw_result_summary,
                dw_id=dw_id,
                query_language=query_type,
            )
            public_direct_result.setdefault("adapter_id", getattr(direct_result, "adapter_id", None))
            public_direct_result.setdefault("backend_type", getattr(direct_result, "backend_type", None))
            public_direct_result.setdefault("dw_id", getattr(direct_result, "dw_id", dw_id))
            public_direct_result.setdefault("execution_source_enforced", True)
            public_direct_result.setdefault("requested_dw_id", dw_id)
            public_direct_result.setdefault("selected_dw_id", getattr(direct_result, "dw_id", dw_id))
            public_direct_result.setdefault("execution_path", public_direct_result.get("adapter_family") or getattr(direct_result, "adapter_id", None) or getattr(direct_result, "backend_type", None))
            if getattr(direct_result, "error", None):
                public_direct_result.setdefault("error", direct_result.error)
            qspec = det.get("query_spec") if isinstance(det.get("query_spec"), dict) else {}

            update_payload = {
                "mdx": query_text,
                "status_code": direct_result.status_code,
                "elapsed_ms": direct_result.elapsed_ms,
                "response_bytes": direct_result.response_bytes,
                "response_digest": direct_result.response_digest,
                "decision": decision.get("decision"),
                "phi": decision.get("phi"),
                "sat": decision.get("sat"),
                "real": decision.get("real"),
                "ceval": decision.get("ceval"),
                "threshold": decision.get("threshold"),
                "catalog": det.get("catalog"),
                "cube": qspec.get("cube") or None,
                "session_id": det.get("session_id") or session_id,
                "objective_id": det.get("objective_id") or objective_id,
                "step_index": det.get("step_index"),
                "query_spec": qspec or None,
                "calculable_constraints": det.get("calculable_constraints"),
                "covered_constraints": det.get("covered_constraints"),
                "raw_result_summary": public_direct_result or direct_result.raw_result_summary,
                "adapter_id": getattr(direct_result, "adapter_id", None),
                "backend_type": getattr(direct_result, "backend_type", None),
            }

            ckg_resp = await asyncio.to_thread(requests.post, MCAD_CKG_URL, json=update_payload, timeout=MCAD_CKG_TIMEOUT_S)
            ckg_resp.raise_for_status()
        except Exception as e:
            print("HYBRID-BI-GATEWAY execution or CKG update exception:", e)
            decision.setdefault("details", {})["bi_gateway_error"] = str(e)

    execution_evidence = _build_execution_evidence(
        decision=decision,
        direct_result=direct_result,
        public_result=public_direct_result,
        graph_update=graph_update,
        query_text=query_text,
        query_type=query_type,
        dw_id=dw_id,
        query_id=query_id,
        payload=payload,
        eval_elapsed_ms=eval_elapsed_ms,
    )
    if isinstance(public_direct_result, dict):
        public_direct_result.setdefault("execution_evidence", execution_evidence)
        public_direct_result.setdefault("evidence_contract", execution_evidence.get("contract_version"))
        exec_summary = execution_evidence.get("execution", {})
        public_direct_result.setdefault("physical_execution", exec_summary.get("physical_execution"))
        public_direct_result.setdefault("status_code", exec_summary.get("status_code"))
        public_direct_result.setdefault("elapsed_ms", exec_summary.get("elapsed_ms"))
        public_direct_result.setdefault("response_bytes", exec_summary.get("response_bytes"))
        public_direct_result.setdefault("response_digest", exec_summary.get("response_digest"))
        public_direct_result.setdefault("result_digest", exec_summary.get("result_digest"))
    LAST_EXECUTION_EVIDENCE.clear()
    LAST_EXECUTION_EVIDENCE.update(execution_evidence)
    _archive_execution_evidence(execution_evidence)

    LAST_DECISION.clear()
    LAST_DECISION.update({
        "decision": decision.get("decision"),
        "decision_reason_code": decision.get("decision_reason_code") or det.get("decision_reason_code"),
        "decision_reason": decision.get("decision_reason") or det.get("decision_reason"),
        "is_redundant": decision.get("is_redundant", det.get("is_redundant", False)),
        "has_marginal_gain": decision.get("has_marginal_gain", det.get("has_marginal_gain", False)),
        "objective_id": det.get("objective_id") or objective_id,
        "session_id": det.get("session_id") or session_id,
        "dw_id": dw_id,
        "adapter_id": getattr(direct_result, "adapter_id", None) if direct_result else None,
        "execution_path": (public_direct_result or {}).get("execution_path") if isinstance(public_direct_result, dict) else None,
        "execution_source_enforced": True,
        "phi": decision.get("phi"),
        "threshold": decision.get("threshold"),
        "sat": decision.get("sat"),
        "real": decision.get("real"),
        "ceval": decision.get("ceval"),
        "useful_part": det.get("useful_part", decision.get("useful_part")),
        "explain": decision.get("explain"),
        "step_index": det.get("step_index") or decision.get("step_index"),
        "gained_resource_ids_count": det.get("gained_resource_ids_count", len(det.get("gained_resource_ids") or [])),
        "newly_contributed_constraints_total": det.get("newly_contributed_constraints_total", []),
        "newly_contributed_constraints_partial": det.get("newly_contributed_constraints_partial", []),
        "query_id": query_id,
        "scenario": {
            "scenario_instance_id": payload.get("scenario_instance_id"),
            "source_scenario_id": payload.get("source_scenario_id") or payload.get("scenario_id"),
            "scenario_name": payload.get("scenario_name"),
            "scenario_source": payload.get("scenario_source"),
            "scenario_query_index": payload.get("scenario_query_index"),
            "scenario_query_id": payload.get("scenario_query_id") or query_id or None,
            "execution_mode": payload.get("execution_mode") or payload.get("query_mode"),
        },
        "query_fingerprint": mdx_fingerprint(query_text),
        "query_digest": mdx_fingerprint(query_text),
        "graph_update": graph_update,
        "details": decision.get("details") if isinstance(decision.get("details"), dict) else {},
        "execution_evidence": execution_evidence,
        "measures": graph_update.get("measures", []),
        "slicers": graph_update.get("slicers", {}),
        "grain": graph_update.get("grain", []),
        "time_window": graph_update.get("time_window", {}),
        "ts_ms": int(time.time() * 1000),
    })

    return {
        "ok": True,
        "mode": "hybrid_bi_gateway",
        "gateway": "mcad.execution_gateway.v2.hybrid",
        "execution_source_enforced": True,
        "allow_fallback": bool(payload.get("allow_fallback", False)),
        "query_id": query_id,
        "dw_id": dw_id,
        "adapter_id": getattr(direct_result, "adapter_id", None) if direct_result else None,
        "execution_path": (public_direct_result or {}).get("execution_path") if isinstance(public_direct_result, dict) else None,
        "decision": decision,
        "execution_evidence": execution_evidence,
        "graph_update": graph_update,
        "direct_result": public_direct_result if public_direct_result else (direct_result.raw_result_summary if direct_result else None),
        "active": ACTIVE_CONTEXT,
    }


def _build_public_pivot4j_url(req: Request, subpath: str = "") -> str:
    url = str(req.url)
    if ".app.github.dev" in url:
        url = re.sub(r"-9000(\.app\.github\.dev)", r"-8090\1", url)
        base = url.split("/", 3)[:3]
        origin = "/".join(base)
        return origin.rstrip("/") + "/pivot4j/" + subpath.lstrip("/")
    host = req.headers.get("host", "localhost:9000")
    if ":9000" in host:
        host = host.replace(":9000", ":8090")
    return f"{req.url.scheme}://{host}/pivot4j/" + subpath.lstrip("/")


@app.get("/pivot4j")
@app.get("/pivot4j/")
def open_pivot4j(req: Request):
    return RedirectResponse(_build_public_pivot4j_url(req))


@app.get("/pivot4j/{path:path}")
def open_pivot4j_subpath(req: Request, path: str):
    return RedirectResponse(_build_public_pivot4j_url(req, path))


@app.post("/xmla")
async def xmla_proxy(req: Request):
    body = await req.body()
    content_type = req.headers.get("content-type", "text/xml")
    kind, payload = classify_xmla(body)

    if kind != "EXECUTE" or not payload:
        r = forward_xmla(body, content_type, timeout_s=30)
        return Response(
            content=r.content,
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "text/xml"),
            headers={"X-MCAD-Decision": "PASS"},
        )

    mdx = payload
    browser_key = extract_session_cookie(req)
    session_id = str(ACTIVE_CONTEXT.get("session_id") or "") or None
    objective_id = str(ACTIVE_CONTEXT.get("objective_id") or MCAD_OBJECTIVE_ID_DEFAULT or "") or None

    decision: dict = {
        "decision": "BLOCK",
        "phi": 0.0,
        "threshold": 0.0,
        "sat": 0.0,
        "real": 0.0,
        "ceval": 0.0,
        "decision_reason_code": "EVAL_UNREACHABLE",
        "decision_reason": "MCAD /eval unavailable or failed.",
        "explain": "BLOCK because MCAD /eval failed; fail-open disabled.",
        "details": {},
    }
    eval_elapsed_ms = None

    try:
        eval_payload: dict = {"mdx": mdx}
        if session_id:
            eval_payload["session_id"] = session_id
        if objective_id:
            eval_payload["objective_id"] = objective_id
        if browser_key:
            eval_payload.setdefault("context", {})["browser_key"] = browser_key
        eval_started = time.time()
        er = await asyncio.to_thread(requests.post, MCAD_EVAL_URL, json=eval_payload, timeout=MCAD_EVAL_TIMEOUT_S)
        eval_elapsed_ms = int((time.time() - eval_started) * 1000)
        if er.ok:
            decision = er.json()
        else:
            decision["decision_reason"] = f"HTTP {er.status_code}: {(er.text or '')[:300]}"
            print("MCAD-EVAL HTTP error:", er.status_code, (er.text or "")[:300])
    except Exception as e:
        decision["decision_reason"] = str(e)
        print("MCAD-EVAL exception:", e)

    det = decision.get("details") if isinstance(decision.get("details"), dict) else {}
    graph_update = _normalize_graph_update(decision, mdx)
    decision["graph_update"] = graph_update
    ACTIVE_CONTEXT["session_id"] = str(det.get("session_id") or session_id or ACTIVE_CONTEXT.get("session_id") or "") or None
    ACTIVE_CONTEXT["objective_id"] = str(det.get("objective_id") or objective_id or ACTIVE_CONTEXT.get("objective_id") or "") or None
    xmla_gate_payload = {"execution_mode": "xmla_proxy", "query_type": "mdx", "query_id": "xmla_execute"}
    execution_evidence = _build_execution_evidence(
        decision=decision,
        direct_result=None,
        public_result={
            "physical_execution": False,
            "execution_path": "xmla_proxy",
            "adapter_id": "xmla_proxy",
            "adapter_family": "xmla_mondrian",
            "dw_id": ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart",
            "logical_query_language": "mdx",
            "physical_query_language": "xmla_mdx",
            "forwarded_to": UPSTREAM,
        },
        graph_update=graph_update,
        query_text=mdx,
        query_type="mdx",
        dw_id=str(ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart"),
        query_id="xmla_execute",
        payload=xmla_gate_payload,
        eval_elapsed_ms=eval_elapsed_ms,
    )
    LAST_EXECUTION_EVIDENCE.clear()
    LAST_EXECUTION_EVIDENCE.update(execution_evidence)
    LAST_DECISION.clear()
    LAST_DECISION.update({
        "decision": decision.get("decision"),
        "decision_reason_code": decision.get("decision_reason_code") or det.get("decision_reason_code"),
        "decision_reason": decision.get("decision_reason") or det.get("decision_reason"),
        "is_redundant": decision.get("is_redundant", det.get("is_redundant", False)),
        "has_marginal_gain": decision.get("has_marginal_gain", det.get("has_marginal_gain", False)),
        "objective_id": det.get("objective_id") or objective_id,
        "session_id": det.get("session_id") or session_id,
        "phi": decision.get("phi"),
        "threshold": decision.get("threshold"),
        "sat": decision.get("sat"),
        "real": decision.get("real"),
        "ceval": decision.get("ceval"),
        "useful_part": det.get("useful_part", decision.get("useful_part")),
        "explain": decision.get("explain"),
        "step_index": det.get("step_index") or decision.get("step_index"),
        "gained_resource_ids_count": det.get("gained_resource_ids_count", len(det.get("gained_resource_ids") or [])),
        "newly_contributed_constraints_total": det.get("newly_contributed_constraints_total", []),
        "newly_contributed_constraints_partial": det.get("newly_contributed_constraints_partial", []),
        "query_fingerprint": mdx_fingerprint(mdx),
        "query_digest": mdx_fingerprint(mdx),
        "graph_update": graph_update,
        "details": decision.get("details") if isinstance(decision.get("details"), dict) else {},
        "execution_evidence": execution_evidence,
        "measures": graph_update.get("measures", []),
        "slicers": graph_update.get("slicers", {}),
        "grain": graph_update.get("grain", []),
        "time_window": graph_update.get("time_window", {}),
        "ts_ms": int(time.time() * 1000),
    })

    if str(decision.get("decision", "ALLOW")).upper() == "BLOCK":
        fault = _fault_from_decision(decision, session_id)
        return Response(
            content=fault,
            status_code=200,
            media_type="text/xml; charset=utf-8",
            headers={
                "X-MCAD-Decision": "BLOCK",
                "X-MCAD-Phi": str(decision.get("phi", "")),
                "X-MCAD-Threshold": str(decision.get("threshold", "")),
                "X-MCAD-Decision-Reason": str(LAST_DECISION.get("decision_reason_code") or ""),
            },
        )

    t0 = time.time()
    r = forward_xmla(body, content_type, timeout_s=60)
    elapsed_ms = int((time.time() - t0) * 1000)
    response_bytes = len(r.content or b"")
    response_digest = hashlib.sha256(r.content or b"").hexdigest()[:16]
    raw_result_summary = summarize_xmla_response(r.content or b"")
    xmla_response_type = None
    _content_sample = (r.content or b"")[:4000].lower()
    if b"executeresponse" in _content_sample:
        xmla_response_type = "ExecuteResponse"
    elif b"discoverresponse" in _content_sample:
        xmla_response_type = "DiscoverResponse"
    elif b"fault" in _content_sample:
        xmla_response_type = "Fault"
    xmla_public_result = raw_result_summary if isinstance(raw_result_summary, dict) else {"xmla_summary": raw_result_summary}
    xmla_public_result.update({
        "physical_execution": bool(r.ok),
        "execution_mode": "real",
        "execution_path": "xmla_mondrian",
        "adapter_id": "xmla_proxy",
        "adapter_family": "xmla_mondrian",
        "dw_id": ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart",
        "logical_query_language": "mdx",
        "physical_query_language": "xmla_mdx",
        "forwarded_to": UPSTREAM,
        "status_code": r.status_code,
        "elapsed_ms": elapsed_ms,
        "response_bytes": response_bytes,
        "response_digest": response_digest,
        "result_digest": response_digest,
        "xmla_response_type": xmla_response_type,
    })
    execution_evidence = _build_execution_evidence(
        decision=decision,
        direct_result=None,
        public_result=xmla_public_result,
        graph_update=graph_update,
        query_text=mdx,
        query_type="mdx",
        dw_id=str(ACTIVE_CONTEXT.get("dw_id") or MCAD_DW_ID_DEFAULT or "foodmart"),
        query_id="xmla_execute",
        payload={"execution_mode": "xmla_proxy", "query_type": "mdx", "query_id": "xmla_execute"},
        eval_elapsed_ms=eval_elapsed_ms,
    )
    LAST_EXECUTION_EVIDENCE.clear()
    LAST_EXECUTION_EVIDENCE.update(execution_evidence)
    LAST_DECISION["execution_evidence"] = execution_evidence

    try:
        qspec = det.get("query_spec") if isinstance(det.get("query_spec"), dict) else {}
        requests.post(
            MCAD_CKG_URL,
            json={
                "mdx": mdx,
                "status_code": r.status_code,
                "elapsed_ms": elapsed_ms,
                "response_bytes": response_bytes,
                "response_digest": response_digest,
                "decision": decision.get("decision"),
                "phi": decision.get("phi"),
                "sat": decision.get("sat"),
                "real": decision.get("real"),
                "ceval": decision.get("ceval"),
                "threshold": decision.get("threshold"),
                "catalog": det.get("catalog"),
                "cube": qspec.get("cube") or None,
                "session_id": det.get("session_id") or session_id,
                "objective_id": det.get("objective_id") or objective_id,
                "step_index": det.get("step_index"),
                "query_spec": qspec or None,
                "calculable_constraints": det.get("calculable_constraints"),
                "covered_constraints": det.get("covered_constraints"),
                "raw_result_summary": raw_result_summary,
            },
            timeout=15,
        )
    except Exception as e:
        print("MCAD-CKG update exception:", e)

    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type", "text/xml"),
        headers={
            "X-MCAD-Decision": "ALLOW",
            "X-MCAD-Phi": str(decision.get("phi", "")),
            "X-MCAD-Threshold": str(decision.get("threshold", "")),
            "X-MCAD-Decision-Reason": str(LAST_DECISION.get("decision_reason_code") or ""),
        },
    )


