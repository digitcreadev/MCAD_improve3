#!/usr/bin/env python3
"""MCAD V9.5.2c — AdventureWorks dataset-aware slicer/SAT fix.

This patch is deliberately in-place and targeted. It fixes the situation where
AdventureWorksDW slicers such as Product.Product Category=Bikes are rejected by
the FoodMart-specific known-member dictionary, causing the ALLOW queries to be
blocked with BLOCK_SLICER_MISMATCH before SQL Server execution.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_block_before(src: str, start_pattern: str, stop_pattern: str, replacement: str, label: str) -> tuple[str, bool]:
    pat = re.compile(start_pattern + r".*?(?=" + stop_pattern + r")", re.M | re.S)
    m = pat.search(src)
    if not m:
        raise RuntimeError(f"Could not find block for {label}")
    return src[:m.start()] + replacement.rstrip() + "\n\n" + src[m.end():], True


def patch_api(api_app: Path) -> list[str]:
    src = read(api_app)
    changed: list[str] = []

    slicer_block = """def _sat_known_members_for_features(features: Dict[str, Any]) -> Dict[str, set[str]]:\n    \"\"\"Return the dataset-specific member dictionary used by slc_ok.\n\n    FoodMart and AdventureWorksDW share generic level names such as\n    Product.Product Category, but they do not share the same member domain.\n    Applying FoodMart's member dictionary to AdventureWorksDW wrongly rejects\n    valid members such as Bikes or Accessories and blocks useful queries with\n    BLOCK_SLICER_MISMATCH. This selector keeps slc_ok dataset-aware.\n    \"\"\"\n    blob_parts = [\n        features.get(\"dw_id\"),\n        features.get(\"dataset\"),\n        features.get(\"cube\"),\n        features.get(\"catalog\"),\n        features.get(\"mdx\"),\n    ]\n    blob = \" \".join(str(x or \"\") for x in blob_parts).lower()\n    if \"adventureworks\" in blob or \"adventure works\" in blob or \"adventure\" in blob:\n        return {\n            \"Product.Product Category\": {\"Bikes\", \"Accessories\", \"Clothing\", \"Components\"},\n            \"Sales Territory.Sales Territory Group\": {\"Europe\", \"North America\", \"Pacific\"},\n            \"Date.Calendar Year\": {\"2005\", \"2006\", \"2007\", \"2008\", \"2010\", \"2011\", \"2012\", \"2013\", \"2014\"},\n        }\n    # Preserve the historical FoodMart guard for the original demo objective.\n    return _FOODMART_KNOWN_MEMBERS\n\n\ndef _sat_check_slc_ok(features: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:\n    slicers = _sat_slicer_pairs(features)\n    errors: list[str] = []\n    normalized_by_level: Dict[str, str] = {}\n    known_members = _sat_known_members_for_features(features)\n    for level, value in slicers.items():\n        level_s = str(level)\n        value_s = str(value)\n        prev = normalized_by_level.get(level_s)\n        if prev is not None and _contract_norm_token(prev) != _contract_norm_token(value_s):\n            errors.append(f\"contradictory slicer values for {level_s}: {prev} vs {value_s}\")\n        normalized_by_level[level_s] = value_s\n        known = known_members.get(level_s)\n        if known is not None and value_s not in known:\n            errors.append(f\"unknown member {level_s}={value_s}\")\n    return (not errors), {\n        \"recognized_slicers\": slicers,\n        \"errors\": errors,\n        \"member_dictionary\": \"AdventureWorksDW\" if known_members is not _FOODMART_KNOWN_MEMBERS else \"FoodMart\",\n    }\n"""
    if "def _sat_known_members_for_features" in src:
        src, _ = replace_block_before(
            src,
            r"^def _sat_known_members_for_features\(",
            r"^def _sat_check_time_ok\(",
            slicer_block,
            "dataset-aware slicer functions",
        )
        changed.append("api:refresh_dataset_aware_slicer_functions")
    elif "def _sat_check_slc_ok" in src:
        src, _ = replace_block_before(
            src,
            r"^def _sat_check_slc_ok\(",
            r"^def _sat_check_time_ok\(",
            slicer_block,
            "_sat_check_slc_ok",
        )
        changed.append("api:dataset_aware_slc_ok")

    context_line = "    context = payload.context if isinstance(payload.context, dict) else {}\n"
    dw_block = (
        '    eval_dw_id = str(context.get("dw_id") or context.get("selected_dw_id") or context.get("requested_dw_id") or "")\n'
        '    if eval_dw_id:\n'
        '        query_spec["dw_id"] = eval_dw_id\n'
        '        query_spec["dataset"] = context.get("dataset") or query_spec.get("dataset")\n'
        '        qp["dw_id"] = eval_dw_id\n'
    )
    if context_line in src and 'query_spec["dw_id"] = eval_dw_id' not in src:
        src = src.replace(context_line, context_line + dw_block, 1)
        changed.append("api:eval_context_dw_id_to_query_spec")

    old_sig = 'def _evaluate_sat_formal_clauses(query_spec: Dict[str, Any], objective_id: str, mdx: str = "") -> Dict[str, Any]:'
    new_sig = 'def _evaluate_sat_formal_clauses(query_spec: Dict[str, Any], objective_id: str, mdx: str = "", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:'
    if old_sig in src:
        src = src.replace(old_sig, new_sig, 1)
        changed.append("api:formal_sat_signature_context")

    features_line = '    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})\n'
    features_context = (
        '    context = context if isinstance(context, dict) else {}\n'
        '    features["dw_id"] = str(context.get("dw_id") or query_spec.get("dw_id") or features.get("dw_id") or "")\n'
        '    features["dataset"] = str(context.get("dataset") or query_spec.get("dataset") or features.get("dataset") or "")\n'
    )
    if features_line in src and 'features["dw_id"] = str(context.get("dw_id")' not in src:
        src = src.replace(features_line, features_line + features_context, 1)
        changed.append("api:formal_sat_features_context")

    old_call = '    formal_sat_eval = _evaluate_sat_formal_clauses(query_spec, objective_id, payload.mdx)'
    new_call = '    formal_sat_eval = _evaluate_sat_formal_clauses(query_spec, objective_id, payload.mdx, context=context)'
    if old_call in src:
        src = src.replace(old_call, new_call, 1)
        changed.append("api:formal_sat_call_context")

    cache_old = '        "measures": features.get("measures"),\n    }\n    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]'
    cache_new = '        "measures": features.get("measures"),\n        "dw_id": features.get("dw_id"),\n        "dataset": features.get("dataset"),\n    }\n    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]'
    if '"dw_id": features.get("dw_id"),' not in src and cache_old in src:
        src = src.replace(cache_old, cache_new, 1)
        changed.append("api:nvac_cache_key_dw_dataset")

    payload_old = '        "measures": _contract_as_list(features.get("measures")),\n        "reason": reason,\n    }'
    payload_new = '        "measures": _contract_as_list(features.get("measures")),\n        "dw_id": str(features.get("dw_id") or ""),\n        "dataset": str(features.get("dataset") or ""),\n        "reason": reason,\n    }'
    if '"dw_id": str(features.get("dw_id") or "")' not in src and payload_old in src:
        src = src.replace(payload_old, payload_new, 1)
        changed.append("api:nvac_probe_payload_dw_dataset")

    write(api_app, src)
    return changed


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    api_app = repo / "bi-stack" / "mcad-api" / "app.py"
    if not api_app.exists():
        raise SystemExit(f"Missing {api_app}")
    changed = patch_api(api_app)
    if changed:
        print("Applied V9.5.2c fixes:")
        for item in changed:
            print(f" - {item}")
    else:
        print("V9.5.2c fixes already present; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
