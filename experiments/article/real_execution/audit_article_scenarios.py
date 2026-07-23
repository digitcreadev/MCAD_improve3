#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def queries(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("queries", "items", "steps"):
            if isinstance(obj.get(key), list):
                return [x for x in obj[key] if isinstance(x, dict)]
    return []


def expected(q: dict[str, Any]) -> str:
    return str(q.get("expected_decision") or q.get("expected") or q.get("decision") or "").upper()


def qtext(q: dict[str, Any]) -> str:
    return str(q.get("mdx") or q.get("query") or q.get("sql") or q.get("query_text") or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="experiments/article/real_execution/article_scenario_registry.json")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    registry = load_json(ROOT / args.registry)
    run_id = datetime.now(timezone.utc).strftime("article_scenario_audit_%Y%m%dT%H%M%SZ")
    out_dir = ROOT / args.out_dir if args.out_dir else ROOT / "reports/article_experiments" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    required_backends = set(registry.get("required_backends", []))
    errors = []
    warnings = []
    scenario_rows = []
    query_rows = []
    objective_owner = {}
    scenario_owner = {}
    dataset_counter = Counter()

    for item in registry.get("logical_scenarios", []):
        dataset_id = item.get("dataset_id")
        scenario_id = item.get("scenario_id")
        objective_id = item.get("objective_id")
        scenario_path = ROOT / item.get("scenario_path", "")
        backends = item.get("backends", {})

        dataset_counter[dataset_id] += 1

        if scenario_id in scenario_owner:
            errors.append(f"Duplicated scenario_id: {scenario_id}")
        scenario_owner[scenario_id] = dataset_id

        if objective_id in objective_owner and objective_owner[objective_id] != dataset_id:
            errors.append(f"Objective reused across datasets: {objective_id}")
        objective_owner[objective_id] = dataset_id

        missing_backends = sorted(required_backends - set(backends))
        if missing_backends:
            errors.append(f"{scenario_id}: missing required backends {missing_backends}")

        if not scenario_path.exists():
            errors.append(f"{scenario_id}: missing scenario file {scenario_path.relative_to(ROOT)}")
            continue

        obj = load_json(scenario_path)
        qs = queries(obj)
        if not qs:
            errors.append(f"{scenario_id}: scenario contains no queries")

        if obj.get("backend_neutral") is not True:
            errors.append(f"{scenario_id}: scenario is not marked backend_neutral=true")

        if obj.get("objective_id") != objective_id:
            errors.append(f"{scenario_id}: objective mismatch registry={objective_id}, file={obj.get('objective_id')}")

        decisions = Counter(expected(q) or "UNKNOWN" for q in qs)
        logical_ids = []
        for idx, q in enumerate(qs, start=1):
            logical_query_id = str(q.get("logical_query_id") or q.get("id") or q.get("query_id") or f"Q{idx}")
            logical_ids.append(logical_query_id)

            if q.get("dw_id") or q.get("backend_id"):
                errors.append(f"{scenario_id}/{logical_query_id}: backend-specific dw_id/backend_id must not be embedded in backend-neutral scenario")

            if expected(q) not in {"ALLOW", "BLOCK"}:
                errors.append(f"{scenario_id}/{logical_query_id}: invalid expected_decision={expected(q)}")

            if not qtext(q):
                errors.append(f"{scenario_id}/{logical_query_id}: missing query text")

            query_rows.append({
                "dataset_id": dataset_id,
                "scenario_id": scenario_id,
                "objective_id": objective_id,
                "query_index": idx,
                "logical_query_id": logical_query_id,
                "expected_decision": expected(q),
                "has_query_text": bool(qtext(q)),
                "query_text_len": len(qtext(q))
            })

        if len(logical_ids) != len(set(logical_ids)):
            errors.append(f"{scenario_id}: duplicated logical_query_id inside scenario")

        if decisions.get("ALLOW", 0) == 0 or decisions.get("BLOCK", 0) == 0:
            errors.append(f"{scenario_id}: scenario must contain both ALLOW and BLOCK queries")

        scenario_rows.append({
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "objective_id": objective_id,
            "scenario_path": str(scenario_path.relative_to(ROOT)),
            "query_count": len(qs),
            "allow_count": decisions.get("ALLOW", 0),
            "block_count": decisions.get("BLOCK", 0),
            "required_backends": ",".join(sorted(required_backends)),
            "declared_backends": ",".join(sorted(backends)),
            "backend_neutral": obj.get("backend_neutral")
        })

    summary = {
        "ok": not errors,
        "run_id": run_id,
        "scenario_count": len(scenario_rows),
        "query_count": len(query_rows),
        "dataset_scenario_counts": dict(dataset_counter),
        "errors": errors,
        "warnings": warnings,
        "note": "This audit validates backend-neutral scenario definitions. It does not execute physical backends."
    }

    write_csv(out_dir / "article_scenario_inventory.csv", scenario_rows)
    write_csv(out_dir / "article_query_inventory.csv", query_rows)
    write_json(out_dir / "article_scenario_audit_summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
