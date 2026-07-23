#!/usr/bin/env python3
"""MCAD V9.5.2b — AdventureWorks Contract/SAT Alignment Fix.

Applies focused in-place edits to the current repository without overwriting
large accumulated app.py files.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_function(src: str, func_name: str, new_func: str) -> str:
    pattern = re.compile(rf"^def {re.escape(func_name)}\([^\n]*\)(?:\s*->[^:]+)?:\n(?:(?:    .*|\s*)\n)*?(?=^def |^@app\.|^# |\Z)", re.M)
    m = pattern.search(src)
    if not m:
        raise RuntimeError(f"Could not find function {func_name}")
    return src[:m.start()] + new_func.rstrip() + "\n\n" + src[m.end():]


def patch_proxy(proxy_app: Path) -> list[str]:
    src = read(proxy_app)
    changed: list[str] = []

    new_constraint_list = '''def _v87_constraint_list(objective: dict | None) -> list[dict]:
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
    return out'''

    if "flattening imported virtual_nodes" not in src:
        src = replace_function(src, "_v87_constraint_list", new_constraint_list)
        changed.append("proxy:_v87_constraint_list")

    new_probe_build = '''def _probe_build_query(mdx: str, cube: str | None = None) -> tuple[str, str]:
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
    return query, measure'''

    if "AdventureWorksDW\n    # does not expose Unit Sales" not in src:
        src = replace_function(src, "_probe_build_query", new_probe_build)
        changed.append("proxy:_probe_build_query")

    write(proxy_app, src)
    return changed


def patch_api(api_app: Path) -> list[str]:
    src = read(api_app)
    changed: list[str] = []

    old_payload = '''    payload = {
        "mdx": str(features.get("mdx") or ""),
        "cube": str(features.get("cube") or "Sales"),
        "slicers": features.get("slicers") if isinstance(features.get("slicers"), dict) else {},
        "group_by": _contract_as_list(features.get("group_by")),
        "measures": _contract_as_list(features.get("measures")),
        "reason": reason,
    }'''
    new_payload = '''    payload = {
        "mdx": str(features.get("mdx") or ""),
        "cube": str(features.get("cube") or "Sales"),
        "slicers": features.get("slicers") if isinstance(features.get("slicers"), dict) else {},
        "group_by": _contract_as_list(features.get("group_by")),
        "measures": _contract_as_list(features.get("measures")),
        "dw_id": str(features.get("dw_id") or ""),
        "reason": reason,
    }'''
    if old_payload in src and '"dw_id": str(features.get("dw_id") or "")' not in src:
        src = src.replace(old_payload, new_payload)
        changed.append("api:nvac_probe_dw_id")

    old_sig = 'def _evaluate_sat_formal_clauses(query_spec: Dict[str, Any], objective_id: str, mdx: str = "") -> Dict[str, Any]:'
    new_sig = 'def _evaluate_sat_formal_clauses(query_spec: Dict[str, Any], objective_id: str, mdx: str = "", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:'
    if old_sig in src:
        src = src.replace(old_sig, new_sig)
        changed.append("api:formal_sat_signature")

    old_line = '    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})\n'
    new_line = '    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})\n    context = context if isinstance(context, dict) else {}\n    features["dw_id"] = str(context.get("dw_id") or query_spec.get("dw_id") or "")\n'
    if old_line in src and 'features["dw_id"] = str(context.get("dw_id")' not in src:
        src = src.replace(old_line, new_line)
        changed.append("api:formal_sat_features_dw_id")

    old_call = '    formal_sat_eval = _evaluate_sat_formal_clauses(query_spec, objective_id, payload.mdx)'
    new_call = '    formal_sat_eval = _evaluate_sat_formal_clauses(query_spec, objective_id, payload.mdx, context=context)'
    if old_call in src:
        src = src.replace(old_call, new_call)
        changed.append("api:formal_sat_call_context")

    write(api_app, src)
    return changed


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    proxy_app = repo / "bi-stack" / "mcad-proxy" / "app.py"
    api_app = repo / "bi-stack" / "mcad-api" / "app.py"
    if not proxy_app.exists():
        raise SystemExit(f"Missing {proxy_app}")
    if not api_app.exists():
        raise SystemExit(f"Missing {api_app}")
    changed = []
    changed.extend(patch_proxy(proxy_app))
    changed.extend(patch_api(api_app))
    if changed:
        print("Applied V9.5.2b fixes:")
        for c in changed:
            print(f" - {c}")
    else:
        print("V9.5.2b fixes already present; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
