"""Canonical formal SAT(QP) layer for MCAD.

This module centralizes the formal BI/OLAP satisfiability checks used by the
interactive BI stack. The proxy and API adapters may supply probes or physical
metadata, but the SAT decision itself is defined here in the backend package.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import re

try:
    from mcad.mdx_parser import parse_cube as backend_parse_cube  # type: ignore
except Exception:  # pragma: no cover
    backend_parse_cube = None


# Optional callback supplied by integration layers such as /bi-stack.
# The backend formal SAT layer must stay pure: it never imports HTTP clients,
# never knows proxy URLs, and never executes a physical BI query by itself.
NvacProbe = Callable[[Dict[str, Any], str], Dict[str, Any]]


_FOODMART_KNOWN_MEMBERS: Dict[str, set[str]] = {
    "Store.Store State": {"CA", "WA", "OR"},
    "Store.Store City": {
        "Portland", "Seattle", "Spokane", "Los Angeles", "San Francisco",
        "Beverly Hills", "Salem",
    },
    "Product.Product Department": {
        "Dairy", "Alcoholic Beverages", "Produce", "Snack Foods",
        "Baked Goods", "Canned Foods", "Frozen Foods", "Meat", "Seafood",
    },
    "Product.Product Category": {
        "Dairy", "Beer and Wine", "Produce", "Snack Foods", "Baking Goods",
        "Bread", "Breakfast Foods", "Canned Foods", "Frozen Foods", "Meat",
        "Seafood", "Carousel", "Starchy Foods", "Eggs", "Canned Products",
    },
}

_MCAD_DATASET_KNOWN_MEMBERS: Dict[str, set[str] | Dict[str, set[str]]] = {
    "FoodMart": _FOODMART_KNOWN_MEMBERS,
    "AdventureWorksDW": {
        "Product.Product Category": {"Bikes", "Accessories", "Clothing", "Components"},
        "Sales Territory.Sales Territory Group": {"Europe", "North America", "Pacific"},
        "Date.Calendar Year": {"2005", "2006", "2007", "2008", "2010", "2011", "2012", "2013", "2014"},
    },
}


def _mcad_dataset_key_from_features(features: Dict[str, Any]) -> str:
    """Infer the logical dataset for formal SAT member validation."""
    blob = " ".join(str(features.get(k) or "") for k in ("dw_id", "dataset", "cube", "catalog", "mdx")).lower()
    if "adventureworks" in blob or "adventure works" in blob or "adventure" in blob:
        return "AdventureWorksDW"
    return "FoodMart"


def _mcad_known_members_for_features(features: Dict[str, Any]) -> Dict[str, set[str]]:
    key = _mcad_dataset_key_from_features(features)
    members = _MCAD_DATASET_KNOWN_MEMBERS.get(key) or _FOODMART_KNOWN_MEMBERS
    return members  # type: ignore[return-value]


def _mcad_is_foodmart_features(features: Dict[str, Any]) -> bool:
    return _mcad_dataset_key_from_features(features) == "FoodMart"

_FOODMART_STORE_CITY_STATE: Dict[str, str] = {
    "Portland": "OR",
    "Seattle": "WA",
    "Spokane": "WA",
    "Salem": "OR",
    "Los Angeles": "CA",
    "San Francisco": "CA",
    "Beverly Hills": "CA",
}

_FOODMART_CATEGORY_DEPARTMENT: Dict[str, str] = {
    "Dairy": "Dairy",
    "Beer and Wine": "Alcoholic Beverages",
    "Produce": "Produce",
    "Snack Foods": "Snack Foods",
    "Baking Goods": "Baked Goods",
    "Bread": "Baked Goods",
    "Breakfast Foods": "Baked Goods",
    "Canned Foods": "Canned Foods",
    "Canned Products": "Canned Foods",
    "Frozen Foods": "Frozen Foods",
    "Meat": "Meat",
    "Seafood": "Seafood",
}

_FOODMART_NONEMPTY_COMBINATIONS: set[tuple[str, str]] = {
    ("CA", "Dairy"), ("CA", "Beer and Wine"), ("CA", "Produce"),
    ("WA", "Dairy"), ("WA", "Beer and Wine"), ("WA", "Produce"),
    ("OR", "Dairy"), ("OR", "Beer and Wine"),
}

_FOODMART_EMPTY_COMBINATIONS: set[tuple[str, str]] = {
    ("OR", "Seafood"),
}

_STOCK_MEASURE_TOKENS = {"stock", "inventory"}
_FORBIDDEN_STOCK_AGG_TOKENS = {"sum", "total"}


def _contract_as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _contract_norm_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _mdx_bracket_parts(chain: str) -> List[str]:
    return [p.strip() for p in re.findall(r"\[([^\]]+)\]", chain or "") if p.strip()]


def _parse_cube(mdx: str) -> Optional[str]:
    if backend_parse_cube is not None:
        try:
            cube = backend_parse_cube(mdx)
            if cube:
                return str(cube)
        except Exception:
            pass
    m = re.search(r"FROM\s+\[([^\]]+)\]", mdx or "", flags=re.I)
    return m.group(1) if m else None


def _contract_extract_qp_features(qp_or_features: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = dict(qp_or_features or {})
    qspec = raw.get("query_spec") if isinstance(raw.get("query_spec"), dict) else raw
    mdx = str(raw.get("mdx") or qspec.get("mdx") or "")
    features = {
        "measures": _contract_as_list(qspec.get("measures")),
        "group_by": _contract_as_list(qspec.get("group_by")),
        "slicers": qspec.get("slicers") if isinstance(qspec.get("slicers"), dict) else {},
        "mdx": mdx,
        "dw_id": qspec.get("dw_id") or raw.get("dw_id"),
        "dataset": qspec.get("dataset") or raw.get("dataset"),
        "cube": qspec.get("cube") or raw.get("cube"),
    }
    if not features["measures"]:
        features["measures"] = re.findall(r"\[Measures\]\.\[([^\]]+)\]", mdx or "", flags=re.I)
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


def _normalize_compact_constraint_to_virtual_node(objective: Dict[str, Any], constraint: Dict[str, Any]) -> Dict[str, Any]:
    grain = constraint.get("grain") or constraint.get("group_by") or []
    if isinstance(grain, str):
        grain_list = [grain]
    elif isinstance(grain, (list, tuple, set)):
        grain_list = [str(x) for x in grain if x is not None]
    else:
        grain_list = []
    return {
        "id": str(constraint.get("virtual_node") or constraint.get("virtual_node_id") or constraint.get("node_id") or f"N_{constraint.get('id', 'c')}") ,
        "fact": str(constraint.get("fact") or objective.get("cube") or "Sales"),
        "grain": grain_list,
        "measure": str(constraint.get("measure") or constraint.get("metric") or ""),
        "aggregator": str(constraint.get("aggregator") or "SUM"),
        "unit": str(constraint.get("unit") or ""),
        "slicers": constraint.get("slicers") if isinstance(constraint.get("slicers"), dict) else {},
        "window_start": constraint.get("window_start"),
        "window_end": constraint.get("window_end"),
    }


def _objective_lookup(objective_id: Optional[str]) -> Optional[Any]:
    if not objective_id:
        return None
    try:
        from mcad.objectives import get_objective  # type: ignore
        return get_objective(str(objective_id))
    except Exception:
        return None


def _constraint_contracts_for_objective(objective_id: Optional[str]) -> List[Dict[str, Any]]:
    obj = _objective_lookup(objective_id)
    if obj is None and str(objective_id or "") == "O_REAL_BEER_WA_MONTH":
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
            vnodes = [_normalize_compact_constraint_to_virtual_node(data, c)]
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


def _feature_contains_value(features: Dict[str, Any], value: Any) -> bool:
    token = _contract_norm_token(value)
    if not token:
        return True
    slicers = features.get("slicers") if isinstance(features.get("slicers"), dict) else {}
    return token in [_contract_norm_token(v) for v in slicers.values()]


def _feature_has_measure(features: Dict[str, Any], required_measure: str) -> bool:
    req = _contract_norm_token(required_measure)
    if not req:
        return False
    measures = {_contract_norm_token(m) for m in _contract_as_list(features.get("measures"))}
    return req in measures or req in _contract_norm_token(features.get("mdx"))


def _feature_has_grain(features: Dict[str, Any], required_grain: List[str]) -> bool:
    if not required_grain:
        return True
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


def _sat_mdx_member_tokens(mdx: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for chain in re.findall(r"\[[^\]]+\](?:\.\[[^\]]+\]){1,}", mdx or ""):
        if chain.lower().startswith("[measures]"):
            continue
        parts = _mdx_bracket_parts(chain)
        if len(parts) >= 3:
            out.append((f"{parts[0]}.{parts[-2]}", parts[-1]))
    return out


def _sat_slicer_pairs(features: Dict[str, Any]) -> Dict[str, str]:
    slicers = features.get("slicers") if isinstance(features.get("slicers"), dict) else {}
    return {str(k): str(v) for k, v in slicers.items() if str(k or "").strip() and str(v or "").strip()}


def _sat_check_grain_ok(features: Dict[str, Any], objective_id: str) -> Tuple[bool, Dict[str, Any]]:
    group_by = _contract_as_list(features.get("group_by"))
    if not group_by:
        return False, {"recognized_grain": [], "reason": "no ROWS/group_by level recognized"}
    contracts = _constraint_contracts_for_objective(objective_id)
    measures = {_contract_norm_token(m) for m in _contract_as_list(features.get("measures"))}
    candidate_contracts = [c for c in contracts if _contract_norm_token(c.get("measure")) in measures]
    if not candidate_contracts:
        return True, {"recognized_grain": group_by, "reason": "no measure-compatible objective constraint; grain is syntactically recognized"}
    compatible = []
    for c in candidate_contracts:
        req = _contract_as_list(c.get("grain"))
        if _feature_has_grain(features, req):
            compatible.append(str(c.get("constraint_id")))
    return bool(compatible), {"recognized_grain": group_by, "compatible_constraints": compatible}


def _sat_check_agg_ok(features: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    measures = _contract_as_list(features.get("measures"))
    analytics = [str(a).lower() for a in _contract_as_list(features.get("analytics"))]
    measure_blob = " ".join(measures).lower()
    if any(tok in measure_blob for tok in _STOCK_MEASURE_TOKENS):
        bad = [a for a in analytics if any(tok in a for tok in _FORBIDDEN_STOCK_AGG_TOKENS)]
        if bad:
            return False, {"reason": "semi-additive stock/inventory measure cannot be aggregated with SUM over time", "bad_aggregators": bad}
    return True, {"aggregators": analytics or ["implicit cube aggregator"], "reason": "no forbidden aggregation detected"}


def _sat_check_unit_ok(features: Dict[str, Any], objective_id: str) -> Tuple[bool, Dict[str, Any]]:
    q_units = features.get("units") if isinstance(features.get("units"), dict) else {}
    if not q_units:
        return True, {"method": "no explicit unit conflict in QP", "checked_units": {}}
    for c in _constraint_contracts_for_objective(objective_id):
        measure = str(c.get("measure") or "")
        required_unit = str(c.get("unit") or "").strip()
        if required_unit and str(q_units.get(measure, "")).strip() not in ("", required_unit):
            return False, {"reason": "unit mismatch", "measure": measure, "expected_unit": required_unit, "query_unit": q_units.get(measure)}
    return True, {"method": "explicit unit compatibility", "checked_units": q_units}


def _sat_check_slc_ok(features: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    slicers = _sat_slicer_pairs(features)
    errors: list[str] = []
    normalized_by_level: Dict[str, str] = {}
    known_members = _mcad_known_members_for_features(features)
    for level, value in slicers.items():
        level_s = str(level)
        value_s = str(value)
        prev = normalized_by_level.get(level_s)
        if prev is not None and _contract_norm_token(prev) != _contract_norm_token(value_s):
            errors.append(f"contradictory slicer values for {level_s}: {prev} vs {value_s}")
        normalized_by_level[level_s] = value_s
        known = known_members.get(level_s)
        if known is not None and value_s not in known:
            errors.append(f"unknown member {level_s}={value_s}")
    return (not errors), {"recognized_slicers": slicers, "errors": errors, "member_dictionary": _mcad_dataset_key_from_features(features)}


def _sat_check_time_ok(features: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    group_by = _contract_as_list(features.get("group_by"))
    time_grains = [g for g in group_by if str(g).startswith("Time.")]
    windows = {"start": features.get("window_start"), "end": features.get("window_end")}
    if windows.get("start") and windows.get("end") and str(windows["start"]) > str(windows["end"]):
        return False, {"time_grains": time_grains, "window": windows, "reason": "incoherent time window"}
    return True, {"time_grains": time_grains, "window": windows, "reason": "time level/window coherent"}


def _sat_hierarchical_empty_conflicts(slicers: Dict[str, str]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    state = slicers.get("Store.Store State")
    city = slicers.get("Store.Store City")
    if state and city:
        expected_state = _FOODMART_STORE_CITY_STATE.get(city)
        if expected_state and _contract_norm_token(expected_state) != _contract_norm_token(state):
            conflicts.append({
                "dimension": "Store", "child_level": "Store.Store City", "child_value": city,
                "parent_level": "Store.Store State", "parent_value": state,
                "expected_parent_value": expected_state,
                "reason": f"Store city {city} belongs to {expected_state}, not {state}",
            })
    department = slicers.get("Product.Product Department")
    category = slicers.get("Product.Product Category")
    if department and category:
        expected_department = _FOODMART_CATEGORY_DEPARTMENT.get(category)
        if expected_department and _contract_norm_token(expected_department) != _contract_norm_token(department):
            conflicts.append({
                "dimension": "Product", "child_level": "Product.Product Category", "child_value": category,
                "parent_level": "Product.Product Department", "parent_value": department,
                "expected_parent_value": expected_department,
                "reason": f"Product category {category} belongs to {expected_department}, not {department}",
            })
    return conflicts


def _nvac_static_nonempty_index_covers_full_slicer_tuple(slicers: Dict[str, str]) -> bool:
    return set(slicers.keys()).issubset({"Store.Store State", "Product.Product Category"})



def _coerce_nvac_probe_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {"probe_attempted": True, "probe_error": "probe callback returned a non-dict result", "non_empty": None, "count": None}
    out = dict(result)
    out.setdefault("probe_attempted", True)
    if "non_empty" not in out:
        out["non_empty"] = None
    if "count" not in out:
        out["count"] = None
    return out


def _call_optional_nvac_probe(features: Dict[str, Any], mdx: str, nvac_probe: Optional[NvacProbe]) -> Dict[str, Any]:
    if nvac_probe is None:
        return {
            "probe_attempted": False,
            "probe_skipped_reason": "no nvac_probe callback supplied",
            "non_empty": None,
            "count": None,
        }
    try:
        # Pass a defensive copy: integration code may enrich or serialize it.
        probe_features = {
            "mdx": mdx or str(features.get("mdx") or ""),
            "cube": features.get("cube"),
            "slicers": dict(features.get("slicers") or {}) if isinstance(features.get("slicers"), dict) else {},
            "group_by": _contract_as_list(features.get("group_by")),
            "measures": _contract_as_list(features.get("measures")),
            "dw_id": features.get("dw_id"),
            "dataset": features.get("dataset"),
            "reason": "static_evidence_uncertain",
        }
        return _coerce_nvac_probe_result(nvac_probe(probe_features, probe_features["mdx"]))
    except Exception as exc:
        return {
            "probe_attempted": True,
            "probe_error": str(exc),
            "non_empty": None,
            "count": None,
        }

def _sat_check_nvac_ok(features: Dict[str, Any], objective_id: str, nvac_probe: Optional[NvacProbe] = None) -> Tuple[bool, Dict[str, Any]]:
    slicers = _sat_slicer_pairs(features)
    mdx = str(features.get("mdx") or "")
    recognized_members = _sat_mdx_member_tokens(mdx)
    unknown_members: list[dict[str, str]] = []
    known_members = _mcad_known_members_for_features(features)
    for level, value in recognized_members:
        known = known_members.get(level)
        if known is not None and value not in known:
            unknown_members.append({"level": level, "value": value})
    if unknown_members:
        return False, {
            "method": "member_dictionary", "known_empty": True, "estimated_cells": 0,
            "unknown_members": unknown_members, "empty_reason": "unknown member(s) in queried subspace",
            "rule": "unknown_member_blocks_directly",
        }

    state = slicers.get("Store.Store State")
    category = slicers.get("Product.Product Category")
    group_by = _contract_as_list(features.get("group_by"))
    category_on_axis = any(
        _contract_norm_token(g) == _contract_norm_token("Product.Product Category")
        or _contract_norm_token(str(g).split('.')[-1]) == _contract_norm_token("Product Category")
        for g in group_by
    )

    hierarchy_conflicts = _sat_hierarchical_empty_conflicts(slicers)
    if hierarchy_conflicts:
        return False, {
            "method": "hierarchical_combination_empty_index", "known_empty": True,
            "estimated_cells": 0, "slicers": slicers,
            "hierarchical_conflicts": hierarchy_conflicts,
            "empty_reason": "known empty hierarchical combination in queried subspace",
            "rule": "known_empty_hierarchical_combination_blocks_directly",
        }

    if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_EMPTY_COMBINATIONS:
        return False, {
            "method": "combination_empty_index", "known_empty": True,
            "estimated_cells": 0, "slicers": slicers,
            "empty_reason": f"known empty combination: Store.State={state}, Product.Category={category}",
            "rule": "known_empty_combination_blocks_directly",
        }

    if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_NONEMPTY_COMBINATIONS and _nvac_static_nonempty_index_covers_full_slicer_tuple(slicers):
        return True, {
            "method": "combination_nonempty_index", "known_empty": False,
            "estimated_cells": 12, "slicers": slicers,
            "probe_attempted": False,
            "rule": "known_nonempty_combination_accepts_directly",
        }

    if _mcad_is_foodmart_features(features) and state and category_on_axis:
        known_state = state in _FOODMART_KNOWN_MEMBERS.get("Store.Store State", set())
        if not known_state:
            return False, {"method": "member_dictionary", "known_empty": True, "estimated_cells": 0, "empty_reason": f"unknown state {state}"}
        cats = [c for (s, c) in _FOODMART_NONEMPTY_COMBINATIONS if s == state]
        if cats:
            return True, {
                "method": "axis_combination_index", "known_empty": False,
                "estimated_cells": max(1, 12 * len(set(cats))),
                "axis_level": "Product.Product Category", "slicers": slicers,
                "probe_attempted": False,
            }

    probe = _call_optional_nvac_probe(features, mdx, nvac_probe)
    if probe.get("probe_attempted") and probe.get("non_empty") is not None:
        non_empty = bool(probe.get("non_empty"))
        return non_empty, {
            "method": "hybrid_probe", "known_empty": not non_empty,
            "estimated_cells": int(probe.get("count") or (1 if non_empty else 0)),
            "slicers": slicers, "probe": probe,
            "empty_reason": None if non_empty else "lightweight probe returned count=0 / empty result",
            "rule": "probe_count_drives_nvac_ok",
        }

    return False, {
        "method": "hybrid_probe_unavailable_strict_false", "known_empty": None,
        "estimated_cells": 0, "slicers": slicers, "probe": probe,
        "empty_reason": "static evidence was insufficient and the lightweight probe was unavailable",
        "rule": "unproven_nvac_blocks_to_preserve_formal_sat",
    }


def evaluate_sat_formal_clauses(query_spec: Dict[str, Any], objective_id: str, mdx: str = "", nvac_probe: Optional[NvacProbe] = None) -> Dict[str, Any]:
    """Evaluate SAT(QP) clauses for a query plan and active objective.

    This is the backend-canonical entry point consumed by bi-stack/mcad-api.
    It returns a stable evidence contract used by decision-details, reports,
    and the CKG update layer.

    nvac_probe is an optional integration callback. When static metadata cannot
    prove non-vacuity, integration layers may provide a bounded physical probe.
    The backend module itself remains pure and never performs physical I/O.
    """
    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})
    features["dw_id"] = query_spec.get("dw_id") or features.get("dw_id") or ""
    features["dataset"] = query_spec.get("dataset") or features.get("dataset") or ""
    features["analytics"] = query_spec.get("analytics") or []
    features["cube"] = query_spec.get("cube") or _parse_cube(mdx or query_spec.get("mdx", "")) or "Sales"
    features["window_start"] = query_spec.get("window_start")
    features["window_end"] = query_spec.get("window_end")
    features["units"] = query_spec.get("units") if isinstance(query_spec.get("units"), dict) else {}

    grain_ok, grain_ev = _sat_check_grain_ok(features, objective_id)
    agg_ok, agg_ev = _sat_check_agg_ok(features)
    unit_ok, unit_ev = _sat_check_unit_ok(features, objective_id)
    slc_ok, slc_ev = _sat_check_slc_ok(features)
    time_ok, time_ev = _sat_check_time_ok(features)
    nvac_ok, nvac_ev = _sat_check_nvac_ok(features, objective_id, nvac_probe=nvac_probe)
    checks = {
        "grain_ok": bool(grain_ok),
        "agg_ok": bool(agg_ok),
        "unit_ok": bool(unit_ok),
        "slc_ok": bool(slc_ok),
        "time_ok": bool(time_ok),
        "nvac_ok": bool(nvac_ok),
    }
    sat = all(checks.values())
    first_false = next((k for k, v in checks.items() if not v), None)
    reason_by_clause = {
        "grain_ok": "BLOCK_GRAIN_MISMATCH",
        "agg_ok": "BLOCK_AGG_MISMATCH",
        "unit_ok": "BLOCK_UNIT_MISMATCH",
        "slc_ok": "BLOCK_SLICER_MISMATCH",
        "time_ok": "BLOCK_TIME_MISMATCH",
        "nvac_ok": "BLOCK_EMPTY_SUBSPACE",
    }
    return {
        "sat": sat,
        "checks": checks,
        "block_reason_code": reason_by_clause.get(first_false, "") if not sat else "",
        "block_reason": f"Formal SAT clause failed: {first_false}" if first_false else "All formal SAT clauses are true.",
        "evidence": {
            "grain_ok": grain_ev,
            "agg_ok": agg_ev,
            "unit_ok": unit_ev,
            "slc_ok": slc_ev,
            "time_ok": time_ev,
            "nvac_ok": nvac_ev,
        },
    }


# Backward-compatible alias used by transitional BI-stack versions.
_evaluate_sat_formal_clauses = evaluate_sat_formal_clauses
