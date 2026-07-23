#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCENARIO_DIR = ROOT / "bi-stack/direct-scenarios"
OUT_DIR = ROOT / "reports/article_experiments/scenario_semantic_uniqueness_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_id_from_obj(obj: Any, path: Path, suffix: str = "") -> str:
    if isinstance(obj, dict):
        return str(
            obj.get("scenario_id")
            or obj.get("id")
            or obj.get("name")
            or (path.stem + suffix)
        )
    return path.stem + suffix


def dataset_from_obj(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("dataset_id") or obj.get("dataset") or obj.get("logical_dataset") or "")

    return ""


def objective_from_obj(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("objective_id") or obj.get("objective") or "")

    return ""


def scenario_objects(path: Path, obj: Any) -> list[dict[str, Any]]:
    """
    Supports:
    1) dict scenario: {"scenario_id": "...", "queries": [...]}
    2) list of query rows: [{"query_id": "...", "mdx": "..."}]
    3) list of scenario objects: [{"scenario_id": "...", "queries": [...]}, ...]
    """
    if isinstance(obj, dict):
        return [obj]

    if isinstance(obj, list):
        scenario_like_items = [
            x for x in obj
            if isinstance(x, dict)
            and any(isinstance(x.get(k), list) for k in ("queries", "steps", "items"))
        ]

        if scenario_like_items:
            return scenario_like_items

        return [{
            "scenario_id": path.stem,
            "dataset_id": "",
            "objective_id": "",
            "queries": obj,
            "_root_type": "list_of_queries"
        }]

    return [{
        "scenario_id": path.stem,
        "dataset_id": "",
        "objective_id": "",
        "queries": [],
        "_root_type": type(obj).__name__
    }]


def extract_queries(obj: dict[str, Any]) -> list[Any]:
    for key in ("queries", "steps", "items"):
        if isinstance(obj.get(key), list):
            return obj[key]
    return []


def qtext(q: Any) -> str:
    if isinstance(q, str):
        return q.strip()

    if not isinstance(q, dict):
        return ""

    return str(
        q.get("mdx")
        or q.get("query")
        or q.get("sql")
        or q.get("query_text")
        or q.get("text")
        or q.get("statement")
        or ""
    ).strip()


def qid(q: Any, idx: int) -> str:
    if isinstance(q, dict):
        return str(
            q.get("logical_query_id")
            or q.get("query_id")
            or q.get("id")
            or q.get("name")
            or f"Q{idx}"
        )
    return f"Q{idx}"


def expected(q: Any) -> str:
    if isinstance(q, dict):
        return str(q.get("expected_decision") or q.get("decision") or "").upper()
    return ""


def write_csv(path: Path, data: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in data:
        for k in r:
            if k not in keys:
                keys.append(k)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(data)


rows: list[dict[str, Any]] = []
load_errors: list[dict[str, Any]] = []
hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

for path in sorted(SCENARIO_DIR.glob("*.json")):
    try:
        root = load_json(path)
    except Exception as e:
        load_errors.append({
            "scenario_file": str(path.relative_to(ROOT)),
            "error": str(e)
        })
        continue

    for sidx, sobj in enumerate(scenario_objects(path, root), start=1):
        sid = scenario_id_from_obj(sobj, path, "" if sidx == 1 else f"__{sidx}")
        dataset_id = dataset_from_obj(sobj)
        objective_id = objective_from_obj(sobj)
        backend_neutral = bool(isinstance(sobj, dict) and sobj.get("backend_neutral") is True)

        qs = extract_queries(sobj)

        for idx, q in enumerate(qs, start=1):
            txt = qtext(q)
            if not txt:
                continue

            h = hashlib.sha256(txt.encode("utf-8")).hexdigest()

            row = {
                "scenario_file": str(path.relative_to(ROOT)),
                "scenario_id": sid,
                "dataset_id": dataset_id,
                "objective_id": objective_id,
                "backend_neutral": backend_neutral,
                "root_type": type(root).__name__,
                "query_index": idx,
                "query_id": qid(q, idx),
                "expected_decision": expected(q),
                "query_hash": h,
                "query_text_len": len(txt),
                "query_text_preview": txt.replace("\n", " ")[:180]
            }

            rows.append(row)
            hash_groups[h].append(row)

duplicate_rows: list[dict[str, Any]] = []

for h, group in hash_groups.items():
    scenario_ids = sorted({r["scenario_id"] for r in group})
    files = sorted({r["scenario_file"] for r in group})

    if len(scenario_ids) > 1 or len(files) > 1:
        for r in group:
            rr = dict(r)
            rr["duplicate_group_size"] = len(group)
            rr["duplicate_scenario_count"] = len(scenario_ids)
            rr["duplicate_file_count"] = len(files)
            rr["duplicate_scenarios"] = "|".join(scenario_ids)
            rr["duplicate_files"] = "|".join(files)
            duplicate_rows.append(rr)

summary = {
    "ok": len(duplicate_rows) == 0 and len(load_errors) == 0,
    "scenario_dir": str(SCENARIO_DIR.relative_to(ROOT)),
    "json_file_count": len(list(SCENARIO_DIR.glob("*.json"))),
    "scenario_count": len({r["scenario_id"] for r in rows}),
    "query_count": len(rows),
    "unique_query_hash_count": len(hash_groups),
    "duplicated_query_rows": len(duplicate_rows),
    "duplicate_groups": sum(
        1 for g in hash_groups.values()
        if len({r["scenario_id"] for r in g}) > 1 or len({r["scenario_file"] for r in g}) > 1
    ),
    "load_error_count": len(load_errors),
    "conclusion": (
        "No cross-scenario query duplication detected."
        if not duplicate_rows and not load_errors
        else "Some scenarios share identical query texts or some files need format review; templates must be diversified before article-scale use."
    )
}

write_csv(OUT_DIR / "scenario_query_hash_inventory.csv", rows)
write_csv(OUT_DIR / "duplicate_query_texts.csv", duplicate_rows)
write_csv(OUT_DIR / "load_errors.csv", load_errors)

(OUT_DIR / "scenario_semantic_uniqueness_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(summary, indent=2, ensure_ascii=False))

if load_errors:
    print("\n[WARN] Some JSON files could not be loaded. See load_errors.csv")

if duplicate_rows:
    print("\n[WARN] Duplicate query texts detected. See duplicate_query_texts.csv")
