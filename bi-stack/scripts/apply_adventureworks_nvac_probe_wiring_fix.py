#!/usr/bin/env python3
"""MCAD V9.5.2e — AdventureWorks NVAC probe wiring fix.

The AdventureWorks objective/scenario import can succeed while all ALLOW
queries are still blocked by nvac_ok=false when mcad-api cannot reach the
mcad-proxy bounded /bi/nvac-probe endpoint. This script fixes the integration
wiring without changing MCAD's formal semantics:

- mcad-api default NVAC probe URL now targets mcad-proxy:9000.
- docker-compose declares MCAD_NVAC_PROBE_URL/MCAD_NVAC_MODE explicitly.
- NVAC probe cache/payload includes dw_id and dataset to avoid FoodMart/AW mix.
- backend formal_sat forwards dw_id/dataset to the optional probe callback.
- /eval passes the integration callback to evaluate_sat_formal_clauses.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def ensure_after(src: str, anchor: str, insertion: str) -> tuple[str, bool]:
    if insertion.strip() in src:
        return src, False
    if anchor not in src:
        return src, False
    return src.replace(anchor, anchor + insertion, 1), True


def patch_api_app(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"missing mcad-api app.py: {path}")
    src = read(path)
    changes: list[str] = []

    # Correct the default Docker-internal proxy port. The proxy service listens on 9000.
    if "http://mcad-proxy:8000/bi/nvac-probe" in src:
        src = src.replace("http://mcad-proxy:8000/bi/nvac-probe", "http://mcad-proxy:9000/bi/nvac-probe")
        changes.append("api:default_probe_url_9000")

    # If the current file lacks the V9.4.1 integration callback, add a compact one.
    if "def _mcad_api_call_nvac_probe" not in src:
        if "import requests" not in src:
            src = src.replace("import re\n", "import re\nimport requests\n", 1)
        if "MCAD_NVAC_PROBE_URL" not in src:
            anchor = "THRESHOLD_DEFAULT = float(os.getenv(\"MCAD_THRESHOLD_DEFAULT\", \"0.60\"))\n"
            insertion = (
                "MCAD_NVAC_MODE = str(os.getenv(\"MCAD_NVAC_MODE\", \"hybrid\")).strip().lower()\n"
                "MCAD_NVAC_PROBE_URL = str(os.getenv(\"MCAD_NVAC_PROBE_URL\", \"http://mcad-proxy:9000/bi/nvac-probe\")).strip()\n"
                "MCAD_NVAC_PROBE_TIMEOUT_S = float(os.getenv(\"MCAD_NVAC_PROBE_TIMEOUT_S\", \"5.0\"))\n"
                "_NVAC_PROBE_CACHE: Dict[str, Dict[str, Any]] = {}\n"
            )
            src, did = ensure_after(src, anchor, insertion)
            if did:
                changes.append("api:add_probe_config")
        callback = r'''

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
            out = {"probe_attempted": True, "probe_url": MCAD_NVAC_PROBE_URL, "probe_http_status": resp.status_code, "probe_error": (resp.text or "")[:500], "elapsed_ms": elapsed_ms, "non_empty": None, "count": None}
        else:
            data = resp.json() if resp.content else {}
            out = {"probe_attempted": True, "probe_url": MCAD_NVAC_PROBE_URL, "elapsed_ms": elapsed_ms, "non_empty": bool(data.get("non_empty")) if data.get("non_empty") is not None else None, "count": data.get("count"), "probe_query": data.get("probe_query"), "probe_measure": data.get("probe_measure"), "raw_probe_summary": data.get("summary"), "dw_id": data.get("dw_id")}
    except Exception as exc:
        out = {"probe_attempted": True, "probe_url": MCAD_NVAC_PROBE_URL, "probe_error": str(exc), "non_empty": None, "count": None}
    _NVAC_PROBE_CACHE[key] = dict(out)
    return out
'''
        # Place callback after canonical formal SAT import if possible, otherwise after models imports.
        marker = "# -------------------------\n# Models\n# -------------------------\n"
        if marker in src:
            src = src.replace(marker, callback + "\n" + marker, 1)
            changes.append("api:add_nvac_probe_callback")

    # Existing callback: make cache key and payload dataset-aware.
    if "def _mcad_api_nvac_probe_cache_key" in src and '"dw_id": features.get("dw_id")' not in src:
        old = '        "measures": features.get("measures") or [],\n    }'
        new = '        "measures": features.get("measures") or [],\n        "dw_id": features.get("dw_id"),\n        "dataset": features.get("dataset"),\n    }'
        if old in src:
            src = src.replace(old, new, 1)
            changes.append("api:probe_cache_dw_dataset")
    if '"dw_id": str(features.get("dw_id") or "")' not in src:
        old = '        "measures": features.get("measures") or [],\n        "reason": features.get("reason") or "static_evidence_uncertain",\n    }'
        new = '        "measures": features.get("measures") or [],\n        "dw_id": str(features.get("dw_id") or ""),\n        "dataset": str(features.get("dataset") or ""),\n        "reason": features.get("reason") or "static_evidence_uncertain",\n    }'
        if old in src:
            src = src.replace(old, new, 1)
            changes.append("api:probe_payload_dw_dataset")
        else:
            old2 = '        "measures": features.get("measures") or [],\n        "reason": reason,\n    }'
            new2 = '        "measures": features.get("measures") or [],\n        "dw_id": str(features.get("dw_id") or ""),\n        "dataset": str(features.get("dataset") or ""),\n        "reason": reason,\n    }'
            if old2 in src:
                src = src.replace(old2, new2, 1)
                changes.append("api:probe_payload_dw_dataset")

    # Ensure formal SAT is called with the callback.
    if "nvac_probe=_mcad_api_call_nvac_probe" not in src and "_evaluate_sat_formal_clauses" in src:
        # Multi-line call with query_spec, objective_id, payload.mdx.
        pat = re.compile(r"_evaluate_sat_formal_clauses\(\s*query_spec,\s*objective_id,\s*payload\.mdx\s*\)")
        src2 = pat.sub("_evaluate_sat_formal_clauses(query_spec, objective_id, payload.mdx, nvac_probe=_mcad_api_call_nvac_probe)", src, count=1)
        if src2 != src:
            src = src2
            changes.append("api:formal_sat_probe_callback")
        else:
            pat2 = re.compile(r"_evaluate_sat_formal_clauses\(\s*query_spec\s*,\s*objective_id\s*,\s*([^\)\n]+)\s*\)")
            src2 = pat2.sub(r"_evaluate_sat_formal_clauses(query_spec, objective_id, \1, nvac_probe=_mcad_api_call_nvac_probe)", src, count=1)
            if src2 != src:
                src = src2
                changes.append("api:formal_sat_probe_callback")

    write(path, src)
    return changes


def patch_backend_formal_sat(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"missing backend formal_sat.py: {path}")
    src = read(path)
    changes: list[str] = []
    # The optional probe must receive dataset/DW context.
    if '"dw_id": features.get("dw_id")' not in src:
        old = '            "measures": _contract_as_list(features.get("measures")),\n            "reason": "static_evidence_uncertain",\n        }'
        new = '            "measures": _contract_as_list(features.get("measures")),\n            "dw_id": features.get("dw_id"),\n            "dataset": features.get("dataset"),\n            "reason": "static_evidence_uncertain",\n        }'
        if old in src:
            src = src.replace(old, new, 1)
            changes.append("backend:optional_probe_features_dw_dataset")
    # Defensive: if evaluate entry has not preserved context, add it.
    marker = '    features = _contract_extract_qp_features({"query_spec": query_spec, "mdx": mdx or query_spec.get("mdx", ""), "objective_id": objective_id})\n'
    inject = (
        '    features["dw_id"] = query_spec.get("dw_id") or features.get("dw_id") or ""\n'
        '    features["dataset"] = query_spec.get("dataset") or features.get("dataset") or ""\n'
    )
    if marker in src and 'features["dw_id"] = query_spec.get("dw_id")' not in src:
        src = src.replace(marker, marker + inject, 1)
        changes.append("backend:evaluate_preserve_dw_dataset")
    write(path, src)
    return changes


def patch_compose(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"missing docker-compose.yml: {path}")
    src = read(path)
    changes: list[str] = []
    if "MCAD_NVAC_PROBE_URL" not in src:
        anchor = '      MCAD_BI_DECISION_MODE: "formal_contributive"\n'
        insertion = (
            '      MCAD_NVAC_MODE: "hybrid"\n'
            '      MCAD_NVAC_PROBE_URL: "http://mcad-proxy:9000/bi/nvac-probe"\n'
            '      MCAD_NVAC_PROBE_TIMEOUT_S: "5.0"\n'
        )
        if anchor in src:
            src = src.replace(anchor, anchor + insertion, 1)
            changes.append("compose:mcad_api_nvac_probe_env")
        else:
            # Fallback: insert under mcad-api environment after threshold.
            anchor2 = '      MCAD_THRESHOLD_DEFAULT: "0.60"\n'
            if anchor2 in src:
                src = src.replace(anchor2, anchor2 + insertion, 1)
                changes.append("compose:mcad_api_nvac_probe_env")
    else:
        if "mcad-proxy:8000/bi/nvac-probe" in src:
            src = src.replace("mcad-proxy:8000/bi/nvac-probe", "mcad-proxy:9000/bi/nvac-probe")
            changes.append("compose:probe_url_9000")
    write(path, src)
    return changes


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    changes: list[str] = []
    changes += patch_api_app(repo / "bi-stack" / "mcad-api" / "app.py")
    changes += patch_backend_formal_sat(repo / "backend" / "mcad" / "formal_sat.py")
    changes += patch_compose(repo / "bi-stack" / "docker-compose.yml")
    if changes:
        print("Applied V9.5.2e fixes:")
        for ch in changes:
            print(f" - {ch}")
    else:
        print("V9.5.2e fixes already present; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
