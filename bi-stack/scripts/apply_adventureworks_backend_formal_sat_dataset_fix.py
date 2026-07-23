#!/usr/bin/env python3
"""MCAD V9.5.2d — AdventureWorks backend formal SAT dataset fix.

V9.5.2c showed that patching only bi-stack/mcad-api/app.py is insufficient in
current deployments because the mcad-api container mounts ../backend at
/app/backend and imports mcad.formal_sat from that canonical backend module.
This in-place patch therefore updates backend/mcad/formal_sat.py directly and
keeps the API/probe payload dataset-aware.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def insert_dataset_helpers(src: str) -> tuple[str, bool]:
    if "def _mcad_known_members_for_features" in src and "_MCAD_DATASET_KNOWN_MEMBERS" in src:
        return src, False
    marker = "}\n\n_FOODMART_STORE_CITY_STATE"
    if marker not in src:
        raise RuntimeError("Could not locate end of _FOODMART_KNOWN_MEMBERS block in backend/mcad/formal_sat.py")
    helpers = '''}

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

_FOODMART_STORE_CITY_STATE'''
    return src.replace(marker, helpers, 1), True


def patch_features_extractor(src: str) -> tuple[str, bool]:
    changed = False
    if '"dw_id": qspec.get("dw_id")' not in src:
        old = '        "mdx": mdx,\n    }'
        new = '        "mdx": mdx,\n        "dw_id": qspec.get("dw_id") or raw.get("dw_id"),\n        "dataset": qspec.get("dataset") or raw.get("dataset"),\n        "cube": qspec.get("cube") or raw.get("cube"),\n    }'
        if old in src:
            src = src.replace(old, new, 1)
            changed = True
    return src, changed


def patch_slc_ok(src: str) -> tuple[str, bool]:
    changed = False
    if 'known_members = _mcad_known_members_for_features(features)' not in src:
        old = '    normalized_by_level: Dict[str, str] = {}\n    for level, value in slicers.items():'
        new = '    normalized_by_level: Dict[str, str] = {}\n    known_members = _mcad_known_members_for_features(features)\n    for level, value in slicers.items():'
        if old in src:
            src = src.replace(old, new, 1)
            changed = True
    if 'known = known_members.get(level_s)' not in src:
        src2 = src.replace('        known = _FOODMART_KNOWN_MEMBERS.get(level_s)\n', '        known = known_members.get(level_s)\n', 1)
        if src2 != src:
            src = src2
            changed = True
    if '"member_dictionary": _mcad_dataset_key_from_features(features)' not in src:
        old = '    return (not errors), {"recognized_slicers": slicers, "errors": errors}\n'
        new = '    return (not errors), {"recognized_slicers": slicers, "errors": errors, "member_dictionary": _mcad_dataset_key_from_features(features)}\n'
        if old in src:
            src = src.replace(old, new, 1)
            changed = True
    return src, changed


def patch_nvac_ok(src: str) -> tuple[str, bool]:
    changed = False
    if 'known_members = _mcad_known_members_for_features(features)' not in src[src.find('def _sat_check_nvac_ok'):src.find('def evaluate_sat_formal_clauses')]:
        old = '    unknown_members: list[dict[str, str]] = []\n    for level, value in recognized_members:'
        new = '    unknown_members: list[dict[str, str]] = []\n    known_members = _mcad_known_members_for_features(features)\n    for level, value in recognized_members:'
        if old in src:
            src = src.replace(old, new, 1)
            changed = True
    if 'known = known_members.get(level)' not in src:
        src2 = src.replace('        known = _FOODMART_KNOWN_MEMBERS.get(level)\n', '        known = known_members.get(level)\n', 1)
        if src2 != src:
            src = src2
            changed = True
    # Make the FoodMart static indexes explicitly FoodMart-only. AdventureWorks goes to the bounded NVAC probe.
    if 'if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_EMPTY_COMBINATIONS:' not in src:
        src = src.replace(
            '    if state and category and (state, category) in _FOODMART_EMPTY_COMBINATIONS:\n',
            '    if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_EMPTY_COMBINATIONS:\n',
            1,
        )
        changed = True
    if 'if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_NONEMPTY_COMBINATIONS' not in src:
        src = src.replace(
            '    if state and category and (state, category) in _FOODMART_NONEMPTY_COMBINATIONS and _nvac_static_nonempty_index_covers_full_slicer_tuple(slicers):\n',
            '    if _mcad_is_foodmart_features(features) and state and category and (state, category) in _FOODMART_NONEMPTY_COMBINATIONS and _nvac_static_nonempty_index_covers_full_slicer_tuple(slicers):\n',
            1,
        )
        changed = True
    if 'if _mcad_is_foodmart_features(features) and state and category_on_axis:' not in src:
        src = src.replace(
            '    if state and category_on_axis:\n',
            '    if _mcad_is_foodmart_features(features) and state and category_on_axis:\n',
            1,
        )
        changed = True
    return src, changed


def patch_probe_features(src: str) -> tuple[str, bool]:
    changed = False
    if '"dw_id": features.get("dw_id")' not in src:
        old = '            "measures": _contract_as_list(features.get("measures")),\n            "reason": "static_evidence_uncertain",\n        }'
        new = '            "measures": _contract_as_list(features.get("measures")),\n            "dw_id": features.get("dw_id"),\n            "dataset": features.get("dataset"),\n            "reason": "static_evidence_uncertain",\n        }'
        if old in src:
            src = src.replace(old, new, 1)
            changed = True
    if '"dw_id": features.get("dw_id")' not in src.split('def _mcad_api_nvac_probe_cache_key')[0]:
        # Do nothing: cache function may not exist in backend formal_sat.py.
        pass
    return src, changed


def patch_evaluate_entry(src: str) -> tuple[str, bool]:
    changed = False
    marker = '    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})\n'
    inject = (
        '    features["dw_id"] = query_spec.get("dw_id") or features.get("dw_id") or ""\n'
        '    features["dataset"] = query_spec.get("dataset") or features.get("dataset") or ""\n'
    )
    if marker in src and inject.strip() not in src:
        src = src.replace(marker, marker + inject, 1)
        changed = True
    return src, changed


def patch_backend_formal_sat(path: Path) -> list[str]:
    src = read(path)
    changes: list[str] = []
    for label, fn in [
        ("backend:dataset_helpers", insert_dataset_helpers),
        ("backend:feature_extractor_dw_dataset", patch_features_extractor),
        ("backend:dataset_aware_slc_ok", patch_slc_ok),
        ("backend:dataset_aware_nvac_members", patch_nvac_ok),
        ("backend:nvac_probe_features_dw_dataset", patch_probe_features),
        ("backend:evaluate_entry_dw_dataset", patch_evaluate_entry),
    ]:
        src, did = fn(src)
        if did:
            changes.append(label)
    write(path, src)
    return changes


def patch_api_app(path: Path) -> list[str]:
    if not path.exists():
        return []
    src = read(path)
    changes: list[str] = []
    # Ensure /eval copies active DW context into query_spec before calling backend formal SAT.
    context_line = '    context = payload.context if isinstance(payload.context, dict) else {}\n'
    dw_block = (
        '    eval_dw_id = str(context.get("dw_id") or context.get("selected_dw_id") or context.get("requested_dw_id") or "")\n'
        '    if eval_dw_id:\n'
        '        query_spec["dw_id"] = eval_dw_id\n'
        '        query_spec["dataset"] = context.get("dataset") or query_spec.get("dataset")\n'
        '        qp["dw_id"] = eval_dw_id\n'
    )
    if context_line in src and 'query_spec["dw_id"] = eval_dw_id' not in src:
        src = src.replace(context_line, context_line + dw_block, 1)
        changes.append("api:eval_context_to_query_spec")
    # Ensure the integration-side NVAC HTTP probe forwards dw_id/dataset to the proxy.
    if '"dw_id": str(features.get("dw_id") or "")' not in src:
        old = '        "measures": features.get("measures") or [],\n        "reason": features.get("reason") or "static_evidence_uncertain",\n    }'
        new = '        "measures": features.get("measures") or [],\n        "dw_id": str(features.get("dw_id") or ""),\n        "dataset": str(features.get("dataset") or ""),\n        "reason": features.get("reason") or "static_evidence_uncertain",\n    }'
        if old in src:
            src = src.replace(old, new, 1)
            changes.append("api:nvac_payload_dw_dataset")
        else:
            old2 = '        "measures": features.get("measures") or [],\n        "reason": reason,\n    }'
            new2 = '        "measures": features.get("measures") or [],\n        "dw_id": str(features.get("dw_id") or ""),\n        "dataset": str(features.get("dataset") or ""),\n        "reason": reason,\n    }'
            if old2 in src:
                src = src.replace(old2, new2, 1)
                changes.append("api:nvac_payload_dw_dataset")
    # Cache key should not mix FoodMart and AdventureWorks probes.
    if '"dw_id": features.get("dw_id")' not in src and 'def _mcad_api_nvac_probe_cache_key' in src:
        old = '        "measures": features.get("measures") or [],\n    }'
        new = '        "measures": features.get("measures") or [],\n        "dw_id": features.get("dw_id"),\n        "dataset": features.get("dataset"),\n    }'
        if old in src:
            src = src.replace(old, new, 1)
            changes.append("api:nvac_cache_dw_dataset")
    write(path, src)
    return changes


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    backend = repo / "backend" / "mcad" / "formal_sat.py"
    api = repo / "bi-stack" / "mcad-api" / "app.py"
    if not backend.exists():
        raise SystemExit(f"Missing canonical backend formal SAT file: {backend}")
    changes = []
    changes += patch_backend_formal_sat(backend)
    changes += patch_api_app(api)
    if changes:
        print("Applied V9.5.2d fixes:")
        for ch in changes:
            print(f" - {ch}")
    else:
        print("V9.5.2d fixes already present; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
