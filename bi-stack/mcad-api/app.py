from __future__ import annotations

import shutil

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import time
import json
import hashlib
import re
import requests
from pathlib import Path
from datetime import datetime, timezone

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:
    GraphDatabase = None  # optional

app = FastAPI(title="MCAD API Adapter", version="1.2.0")

DATA_DIR = Path(os.getenv("MCAD_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

THRESHOLD_DEFAULT = float(os.getenv("MCAD_THRESHOLD_DEFAULT", "0.60"))
BI_DECISION_MODE = str(os.getenv("MCAD_BI_DECISION_MODE", "formal_contributive")).strip().lower()

# V8.8.1 hybrid nvac_ok(QP): static metadata first, then lightweight
# FoodMart probe when static evidence is insufficient. In Docker, mcad-api
# can call the mcad-proxy service directly; the probe endpoint never calls
# /eval, so it does not create a decision recursion.
MCAD_NVAC_MODE = str(os.getenv("MCAD_NVAC_MODE", "hybrid")).strip().lower()
MCAD_NVAC_PROBE_URL = str(os.getenv("MCAD_NVAC_PROBE_URL", "http://mcad-proxy:9000/bi/nvac-probe")).strip()
MCAD_NVAC_PROBE_TIMEOUT_S = float(os.getenv("MCAD_NVAC_PROBE_TIMEOUT_S", "3.0"))
_NVAC_PROBE_CACHE: Dict[str, Dict[str, Any]] = {}


# Neo4j (optionnel)
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Prefer the richer backend MDX parser when available.
try:
    from mcad.mdx_parser import parse_mdx as backend_parse_mdx  # type: ignore
except Exception:
    backend_parse_mdx = None

# Canonical MCAD formal SAT layer: the BI stack must consume the backend model
# instead of redefining SAT(QP) locally. If this import fails, /eval fails closed
# through the proxy default EVAL_UNREACHABLE/BLOCK behavior.
try:
    from mcad.formal_sat import evaluate_sat_formal_clauses as _evaluate_sat_formal_clauses  # type: ignore
except Exception as _formal_sat_import_exc:  # pragma: no cover - deployment guard
    def _evaluate_sat_formal_clauses(*args, **kwargs):  # type: ignore
        raise RuntimeError("Canonical backend formal SAT layer is unavailable") from _formal_sat_import_exc


def _mcad_api_nvac_probe_cache_key(features: Dict[str, Any], mdx: str) -> str:
    data = {
        "mdx": mdx or str(features.get("mdx") or ""),
        "cube": features.get("cube"),
        "slicers": features.get("slicers") if isinstance(features.get("slicers"), dict) else {},
        "group_by": features.get("group_by") or [],
        "measures": features.get("measures") or [],
        "dw_id": features.get("dw_id"),
        "dataset": features.get("dataset"),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def _mcad_api_call_nvac_probe(features: Dict[str, Any], mdx: str) -> Dict[str, Any]:
    """Integration-side nvac_ok physical probe.

    The canonical backend formal SAT module receives this as a callback; it does
    not know proxy URLs and does not perform HTTP/BI I/O by itself. This keeps
    /backend pure while allowing /bi-stack to provide bounded real-DW evidence.
    """
    mode = MCAD_NVAC_MODE if MCAD_NVAC_MODE in {"static", "probe", "hybrid"} else "hybrid"
    if mode == "static":
        return {"probe_attempted": False, "probe_skipped_reason": "MCAD_NVAC_MODE=static", "non_empty": None, "count": None}
    if not MCAD_NVAC_PROBE_URL:
        return {"probe_attempted": False, "probe_skipped_reason": "MCAD_NVAC_PROBE_URL is empty", "non_empty": None, "count": None}

    key = _mcad_api_nvac_probe_cache_key(features, mdx)
    if key in _NVAC_PROBE_CACHE:
        cached = dict(_NVAC_PROBE_CACHE[key])
        cached["cache_hit"] = True
        return cached

    payload = {
        "mdx": mdx or str(features.get("mdx") or ""),
        "cube": str(features.get("cube") or "Sales"),
        "slicers": features.get("slicers") if isinstance(features.get("slicers"), dict) else {},
        "group_by": features.get("group_by") or [],
        "measures": features.get("measures") or [],
        "dw_id": str(features.get("dw_id") or ""),
        "dataset": str(features.get("dataset") or ""),
        "reason": features.get("reason") or "static_evidence_uncertain",
    }
    started = time.time()
    try:
        resp = requests.post(MCAD_NVAC_PROBE_URL, json=payload, timeout=MCAD_NVAC_PROBE_TIMEOUT_S)
        elapsed_ms = int((time.time() - started) * 1000)
        if not resp.ok:
            out = {
                "probe_attempted": True,
                "probe_url": MCAD_NVAC_PROBE_URL,
                "probe_http_status": resp.status_code,
                "probe_error": (resp.text or "")[:500],
                "elapsed_ms": elapsed_ms,
                "non_empty": None,
                "count": None,
            }
        else:
            data = resp.json() if resp.content else {}
            out = {
                "probe_attempted": True,
                "probe_url": MCAD_NVAC_PROBE_URL,
                "elapsed_ms": elapsed_ms,
                "non_empty": bool(data.get("non_empty")) if data.get("non_empty") is not None else None,
                "count": data.get("count"),
                "probe_query": data.get("probe_query"),
                "probe_measure": data.get("probe_measure"),
                "raw_probe_summary": data.get("summary"),
            }
    except Exception as exc:
        out = {
            "probe_attempted": True,
            "probe_url": MCAD_NVAC_PROBE_URL,
            "probe_error": str(exc),
            "non_empty": None,
            "count": None,
        }
    _NVAC_PROBE_CACHE[key] = dict(out)
    return out
try:
    from execution.useful_result_extractor import extract_useful_result_summary  # type: ignore
except Exception:
    extract_useful_result_summary = None


# -------------------------
# Models
# -------------------------

class EvalRequest(BaseModel):
    mdx: str
    session_id: Optional[str] = None
    objective_id: Optional[str] = None
    user_id: Optional[str] = None
    catalog: Optional[str] = None
    cube: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class EvalResponse(BaseModel):
    decision: str                 # "ALLOW" | "BLOCK"
    phi: float
    threshold: float
    sat: float
    real: float
    ceval: float
    explain: str
    decision_reason_code: Optional[str] = None
    decision_reason: Optional[str] = None
    is_redundant: bool = False
    has_marginal_gain: bool = False
    details: Dict[str, Any] = {}


class CkgUpdateRequest(BaseModel):
    mdx: str
    status_code: int
    elapsed_ms: int
    response_bytes: Optional[int] = None
    response_digest: Optional[str] = None

    # provenant de /eval (via mcad-proxy)
    objective_id: Optional[str] = None
    step_index: Optional[int] = None
    query_spec: Optional[Dict[str, Any]] = None
    calculable_constraints: Optional[List[str]] = None
    covered_constraints: Optional[List[str]] = None
    raw_result_summary: Optional[Dict[str, Any]] = None
    useful_result_summary: Optional[Dict[str, Any]] = None

    decision: Optional[str] = None
    phi: Optional[float] = None
    sat: Optional[float] = None
    real: Optional[float] = None
    ceval: Optional[float] = None
    threshold: Optional[float] = None

    catalog: Optional[str] = None
    cube: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    objective_id: str
    dw_id: str = "foodmart"


class ResumeSessionRequest(BaseModel):
    session_id: str


class UISessionHistoryEntry(BaseModel):
    session_id: str
    objective_id: str
    timestamp: datetime
    step_index: int
    decision: str
    decision_reason_code: Optional[str] = None
    decision_reason: Optional[str] = None
    phi: float = 0.0
    delta_phi_t: float = 0.0
    mdx: str = ""
    query_digest: Optional[str] = None
    newly_contributed_constraints_total: List[str] = []
    newly_contributed_constraints_partial: List[str] = []
    gained_resource_ids: List[str] = []
    calculable_constraints_total: List[str] = []
    calculable_constraints_partial: List[str] = []
    covered_constraints: List[str] = []


def _safe_step_index(session_state, session_history) -> int:
    return max(int(getattr(session_state, 'step_index', 0) or 0), len(session_history or [])) + 1


def _append_ui_history_entry(SESSION_STORE, state, *, objective_id: str, mdx: str, phi: float, delta_phi_t: float,
                             decision: str, decision_reason_code: str, decision_reason: str, query_digest: str,
                             newly_total: List[str], newly_partial: List[str], gained_resource_ids: List[str],
                             calc_total: List[str], calc_partial: List[str], covered_constraints: List[str]) -> None:
    history = list(getattr(state, 'history', []) or [])
    entry = UISessionHistoryEntry(
        session_id=state.session_id,
        objective_id=objective_id,
        timestamp=datetime.now(timezone.utc),
        step_index=_safe_step_index(state, history),
        decision=str(decision),
        decision_reason_code=str(decision_reason_code or ''),
        decision_reason=str(decision_reason or ''),
        phi=float(phi or 0.0),
        delta_phi_t=float(delta_phi_t or 0.0),
        mdx=str(mdx or ''),
        query_digest=str(query_digest or ''),
        newly_contributed_constraints_total=[str(x) for x in (newly_total or [])],
        newly_contributed_constraints_partial=[str(x) for x in (newly_partial or [])],
        gained_resource_ids=[str(x) for x in (gained_resource_ids or [])],
        calculable_constraints_total=[str(x) for x in (calc_total or [])],
        calculable_constraints_partial=[str(x) for x in (calc_partial or [])],
        covered_constraints=[str(x) for x in (covered_constraints or [])],
    )
    try:
        SESSION_STORE.append_history(state.session_id, entry)
        state.step_index = entry.step_index
        state.covered_constraints = sorted(set(getattr(state, 'covered_constraints', []) or []) | set(entry.covered_constraints or []))
        state.phi_leq_t = max(float(getattr(state, 'phi_leq_t', 0.0) or 0.0), float(phi or 0.0))
    except Exception:
        pass



def _coerce_entry_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _set_history_attr(entry: Any, name: str, value: Any) -> None:
    """Best-effort mutation for pydantic/dataclass/plain history entries."""
    try:
        setattr(entry, name, value)
    except Exception:
        try:
            if isinstance(entry, dict):
                entry[name] = value
        except Exception:
            pass


def _get_history_attr(entry: Any, name: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _sync_effective_decision_to_history(
    SESSION_STORE,
    state,
    *,
    objective_id: str,
    mdx: str,
    decision: str,
    reason_code: str,
    reason: str,
    phi: float,
    delta_phi_t: float,
    covered_constraints: List[str],
    realized_virtual_nodes: List[str],
    query_digest: str,
) -> Optional[int]:
    """Make the session audit log reflect the effective contract-first decision.

    The legacy formal engine can append a provisional BLOCK entry before the
    generalized objective contract upgrades the effective decision to ALLOW.
    Without this synchronization, /graph/state becomes covered while History and
    ALLOW/BLOCK metrics still show BLOCK. This function rewrites only the most
    recent entry for the evaluated query; if no entry exists, it appends a small
    UI history entry.
    """
    session_id = str(getattr(state, "session_id", "") or "")
    decision = str(decision or "BLOCK").upper()
    reason_code = str(reason_code or ("ALLOW_NEW_TOTAL" if decision == "ALLOW" else "BLOCK_UNKNOWN"))
    reason = str(reason or reason_code)
    covered = _coerce_entry_list(covered_constraints) if decision == "ALLOW" else []
    realized = _coerce_entry_list(realized_virtual_nodes) if decision == "ALLOW" else []
    try:
        history = list(getattr(state, "history", []) or [])
    except Exception:
        history = []

    if history:
        entry = history[-1]
        step_index = int(_get_history_attr(entry, "step_index", len(history)) or len(history))
        _set_history_attr(entry, "objective_id", objective_id)
        _set_history_attr(entry, "decision", decision)
        _set_history_attr(entry, "decision_reason_code", reason_code)
        _set_history_attr(entry, "decision_reason", reason)
        _set_history_attr(entry, "phi", float(phi or 0.0))
        _set_history_attr(entry, "delta_phi_t", float(delta_phi_t or 0.0))
        _set_history_attr(entry, "mdx", str(mdx or _get_history_attr(entry, "mdx", "")))
        _set_history_attr(entry, "query_digest", str(query_digest or _get_history_attr(entry, "query_digest", "")))
        _set_history_attr(entry, "covered_constraints", covered)
        _set_history_attr(entry, "newly_contributed_constraints_total", covered)
        _set_history_attr(entry, "newly_contributed_constraints_partial", [])
        _set_history_attr(entry, "calculable_constraints_total", covered)
        _set_history_attr(entry, "calculable_constraints_partial", [])
        _set_history_attr(entry, "gained_resource_ids", realized)
        try:
            state.history = history
        except Exception:
            pass
        try:
            state.step_index = max(int(getattr(state, "step_index", 0) or 0), step_index)
            state.covered_constraints = sorted(set(_coerce_entry_list(getattr(state, "covered_constraints", []))) | set(covered))
            state.phi_leq_t = max(float(getattr(state, "phi_leq_t", 0.0) or 0.0), float(phi or 0.0))
        except Exception:
            pass
        return step_index

    # Fallback for stores where the real engine did not append anything.
    try:
        _append_ui_history_entry(
            SESSION_STORE,
            state,
            objective_id=objective_id,
            mdx=mdx,
            phi=float(phi or 0.0),
            delta_phi_t=float(delta_phi_t or 0.0),
            decision=decision,
            decision_reason_code=reason_code,
            decision_reason=reason,
            query_digest=query_digest,
            newly_total=covered,
            newly_partial=[],
            gained_resource_ids=realized,
            calc_total=covered,
            calc_partial=[],
            covered_constraints=covered,
        )
        return int(getattr(state, "step_index", 0) or 0)
    except Exception:
        return None



# -------------------------
# MDX helpers
# -------------------------

_CUBE_RE = re.compile(r"FROM\s+\[([^\]]+)\]", re.IGNORECASE)
_MEASURE_RE = re.compile(r"\[Measures\]\.\[([^\]]+)\]", re.IGNORECASE)

def parse_cube(mdx: str) -> Optional[str]:
    m = _CUBE_RE.search(mdx or "")
    return m.group(1) if m else None

def parse_measures(mdx: str) -> List[str]:
    return _MEASURE_RE.findall(mdx or "")

def _mdx_bracket_parts(chain: str) -> List[str]:
    return [p.strip() for p in re.findall(r"\[([^\]]+)\]", chain or "") if p.strip()]


def _mdx_level_name(parts: List[str]) -> Optional[str]:
    """Normalize arbitrary MDX hierarchy paths to MCAD grain ids.

    Examples:
      [Time].[Month].Members -> Time.Month
      [Time].[Time].[Month].Members -> Time.Month
      [Product].[Product Category].Members -> Product.Product Category
    """
    if len(parts) < 2:
        return None
    dim = parts[0]
    level = parts[-1]
    return f"{dim}.{level}"


def _regex_mdx_features(mdx: str) -> Dict[str, Any]:
    """Resilient MDX feature extraction used to support diverse MDX shapes.

    It is intentionally conservative: it extracts measures, ROWS grain levels,
    and WHERE slicers without relying on a single hierarchy style. It supports
    both [Time].[Month].Members and [Time].[Time].[Month].Members, plus
    CrossJoin/NonEmptyCrossJoin expressions.
    """
    text = mdx or ""
    measures = sorted({m for m in parse_measures(text) if m})
    group_by: List[str] = []
    slicers: Dict[str, str] = {}

    # ROWS axis: everything immediately before ON ROWS, including CrossJoin().
    row_exprs = re.findall(r"(?is)(.*?)(?:ON\s+ROWS)", text)
    if row_exprs:
        row_expr = row_exprs[-1]
        # Keep only the segment after the previous axis separator when present.
        if "ON COLUMNS" in row_expr.upper():
            row_expr = re.split(r"(?is)ON\s+COLUMNS\s*,", row_expr)[-1]
        for chain in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\])+\s*(?:\.Members)?", row_expr, flags=re.I):
            if chain.lower().startswith("[measures]"):
                continue
            if ".members" not in chain.lower():
                continue
            level = _mdx_level_name(_mdx_bracket_parts(chain))
            if level:
                group_by.append(level)

    # WHERE slicers: ([Dim].[Hierarchy].[Member], ...). Use last token as value.
    where_match = re.search(r"(?is)\bWHERE\s*\((.*)\)\s*$", text)
    if where_match:
        where_expr = where_match.group(1)
        for chain in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\])+", where_expr):
            if chain.lower().startswith("[measures]"):
                continue
            parts = _mdx_bracket_parts(chain)
            if len(parts) >= 2:
                key_parts = parts[:-1]
                # Collapse duplicate hierarchy name: Store.Store State.CA -> Store.Store State
                key = f"{key_parts[0]}.{key_parts[-1]}" if len(key_parts) >= 2 else key_parts[0]
                slicers[key] = parts[-1]

    return {
        "measures": measures,
        "group_by": sorted(set(group_by)),
        "slicers": slicers,
    }

def mdx_fingerprint(mdx: str) -> str:
    return hashlib.sha256((mdx or "").encode("utf-8")).hexdigest()[:16]


def build_query_spec(mdx: str, cube_override: Optional[str] = None) -> Dict[str, Any]:
    """Build a MCAD-friendly query_spec from raw MDX.

    We prefer the richer backend parser so the BI-real path uses roughly the
    same analytical structure as the offline benchmark path. We keep a small
    regex fallback for resilience.
    """
    if backend_parse_mdx is not None:
        try:
            parsed = backend_parse_mdx(mdx) or {}
        except Exception:
            parsed = {}
    else:
        parsed = {}

    regex_features = _regex_mdx_features(mdx)
    cube = cube_override or parsed.get("cube") or parse_cube(mdx)
    measures = sorted({m for m in ((parsed.get("measures") or []) + regex_features.get("measures", [])) if m})
    analytics = [str(a).upper() for a in (parsed.get("analytics") or parsed.get("aggregators") or []) if a]
    group_by = sorted({str(g) for g in ((parsed.get("group_by") or []) + regex_features.get("group_by", [])) if g})
    slicers = parsed.get("slicers") if isinstance(parsed.get("slicers"), dict) else {}
    slicers = {**regex_features.get("slicers", {}), **slicers}
    time_members = [str(t) for t in (parsed.get("time_members") or []) if t]
    calculated_members = [str(t) for t in (parsed.get("calculated_members") or []) if t]
    named_sets = [str(t) for t in (parsed.get("named_sets") or []) if t]

    return {
        "mdx": mdx,
        "cube": cube,
        "measures": measures,
        "group_by": group_by,
        "slicers": slicers,
        "analytics": analytics,
        "axes": parsed.get("axes") or [],
        "time_members": time_members,
        "window_start": parsed.get("window_start"),
        "window_end": parsed.get("window_end"),
        "calculated_members": calculated_members,
        "named_sets": named_sets,
        "language": parsed.get("language") or "mdx",
        "fingerprint": parsed.get("fingerprint") or mdx_fingerprint(mdx),
    }




# -------------------------
# Decision detail archive (V8.9)
# -------------------------

def _json_safe(value: Any) -> Any:
    """Convert pydantic/dataclass/datetime/nested values to JSON-safe objects."""
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        try:
            return _json_safe(value.dict())
        except Exception:
            pass
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _ensure_decision_details_file() -> None:
    """Force creation of the append-only decision evidence archive.

    The archive is not optional anymore: every /eval call must be able to
    persist a complete evidence record. If the file is absent, create it as an
    empty JSON object. If it is corrupt, keep a .corrupt backup and recreate it
    so future evaluations are still archived.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _DECISION_DETAILS_FILE.exists():
        _DECISION_DETAILS_FILE.write_text("{}", encoding="utf-8")
        return
    try:
        raw = _DECISION_DETAILS_FILE.read_text(encoding="utf-8") or "{}"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("decision_details.json root must be an object")
    except Exception:
        try:
            backup = _DECISION_DETAILS_FILE.with_suffix(_DECISION_DETAILS_FILE.suffix + ".corrupt")
            backup.write_text(_DECISION_DETAILS_FILE.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except Exception:
            pass
        _DECISION_DETAILS_FILE.write_text("{}", encoding="utf-8")


def _load_decision_details_raw() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_decision_details_file()
    try:
        data = json.loads(_DECISION_DETAILS_FILE.read_text(encoding="utf-8") or "{}")
        if isinstance(data, dict):
            return {str(k): [x for x in (v or []) if isinstance(x, dict)] for k, v in data.items()}
    except Exception:
        pass
    return {}


def _write_decision_details_raw(data: Dict[str, List[Dict[str, Any]]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _DECISION_DETAILS_FILE.with_suffix(_DECISION_DETAILS_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(_json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_DECISION_DETAILS_FILE)




def _clear_session_effective_trace(session_id: str, *, reset_session_store: bool = True) -> Dict[str, Any]:
    """Clear the effective scenario trace of a session.

    This is intentionally stronger than clearing the UI table: it removes the
    authoritative decision-details archive for the session and resets the
    in-memory session-store contribution state when available. It is used when a
    logical session is created/reused with the same id after a rebuild, or when
    the user explicitly wants a fresh experimental run.
    """
    sid = str(session_id or "").strip()
    if not sid:
        return {"cleared": False, "reason": "empty_session_id"}

    data = _load_decision_details_raw()
    removed_decision_details = len(data.get(sid, []) or [])
    if sid in data:
        data.pop(sid, None)
        _write_decision_details_raw(data)

    removed_graph_state = False
    try:
        if sid in _GRAPH_SESSION_STATE:
            _GRAPH_SESSION_STATE.pop(sid, None)
            removed_graph_state = True
    except Exception:
        pass

    reset_store = False
    if reset_session_store:
        try:
            from mcad.session_store import SESSION_STORE
            state = SESSION_STORE.get_session(sid)
            # Best effort: different session-store implementations can be
            # pydantic models, dataclasses, or plain objects.
            for attr, value in [
                ("history", []),
                ("step_index", 0),
                ("phi_leq_t", 0.0),
                ("phi_weighted_leq_t", 0.0),
                ("covered_constraints", []),
                ("covered_constraints_total", []),
                ("covered_constraints_partial", []),
                ("realized_virtual_nodes", []),
                ("gained_resource_ids", []),
            ]:
                try:
                    setattr(state, attr, value)
                except Exception:
                    pass
            # Some stores expose dictionaries instead of attributes.
            if isinstance(state, dict):
                state.update({
                    "history": [],
                    "step_index": 0,
                    "phi_leq_t": 0.0,
                    "phi_weighted_leq_t": 0.0,
                    "covered_constraints": [],
                    "covered_constraints_total": [],
                    "covered_constraints_partial": [],
                    "realized_virtual_nodes": [],
                    "gained_resource_ids": [],
                })
            reset_store = True
        except Exception:
            reset_store = False

    return {
        "cleared": True,
        "session_id": sid,
        "removed_decision_details": removed_decision_details,
        "removed_graph_state": removed_graph_state,
        "reset_session_store": reset_store,
    }

def _record_decision_detail(session_id: Optional[str], item: Dict[str, Any]) -> None:
    """Persist a full, re-openable evidence record for one evaluation step."""
    sid = str(session_id or item.get("session_id") or "").strip()
    if not sid:
        return
    data = _load_decision_details_raw()
    rows = list(data.get(sid, []) or [])
    step = item.get("step_index")
    try:
        step_i = int(step)
    except Exception:
        step_i = len(rows) + 1
    item["step_index"] = step_i
    item.setdefault("session_id", sid)
    item.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    rows = [r for r in rows if int(r.get("step_index") or -1) != step_i]
    item = _ensure_explainability(item)
    rows.append(_json_safe(item))
    rows.sort(key=lambda r: int(r.get("step_index") or 0))
    data[sid] = rows
    _write_decision_details_raw(data)


def _decision_detail_by_step(session_id: str, step_index: int) -> Optional[Dict[str, Any]]:
    for item in _load_decision_details_raw().get(str(session_id), []) or []:
        try:
            if int(item.get("step_index") or -1) == int(step_index):
                return item
        except Exception:
            continue
    return None


# -------------------------
# MCAD graph_update contract state (generalized objective contract)
# -------------------------

_IMPORTED_OBJECTIVES_FILE = DATA_DIR / "imported_objectives.json"
_DECISION_DETAILS_FILE = DATA_DIR / "decision_details.json"
_GRAPH_SESSION_STATE: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
def _mcad_v892_startup_ensure_decision_archive() -> None:
    try:
        _ensure_decision_details_file()
    except Exception:
        # Startup must not prevent the service from booting; /eval will retry.
        pass


def _contract_as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _contract_norm_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _contract_norm_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _contract_extract_qp_features(qp_or_features: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = dict(qp_or_features or {})
    qspec = raw.get("query_spec") if isinstance(raw.get("query_spec"), dict) else raw
    mdx = str(raw.get("mdx") or qspec.get("mdx") or "")
    features = {
        "measures": _contract_as_list(qspec.get("measures")),
        "group_by": _contract_as_list(qspec.get("group_by")),
        "slicers": qspec.get("slicers") if isinstance(qspec.get("slicers"), dict) else {},
        "mdx": mdx,
    }
    if not features["measures"]:
        features["measures"] = parse_measures(mdx)
    return features


def _objective_to_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {
        "id": getattr(obj, "id", ""),
        "name": getattr(obj, "name", getattr(obj, "id", "")),
        "description": getattr(obj, "description", ""),
        "kpis": list(getattr(obj, "kpis", []) or []),
        "constraints": [_objective_to_dict(c) for c in (getattr(obj, "constraints", []) or [])],
    }


def _load_imported_objectives_raw() -> List[Dict[str, Any]]:
    try:
        if _IMPORTED_OBJECTIVES_FILE.exists():
            data = json.loads(_IMPORTED_OBJECTIVES_FILE.read_text(encoding="utf-8") or "{}")
            if isinstance(data, dict):
                return [x for x in (data.get("objectives") or []) if isinstance(x, dict)]
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _write_imported_objectives_raw(items: List[Dict[str, Any]]) -> None:
    by_id: Dict[str, Dict[str, Any]] = {}
    for it in items:
        oid = str(it.get("id") or "").strip()
        if oid:
            by_id[oid] = it
    _IMPORTED_OBJECTIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _IMPORTED_OBJECTIVES_FILE.write_text(json.dumps({"objectives": list(by_id.values())}, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_imported_objective(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either native MCAD Objective JSON or a compact UI-friendly schema.

    Compact constraint example accepted:
      {"id":"c_x", "measure":"Store Sales", "grain":"Time.Month",
       "slicers":{"Store.Store State":"CA"}, "virtual_node":"N_x"}
    """
    oid = str(obj.get("id") or obj.get("objective_id") or "").strip()
    if not oid:
        raise ValueError("Objective id is required")
    constraints_out: List[Dict[str, Any]] = []
    for idx, c in enumerate(obj.get("constraints") or []):
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or f"c_{idx+1}").strip()
        label = str(c.get("label") or c.get("description") or cid)
        virtual_nodes = c.get("virtual_nodes") if isinstance(c.get("virtual_nodes"), list) else None
        if virtual_nodes is None:
            measure = str(c.get("measure") or c.get("metric") or "").strip()
            grain = c.get("grain") or c.get("group_by") or []
            if isinstance(grain, str):
                grain_list = [grain]
            elif isinstance(grain, (list, tuple, set)):
                grain_list = [str(x) for x in grain if x is not None]
            else:
                grain_list = []
            slicers = c.get("slicers") if isinstance(c.get("slicers"), dict) else {}
            vnode_id = str(c.get("virtual_node") or c.get("virtual_node_id") or c.get("node_id") or f"N_{cid}")
            virtual_nodes = [{
                "id": vnode_id,
                "fact": str(c.get("fact") or obj.get("cube") or "Sales"),
                "grain": grain_list,
                "measure": measure,
                "aggregator": str(c.get("aggregator") or "SUM"),
                "unit": str(c.get("unit") or ""),
                "slicers": slicers,
                "window_start": c.get("window_start"),
                "window_end": c.get("window_end"),
            }]
        constraints_out.append({
            "id": cid,
            "kpi_id": str(c.get("kpi_id") or c.get("kpi") or cid),
            "description": str(c.get("description") or label),
            "weight": float(c.get("weight", 1.0) or 1.0),
            "requirement_sets": c.get("requirement_sets") or [],
            "virtual_nodes": virtual_nodes,
        })
    return {
        "id": oid,
        "name": str(obj.get("name") or oid),
        "description": str(obj.get("description") or ""),
        "kpis": obj.get("kpis") or [c.get("kpi_id", c.get("id")) for c in constraints_out],
        "constraints": constraints_out,
    }


def _extract_objectives_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict) and isinstance(payload.get("objectives"), list):
        raw = payload.get("objectives") or []
    elif isinstance(payload, dict):
        raw = [payload]
    else:
        raise ValueError("JSON must be an objective object, a list, or {'objectives': [...]}")
    return [_normalize_imported_objective(x) for x in raw if isinstance(x, dict)]


def _register_imported_objectives() -> None:
    """Load persisted imported objectives into mcad.objectives in-memory registry."""
    try:
        from mcad.models import Objective  # type: ignore
        from mcad.objectives import save_objective  # type: ignore
    except Exception:
        return
    for raw in _load_imported_objectives_raw():
        try:
            save_objective(Objective(**_normalize_imported_objective(raw)))
        except Exception:
            continue


def _objective_lookup(objective_id: Optional[str]) -> Optional[Any]:
    if not objective_id:
        return None
    _register_imported_objectives()
    try:
        from mcad.objectives import get_objective  # type: ignore
        return get_objective(str(objective_id))
    except Exception:
        for raw in _load_imported_objectives_raw():
            if str(raw.get("id")) == str(objective_id):
                return raw
    return None


def _constraint_contracts_for_objective(objective_id: Optional[str]) -> List[Dict[str, Any]]:
    obj = _objective_lookup(objective_id)
    if obj is None and str(objective_id or "") == "O_REAL_BEER_WA_MONTH":
        # Conservative fallback for the original FoodMart demo objective.
        return [
            {"constraint_id": "c_sales", "virtual_node_id": "N_c_sales", "measure": "Store Sales", "grain": ["Time.Month"], "slicers": {"Store.Store State": "WA", "Product.Product Category": "Beer and Wine"}, "label": "Store Sales calculability"},
            {"constraint_id": "c_profit", "virtual_node_id": "N_c_profit", "measure": "Profit", "grain": ["Time.Month"], "slicers": {"Store.Store State": "WA", "Product.Product Category": "Beer and Wine"}, "label": "Profit calculability"},
        ]
    data = _objective_to_dict(obj or {})
    contracts: List[Dict[str, Any]] = []
    for c in data.get("constraints") or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        label = str(c.get("label") or c.get("description") or cid)
        vnodes = c.get("virtual_nodes") or []
        if not vnodes and any(k in c for k in ("measure", "grain", "slicers", "virtual_node")):
            vnodes = [_normalize_imported_objective({"id":"__tmp__", "constraints":[c]})["constraints"][0]["virtual_nodes"][0]]
        for vn in vnodes:
            if not isinstance(vn, dict):
                vn = _objective_to_dict(vn)
            vid = str(vn.get("id") or c.get("virtual_node") or f"N_{cid}")
            contracts.append({
                "constraint_id": cid,
                "virtual_node_id": vid,
                "measure": str(vn.get("measure") or c.get("measure") or ""),
                "grain": _contract_as_list(vn.get("grain") or c.get("grain") or []),
                "slicers": vn.get("slicers") if isinstance(vn.get("slicers"), dict) else (c.get("slicers") if isinstance(c.get("slicers"), dict) else {}),
                "label": label,
                "fact": str(vn.get("fact") or ""),
                "aggregator": str(vn.get("aggregator") or ""),
                "unit": str(vn.get("unit") or ""),
            })
    return [c for c in contracts if c.get("constraint_id")]


def _required_constraints_for_objective(objective_id: Optional[str]) -> List[str]:
    return [c["constraint_id"] for c in _constraint_contracts_for_objective(objective_id)] or ["c_sales", "c_profit"]


def _virtual_node_by_constraint_for_objective(objective_id: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in _constraint_contracts_for_objective(objective_id):
        out.setdefault(str(c["constraint_id"]), str(c.get("virtual_node_id") or f"N_{c['constraint_id']}"))
    return out


def _feature_contains_value(features: Dict[str, Any], value: Any) -> bool:
    token = _contract_norm_token(value)
    if not token:
        return True
    slicers = features.get("slicers") if isinstance(features.get("slicers"), dict) else {}
    values = [_contract_norm_token(v) for v in slicers.values()]
    # Do NOT use a raw MDX substring test here. Short members such as "CA"
    # can appear inside hierarchy names like "Product Category", which caused
    # WA x Dairy queries to incorrectly match constraints requiring CA.
    # A required slicer value is satisfied only if it is an explicit slicer
    # value. If the required level is on ROWS/CrossJoin, _feature_has_slicers
    # handles that separately through the group_by rule.
    return token in values


def _feature_has_measure(features: Dict[str, Any], required_measure: str) -> bool:
    req = _contract_norm_token(required_measure)
    if not req:
        return False
    measures = {_contract_norm_token(m) for m in _contract_as_list(features.get("measures"))}
    return req in measures or req in _contract_norm_token(features.get("mdx"))


def _feature_has_grain(features: Dict[str, Any], required_grain: List[str]) -> bool:
    if not required_grain:
        return True

    # Formal grain compatibility must be evaluated on the effective cell grain
    # addressed by QP, not only on projected ROWS/COLUMNS axes. A level fixed in
    # WHERE is part of the cell context. Example: ROWS=Time.Month and
    # WHERE Product.Category=Beer, Store.State=WA addresses cells at
    # Time.Month × Product.Category × Store.State even if those two levels are
    # not displayed on ROWS. This keeps grain_ok aligned with the article's QP
    # abstraction: axes + slicer context.
    group_levels = _contract_as_list(features.get("group_by"))
    slicer_levels = list((features.get("slicers") or {}).keys()) if isinstance(features.get("slicers"), dict) else []
    effective_levels = list(group_levels) + [str(k) for k in slicer_levels]
    effective_tokens = {_contract_norm_token(g) for g in effective_levels}
    effective_last_tokens = {_contract_norm_token(str(g).split(".")[-1]) for g in effective_levels}

    for g in required_grain:
        gt = _contract_norm_token(g)
        last = _contract_norm_token(str(g).split(".")[-1])
        if gt not in effective_tokens and last not in effective_last_tokens:
            return False
    return True


def _feature_has_slicers(features: Dict[str, Any], required_slicers: Dict[str, Any]) -> bool:
    """Return True when required slicers are computable from the QP.

    A required slicer is satisfied in either of these cases:
      1. the required member value is explicitly present in WHERE / MDX; or
      2. the corresponding level is present on an analysis axis (group_by).

    Case (2) is important for generalized objectives: a query returning all
    Product Category members by Month can still compute the Dairy category
    contribution, even when Dairy is not fixed in WHERE.
    """
    if not required_slicers:
        return True

    group_tokens = {_contract_norm_token(g) for g in _contract_as_list(features.get("group_by"))}
    group_last_tokens = {_contract_norm_token(str(g).split(".")[-1]) for g in _contract_as_list(features.get("group_by"))}

    for key, value in required_slicers.items():
        if _feature_contains_value(features, value):
            continue

        key_token = _contract_norm_token(key)
        key_last = _contract_norm_token(str(key).split(".")[-1])
        if key_token in group_tokens or key_last in group_last_tokens:
            continue

        return False
    return True



# ---------------------------------------------------------------------------
# V9.4.1 — Canonical formal SAT(QP) layer
# ---------------------------------------------------------------------------
# Formal SAT(QP) clauses are now defined in backend/mcad/formal_sat.py and
# imported above as _evaluate_sat_formal_clauses. The API adapter remains
# responsible only for request handling, evidence archiving and report export.


def _infer_objective_constraint_from_qp_features(qp_features: Optional[Dict[str, Any]], objective_id: Optional[str] = None) -> Dict[str, List[str]]:
    """Infer graph_update coverage by comparing QP features with the active objective contract.

    This is objective-driven: constraints are not hard-coded. A constraint is
    covered only when the QP matches its required measure, grain and slicers.
    observed_resources are provenance only and are never promoted to Real(QP).
    """
    raw = dict(qp_features or {})
    objective_id = objective_id or raw.get("objective_id") or raw.get("objective") or "O_REAL_BEER_WA_MONTH"
    features = _contract_extract_qp_features(raw)
    observed_resources = sorted(str(m) for m in _contract_as_list(features.get("measures")))
    matches: List[Dict[str, Any]] = []
    for contract in _constraint_contracts_for_objective(str(objective_id)):
        if not _feature_has_measure(features, str(contract.get("measure") or "")):
            continue
        if not _feature_has_grain(features, _contract_as_list(contract.get("grain"))):
            continue
        if not _feature_has_slicers(features, contract.get("slicers") if isinstance(contract.get("slicers"), dict) else {}):
            continue
        matches.append(contract)

    # Specificity rule: when a query is explicitly at a finer displayed grain,
    # e.g. Time.Month x Product.Category, do not also mark the coarser Time.Month
    # constraint as newly covered. However, if a longer contract only matched
    # because a level was fixed in WHERE, prefer the axis-complete contract. This
    # distinguishes Q2 (Profit by Month with Product.Category fixed to Dairy) from
    # Q9 (Profit by Month x Product.Category on ROWS).
    if len(matches) > 1:
        group_tokens = {_contract_norm_token(g) for g in _contract_as_list(features.get("group_by"))}
        group_last_tokens = {_contract_norm_token(str(g).split(".")[-1]) for g in _contract_as_list(features.get("group_by"))}
        def axis_complete(m: Dict[str, Any]) -> bool:
            for g in _contract_as_list(m.get("grain")):
                gt = _contract_norm_token(g)
                last = _contract_norm_token(str(g).split(".")[-1])
                if gt not in group_tokens and last not in group_last_tokens:
                    return False
            return True
        axis_matches = [m for m in matches if axis_complete(m)]
        if axis_matches:
            max_axis_len = max(len(_contract_as_list(m.get("grain"))) for m in axis_matches)
            matches = [m for m in axis_matches if len(_contract_as_list(m.get("grain"))) == max_axis_len]
        else:
            max_grain_len = max(len(_contract_as_list(m.get("grain"))) for m in matches)
            if max_grain_len > 1:
                matches = [m for m in matches if len(_contract_as_list(m.get("grain"))) == max_grain_len]

    covered: List[str] = []
    realized: List[str] = []
    for contract in matches:
        cid = str(contract["constraint_id"])
        vid = str(contract.get("virtual_node_id") or f"N_{cid}")
        covered.append(cid)
        realized.append(vid)

    return {"covered_constraints": sorted(set(covered)), "realized_virtual_nodes": sorted(set(realized)), "observed_resources": observed_resources}


def _empty_graph_session_state(session_id: str, objective_id: Optional[str] = None) -> Dict[str, Any]:
    return {"session_id": session_id, "objective_id": objective_id, "cumulative_covered_constraints": [], "cumulative_realized_virtual_nodes": [], "observed_resources": [], "events": []}


def _merge_graph_session_state(session_id: str, graph_update: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    update = dict(graph_update or {})
    state = _GRAPH_SESSION_STATE.setdefault(str(session_id), _empty_graph_session_state(str(session_id), update.get("objective_id")))
    if update.get("objective_id"):
        state["objective_id"] = update.get("objective_id")
    objective_id = str(state.get("objective_id") or update.get("objective_id") or "")
    required = _required_constraints_for_objective(objective_id)
    vnode_by_constraint = _virtual_node_by_constraint_for_objective(objective_id)

    observed = set(_contract_as_list(state.get("observed_resources")))
    observed.update(_contract_as_list(update.get("observed_resources")))
    state["observed_resources"] = sorted(observed)

    decision = str(update.get("decision") or "ALLOW").upper()
    if decision != "BLOCK":
        covered = set(_contract_as_list(state.get("cumulative_covered_constraints")))
        incoming = set(_contract_as_list(update.get("covered_constraints")))
        covered.update(c for c in incoming if c in required)
        state["cumulative_covered_constraints"] = [c for c in required if c in covered]
        realized = set(_contract_as_list(state.get("cumulative_realized_virtual_nodes")))
        for cid in state["cumulative_covered_constraints"]:
            if cid in vnode_by_constraint:
                realized.add(vnode_by_constraint[cid])
        valid_realized = set(vnode_by_constraint.values())
        for vid in _contract_as_list(update.get("realized_virtual_nodes")):
            if vid in valid_realized:
                realized.add(vid)
        state["cumulative_realized_virtual_nodes"] = sorted(realized)

    state.setdefault("events", []).append({"decision": decision, "covered_constraints": _contract_as_list(update.get("covered_constraints")) if decision != "BLOCK" else [], "realized_virtual_nodes": _contract_as_list(update.get("realized_virtual_nodes")) if decision != "BLOCK" else [], "observed_resources": _contract_as_list(update.get("observed_resources")), "step_index": update.get("step_index")})
    return state


def _public_graph_session_state(session_id: str, objective_id: Optional[str] = None) -> Dict[str, Any]:
    state = _GRAPH_SESSION_STATE.setdefault(str(session_id), _empty_graph_session_state(str(session_id), objective_id))
    if objective_id:
        state["objective_id"] = objective_id
    objective_id = str(state.get("objective_id") or objective_id or "")
    required = _required_constraints_for_objective(objective_id)
    covered_set = set(_contract_as_list(state.get("cumulative_covered_constraints")))
    covered = [c for c in required if c in covered_set]
    pending = [c for c in required if c not in covered_set]
    realized = sorted(set(_contract_as_list(state.get("cumulative_realized_virtual_nodes"))))
    phi = (len(covered) / len(required)) if required else 0.0
    objective_state = "pending" if not covered else ("covered" if not pending else "partial")
    return {"ok": True, "session_id": str(session_id), "objective_id": objective_id, "required_constraints": required, "objective_state": objective_state, "session_phi": phi, "cumulative_covered_constraints": covered, "pending_constraints": pending, "cumulative_realized_virtual_nodes": realized, "observed_resources": sorted(set(_contract_as_list(state.get("observed_resources")))), "events": list(state.get("events") or [])}


def _graph_from_contract_state(contract_state: Dict[str, Any]) -> Dict[str, Any]:
    oid = str(contract_state.get("objective_id") or "O")
    covered = set(contract_state.get("cumulative_covered_constraints") or [])
    realized = set(contract_state.get("cumulative_realized_virtual_nodes") or [])
    objective_status = contract_state.get("objective_state") or "pending"
    nodes = [{"id": oid, "label": f"Objective {oid}", "type": "objective", "kind": "objective", "state": objective_status, "status": objective_status}]
    edges: List[Dict[str, Any]] = []
    for c in _constraint_contracts_for_objective(oid):
        cid = str(c["constraint_id"])
        vid = str(c.get("virtual_node_id") or f"N_{cid}")
        c_state = "covered" if cid in covered else "pending"
        v_state = "realized" if vid in realized else "pending"
        nodes.append({"id": cid, "label": str(c.get("label") or cid), "type": "constraint", "kind": "constraint", "state": c_state, "status": "total" if c_state == "covered" else "none", "measure": c.get("measure"), "grain": c.get("grain"), "slicers": c.get("slicers")})
        nodes.append({"id": vid, "label": f"Virtual node {vid}", "type": "virtual_node", "kind": "resource", "state": v_state, "status": "covered" if v_state == "realized" else "pending", "measure": c.get("measure"), "grain": c.get("grain"), "slicers": c.get("slicers")})
        edges.append({"id": f"e_{oid}_{cid}", "source": oid, "target": cid, "type": "HAS_CONSTRAINT"})
        edges.append({"id": f"e_{cid}_{vid}", "source": cid, "target": vid, "type": "SUPPORTED_BY"})
    return {"nodes": nodes, "edges": edges}

# -------------------------
# Adapter persistence (JSONL / Neo4j)
# -------------------------

def update_ckg_file(payload: CkgUpdateRequest) -> Dict[str, Any]:
    """Append-only JSONL event log in /app/data/ckg_events.jsonl."""
    # pydantic v1/v2 compatibility
    event = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    event["ts"] = int(time.time() * 1000)
    event["fingerprint"] = mdx_fingerprint(payload.mdx)

    out = DATA_DIR / "ckg_events.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"mode": "file", "path": str(out), "fingerprint": event["fingerprint"]}


def update_ckg_neo4j(payload: CkgUpdateRequest) -> Dict[str, Any]:
    """Optional Neo4j persistence."""
    if GraphDatabase is None:
        raise RuntimeError("neo4j driver not available")
    if not (NEO4J_URI and NEO4J_PASSWORD):
        raise RuntimeError("NEO4J_URI/NEO4J_PASSWORD not configured")

    fp = mdx_fingerprint(payload.mdx)
    session_id = payload.session_id or "default-session"
    user_id = payload.user_id or "default-user"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    cypher = """
    MERGE (u:User {id:$user_id})
    MERGE (s:Session {id:$session_id})
    MERGE (q:Query {fp:$fp})
      ON CREATE SET q.mdx=$mdx
    CREATE (e:Execution {
      ts:$ts,
      status_code:$status_code,
      elapsed_ms:$elapsed_ms,
      response_bytes:$response_bytes,
      decision:$decision,
      phi:$phi,
      sat:$sat,
      real:$real,
      ceval:$ceval,
      threshold:$threshold
    })
    MERGE (u)-[:HAS_SESSION]->(s)
    MERGE (s)-[:ISSUED]->(q)
    CREATE (q)-[:EXECUTED_AS]->(e)
    RETURN e.ts as ts
    """
    params = {
        "user_id": user_id,
        "session_id": session_id,
        "fp": fp,
        "mdx": payload.mdx,
        "ts": int(time.time() * 1000),
        "status_code": payload.status_code,
        "elapsed_ms": payload.elapsed_ms,
        "response_bytes": payload.response_bytes,
        "decision": payload.decision,
        "phi": payload.phi,
        "sat": payload.sat,
        "real": payload.real,
        "ceval": payload.ceval,
        "threshold": payload.threshold,
    }
    with driver.session() as sess:
        rec = sess.run(cypher, params).single()
    driver.close()
    return {"mode": "neo4j", "fp": fp, "ts": rec["ts"] if rec else None}


# -------------------------
# Backend CKGGraph update (normalized IDs)
# -------------------------

def _prefix_if_missing(raw: Optional[str], prefix: str) -> Optional[str]:
    if not raw:
        return None
    s = str(raw)
    return s if s.startswith(prefix) else f"{prefix}{s}"


def update_ckg_backend(payload: CkgUpdateRequest) -> Dict[str, Any]:
    """
    Best-effort: update the REAL backend CKGGraph (networkx) after ALLOW execution.

    Normalized identifiers:
      - session::S_0001
      - objective::O_...
      - qp::S_0001::t001
      - exec::S_0001::t001::<digest>::<ts>
    """
    try:
        import mcad.engine as engine  # type: ignore

        # Try to obtain a CKGGraph instance from engine (robust)
        ckg = None
        if hasattr(engine, "get_ckg") and callable(getattr(engine, "get_ckg")):
            ckg = engine.get_ckg()
        else:
            for attr in ("CKG", "CKG_GRAPH", "GLOBAL_CKG", "ckg", "CKG_INSTANCE"):
                if hasattr(engine, attr):
                    ckg = getattr(engine, attr)
                    break

        if ckg is None:
            return {"mode": "backend", "ok": False, "reason": "no_ckg_instance_exposed"}

        if not hasattr(ckg, "G"):
            return {"mode": "backend", "ok": False, "reason": "ckg_instance_has_no_graph"}

        G = getattr(ckg, "G")

        sid_raw = payload.session_id or os.getenv("MCAD_SESSION_ID_DEFAULT", "S_0001")
        sid = _prefix_if_missing(sid_raw, "session::")  # type: ignore
        oid_raw = payload.objective_id or os.getenv("MCAD_OBJECTIVE_ID_DEFAULT")
        oid = _prefix_if_missing(oid_raw, "objective::")

        step_idx = int(payload.step_index or 0)
        digest = payload.response_digest or mdx_fingerprint(payload.mdx)
        ts = int(time.time() * 1000)

        exec_id = f"exec::{sid_raw}::t{step_idx:03d}::{digest}::{ts}" if step_idx > 0 else f"exec::{sid_raw}::{digest}::{ts}"
        qpid = f"qp::{sid_raw}::t{step_idx:03d}" if step_idx > 0 else None

        # Ensure session/objective nodes
        if sid and not G.has_node(sid):
            G.add_node(sid, type="session", session_id=sid_raw)
        if oid and not G.has_node(oid):
            G.add_node(oid, type="objective", objective_id=oid_raw)

        # Execution node
        G.add_node(
            exec_id,
            type="execution",
            mdx=payload.mdx,
            fingerprint=mdx_fingerprint(payload.mdx),
            response_digest=payload.response_digest,
            status_code=payload.status_code,
            elapsed_ms=payload.elapsed_ms,
            response_bytes=payload.response_bytes,
            decision=payload.decision,
            phi=payload.phi,
            threshold=payload.threshold,
            sat=payload.sat,
            real=payload.real,
            ceval=payload.ceval,
            step_index=step_idx,
            query_spec=json.dumps(payload.query_spec or {}, ensure_ascii=False),
            calculable_constraints=json.dumps(payload.calculable_constraints or [], ensure_ascii=False),
            covered_constraints=json.dumps(payload.covered_constraints or [], ensure_ascii=False),
            raw_result_summary=json.dumps(payload.raw_result_summary or {}, ensure_ascii=False),
            useful_result_summary=json.dumps(payload.useful_result_summary or {}, ensure_ascii=False),
            ts=ts,
        )

        # Edges
        if sid:
            G.add_edge(sid, exec_id, type="HAS_EXECUTION")
        if oid:
            G.add_edge(exec_id, oid, type="FOR_OBJECTIVE")
        if qpid and G.has_node(qpid):
            G.add_edge(exec_id, qpid, type="EXECUTED_QP")

        # IMPORTANT: stop creating legacy raw session nodes ("S_0001")
        # Optional safe cleanup: remove raw node only if isolated
        if G.has_node(sid_raw) and sid_raw != sid:
            try:
                # if it has no incident edges, remove it
                deg = 0
                if hasattr(G, "degree"):
                    deg = int(G.degree(sid_raw))  # type: ignore
                if deg == 0:
                    G.remove_node(sid_raw)
            except Exception:
                pass

        # Persist snapshot (try both call signatures)
        snap = str(DATA_DIR / "ckg_state.json")
        try:
            if hasattr(ckg, "save_state_json") and callable(getattr(ckg, "save_state_json")):
                try:
                    ckg.save_state_json(snap)
                except TypeError:
                    ckg.save_state_json(path=snap)  # type: ignore
        except Exception:
            pass

        return {"mode": "backend", "ok": True, "exec_id": exec_id, "qpid": qpid, "session": sid, "objective": oid, "snapshot": snap}
    except Exception as e:
        return {"mode": "backend", "ok": False, "error": str(e)}




def _resolve_bi_decision(
    *,
    sat: bool,
    phi: float,
    threshold: float,
    calculable_constraints: List[str],
    calculable_constraints_total: List[str],
    calculable_constraints_partial: List[str],
    newly_contributed_constraints_total: List[str],
    newly_contributed_constraints_partial: List[str],
    gained_resource_ids: List[str],
    phi_leq_t: Optional[float],
    delta_phi_t: Optional[float],
) -> tuple[str, str]:
    """Resolve ALLOW/BLOCK in the BI-real path.

    Default policy is aligned with the manuscript formalization:
      - ALLOW iff SAT(QP) is true and Ceval(QP, O) is non-empty.

    The threshold is preserved as an explanatory / ranking signal, not as the
    default blocking rule. A stricter threshold-based mode is still available
    through MCAD_BI_DECISION_MODE=strict_threshold for experimentation.
    """
    has_ceval = bool(calculable_constraints)
    has_total = bool(calculable_constraints_total)
    has_partial = bool(calculable_constraints_partial)
    has_new_total = bool(newly_contributed_constraints_total)
    has_new_partial = bool(newly_contributed_constraints_partial)
    has_gain = bool(gained_resource_ids)
    phi_leq_t_val = float(phi_leq_t or 0.0)
    delta_phi_t_val = float(delta_phi_t or 0.0)

    mode = BI_DECISION_MODE
    if mode == "strict_threshold":
        decision = "ALLOW" if sat and has_ceval and (phi >= threshold) else "BLOCK"
        reason = "strict_threshold"
        return decision, reason

    if mode == "cumulative_progressive":
        decision = "ALLOW" if sat and (has_gain or has_new_total or has_new_partial or delta_phi_t_val > 0.0 or phi_leq_t_val > 0.0) else "BLOCK"
        reason = "cumulative_progressive"
        return decision, reason

    # Default: formal_contributive
    decision = "ALLOW" if sat and has_gain and (has_total or has_partial or has_new_total or has_new_partial) else "BLOCK"
    reason = "formal_contributive_session_marginal"
    return decision, reason

# -------------------------
# API endpoints
# -------------------------

@app.get("/health")
def health():
    # objective loading status from backend
    try:
        from mcad.objectives import list_objectives
        objs = list_objectives()
        obj_loaded = bool(objs)
        obj_count = len(objs)
        obj_err = None
    except Exception as e:
        obj_loaded = False
        obj_count = 0
        obj_err = str(e)

    return {
        "ok": True,
        "service": "mcad-api",
        "threshold_default": THRESHOLD_DEFAULT,
        "bi_decision_mode": BI_DECISION_MODE,
        "objectives": {
            "loaded": obj_loaded,
            "count": obj_count,
            "yaml_primary": os.getenv("MCAD_OBJECTIVES_YAML"),
            "yaml_fallback": os.getenv("MCAD_OBJECTIVES_FALLBACK_YAML"),
            "error": obj_err,
        },
    }



# -------------------------
# Import validation helpers (V8.7)
# -------------------------

def _all_objective_ids(include_imported: bool = True) -> set[str]:
    ids: set[str] = set()
    try:
        from mcad.objectives import list_objectives  # type: ignore
        for obj in list_objectives():
            data = _objective_to_dict(obj)
            oid = str(data.get("id") or "").strip()
            if oid:
                ids.add(oid)
    except Exception:
        pass
    if include_imported:
        for raw in _load_imported_objectives_raw():
            oid = str(raw.get("id") or raw.get("objective_id") or "").strip()
            if oid:
                ids.add(oid)
    return ids


def _validate_one_objective_schema(obj: Any, *, existing_ids: Optional[set[str]] = None, check_unique: bool = True) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    normalized: Optional[Dict[str, Any]] = None

    if not isinstance(obj, dict):
        return {"ok": False, "errors": ["objective must be a JSON object"], "warnings": [], "objective": None, "objective_id": None}

    oid = str(obj.get("id") or obj.get("objective_id") or "").strip()
    if not oid:
        errors.append("id is required and must be non-empty")
    elif check_unique and existing_ids and oid in existing_ids:
        warnings.append(f"objective id already exists and will be replaced on import: {oid}")

    name = str(obj.get("name") or "").strip()
    if not name:
        errors.append("name is required and must be non-empty")

    if not str(obj.get("dw_id") or obj.get("dw") or "").strip():
        warnings.append("dw_id is missing; default/runtime value may be used")

    if not str(obj.get("cube") or "").strip():
        warnings.append("cube is missing; parser/runtime cube detection may be used")

    constraints = obj.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        errors.append("constraints must be a non-empty list")
        constraints = []

    seen_constraints: set[str] = set()
    seen_vnodes: set[str] = set()
    for i, c in enumerate(constraints):
        prefix = f"constraints[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{prefix} must be an object")
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            errors.append(f"{prefix}.id is required")
        elif cid in seen_constraints:
            errors.append(f"{prefix}.id duplicates {cid}")
        else:
            seen_constraints.add(cid)

        if not str(c.get("label") or c.get("description") or "").strip():
            warnings.append(f"{prefix}.label is missing; id will be used as label")

        if not str(c.get("measure") or c.get("metric") or "").strip():
            errors.append(f"{prefix}.measure is required")

        grain = c.get("grain", c.get("group_by"))
        if isinstance(grain, str):
            if not grain.strip():
                errors.append(f"{prefix}.grain must not be empty")
        elif isinstance(grain, list):
            if not [x for x in grain if str(x).strip()]:
                errors.append(f"{prefix}.grain list must not be empty")
        else:
            errors.append(f"{prefix}.grain must be a string or a non-empty list")

        slicers = c.get("slicers")
        if slicers is None:
            errors.append(f"{prefix}.slicers is required")
        elif not isinstance(slicers, dict):
            errors.append(f"{prefix}.slicers must be an object/dictionary")

        vnode = str(c.get("virtual_node") or c.get("virtual_node_id") or c.get("node_id") or "").strip()
        vnodes = c.get("virtual_nodes")
        if not vnode and not isinstance(vnodes, list):
            errors.append(f"{prefix}.virtual_node is required")
        if vnode:
            if vnode in seen_vnodes:
                errors.append(f"{prefix}.virtual_node duplicates {vnode}")
            else:
                seen_vnodes.add(vnode)
        if isinstance(vnodes, list):
            for j, vn in enumerate(vnodes):
                vid = ""
                if isinstance(vn, dict):
                    vid = str(vn.get("id") or vn.get("node_id") or "").strip()
                else:
                    vid = str(vn or "").strip()
                if vid:
                    if vid in seen_vnodes:
                        errors.append(f"{prefix}.virtual_nodes[{j}] duplicates {vid}")
                    else:
                        seen_vnodes.add(vid)

    if not errors:
        try:
            normalized = _normalize_imported_objective(obj)
        except Exception as e:
            errors.append(f"normalization failed: {e}")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "objective": normalized, "objective_id": oid}


def _validate_objectives_payload(payload: Any, *, check_unique: bool = True) -> Dict[str, Any]:
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("objectives"), list):
        raw_items = payload.get("objectives") or []
    elif isinstance(payload, dict):
        raw_items = [payload]
    else:
        return {"ok": False, "status": "refused", "kind": "objectives", "errors": ["JSON must be an objective object, a list, or {'objectives': [...]}"], "warnings": [], "items": []}

    existing = _all_objective_ids(include_imported=True)
    payload_ids: set[str] = set()
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    normalized: List[Dict[str, Any]] = []

    for idx, raw in enumerate(raw_items):
        rep = _validate_one_objective_schema(raw, existing_ids=existing, check_unique=check_unique)
        oid = str(rep.get("objective_id") or f"#{idx}")
        if oid in payload_ids:
            rep.setdefault("errors", []).append(f"objective id duplicated inside payload: {oid}")
            rep["ok"] = False
        if oid:
            payload_ids.add(oid)
        for e in rep.get("errors", []):
            errors.append(f"{oid}: {e}")
        for w in rep.get("warnings", []):
            warnings.append(f"{oid}: {w}")
        if rep.get("objective"):
            normalized.append(rep["objective"])
        items.append({"id": oid, "ok": rep.get("ok", False), "errors": rep.get("errors", []), "warnings": rep.get("warnings", [])})

    status = "accepted" if not errors and not warnings else ("accepted_with_warnings" if not errors else "refused")
    return {
        "ok": not errors,
        "status": status,
        "kind": "objectives",
        "accepted_count": len(normalized) if not errors else 0,
        "errors": errors,
        "warnings": warnings,
        "items": items,
        "objectives": normalized,
    }

@app.get("/objectives")
def objectives_api():
    _register_imported_objectives()
    objs = []
    seen = set()
    try:
        from mcad.objectives import list_objectives
        static_objs = list_objectives()
    except Exception:
        static_objs = []
    for obj in static_objs:
        data = _objective_to_dict(obj)
        oid = str(data.get("id") or "")
        constraints = data.get("constraints") or []
        if oid:
            seen.add(oid)
        objs.append({
            "id": oid,
            "name": data.get("name") or oid,
            "label": data.get("name") or oid,
            "description": data.get("description", ""),
            "constraint_count": len(constraints),
            "constraints": constraints,
            "source": "static",
        })
    # Always merge persisted JSON-imported objectives, even if mcad.objectives
    # cannot dynamically register them in the current runtime.
    for raw in _load_imported_objectives_raw():
        data = _normalize_imported_objective(raw)
        oid = str(data.get("id") or "")
        if not oid or oid in seen:
            continue
        constraints = data.get("constraints") or []
        objs.append({
            "id": oid,
            "name": data.get("name") or oid,
            "label": data.get("name") or oid,
            "description": data.get("description", ""),
            "constraint_count": len(constraints),
            "constraints": constraints,
            "source": "imported_json",
        })
        seen.add(oid)
    return {"ok": True, "items": objs}


@app.get("/objectives/{objective_id}")
def objective_detail_api(objective_id: str):
    _register_imported_objectives()
    obj = _objective_lookup(objective_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"Unknown objective_id={objective_id}")
    data = _objective_to_dict(obj)
    data["contracts"] = _constraint_contracts_for_objective(objective_id)
    return {"ok": True, "objective": data}


@app.post("/objectives/validate")
def validate_objectives_api(payload: Any = Body(...)):
    return _validate_objectives_payload(payload, check_unique=True)


@app.post("/objectives/import")
def import_objectives_api(payload: Any = Body(...)):
    report = _validate_objectives_payload(payload, check_unique=True)
    if not report.get("ok"):
        raise HTTPException(status_code=400, detail=report)
    normalized = report.get("objectives") or []
    existing = _load_imported_objectives_raw()
    by_id = {str(x.get("id")): x for x in existing if x.get("id")}
    for obj in normalized:
        by_id[str(obj["id"])] = obj
    _write_imported_objectives_raw(list(by_id.values()))
    _register_imported_objectives()
    return {
        "ok": True,
        "status": report.get("status", "accepted"),
        "imported_count": len(normalized),
        "objective_ids": [x["id"] for x in normalized],
        "warnings": report.get("warnings", []),
        "report": report,
    }


@app.delete("/objectives/{objective_id}")
def delete_imported_objective_api(objective_id: str):
    oid = str(objective_id or "").strip()
    if not oid:
        raise HTTPException(status_code=400, detail="objective_id is required")
    existing = _load_imported_objectives_raw()
    remaining = [x for x in existing if str(x.get("id")) != oid]
    if len(remaining) == len(existing):
        raise HTTPException(status_code=404, detail=f"Imported objective not found or not removable: {oid}")
    _write_imported_objectives_raw(remaining)
    return {"ok": True, "deleted_objective_id": oid, "remaining_imported_count": len(remaining)}



# MCAD_V948T_SESSION_COVERAGE_PROJECTION_FIX
def _session_covered_constraints_for_api(state: Any) -> List[str]:
    # Read-only union of:
    # 1. SessionState.covered_constraints;
    # 2. effective history contribution fields;
    # 3. in-memory contract graph cumulative coverage.
    # The result is ordered by the objective contract and is never inferred
    # from phi alone.
    session_id = str(getattr(state, "session_id", "") or "")
    objective_id = str(getattr(state, "objective_id", "") or "")
    required = _required_constraints_for_objective(objective_id)

    covered = set(
        _contract_as_list(
            getattr(state, "covered_constraints", [])
        )
    )

    try:
        history = list(getattr(state, "history", []) or [])
    except Exception:
        history = []

    for entry in history:
        for field in (
            "covered_constraints",
            "newly_contributed_constraints_total",
            "calculable_constraints_total",
        ):
            covered.update(
                _contract_as_list(
                    _get_history_attr(entry, field, [])
                )
            )

    graph_state = _GRAPH_SESSION_STATE.get(session_id) or {}
    covered.update(
        _contract_as_list(
            graph_state.get(
                "cumulative_covered_constraints"
            )
        )
    )

    if required:
        return [
            constraint_id
            for constraint_id in required
            if constraint_id in covered
        ]

    return sorted(covered)


@app.get("/sessions")
def sessions_api():
    from mcad.session_store import SESSION_STORE
    items = []
    for s in SESSION_STORE.list_sessions():
        items.append({
            "session_id": s.session_id,
            "objective_id": s.objective_id,
            "dw_id": s.dw_id,
            "status": s.status,
            "step_index": s.step_index,
            "phi_leq_t": s.phi_leq_t,
            "phi_weighted_leq_t": getattr(s, "phi_weighted_leq_t", 0.0),
            "covered_constraints": _session_covered_constraints_for_api(s),
            "history_length": len(list(getattr(s, "history", []) or [])),
        })
    return {"ok": True, "items": items}


@app.post("/sessions/create")
def create_session_api(payload: CreateSessionRequest):
    from mcad.session_store import SESSION_STORE
    obj = _objective_lookup(str(payload.objective_id))
    if obj is None:
        raise HTTPException(status_code=404, detail=f"Unknown objective_id={payload.objective_id}")
    data = _objective_to_dict(obj)
    objective_id = str(data.get("id") or payload.objective_id)
    state = SESSION_STORE.create_session(objective_id=objective_id, dw_id=str(payload.dw_id or "foodmart"))
    # A rebuilt Docker/API process may restart session ids from S_0001 while the
    # DATA_DIR archive still contains old S_0001 evidence. A newly created
    # logical session must therefore start with an empty effective trace.
    _clear_session_effective_trace(str(state.session_id), reset_session_store=False)
    return {
        "ok": True,
        "session": {
            "session_id": state.session_id,
            "objective_id": state.objective_id,
            "dw_id": state.dw_id,
            "status": state.status,
            "step_index": state.step_index,
            "phi_leq_t": state.phi_leq_t,
            "history_length": len(list(getattr(state, "history", []) or [])),
        },
    }


# MCAD_UI_V948_SESSION_DELETE_API
def _v948_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _v948_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_v948_json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        return _v948_json_safe(value.model_dump())
    if hasattr(value, "dict"):
        return _v948_json_safe(value.dict())
    if hasattr(value, "__dict__"):
        return _v948_json_safe(vars(value))
    return str(value)


def _v948_session_backup_dir(session_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = DATA_DIR / "deleted_sessions" / f"{session_id}_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    return target


def _v948_prune_session_from_json(value: Any, session_id: str) -> tuple[Any, int]:
    removed = 0
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict) and str(item.get("session_id") or "") == session_id:
                removed += 1
                continue
            cleaned, child_removed = _v948_prune_session_from_json(item, session_id)
            removed += child_removed
            out.append(cleaned)
        return out, removed

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key) == session_id:
                removed += 1
                continue
            cleaned, child_removed = _v948_prune_session_from_json(item, session_id)
            removed += child_removed
            out[key] = cleaned
        return out, removed

    return value, removed


def _v948_prune_session_from_json_file(path: Path, session_id: str) -> Dict[str, Any]:
    result = {"path": str(path), "exists": path.exists(), "removed": 0, "updated": False}
    if not path.exists():
        return result
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        cleaned, removed = _v948_prune_session_from_json(raw, session_id)
        if removed:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(_json_safe(cleaned), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(path)
            result.update({"removed": removed, "updated": True})
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _v948_json_contains_session(value: Any, session_id: str) -> bool:
    if isinstance(value, dict):
        if str(value.get("session_id") or "") == session_id:
            return True
        return any(_v948_json_contains_session(v, session_id) for v in value.values())
    if isinstance(value, list):
        return any(_v948_json_contains_session(v, session_id) for v in value)
    return False


def _v948_prune_session_from_jsonl(path: Path, session_id: str) -> Dict[str, Any]:
    result = {"path": str(path), "exists": path.exists(), "removed": 0, "kept": 0, "updated": False}
    if not path.exists():
        return result

    kept_lines = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        keep = True
        try:
            item = json.loads(line)
            keep = not _v948_json_contains_session(item, session_id)
        except Exception:
            keep = True
        if keep:
            kept_lines.append(line)
        else:
            result["removed"] += 1

    result["kept"] = len(kept_lines)
    if result["removed"]:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")
        tmp.replace(path)
        result["updated"] = True
    return result


@app.delete("/sessions/{session_id}")
def delete_session_api(session_id: str):
    from mcad.session_store import SESSION_STORE

    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        state = SESSION_STORE.get_session(sid)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown session_id={sid}") from exc

    backup_dir = _v948_session_backup_dir(sid)
    (backup_dir / "session.json").write_text(
        json.dumps(_v948_json_safe(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    decision_data = _load_decision_details_raw()
    (backup_dir / "decision_details.json").write_text(
        json.dumps(_json_safe(decision_data.get(sid, [])), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (backup_dir / "graph_session_state.json").write_text(
        json.dumps(_json_safe(_GRAPH_SESSION_STATE.get(sid) or {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ckg_state_file = DATA_DIR / "ckg_state.json"
    ckg_events_file = DATA_DIR / "ckg_events.jsonl"
    for source in (ckg_state_file, ckg_events_file):
        if source.exists():
            shutil.copy2(source, backup_dir / source.name)

    clear_result = _clear_session_effective_trace(sid, reset_session_store=False)
    ckg_state_result = _v948_prune_session_from_json_file(ckg_state_file, sid)
    ckg_events_result = _v948_prune_session_from_jsonl(ckg_events_file, sid)
    SESSION_STORE.delete_session(sid)

    manifest = {
        "version": "mcad.deleted_session_backup.v1",
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "session_id": sid,
        "backup_dir": str(backup_dir),
        "clear_result": clear_result,
        "ckg_state_result": ckg_state_result,
        "ckg_events_result": ckg_events_result,
    }
    (backup_dir / "deletion_manifest.json").write_text(
        json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "deleted_session_id": sid,
        "backup_dir": str(backup_dir),
        "clear_result": clear_result,
        "ckg_state_result": ckg_state_result,
        "ckg_events_result": ckg_events_result,
    }



@app.get("/sessions/{session_id}")
def get_session_api(session_id: str):
    from mcad.session_store import SESSION_STORE
    try:
        state = SESSION_STORE.get_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown session_id={session_id}") from e
    return {
        "ok": True,
        "session": {
            "session_id": state.session_id,
            "objective_id": state.objective_id,
            "dw_id": state.dw_id,
            "status": state.status,
            "step_index": state.step_index,
            "phi_leq_t": state.phi_leq_t,
            "phi_weighted_leq_t": getattr(state, "phi_weighted_leq_t", 0.0),
            "covered_constraints": _session_covered_constraints_for_api(state),
            "history_length": len(list(getattr(state, "history", []) or [])),
        },
    }




@app.get("/datawarehouses")
def datawarehouses_api():
    from mcad.datawarehouses import list_datawarehouses
    return {"ok": True, "items": list_datawarehouses()}


@app.get("/sessions/{session_id}/history")
def get_session_history_api(session_id: str):
    from mcad.session_store import SESSION_STORE
    try:
        entries = SESSION_STORE.get_history(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown session_id={session_id}") from e
    items = []
    for e in entries:
        d = e.model_dump() if hasattr(e, 'model_dump') else e.dict()
        d['timestamp'] = str(d.get('timestamp'))
        items.append(d)
    items = [_ensure_explainability(x) for x in (items or [])]
    return {"ok": True, "session_id": session_id, "items": items}


# V9.0 — Explainability & Evidence Layer
def _truth(v: Any) -> bool:
    return bool(v is True or v == 1 or str(v).lower() == "true")

def _short_json_value(v: Any, max_len: int = 220) -> str:
    try:
        text = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    except Exception:
        text = str(v)
    text = text.replace('\n', ' ')
    return text if len(text) <= max_len else text[:max_len-1] + '…'

def _decision_detail_core(item: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    dec = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    det = dec.get("details") if isinstance(dec.get("details"), dict) else {}
    summary = item.get("decision_summary") if isinstance(item.get("decision_summary"), dict) else {}
    sat = item.get("sat_checks") if isinstance(item.get("sat_checks"), dict) else (det.get("sat_checks") if isinstance(det.get("sat_checks"), dict) else {})
    sat_ev = item.get("sat_evidence") if isinstance(item.get("sat_evidence"), dict) else (det.get("sat_evidence") if isinstance(det.get("sat_evidence"), dict) else {})
    nvac = item.get("nvac_evidence") if isinstance(item.get("nvac_evidence"), dict) else (det.get("nvac_evidence") if isinstance(det.get("nvac_evidence"), dict) else {})
    qspec = item.get("query_spec") if isinstance(item.get("query_spec"), dict) else (det.get("query_spec") if isinstance(det.get("query_spec"), dict) else {})
    graph = item.get("graph_update") if isinstance(item.get("graph_update"), dict) else (det.get("graph_update") if isinstance(det.get("graph_update"), dict) else {})
    return summary, sat, sat_ev, nvac, {"qspec": qspec, "graph": graph, "details": det, "decision": dec}

def _build_formal_explainability(item: Dict[str, Any]) -> Dict[str, Any]:
    """Create deterministic, article-aligned explanations from archived evidence.

    This is deliberately rule-based: it does not invent facts and can be used as
    the authoritative explanation. An LLM may later rewrite this text, but only
    using this object as grounded input.
    """
    summary, sat, sat_ev, nvac, other = _decision_detail_core(item)
    qspec, graph, det, dec = other["qspec"], other["graph"], other["details"], other["decision"]
    decision = str(summary.get("decision") or dec.get("decision") or "UNKNOWN").upper()
    reason_code = str(summary.get("decision_reason_code") or dec.get("decision_reason_code") or "")
    reason = str(summary.get("decision_reason") or dec.get("decision_reason") or "")
    phi = summary.get("phi", dec.get("phi"))
    dphi = summary.get("delta_phi_t", det.get("delta_phi_t", dec.get("delta_phi")))
    ceval = summary.get("ceval", dec.get("ceval"))
    real = summary.get("real", dec.get("real"))
    formal_sat = bool(summary.get("formal_sat", summary.get("sat", det.get("formal_sat", dec.get("sat")))))

    check_order = ["grain_ok", "agg_ok", "unit_ok", "slc_ok", "time_ok", "nvac_ok"]
    failed = [k for k in check_order if sat.get(k) is False]
    passed = [k for k in check_order if sat.get(k) is True]

    measures = qspec.get("measures") or []
    grain = qspec.get("group_by") or []
    slicers = qspec.get("slicers") or {}
    covered = det.get("covered_constraints") or graph.get("covered_constraints") or det.get("calculable_constraints_total") or []
    realized = det.get("realized_virtual_nodes") or graph.get("realized_virtual_nodes") or []
    observed = det.get("observed_resources") or graph.get("observed_resources") or measures

    formula = {
        "SAT(QP)": bool(formal_sat),
        "Real(QP)": real,
        "Ceval(QP,O)": covered,
        "phi": phi,
        "delta_phi": dphi,
        "decision": decision,
        "reason_code": reason_code,
    }

    steps_fr = []
    steps_en = []
    steps_fr.append(f"QP interroge le cube {qspec.get('cube','—')} avec les mesures {', '.join(map(str, measures)) or '—'}, le grain {', '.join(map(str, grain)) or '—'} et les slicers {_short_json_value(slicers)}.")
    steps_en.append(f"QP queries cube {qspec.get('cube','—')} with measures {', '.join(map(str, measures)) or '—'}, grain {', '.join(map(str, grain)) or '—'} and slicers {_short_json_value(slicers)}.")

    if formal_sat:
        steps_fr.append("SAT(QP)=true : toutes les clauses formelles disponibles sont satisfaites (grain_ok, agg_ok, unit_ok, slc_ok, time_ok, nvac_ok).")
        steps_en.append("SAT(QP)=true: all available formal clauses are satisfied (grain_ok, agg_ok, unit_ok, slc_ok, time_ok, nvac_ok).")
    else:
        f = ", ".join(failed) or "clause inconnue"
        steps_fr.append(f"SAT(QP)=false : la ou les clauses formelles échouées sont {f}.")
        steps_en.append(f"SAT(QP)=false: the failed formal clause(s) are {f}.")

    if nvac:
        method = nvac.get("method", "—")
        known_empty = nvac.get("known_empty")
        estimated = nvac.get("estimated_cells")
        probe = _mcad_v948h_nested_probe_attempted(nvac)
        hconf = nvac.get("hierarchical_conflicts") if isinstance(nvac.get("hierarchical_conflicts"), list) else []
        if sat.get("nvac_ok") is False:
            if hconf:
                conflicts_fr = "; ".join(str(c.get("reason", c)) for c in hconf)
                conflicts_en = conflicts_fr
                steps_fr.append(f"nvac_ok(QP)=false : le sous-espace réel est vide à cause de conflits hiérarchiques connus ({conflicts_fr}).")
                steps_en.append(f"nvac_ok(QP)=false: the real subspace is empty due to known hierarchical conflicts ({conflicts_en}).")
            else:
                steps_fr.append(f"nvac_ok(QP)=false : méthode={method}, known_empty={known_empty}, estimated_cells={estimated}.")
                steps_en.append(f"nvac_ok(QP)=false: method={method}, known_empty={known_empty}, estimated_cells={estimated}.")
        else:
            steps_fr.append(f"nvac_ok(QP)=true : méthode={method}, estimated_cells={estimated}, probe_attempted={probe}.")
            steps_en.append(f"nvac_ok(QP)=true: method={method}, estimated_cells={estimated}, probe_attempted={probe}.")

    if not formal_sat:
        steps_fr.append("Comme SAT(QP)=false, MCAD bloque la requête avant toute contribution décisionnelle.")
        steps_en.append("Since SAT(QP)=false, MCAD blocks the query before any decision contribution is accepted.")
    else:
        if covered:
            steps_fr.append(f"Ceval(QP,O) contient {len(covered)} contrainte(s) calculable(s) : {', '.join(map(str, covered))}.")
            steps_en.append(f"Ceval(QP,O) contains {len(covered)} calculable constraint(s): {', '.join(map(str, covered))}.")
        else:
            steps_fr.append("Ceval(QP,O)=∅ : aucune contrainte de l’objectif actif ne devient calculable par cette requête.")
            steps_en.append("Ceval(QP,O)=∅: no active-objective constraint becomes calculable through this query.")
        if decision == "ALLOW":
            steps_fr.append(f"Décision ALLOW : Δφ={dphi} indique un gain marginal positif pour la session.")
            steps_en.append(f"Decision ALLOW: Δφ={dphi} indicates a positive marginal gain for the session.")
        elif str(reason_code).startswith("BLOCK_REDUNDANT"):
            steps_fr.append("Décision BLOCK : la requête est redondante, les contraintes correspondantes ont déjà été couvertes dans la session, donc Δφ=0.")
            steps_en.append("Decision BLOCK: the query is redundant; matching constraints were already covered in the session, so Δφ=0.")
        elif reason_code == "BLOCK_OUT_OF_OBJECTIVE_SCOPE":
            steps_fr.append("Décision BLOCK : le QP est valide mais son contexte est hors périmètre de l’objectif actif, donc Ceval(QP,O)=∅.")
            steps_en.append("Decision BLOCK: QP is valid but its context is outside the active objective scope, so Ceval(QP,O)=∅.")
        elif reason_code == "BLOCK_MEASURE_NOT_TARGETED":
            steps_fr.append("Décision BLOCK : le QP est valide mais la mesure observée n’est ciblée par aucune contrainte de l’objectif actif.")
            steps_en.append("Decision BLOCK: QP is valid but the observed measure is not targeted by any active-objective constraint.")
        elif decision == "BLOCK":
            steps_fr.append(f"Décision BLOCK : {reason or reason_code}.")
            steps_en.append(f"Decision BLOCK: {reason or reason_code}.")

    summary_fr = " ".join(steps_fr[-2:]) if len(steps_fr) >= 2 else (reason or reason_code)
    summary_en = " ".join(steps_en[-2:]) if len(steps_en) >= 2 else (reason or reason_code)

    return _json_safe({
        "version": "mcad.explainability.v1",
        "is_authoritative": True,
        "generator": "deterministic_formal_evidence_renderer",
        "llm_safe": True,
        "summary_fr": summary_fr,
        "summary_en": summary_en,
        "reasoning_steps_fr": steps_fr,
        "reasoning_steps_en": steps_en,
        "formal_mapping": formula,
        "evidence_digest": {
            "passed_sat_clauses": passed,
            "failed_sat_clauses": failed,
            "nvac_method": nvac.get("method") if isinstance(nvac, dict) else None,
            "covered_constraints": covered,
            "realized_virtual_nodes": realized,
            "observed_resources": observed,
        },
        "llm_grounding_payload": {
            "instruction": "Rewrite the explanation without changing facts. Do not alter the decision, SAT clauses, Ceval, phi, delta_phi, or evidence.",
            "facts": formula,
            "sat_checks": sat,
            "nvac_evidence": nvac,
            "query_spec": {"cube": qspec.get("cube"), "measures": measures, "group_by": grain, "slicers": slicers},
        },
    })

def _ensure_explainability(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return item
    if not isinstance(item.get("formal_explanation"), dict):
        item["formal_explanation"] = _build_formal_explainability(item)
    return item


def _history_entry_to_decision_detail(session_id: str, entry: Any) -> Dict[str, Any]:
    """Best-effort fallback detail generated from session history.

    This prevents the UI detail modal from failing with HTTP 500/404 when the
    append-only decision detail archive is missing an older step or was created
    before V8.9. It is intentionally marked as fallback evidence.
    """
    d = _json_safe(entry.model_dump() if hasattr(entry, "model_dump") else (entry.dict() if hasattr(entry, "dict") else dict(entry or {})))
    det = d.get("details") if isinstance(d.get("details"), dict) else {}
    gu = d.get("graph_update") if isinstance(d.get("graph_update"), dict) else (det.get("graph_update") if isinstance(det.get("graph_update"), dict) else {})
    qspec = d.get("query_spec") if isinstance(d.get("query_spec"), dict) else (det.get("query_spec") if isinstance(det.get("query_spec"), dict) else {})
    step = int(d.get("step_index") or 0)
    return {
        "session_id": str(session_id),
        "step_index": step,
        "objective_id": d.get("objective_id") or det.get("objective_id") or gu.get("objective_id"),
        "timestamp": d.get("timestamp"),
        "query_digest": d.get("query_digest"),
        "mdx": d.get("mdx") or qspec.get("mdx") or "",
        "decision_summary": {
            "decision": d.get("decision"),
            "decision_reason_code": d.get("decision_reason_code"),
            "decision_reason": d.get("decision_reason"),
            "phi": d.get("phi"),
            "delta_phi_t": d.get("delta_phi_t"),
            "sat": d.get("sat"),
            "real": d.get("real"),
            "ceval": d.get("ceval"),
        },
        "sat_checks": gu.get("sat_checks") or det.get("sat_checks") or {},
        "sat_evidence": det.get("sat_evidence") or {},
        "nvac_evidence": gu.get("nvac_evidence") or det.get("nvac_evidence") or {},
        "query_spec": qspec,
        "graph_update": gu,
        "decision": d,
        "archive_fallback": True,
        "archive_note": "Generated from session history because the full V8.9 decision_details archive did not contain this step.",
    }


def _fallback_decision_detail_from_history(session_id: str, step_index: int) -> Optional[Dict[str, Any]]:
    try:
        from mcad.session_store import SESSION_STORE
        state = SESSION_STORE.get_session(session_id)
        history = list(getattr(state, "history", []) or [])
    except Exception:
        return None
    for e in history:
        try:
            d = e.model_dump() if hasattr(e, "model_dump") else (e.dict() if hasattr(e, "dict") else dict(e or {}))
            if int(d.get("step_index") or -1) == int(step_index):
                return _history_entry_to_decision_detail(session_id, e)
        except Exception:
            continue
    return None


@app.post("/sessions/{session_id}/trace/reset")
def reset_session_effective_trace_api(session_id: str):
    result = _clear_session_effective_trace(session_id, reset_session_store=True)
    return {"ok": bool(result.get("cleared")), "reset": result}


@app.get("/decision-details/archive/status")
def decision_details_archive_status_api():
    _ensure_decision_details_file()
    data = _load_decision_details_raw()
    total = sum(len(v or []) for v in data.values())
    return {
        "ok": True,
        "path": str(_DECISION_DETAILS_FILE),
        "exists": _DECISION_DETAILS_FILE.exists(),
        "sessions": sorted(data.keys()),
        "total_records": total,
    }


@app.get("/sessions/{session_id}/decision-details")
def get_session_decision_details_api(session_id: str):
    # Do not require SESSION_STORE.get_session() here. The details archive is
    # append-only evidence and can remain useful even if the in-memory session
    # object was reset/reloaded.
    items = _load_decision_details_raw().get(str(session_id), []) or []
    if not items:
        try:
            from mcad.session_store import SESSION_STORE
            state = SESSION_STORE.get_session(session_id)
            items = [_history_entry_to_decision_detail(session_id, e) for e in (getattr(state, "history", []) or [])]
        except Exception:
            items = []
    return {"ok": True, "session_id": session_id, "items": items}



# MCAD_V948H_NESTED_NVAC_PROBE_ATTEMPTED_FIX
def _mcad_v948h_nested_probe_attempted(nvac: Any) -> Any:
    if not isinstance(nvac, dict):
        return None
    value = nvac.get("probe_attempted")
    if value is not None:
        return value
    probe = nvac.get("probe")
    return probe.get("probe_attempted") if isinstance(probe, dict) else None


def _mcad_v948h_refresh_probe_text(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    nvac = item.get("nvac_evidence")
    if not isinstance(nvac, dict):
        graph_update = item.get("graph_update")
        nvac = graph_update.get("nvac_evidence") if isinstance(graph_update, dict) else None
    attempted = _mcad_v948h_nested_probe_attempted(nvac)
    explanation = item.get("formal_explanation")
    if attempted is None or not isinstance(explanation, dict):
        return item
    replacement = "true" if bool(attempted) else "false"
    for key in ("reasoning_steps_fr", "reasoning_steps_en"):
        values = explanation.get(key)
        if isinstance(values, list):
            explanation[key] = [
                value.replace("probe_attempted=None", f"probe_attempted={replacement}")
                if isinstance(value, str) else value
                for value in values
            ]
    item["formal_explanation"] = explanation
    return item


_mcad_v948h_original_ensure_explainability = _ensure_explainability


def _ensure_explainability(item: Dict[str, Any]) -> Dict[str, Any]:
    return _mcad_v948h_refresh_probe_text(
        _mcad_v948h_original_ensure_explainability(item)
    )



@app.get("/sessions/{session_id}/decision-details/{step_index}")
def get_session_decision_detail_api(session_id: str, step_index: int):
    item = _decision_detail_by_step(session_id, step_index)
    if item is None:
        item = _fallback_decision_detail_from_history(session_id, step_index)
    if item is None:
        # Return an explicit placeholder instead of a server error so the UI can
        # explain that the archive is missing for older executions.
        item = {
            "session_id": session_id,
            "step_index": int(step_index),
            "decision_summary": {"decision": "UNKNOWN", "decision_reason_code": "DETAIL_NOT_ARCHIVED", "decision_reason": "No archived detail is available for this step."},
            "sat_checks": {},
            "sat_evidence": {},
            "nvac_evidence": {},
            "query_spec": {},
            "graph_update": {},
            "archive_fallback": True,
            "archive_note": "No decision detail was found. Re-run the query after V8.9.1 to archive full evidence.",
        }
    item = _ensure_explainability(item)
    return {"ok": True, "session_id": session_id, "step_index": step_index, "item": item}


@app.get("/sessions/{session_id}/decision-details/{step_index}/explainability")
def get_session_decision_detail_explainability_api(session_id: str, step_index: int):
    item = _decision_detail_by_step(session_id, step_index)
    if item is None:
        item = _fallback_decision_detail_from_history(session_id, step_index)
    if item is None:
        item = {"session_id": session_id, "step_index": int(step_index), "decision_summary": {"decision": "UNKNOWN", "decision_reason_code": "DETAIL_NOT_ARCHIVED"}, "sat_checks": {}, "nvac_evidence": {}}
    item = _ensure_explainability(item)
    return {"ok": True, "session_id": session_id, "step_index": int(step_index), "formal_explanation": item.get("formal_explanation", {})}


@app.get("/sessions/{session_id}/decision-details/{step_index}/markdown", response_class=PlainTextResponse)
def get_session_decision_detail_markdown_api(session_id: str, step_index: int):
    item = _decision_detail_by_step(session_id, step_index)
    if item is None:
        item = _fallback_decision_detail_from_history(session_id, step_index)
    if item is None:
        item = {
            "session_id": session_id,
            "step_index": int(step_index),
            "decision_summary": {"decision": "UNKNOWN", "decision_reason_code": "DETAIL_NOT_ARCHIVED", "decision_reason": "No archived detail is available for this step."},
            "sat_checks": {},
            "sat_evidence": {},
            "nvac_evidence": {},
            "query_spec": {},
            "graph_update": {},
            "archive_fallback": True,
            "archive_note": "No decision detail was found. Re-run the query after V8.9.2 to archive full evidence.",
        }
    item = _ensure_explainability(item)
    item = _mcad_v948h_refresh_probe_text(item)
    s = item.get("decision_summary") or {}
    q = item.get("query_spec") or {}
    lines = [
        f"# MCAD Decision Detail — {session_id} / step {step_index}",
        "",
        f"- Objective: `{item.get('objective_id','')}`",
        f"- Decision: **{s.get('decision','')}**",
        f"- Reason code: `{s.get('decision_reason_code','')}`",
        f"- Reason: {s.get('decision_reason','')}",
        f"- φ: {s.get('phi', '')}",
        f"- Δφ: {s.get('delta_phi_t', '')}",
        "",
        "## Formal explanation",
        item.get("formal_explanation", {}).get("summary_fr") or "",
        "",
        "### Reasoning steps",
        *[f"- {x}" for x in (item.get("formal_explanation", {}).get("reasoning_steps_fr") or [])],
        "",
        "## Formal SAT(QP)",
        "```json",
        json.dumps(item.get("sat_checks", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## nvac_ok evidence",
        "```json",
        json.dumps(item.get("nvac_evidence", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Query specification",
        "```json",
        json.dumps(q, ensure_ascii=False, indent=2),
        "```",
        "",
        "## MDX",
        "```mdx",
        str(item.get("mdx") or q.get("mdx") or ""),
        "```",
    ]
    return "\n".join(lines)


@app.get("/sessions/{session_id}/graph")
def get_session_graph_api(session_id: str):
    from mcad.session_store import SESSION_STORE
    from mcad.objectives import get_objective
    try:
        state = SESSION_STORE.get_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown session_id={session_id}") from e

    obj = get_objective(state.objective_id)
    history = SESSION_STORE.get_history(session_id)
    total = max(1, len(getattr(obj, 'constraints', []) or []))
    total_nodes = sum(len(getattr(c, 'virtual_nodes', []) or []) for c in (getattr(obj, 'constraints', []) or []))

    total_done = set()
    partial_done = set()
    covered_resources = set()
    covered_constraints = set(getattr(state, 'covered_constraints', []) or [])
    causal = {}

    for entry in history:
        total_done.update(getattr(entry, 'calculable_constraints_total', []) or [])
        partial_done.update(getattr(entry, 'calculable_constraints_partial', []) or [])
        partial_done.update(getattr(entry, 'newly_contributed_constraints_partial', []) or [])
        covered_constraints.update(getattr(entry, 'covered_constraints', []) or [])
        covered_resources.update(getattr(entry, 'gained_resource_ids', []) or [])
        for cid in (getattr(entry, 'newly_contributed_constraints_total', []) or []):
            causal.setdefault(cid, []).append({
                "step_index": getattr(entry, 'step_index', None),
                "decision": getattr(entry, 'decision', None),
                "query_digest": getattr(entry, 'query_digest', None),
                "query_excerpt": (getattr(entry, 'mdx', '') or '')[:160],
            })
        for cid in (getattr(entry, 'newly_contributed_constraints_partial', []) or []):
            causal.setdefault(cid, []).append({
                "step_index": getattr(entry, 'step_index', None),
                "decision": getattr(entry, 'decision', None),
                "query_digest": getattr(entry, 'query_digest', None),
                "query_excerpt": (getattr(entry, 'mdx', '') or '')[:160],
            })

    total_done.update(covered_constraints)

    nodes = [{"id": obj.id, "label": getattr(obj, 'name', obj.id), "kind": "objective", "status": "active"}]
    edges = []

    for c in getattr(obj, 'constraints', []) or []:
        status = 'none'
        if c.id in total_done:
            status = 'total'
        elif c.id in partial_done:
            status = 'partial'
        nodes.append({
            "id": c.id,
            "label": c.id,
            "kind": "constraint",
            "status": status,
            "description": getattr(c, 'description', ''),
            "causal": causal.get(c.id, []),
        })
        edges.append({"source": obj.id, "target": c.id})
        for vn in getattr(c, 'virtual_nodes', []) or []:
            vstatus = 'covered' if vn.id in covered_resources else 'pending'
            nodes.append({
                "id": vn.id,
                "label": vn.id,
                "kind": "resource",
                "status": vstatus,
                "measure": getattr(vn, 'measure', ''),
                "grain": getattr(vn, 'grain', []),
            })
            edges.append({"source": c.id, "target": vn.id})

    allow_count = sum(1 for h in history if str(getattr(h, 'decision', '')).upper() == 'ALLOW')
    block_count = sum(1 for h in history if str(getattr(h, 'decision', '')).upper() == 'BLOCK')
    n = allow_count + block_count
    alignment_score = ((allow_count - block_count) / n) if n else 0.0
    allow_rate = (allow_count / n) if n else 0.0
    total_rate = (len(total_done) / total) if total else 0.0
    partial_rate = (len(partial_done) / total) if total else 0.0
    completion_rate = ((len(total_done) + 0.5 * len(partial_done - total_done)) / total) if total else 0.0

    return {
        "ok": True,
        "session_id": session_id,
        "objective_id": state.objective_id,
        "dw_id": state.dw_id,
        "graph": {"nodes": nodes, "edges": edges},
        "metrics": {
            "constraint_count": total,
            "resource_count": total_nodes,
            "calculability_rate_total": total_rate,
            "calculability_rate_partial": partial_rate,
            "completion_rate": completion_rate,
            "analytic_alignment_score": alignment_score,
            "allow_rate": allow_rate,
            "allow_count": allow_count,
            "block_count": block_count,
        },
    }



# -------------------------
# V9.1 formal session report export
# -------------------------

def _detail_step_index(item: Dict[str, Any]) -> int:
    try:
        return int(item.get("step_index") or 0)
    except Exception:
        return 0


def _detail_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    s = item.get("decision_summary") if isinstance(item.get("decision_summary"), dict) else {}
    d = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    det = d.get("details") if isinstance(d.get("details"), dict) else {}
    return {
        "decision": s.get("decision") or d.get("decision"),
        "reason_code": s.get("decision_reason_code") or d.get("decision_reason_code") or det.get("decision_reason_code"),
        "reason": s.get("decision_reason") or d.get("decision_reason") or det.get("decision_reason"),
        "formal_sat": s.get("formal_sat", det.get("formal_sat", s.get("sat"))),
        "sat": s.get("sat", d.get("sat")),
        "real": s.get("real", d.get("real")),
        "ceval": s.get("ceval", d.get("ceval")),
        "phi": s.get("phi", d.get("phi")),
        "phi_leq_t": det.get("phi_leq_t", s.get("phi_leq_t", s.get("phi"))),
        "delta_phi_t": s.get("delta_phi_t", det.get("delta_phi_t", d.get("delta_phi_t", d.get("dphi")))),
    }



def _scope_id_set(s: Optional[str]) -> set[str]:
    if not s:
        return set()
    return {x.strip() for x in re.split(r"[,;\s]+", str(s)) if x.strip()}


def _detail_scenario_context(it: Dict[str, Any]) -> Dict[str, Any]:
    sc = it.get("scenario") if isinstance(it.get("scenario"), dict) else {}
    dec = it.get("decision") if isinstance(it.get("decision"), dict) else {}
    det = dec.get("details") if isinstance(dec.get("details"), dict) else {}
    sc2 = det.get("scenario") if isinstance(det.get("scenario"), dict) else {}
    merged: Dict[str, Any] = {}
    merged.update(sc2)
    merged.update(sc)
    return merged


def _filter_decision_items_by_scope(items: List[Dict[str, Any]], *, scenario_instance_ids: Optional[str] = None, scenario_ids: Optional[str] = None) -> List[Dict[str, Any]]:
    inst_ids = _scope_id_set(scenario_instance_ids)
    source_ids = _scope_id_set(scenario_ids)
    if not inst_ids and not source_ids:
        return items
    out: List[Dict[str, Any]] = []
    for it in items:
        sc = _detail_scenario_context(it)
        inst = str(sc.get("scenario_instance_id") or "")
        sid = str(sc.get("source_scenario_id") or sc.get("scenario_id") or "")
        if inst_ids and inst in inst_ids:
            out.append(it)
            continue
        if source_ids and sid in source_ids:
            out.append(it)
            continue
    return out


def _effective_detail_summary_values(it: Dict[str, Any], s: Dict[str, Any], gu: Dict[str, Any], fe: Dict[str, Any]) -> Dict[str, Any]:
    sat = bool(s.get("formal_sat", s.get("sat", False)))
    decision = str(s.get("decision") or "").upper()
    covered = list(gu.get("covered_constraints") or (fe.get("evidence_digest") or {}).get("covered_constraints") or [])
    realized = list(gu.get("realized_virtual_nodes") or (fe.get("evidence_digest") or {}).get("realized_virtual_nodes") or [])
    if not sat or decision != "ALLOW":
        # Official reports must not count raw/legacy Real/Ceval/φ when the formal
        # SAT gate blocked the query, or when the query was valid but non-contributive.
        return {"covered": [], "realized": [], "delta_phi_t": 0.0, "phi": 0.0}
    return {
        "covered": covered,
        "realized": realized,
        "delta_phi_t": float(s.get("delta_phi_t") or 0.0),
        "phi": float(s.get("phi") or 0.0),
    }

def _objective_contract_index(objective_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
    return {str(c.get("constraint_id")): dict(c) for c in _constraint_contracts_for_objective(objective_id)}


def _build_session_report(session_id: str, scenario_instance_ids: Optional[str] = None, scenario_ids: Optional[str] = None) -> Dict[str, Any]:
    raw_items = _load_decision_details_raw().get(str(session_id), []) or []
    if not raw_items:
        try:
            from mcad.session_store import SESSION_STORE
            state = SESSION_STORE.get_session(session_id)
            raw_items = [_history_entry_to_decision_detail(session_id, e) for e in (getattr(state, "history", []) or [])]
        except Exception:
            raw_items = []
    items = [_ensure_explainability(dict(x)) for x in raw_items if isinstance(x, dict)]
    items = _filter_decision_items_by_scope(items, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids)
    items.sort(key=_detail_step_index)
    objective_id = ""
    for it in items:
        if it.get("objective_id"):
            objective_id = str(it.get("objective_id"))
            break
    constraints = _objective_contract_index(objective_id)
    required = list(constraints.keys())
    covered_order: List[str] = []
    rows: List[Dict[str, Any]] = []
    for it in items:
        s = _detail_summary(it)
        q = it.get("query_spec") if isinstance(it.get("query_spec"), dict) else {}
        sat = it.get("sat_checks") if isinstance(it.get("sat_checks"), dict) else {}
        nvac = it.get("nvac_evidence") if isinstance(it.get("nvac_evidence"), dict) else {}
        gu = it.get("graph_update") if isinstance(it.get("graph_update"), dict) else {}
        fe = it.get("formal_explanation") if isinstance(it.get("formal_explanation"), dict) else {}
        covered = list(gu.get("covered_constraints") or (fe.get("evidence_digest") or {}).get("covered_constraints") or [])
        realized = list(gu.get("realized_virtual_nodes") or (fe.get("evidence_digest") or {}).get("realized_virtual_nodes") or [])
        eff = _effective_detail_summary_values(it, s, gu, fe)
        covered = eff["covered"]
        realized = eff["realized"]
        failed = [k for k, v in sat.items() if v is False]
        passed = [k for k, v in sat.items() if v is True]
        d = it.get("decision") if isinstance(it.get("decision"), dict) else {}
        det = d.get("details") if isinstance(d.get("details"), dict) else {}
        eval_ms = det.get("eval_ms", it.get("eval_ms"))
        for c in covered:
            if str(c) not in covered_order:
                covered_order.append(str(c))
        rows.append({
            "step_index": _detail_step_index(it),
            "decision": s.get("decision"),
            "reason_code": s.get("reason_code"),
            "reason": s.get("reason"),
            "scenario": _detail_scenario_context(it),
            "formal_sat": bool(s.get("formal_sat")),
            "passed_sat_clauses": passed,
            "failed_sat_clauses": failed,
            "nvac_ok": sat.get("nvac_ok"),
            "nvac_method": nvac.get("method"),
            "nvac_estimated_cells": nvac.get("estimated_cells"),
            "probe_attempted": _mcad_v948h_nested_probe_attempted(nvac),
            "measures": q.get("measures") or [],
            "grain": q.get("group_by") or [],
            "slicers": q.get("slicers") or {},
            "ceval": covered,
            "realized_virtual_nodes": realized,
            "phi": eff["phi"],
            "phi_leq_t": 0.0,
            "delta_phi_t": eff["delta_phi_t"],
            "eval_ms": eval_ms,
            "mdx": it.get("mdx") or q.get("mdx") or "",
            "formal_summary_fr": fe.get("summary_fr") or "",
        })
    # Recompute φ≤t from effective covered constraints rather than trusting raw
    # engine compatibility fields. This avoids contradictions such as φ=1 while
    # covered_constraints=[] when formal SAT blocked earlier queries.
    cumulative: List[str] = []
    total_for_phi = max(1, len(required))
    for r in rows:
        for c in r.get("ceval") or []:
            if str(c) not in cumulative:
                cumulative.append(str(c))
        r["phi_leq_t"] = len([c for c in cumulative if (not required or c in required)]) / total_for_phi if required else 0.0

    allow_count = sum(1 for r in rows if str(r.get("decision") or "").upper() == "ALLOW")
    block_count = sum(1 for r in rows if str(r.get("decision") or "").upper() == "BLOCK")
    reason_counts: Dict[str, int] = {}
    for r in rows:
        rc = str(r.get("reason_code") or "UNKNOWN")
        reason_counts[rc] = reason_counts.get(rc, 0) + 1
    total_constraints = len(required)
    covered_constraints = [c for c in covered_order if (not required or c in required)]
    remaining_constraints = [c for c in required if c not in covered_constraints]
    completion_rate = (len(covered_constraints) / total_constraints) if total_constraints else 0.0
    phi_t = completion_rate
    return _json_safe({
        "version": "mcad.session_report.v1",
        "is_authoritative": True,
        "generator": "deterministic_formal_session_reporter",
        "session_id": session_id,
        "objective_id": objective_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"scenario_instance_ids": sorted(_scope_id_set(scenario_instance_ids)), "scenario_ids": sorted(_scope_id_set(scenario_ids))},
        "objective_constraints": list(constraints.values()),
        "summary": {
            "total_queries": len(rows),
            "allow_count": allow_count,
            "block_count": block_count,
            "reason_code_distribution": reason_counts,
            "total_constraints": total_constraints,
            "covered_constraints": covered_constraints,
            "remaining_constraints": remaining_constraints,
            "completion_rate": completion_rate,
            "phi_t": phi_t,
        },
        "rows": rows,
    })


def _session_report_markdown(report: Dict[str, Any]) -> str:
    s = report.get("summary") or {}
    lines = [
        f"# MCAD Formal Session Report — {report.get('session_id','')}",
        "",
        f"- Objective: `{report.get('objective_id','')}`",
        f"- Generated at: `{report.get('generated_at','')}`",
        f"- Total queries: **{s.get('total_queries',0)}**",
        f"- ALLOW / BLOCK: **{s.get('allow_count',0)} / {s.get('block_count',0)}**",
        f"- Completion rate: **{float(s.get('completion_rate') or 0):.3f}**",
        f"- φ(t): **{s.get('phi_t',0)}**",
        "",
        "## Objective coverage",
        "",
        f"- Covered constraints: `{', '.join(s.get('covered_constraints') or []) or '—'}`",
        f"- Remaining constraints: `{', '.join(s.get('remaining_constraints') or []) or '—'}`",
        "",
        "## Reason-code distribution",
        "",
        "```json",
        json.dumps(s.get("reason_code_distribution") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Formal trace table",
        "",
        "| Step | SAT(QP) | Failed clauses | Ceval(QP,O) | Δφ | Decision | Reason | nvac method |",
        "|---:|:---:|---|---|---:|---|---|---|",
    ]
    for r in report.get("rows") or []:
        failed = ", ".join(r.get("failed_sat_clauses") or []) or "—"
        ceval = ", ".join(r.get("ceval") or []) or "∅"
        lines.append(f"| {r.get('step_index')} | {str(r.get('formal_sat')).lower()} | {failed} | {ceval} | {r.get('delta_phi_t')} | {r.get('decision')} | {r.get('reason_code')} | {r.get('nvac_method') or '—'} |")
    lines += ["", "## Per-query formal explanations", ""]
    for r in report.get("rows") or []:
        lines += [
            f"### Step {r.get('step_index')} — {r.get('decision')} / {r.get('reason_code')}",
            "",
            r.get("formal_summary_fr") or f"SAT(QP)={r.get('formal_sat')}, Ceval={r.get('ceval') or []}, Δφ={r.get('delta_phi_t')}.",
            "",
            f"- Measures: `{', '.join(map(str,r.get('measures') or [])) or '—'}`",
            f"- Grain: `{', '.join(map(str,r.get('grain') or [])) or '—'}`",
            f"- Slicers: `{json.dumps(r.get('slicers') or {}, ensure_ascii=False)}`",
            f"- nvac_ok: `{r.get('nvac_ok')}` via `{r.get('nvac_method') or '—'}`",
            "",
            "```mdx",
            str(r.get("mdx") or ""),
            "```",
            "",
        ]
    return "\n".join(lines)


def _session_report_csv(report: Dict[str, Any]) -> str:
    import csv, io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["step","formal_sat","failed_sat_clauses","nvac_ok","nvac_method","ceval","delta_phi","decision","reason_code","measures","grain","slicers","mdx"])
    for r in report.get("rows") or []:
        writer.writerow([
            r.get("step_index"),
            r.get("formal_sat"),
            ";".join(r.get("failed_sat_clauses") or []),
            r.get("nvac_ok"),
            r.get("nvac_method"),
            ";".join(r.get("ceval") or []),
            r.get("delta_phi_t"),
            r.get("decision"),
            r.get("reason_code"),
            ";".join(map(str, r.get("measures") or [])),
            ";".join(map(str, r.get("grain") or [])),
            json.dumps(r.get("slicers") or {}, ensure_ascii=False),
            str(r.get("mdx") or "").replace("\r", " ").replace("\n", " "),
        ])
    return out.getvalue()


@app.get("/sessions/{session_id}/report")
def get_session_report_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return {"ok": True, "report": _build_session_report(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids)}


@app.get("/sessions/{session_id}/report/markdown", response_class=PlainTextResponse)
def get_session_report_markdown_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return _session_report_markdown(_build_session_report(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids))


@app.get("/sessions/{session_id}/report/csv", response_class=PlainTextResponse)
def get_session_report_csv_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return _session_report_csv(_build_session_report(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids))


# -------------------------
# V9.2 experimental metrics dashboard/export
# -------------------------

def _pct(n: float, d: float) -> float:
    try:
        return (float(n) / float(d)) if float(d) else 0.0
    except Exception:
        return 0.0


def _count_values(values: List[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in values:
        key = str(v if v is not None and v != "" else "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_session_metrics(session_id: str, scenario_instance_ids: Optional[str] = None, scenario_ids: Optional[str] = None) -> Dict[str, Any]:
    report = _build_session_report(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids)
    rows = list(report.get("rows") or [])
    summary = dict(report.get("summary") or {})
    total = len(rows)
    allow_count = int(summary.get("allow_count") or 0)
    block_count = int(summary.get("block_count") or 0)
    sat_true = sum(1 for r in rows if bool(r.get("formal_sat")) is True)
    sat_false = sum(1 for r in rows if bool(r.get("formal_sat")) is False)
    failed_clause_counts: Dict[str, int] = {}
    for r in rows:
        failed = r.get("failed_sat_clauses") or []
        if not failed:
            failed_clause_counts["none"] = failed_clause_counts.get("none", 0) + 1
        for c in failed:
            failed_clause_counts[str(c)] = failed_clause_counts.get(str(c), 0) + 1
    nvac_method_counts = _count_values([r.get("nvac_method") for r in rows])
    decision_counts = {"ALLOW": allow_count, "BLOCK": block_count}
    reason_code_distribution = dict(summary.get("reason_code_distribution") or {})
    phi_series = []
    delta_phi_series = []
    for r in rows:
        step = r.get("step_index")
        phi_series.append({"step": step, "phi_leq_t": r.get("phi_leq_t"), "decision": r.get("decision"), "reason_code": r.get("reason_code")})
        delta_phi_series.append({"step": step, "delta_phi": r.get("delta_phi_t"), "decision": r.get("decision"), "reason_code": r.get("reason_code")})
    # Compute eval times from archived details, preserving report step order when possible.
    raw_items = _load_decision_details_raw().get(str(session_id), []) or []
    row_steps = {int(r.get("step_index") or -1) for r in rows}
    eval_times = []
    for it in raw_items:
        try:
            if row_steps and int(it.get("step_index") or -1) not in row_steps:
                continue
            d = it.get("decision") if isinstance(it.get("decision"), dict) else {}
            det = d.get("details") if isinstance(d.get("details"), dict) else {}
            if det.get("eval_ms") is not None:
                eval_times.append(float(det.get("eval_ms")))
        except Exception:
            pass
    avg_eval_ms = (sum(eval_times) / len(eval_times)) if eval_times else 0.0
    max_eval_ms = max(eval_times) if eval_times else 0.0
    min_eval_ms = min(eval_times) if eval_times else 0.0
    trace = []
    for r in rows:
        trace.append({
            "step": r.get("step_index"),
            "formal_sat": bool(r.get("formal_sat")),
            "failed_sat_clauses": r.get("failed_sat_clauses") or [],
            "nvac_ok": r.get("nvac_ok"),
            "nvac_method": r.get("nvac_method"),
            "ceval": r.get("ceval") or [],
            "delta_phi": r.get("delta_phi_t"),
            "phi_leq_t": r.get("phi_leq_t"),
            "decision": r.get("decision"),
            "reason_code": r.get("reason_code"),
            "measures": r.get("measures") or [],
            "grain": r.get("grain") or [],
            "slicers": r.get("slicers") or {},
        })
    metrics = {
        "version": "mcad.experimental_metrics.v1",
        "is_authoritative": True,
        "generator": "deterministic_session_metrics_aggregator",
        "session_id": session_id,
        "objective_id": report.get("objective_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_queries": total,
            "allow_count": allow_count,
            "block_count": block_count,
            "allow_rate": _pct(allow_count, total),
            "block_rate": _pct(block_count, total),
            "sat_true_count": sat_true,
            "sat_false_count": sat_false,
            "sat_success_rate": _pct(sat_true, total),
            "sat_failure_rate": _pct(sat_false, total),
            "final_phi": summary.get("phi_t"),
            "completion_rate": summary.get("completion_rate"),
            "total_constraints": summary.get("total_constraints"),
            "covered_constraints_count": len(summary.get("covered_constraints") or []),
            "remaining_constraints_count": len(summary.get("remaining_constraints") or []),
            "avg_eval_ms": avg_eval_ms,
            "min_eval_ms": min_eval_ms,
            "max_eval_ms": max_eval_ms,
        },
        "distributions": {
            "decision": decision_counts,
            "reason_code": reason_code_distribution,
            "failed_sat_clause": failed_clause_counts,
            "nvac_method": nvac_method_counts,
        },
        "coverage": {
            "covered_constraints": summary.get("covered_constraints") or [],
            "remaining_constraints": summary.get("remaining_constraints") or [],
        },
        "series": {
            "phi_leq_t": phi_series,
            "delta_phi": delta_phi_series,
        },
        "trace": trace,
    }
    return _json_safe(metrics)


def _session_metrics_markdown(metrics: Dict[str, Any]) -> str:
    s = metrics.get("summary") or {}
    d = metrics.get("distributions") or {}
    cov = metrics.get("coverage") or {}
    lines = [
        f"# MCAD Experimental Metrics — {metrics.get('session_id','')}",
        "",
        f"- Objective: `{metrics.get('objective_id','')}`",
        f"- Generated at: `{metrics.get('generated_at','')}`",
        f"- Total queries: **{s.get('total_queries',0)}**",
        f"- ALLOW / BLOCK: **{s.get('allow_count',0)} / {s.get('block_count',0)}**",
        f"- SAT true / false: **{s.get('sat_true_count',0)} / {s.get('sat_false_count',0)}**",
        f"- Final φ(t): **{s.get('final_phi',0)}**",
        f"- Completion rate: **{float(s.get('completion_rate') or 0):.3f}**",
        f"- Average eval time: **{float(s.get('avg_eval_ms') or 0):.2f} ms**",
        "",
        "## Distributions",
        "",
        "### Decision distribution",
        "```json",
        json.dumps(d.get("decision") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "### Reason-code distribution",
        "```json",
        json.dumps(d.get("reason_code") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "### Failed SAT-clause distribution",
        "```json",
        json.dumps(d.get("failed_sat_clause") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "### nvac method distribution",
        "```json",
        json.dumps(d.get("nvac_method") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Objective coverage",
        "",
        f"- Covered constraints: `{', '.join(cov.get('covered_constraints') or []) or '—'}`",
        f"- Remaining constraints: `{', '.join(cov.get('remaining_constraints') or []) or '—'}`",
        "",
        "## Query-by-query metrics trace",
        "",
        "| Step | SAT | Failed clauses | nvac | Ceval | Δφ | φ≤t | Decision | Reason |",
        "|---:|:---:|---|---|---|---:|---:|---|---|",
    ]
    for r in metrics.get("trace") or []:
        failed = ", ".join(r.get("failed_sat_clauses") or []) or "—"
        ceval = ", ".join(r.get("ceval") or []) or "∅"
        lines.append(f"| {r.get('step')} | {str(r.get('formal_sat')).lower()} | {failed} | {r.get('nvac_method') or '—'} | {ceval} | {r.get('delta_phi')} | {r.get('phi_leq_t')} | {r.get('decision')} | {r.get('reason_code')} |")
    return "\n".join(lines)


def _session_metrics_csv(metrics: Dict[str, Any]) -> str:
    import csv, io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["step","formal_sat","failed_sat_clauses","nvac_ok","nvac_method","ceval","delta_phi","phi_leq_t","decision","reason_code","measures","grain","slicers"])
    for r in metrics.get("trace") or []:
        writer.writerow([
            r.get("step"),
            r.get("formal_sat"),
            ";".join(r.get("failed_sat_clauses") or []),
            r.get("nvac_ok"),
            r.get("nvac_method"),
            ";".join(r.get("ceval") or []),
            r.get("delta_phi"),
            r.get("phi_leq_t"),
            r.get("decision"),
            r.get("reason_code"),
            ";".join(map(str, r.get("measures") or [])),
            ";".join(map(str, r.get("grain") or [])),
            json.dumps(r.get("slicers") or {}, ensure_ascii=False),
        ])
    return out.getvalue()


@app.get("/sessions/{session_id}/metrics")
def get_session_metrics_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return {"ok": True, "metrics": _build_session_metrics(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids)}


@app.get("/sessions/{session_id}/metrics/markdown", response_class=PlainTextResponse)
def get_session_metrics_markdown_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return _session_metrics_markdown(_build_session_metrics(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids))


@app.get("/sessions/{session_id}/metrics/csv", response_class=PlainTextResponse)
def get_session_metrics_csv_api(session_id: str, scenario_instance_ids: Optional[str] = Query(None), scenario_ids: Optional[str] = Query(None)):
    return _session_metrics_csv(_build_session_metrics(session_id, scenario_instance_ids=scenario_instance_ids, scenario_ids=scenario_ids))


@app.get("/sessions/{session_id}/graph/state")
def get_session_graph_state_api(session_id: str):
    from mcad.session_store import SESSION_STORE
    try:
        state = SESSION_STORE.get_session(session_id)
        objective_id = state.objective_id
        dw_id = state.dw_id
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown session_id={session_id}") from e
    public = _public_graph_session_state(session_id, objective_id)
    public["dw_id"] = dw_id
    public["graph"] = _graph_from_contract_state(public)
    public["nodes"] = public["graph"]["nodes"]
    public["edges"] = public["graph"]["edges"]
    public["graph_update"] = {
        "contract_version": "mcad.graph_update.v1",
        "objective_id": public.get("objective_id"),
        "session_id": public.get("session_id"),
        "required_constraints": public.get("required_constraints", []),
        "cumulative_covered_constraints": public.get("cumulative_covered_constraints", []),
        "pending_constraints": public.get("pending_constraints", []),
        "cumulative_realized_virtual_nodes": public.get("cumulative_realized_virtual_nodes", []),
        "objective_state": public.get("objective_state"),
        "session_phi": public.get("session_phi"),
    }
    # Metrics must be consistent with the UI history. Contract-first ALLOW
    # entries may have reason codes such as ALLOW_NEW_TOTAL; count them as
    # ALLOW even when older compatibility fields are incomplete.
    try:
        history = SESSION_STORE.get_history(session_id)
    except Exception:
        history = []

    def _hist_decision_kind(entry: Any) -> str:
        decision = str(getattr(entry, "decision", "") or "").upper()
        reason = str(getattr(entry, "decision_reason_code", "") or "").upper()
        if decision == "ALLOW" or reason.startswith("ALLOW"):
            return "ALLOW"
        return "BLOCK"

    allow_count = sum(1 for h in history if _hist_decision_kind(h) == "ALLOW")
    block_count = sum(1 for h in history if _hist_decision_kind(h) == "BLOCK")
    n_decisions = allow_count + block_count
    allow_rate = (allow_count / n_decisions) if n_decisions else 0.0
    alignment_score = public["session_phi"]

    public["metrics"] = {
        "constraint_count": len(public.get("required_constraints", [])),
        "resource_count": len(public.get("cumulative_realized_virtual_nodes", [])),
        "completion_rate": public["session_phi"],
        "calculability_rate_total": 1.0 if public["objective_state"] == "covered" else 0.0,
        "calculability_rate_partial": public["session_phi"] if public["objective_state"] == "partial" else 0.0,
        "analytic_alignment_score": alignment_score,
        "allow_rate": allow_rate,
        "allow_count": allow_count,
        "block_count": block_count,
    }
    return public

@app.post("/eval", response_model=EvalResponse)
def eval_query(payload: EvalRequest):
    t0 = time.time()

    _register_imported_objectives()
    import mcad.engine as engine  # type: ignore
    from mcad.models import EvaluateWithObjectiveAndSessionRequest  # type: ignore
    from mcad.objectives import list_objectives, get_objective  # type: ignore
    from mcad.session_store import SESSION_STORE  # type: ignore

    # 1) deterministic mdx -> richer query_spec
    query_spec = build_query_spec(payload.mdx, cube_override=payload.cube)
    cube = query_spec.get("cube")
    measures = list(query_spec.get("measures") or [])

    qp = {
        "mdx": payload.mdx,
        "query_spec": query_spec,
        "catalog": payload.catalog,
        "cube": cube,
        "measures": measures,
        "user_id": payload.user_id,
    }

    context = payload.context if isinstance(payload.context, dict) else {}
    eval_dw_id = str(context.get("dw_id") or context.get("selected_dw_id") or context.get("requested_dw_id") or "")
    if eval_dw_id:
        query_spec["dw_id"] = eval_dw_id
        query_spec["dataset"] = context.get("dataset") or query_spec.get("dataset")
        qp["dw_id"] = eval_dw_id
    scenario_context = {
        "scenario_instance_id": context.get("scenario_instance_id"),
        "source_scenario_id": context.get("source_scenario_id") or context.get("scenario_id"),
        "scenario_name": context.get("scenario_name"),
        "scenario_source": context.get("scenario_source"),
        "scenario_query_index": context.get("scenario_query_index"),
        "scenario_query_id": context.get("scenario_query_id") or context.get("query_id"),
        "execution_mode": context.get("execution_mode") or context.get("query_mode"),
    }
    scenario_context = {k: v for k, v in scenario_context.items() if v is not None and v != ""}

    # 2) objective_id resolution
    objective_id = payload.objective_id
    if payload.context and isinstance(payload.context, dict):
        objective_id = objective_id or payload.context.get("objective_id")
    if not objective_id:
        objective_id = os.getenv("MCAD_OBJECTIVE_ID_DEFAULT")
    if not objective_id:
        objs = list_objectives()
        if not objs:
            raise HTTPException(status_code=500, detail="No objectives loaded (check MCAD_OBJECTIVES_YAML / MCAD_OBJECTIVES_FALLBACK_YAML).")
        objective_id = objs[0].id

    try:
        obj = get_objective(str(objective_id))
    except Exception:
        obj = _objective_lookup(str(objective_id))
    if obj is None:
        raise HTTPException(status_code=400, detail=f"Unknown objective_id={objective_id}")
    obj_data = _objective_to_dict(obj)
    objective_id = str(obj_data.get("id") or getattr(obj, "id", objective_id))

    # 3) session_id (provided or stable default)
    session_id = payload.session_id or os.getenv("MCAD_SESSION_ID_DEFAULT", "S_0001")
    try:
        state = SESSION_STORE.get_session(session_id)
    except KeyError:
        dw_id = (payload.context or {}).get("dw_id") if isinstance(payload.context, dict) else None
        dw_id = str(dw_id or os.getenv("MCAD_DW_ID_DEFAULT", "foodmart"))
        if hasattr(SESSION_STORE, 'create_session_with_id'):
            state = SESSION_STORE.create_session_with_id(session_id=session_id, objective_id=objective_id, dw_id=dw_id)
        else:
            state = SESSION_STORE.create_session(objective_id=objective_id, dw_id=dw_id)
            session_id = state.session_id
    session_id = str(getattr(state, 'session_id', session_id))
    # 4) real engine call
    req = EvaluateWithObjectiveAndSessionRequest(session_id=session_id, objective_id=objective_id, qp=qp)
    try:
        out = engine.evaluate_with_objective_and_session(req)
    except Exception as e:
        response_obj = EvalResponse(
            decision="BLOCK",
            phi=0.0,
            threshold=float(getattr(obj, "threshold", getattr(obj, "theta", THRESHOLD_DEFAULT)) or THRESHOLD_DEFAULT),
            sat=0.0,
            real=0.0,
            ceval=0.0,
            explain=f"MCAD eval error: {e}",
            decision_reason_code="EVAL_ERROR",
            decision_reason=str(e),
            is_redundant=False,
            has_marginal_gain=False,
            details={"objective_id": objective_id, "session_id": session_id, "query_spec": query_spec, "eval_error": str(e)},
        )

    # 5) ratios for compatibility
    constraints = getattr(obj, "constraints", []) or []
    total_constraints = max(1, len(constraints))
    total_nv = sum(len(getattr(c, "virtual_nodes", []) or []) for c in constraints)

    real_ratio = (len(out.real_node_ids) / max(1, total_nv)) if total_nv > 0 else (1.0 if len(out.real_node_ids) > 0 else 0.0)
    ceval_ratio = len(out.calculable_constraints) / total_constraints

    # 6) decision rule
    threshold = float(getattr(obj, "threshold", getattr(obj, "theta", THRESHOLD_DEFAULT)) or THRESHOLD_DEFAULT)
    phi = float(out.phi)
    phi_leq_t = getattr(out, "phi_leq_t", None)
    delta_phi_t = getattr(out, "delta_phi_t", None)

    decision, decision_policy = _resolve_bi_decision(
        sat=bool(out.sat),
        phi=phi,
        threshold=threshold,
        calculable_constraints=list(out.calculable_constraints),
        calculable_constraints_total=list(getattr(out, "calculable_constraints_total", []) or []),
        calculable_constraints_partial=list(getattr(out, "calculable_constraints_partial", []) or []),
        newly_contributed_constraints_total=list(getattr(out, "newly_contributed_constraints_total", []) or []),
        newly_contributed_constraints_partial=list(getattr(out, "newly_contributed_constraints_partial", []) or []),
        gained_resource_ids=list(getattr(out, "gained_resource_ids", []) or []),
        phi_leq_t=phi_leq_t,
        delta_phi_t=delta_phi_t,
    )

    # Strict graph contract: graph coverage is based on QP features, not query ids.
    # For imported/generalized objectives, the formal engine can still reject
    # syntactically valid BI-direct MDX because its legacy SAT parser does not
    # know every Mondrian hierarchy spelling. The objective contract is therefore
    # used as the authoritative contribution layer: if the QP matches a pending
    # constraint of the active objective, the decision becomes ALLOW.
    contract_update = _infer_objective_constraint_from_qp_features({"query_spec": query_spec, "mdx": payload.mdx, "objective_id": objective_id}, objective_id=objective_id)
    strict_covered_constraints = list(contract_update.get("covered_constraints") or [])
    strict_realized_virtual_nodes = list(contract_update.get("realized_virtual_nodes") or [])
    strict_observed_resources = list(contract_update.get("observed_resources") or [])

    formal_sat_eval = _evaluate_sat_formal_clauses(
        query_spec,
        objective_id,
        payload.mdx,
        nvac_probe=_mcad_api_call_nvac_probe,
    )
    formal_sat = bool(formal_sat_eval.get("sat"))

    contract_required = _required_constraints_for_objective(objective_id)
    contract_state = _GRAPH_SESSION_STATE.get(str(session_id or ""), {}) if session_id else {}
    contract_already_covered = set(_contract_as_list(contract_state.get("cumulative_covered_constraints")))
    contract_incoming = set(strict_covered_constraints)
    contract_new = sorted(c for c in contract_incoming if c not in contract_already_covered and c in contract_required)
    contract_after = sorted((contract_already_covered | set(contract_new)) & set(contract_required), key=lambda c: contract_required.index(c) if c in contract_required else 999)
    contract_phi_after = (len(contract_after) / len(contract_required)) if contract_required else 0.0
    contract_delta_phi = (len(contract_new) / len(contract_required)) if contract_required else 0.0

    override_reason_code = str(getattr(out, "decision_reason_code", "") or "")
    override_reason = str(getattr(out, "decision_reason", "") or "")
    override_is_redundant = bool(getattr(out, "is_redundant", False))
    override_has_marginal_gain = bool(getattr(out, "has_marginal_gain", False))

    if not formal_sat:
        # Formal SAT(QP) is the gatekeeper: even a syntactically contract-like
        # query is blocked when grain_ok/agg_ok/unit_ok/slc_ok/time_ok/nvac_ok
        # is false. This makes the implementation faithful to the manuscript.
        decision = "BLOCK"
        decision_policy = f"{decision_policy}+formal_sat_gate"
        override_reason_code = str(formal_sat_eval.get("block_reason_code") or "BLOCK_SAT_FALSE")
        override_reason = str(formal_sat_eval.get("block_reason") or "Formal SAT(QP) failed.")
        override_is_redundant = False
        override_has_marginal_gain = False
        strict_covered_constraints = []
        strict_realized_virtual_nodes = []
        contract_new = []
        contract_after = sorted(contract_already_covered & set(contract_required), key=lambda c: contract_required.index(c) if c in contract_required else 999)
        # Effective public contribution metrics must be zero for the current query
        # when SAT is false. Keep legacy_engine_* only as debug evidence.
        phi = float(len(contract_after) / len(contract_required)) if contract_required else 0.0
        phi_leq_t = float(phi)
        delta_phi_t = 0.0
        ceval_ratio = 0.0
        real_ratio = 0.0
    elif contract_incoming and contract_new:
        # Contract-contributive query: accept it when formal SAT(QP) is true,
        # even if the legacy engine SAT parser returned false.
        decision = "ALLOW"
        decision_policy = f"{decision_policy}+contract_contributive"
        override_reason_code = "ALLOW_NEW_TOTAL"
        override_reason = "Contract-driven contribution: the QP matches pending constraint(s) of the active objective."
        override_is_redundant = False
        override_has_marginal_gain = True
        phi = float(contract_phi_after)
        phi_leq_t = float(contract_phi_after)
        delta_phi_t = float(contract_delta_phi)
        ceval_ratio = float(len(contract_incoming) / len(contract_required)) if contract_required else float(ceval_ratio)
        real_ratio = float(len(strict_realized_virtual_nodes) / max(1, len(contract_required)))
    elif contract_incoming and not contract_new:
        # Contract matches, but all matched constraints are already covered.
        decision = "BLOCK"
        decision_policy = f"{decision_policy}+contract_redundant"
        override_reason_code = "BLOCK_REDUNDANT_DPHI_ZERO"
        override_reason = "Contract-driven redundancy: matched constraint(s) already covered in the current session."
        override_is_redundant = True
        override_has_marginal_gain = False
        phi = float(len(contract_already_covered & set(contract_required)) / len(contract_required)) if contract_required else float(phi)
        phi_leq_t = float(phi)
        delta_phi_t = 0.0
        strict_covered_constraints = []
        strict_realized_virtual_nodes = []
    elif decision == "BLOCK":
        # Non-contributive BLOCK: keep observations as provenance only.
        strict_covered_constraints = []
        strict_realized_virtual_nodes = []

    effective_step_index = getattr(out, "step_index", None)
    eval_graph_update = {
        "contract_version": "mcad.graph_update.v1",
        "decision": decision,
        "objective_id": objective_id,
        "session_id": session_id,
        "step_index": effective_step_index,
        "covered_constraints": strict_covered_constraints,
        "realized_virtual_nodes": strict_realized_virtual_nodes,
        "observed_resources": strict_observed_resources,
        "sat_checks": formal_sat_eval.get("checks", {}),
        "nvac_evidence": formal_sat_eval.get("evidence", {}).get("nvac_ok", {}),
    }

    synced_step_index = _sync_effective_decision_to_history(
        SESSION_STORE,
        state,
        objective_id=objective_id,
        mdx=payload.mdx,
        decision=decision,
        reason_code=override_reason_code,
        reason=override_reason,
        phi=float(phi or 0.0),
        delta_phi_t=float(delta_phi_t or 0.0),
        covered_constraints=strict_covered_constraints,
        realized_virtual_nodes=strict_realized_virtual_nodes,
        query_digest=mdx_fingerprint(payload.mdx),
    )
    if synced_step_index is not None:
        effective_step_index = synced_step_index
        eval_graph_update["step_index"] = synced_step_index

    print(
        f"ENGINE=real policy={decision_policy} formal_sat={formal_sat} legacy_engine_sat={bool(out.sat)} "
        f"phi={phi:.6f} phi_leq_t={float(phi_leq_t or 0.0):.6f} "
        f"threshold={threshold:.6f} decision={decision}"
    )

    explain = (
        f"ENGINE=real mode={decision_policy} formal_sat={formal_sat} legacy_engine_sat={bool(out.sat)} "
        f"phi={phi:.3f} theta={threshold:.3f} "
        f"Ceval={len(out.calculable_constraints)}/{total_constraints} "
        f"RealNV={len(out.real_node_ids)}/{max(1,total_nv)} "
        f"phi_leq_t={float(phi_leq_t or 0.0):.3f} "
        f"dphi={float(delta_phi_t or 0.0):.3f} => {decision}"
    )

    def _dump(x):
        if hasattr(x, "model_dump"):
            return x.model_dump()
        if hasattr(x, "dict"):
            return x.dict()
        return x


    response_obj = EvalResponse(
        decision=decision,
        phi=phi,
        threshold=threshold,
        sat=1.0 if formal_sat else 0.0,
        real=float(real_ratio),
        ceval=float(ceval_ratio),
        explain=explain,
        decision_reason_code=override_reason_code,
        decision_reason=override_reason,
        is_redundant=override_is_redundant,
        has_marginal_gain=override_has_marginal_gain,
        details={
            "engine": "evaluate_with_objective_and_session(payload)",
            "decision_policy": decision_policy,
            "decision_reason_code": override_reason_code,
            "decision_reason": override_reason,
            "is_redundant": override_is_redundant,
            "has_marginal_gain": override_has_marginal_gain,
            "gained_resource_ids_count": int(len(strict_realized_virtual_nodes)),
            "threshold_used_for_ranking": threshold,
            "objective_id": objective_id,
            "session_id": session_id,
            "step_index": effective_step_index,
            "phi_weighted": float(getattr(out, "phi_weighted", 0.0)),
            "phi_leq_t": phi_leq_t,
            "delta_phi_t": delta_phi_t,
            "real_node_ids": list(out.real_node_ids),
            "calculable_constraints": strict_covered_constraints,
            "calculable_constraints_total": strict_covered_constraints,
            "calculable_constraints_partial": [],
            "newly_contributed_constraints_total": strict_covered_constraints if decision == "ALLOW" else [],
            "newly_contributed_constraints_partial": [],
            "gained_resource_ids": strict_realized_virtual_nodes if decision == "ALLOW" else [],
            "covered_constraints": strict_covered_constraints,
            "realized_virtual_nodes": strict_realized_virtual_nodes,
            "observed_resources": strict_observed_resources,
            "graph_update": eval_graph_update,
            "scenario": scenario_context,
            "formal_sat": bool(formal_sat),
            "formal_sat_source": "formal_sat_eval.checks",
            "sat_checks": formal_sat_eval.get("checks", {}),
            "sat_evidence": formal_sat_eval.get("evidence", {}),
            "nvac_ok": bool(formal_sat_eval.get("checks", {}).get("nvac_ok", False)),
            "nvac_evidence": formal_sat_eval.get("evidence", {}).get("nvac_ok", {}),
            "legacy_engine_sat_debug": bool(out.sat),
            "legacy_engine_clauses_debug": [_dump(c) for c in (getattr(out, "clauses", []) or [])],
            "query_spec": query_spec,
            "eval_ms": int((time.time() - t0) * 1000),
        },
    )

    _record_decision_detail(session_id, {
        "session_id": session_id,
        "objective_id": objective_id,
        "step_index": effective_step_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_digest": mdx_fingerprint(payload.mdx),
        "mdx": payload.mdx,
        "cube": query_spec.get("cube"),
        "measures": query_spec.get("measures", []),
        "group_by": query_spec.get("group_by", []),
        "slicers": query_spec.get("slicers", {}),
        "decision": response_obj.model_dump() if hasattr(response_obj, "model_dump") else response_obj.dict(),
        "scenario": scenario_context,
        "decision_summary": {
            "decision": decision,
            "decision_reason_code": override_reason_code,
            "decision_reason": override_reason,
            "phi": float(phi or 0.0),
            "delta_phi_t": float(delta_phi_t or 0.0),
            "sat": bool(formal_sat),
            "formal_sat": bool(formal_sat),
            "formal_sat_source": "formal_sat_eval.checks",
            "legacy_engine_sat_debug": bool(out.sat),
            "real": float(real_ratio),
            "ceval": float(ceval_ratio),
        },
        "sat_checks": formal_sat_eval.get("checks", {}),
        "sat_evidence": formal_sat_eval.get("evidence", {}),
        "nvac_evidence": formal_sat_eval.get("evidence", {}).get("nvac_ok", {}),
        "query_spec": query_spec,
        "graph_update": eval_graph_update,
    })
    return response_obj


@app.post("/ckg/update")
def ckg_update(payload: CkgUpdateRequest):
    """Called by mcad-proxy AFTER execution (ALLOW)."""
    t0 = time.time()

    if extract_useful_result_summary is not None and not payload.useful_result_summary:
        try:
            payload.useful_result_summary = extract_useful_result_summary(
                payload.raw_result_summary or {},
                payload.query_spec or {},
                payload.decision,
                payload.calculable_constraints or [],
                payload.covered_constraints or [],
            )
        except Exception as e:
            payload.useful_result_summary = {
                'kind': 'useful_result_summary',
                'error': str(e),
                'materialization_level': 'summary_only_v1',
            }

    graph_update = _infer_objective_constraint_from_qp_features({"query_spec": payload.query_spec or {}, "mdx": payload.mdx, "objective_id": payload.objective_id}, objective_id=payload.objective_id)
    graph_update.update({
        "decision": str(payload.decision or "").upper() or "ALLOW",
        "objective_id": payload.objective_id,
        "session_id": payload.session_id,
        "step_index": payload.step_index,
    })
    if graph_update["decision"] == "BLOCK":
        graph_update["covered_constraints"] = []
        graph_update["realized_virtual_nodes"] = []
    if payload.session_id:
        _merge_graph_session_state(str(payload.session_id), graph_update)
        payload.covered_constraints = list(graph_update.get("covered_constraints") or [])

    backend_res = update_ckg_backend(payload)

    try:
        if NEO4J_URI and NEO4J_PASSWORD:
            adapter_res = update_ckg_neo4j(payload)
        else:
            adapter_res = update_ckg_file(payload)
        ok = True
    except Exception as e:
        ok = False
        adapter_res = {"error": str(e)}

    return {
        "ok": ok,
        "adapter_ms": int((time.time() - t0) * 1000),
        "backend": backend_res,
        "result": adapter_res,
    }


@app.get("/ckg/events", response_class=PlainTextResponse)
def ckg_events(tail: int = Query(50, ge=1, le=500)):
    """Return last N JSONL events."""
    p = DATA_DIR / "ckg_events.jsonl"
    if not p.exists():
        return "ckg_events.jsonl ABSENT"
    lines = p.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-tail:]) + "\n"


@app.get("/ckg/state/summary")
def ckg_state_summary():
    """Quick summary of /app/data/ckg_state.json snapshot."""
    p = DATA_DIR / "ckg_state.json"
    if not p.exists():
        return {"ok": False, "error": "ckg_state.json ABSENT"}
    d = json.loads(p.read_text(encoding="utf-8"))
    nodes = d.get("nodes", {}) or {}
    edges = d.get("edges", {}) or {}

    def _is_exec(k: str) -> bool:
        return k.startswith("exec:") or k.startswith("exec::")
    def _is_qp(k: str) -> bool:
        return k.startswith("qp:") or k.startswith("qp::")

    exec_count = sum(1 for k in nodes.keys() if _is_exec(str(k)))
    qp_count = sum(1 for k in nodes.keys() if _is_qp(str(k)))
    return {"ok": True, "nodes": len(nodes), "edges": len(edges), "exec_count": exec_count, "qp_count": qp_count}
