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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def as_query_list(scenario_obj: Any) -> list[dict[str, Any]]:
    if isinstance(scenario_obj, list):
        return [q for q in scenario_obj if isinstance(q, dict)]

    if not isinstance(scenario_obj, dict):
        return []

    candidates = [
        scenario_obj.get("queries"),
        scenario_obj.get("items"),
        scenario_obj.get("steps"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [q for q in candidate if isinstance(q, dict)]

    return []


def scenario_id_from(path: Path, scenario_obj: Any) -> str:
    if isinstance(scenario_obj, dict):
        return str(
            scenario_obj.get("id")
            or scenario_obj.get("scenario_id")
            or scenario_obj.get("name")
            or path.stem
        )
    return path.stem


def query_text_from(q: dict[str, Any]) -> str:
    return str(
        q.get("mdx")
        or q.get("sql")
        or q.get("query")
        or q.get("query_text")
        or ""
    )


def normalize_expected_decision(q: dict[str, Any]) -> str:
    return str(
        q.get("expected_decision")
        or q.get("expected")
        or q.get("decision")
        or ""
    ).upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        default="experiments/article/real_execution/real_scenario_registry.json",
    )
    parser.add_argument(
        "--catalog",
        default="experiments/article/real_execution/dataset_experimental_catalog.json",
    )
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    registry_path = ROOT / args.registry
    catalog_path = ROOT / args.catalog

    if not registry_path.exists():
        raise SystemExit(f"[FAIL] missing registry: {registry_path}")
    if not catalog_path.exists():
        raise SystemExit(f"[FAIL] missing catalog: {catalog_path}")

    run_id = datetime.now(timezone.utc).strftime("real_scenario_audit_%Y%m%dT%H%M%SZ")
    out_dir = ROOT / args.out_dir if args.out_dir else ROOT / "reports" / "article_experiments" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = load_json(registry_path)
    catalog = load_json(catalog_path)

    scenario_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    query_owner: dict[str, str] = {}
    scenario_owner: dict[str, str] = {}

    for dataset_id, backends in registry.items():
        if dataset_id not in catalog.get("datasets", {}):
            errors.append(f"Dataset {dataset_id} exists in scenario registry but not in dataset catalog.")

        for backend_id, scenario_paths in backends.items():
            if not isinstance(scenario_paths, list):
                errors.append(f"{dataset_id}/{backend_id} scenario list is not a list.")
                continue

            for rel_path in scenario_paths:
                scenario_path = ROOT / rel_path
                exists = scenario_path.exists()

                if not exists:
                    errors.append(f"Missing scenario file: {rel_path}")
                    scenario_rows.append({
                        "dataset_id": dataset_id,
                        "backend_id": backend_id,
                        "scenario_path": rel_path,
                        "scenario_id": "",
                        "exists": False,
                        "query_count": 0,
                        "allow_count": 0,
                        "block_count": 0,
                        "unknown_decision_count": 0,
                    })
                    continue

                try:
                    scenario_obj = load_json(scenario_path)
                except Exception as exc:
                    errors.append(f"Invalid JSON in {rel_path}: {exc}")
                    continue

                scenario_id = scenario_id_from(scenario_path, scenario_obj)
                queries = as_query_list(scenario_obj)

                if scenario_id in scenario_owner and scenario_owner[scenario_id] != dataset_id:
                    errors.append(
                        f"Scenario id reused across datasets: {scenario_id} "
                        f"({scenario_owner[scenario_id]} and {dataset_id})"
                    )
                scenario_owner[scenario_id] = dataset_id

                decision_counter = Counter()
                for idx, q in enumerate(queries, start=1):
                    qid = str(q.get("id") or q.get("query_id") or f"{scenario_id}_Q{idx}")
                    expected = normalize_expected_decision(q)
                    decision_counter[expected or "UNKNOWN"] += 1

                    qtext = query_text_from(q)
                    objective_id = str(
                        q.get("objective_id")
                        or (scenario_obj.get("objective_id") if isinstance(scenario_obj, dict) else "")
                        or ""
                    )
                    dw_id = str(
                        q.get("dw_id")
                        or (scenario_obj.get("dw_id") if isinstance(scenario_obj, dict) else "")
                        or ""
                    )

                    if qid in query_owner and query_owner[qid] != dataset_id:
                        errors.append(
                            f"Physical query id reused across datasets: {qid} "
                            f"({query_owner[qid]} and {dataset_id})"
                        )
                    query_owner[qid] = dataset_id

                    if expected not in {"ALLOW", "BLOCK"}:
                        warnings.append(f"{rel_path} query {qid}: missing or invalid expected decision: {expected!r}")

                    if not qtext:
                        warnings.append(f"{rel_path} query {qid}: missing query text.")

                    query_rows.append({
                        "dataset_id": dataset_id,
                        "backend_id": backend_id,
                        "scenario_id": scenario_id,
                        "scenario_path": rel_path,
                        "query_index": idx,
                        "query_id": qid,
                        "expected_decision": expected,
                        "objective_id": objective_id,
                        "dw_id": dw_id,
                        "query_type": str(q.get("query_type") or q.get("language") or ""),
                        "has_query_text": bool(qtext),
                        "query_text_len": len(qtext),
                    })

                scenario_rows.append({
                    "dataset_id": dataset_id,
                    "backend_id": backend_id,
                    "scenario_path": rel_path,
                    "scenario_id": scenario_id,
                    "exists": True,
                    "query_count": len(queries),
                    "allow_count": decision_counter.get("ALLOW", 0),
                    "block_count": decision_counter.get("BLOCK", 0),
                    "unknown_decision_count": decision_counter.get("UNKNOWN", 0),
                })

                if len(queries) == 0:
                    errors.append(f"Scenario has no queries: {rel_path}")

    dataset_counts = defaultdict(lambda: {"scenarios": 0, "queries": 0, "allow": 0, "block": 0})
    for row in scenario_rows:
        ds = row["dataset_id"]
        dataset_counts[ds]["scenarios"] += 1
        dataset_counts[ds]["queries"] += int(row["query_count"])
        dataset_counts[ds]["allow"] += int(row["allow_count"])
        dataset_counts[ds]["block"] += int(row["block_count"])

    objective_rows: list[dict[str, Any]] = []
    for dataset_id, ds in catalog.get("datasets", {}).items():
        for obj in ds.get("objectives", []):
            objective_rows.append({
                "dataset_id": dataset_id,
                "objective_id": obj.get("id"),
                "title": obj.get("title"),
                "grain": obj.get("grain"),
                "measure_count": len(obj.get("measures", [])),
                "dimension_count": len(obj.get("dimensions", [])),
            })

    summary = {
        "ok": not errors,
        "run_id": run_id,
        "registry": args.registry,
        "catalog": args.catalog,
        "scenario_count": len(scenario_rows),
        "query_count": len(query_rows),
        "dataset_counts": dict(dataset_counts),
        "errors": errors,
        "warnings": warnings,
        "output_dir": str(out_dir),
        "note": (
            "This is a static scenario/catalog audit. It does not execute physical "
            "queries yet. It validates whether the available scenario files can be "
            "used as dataset-specific physical query catalogs."
        ),
    }

    write_csv(out_dir / "real_scenario_inventory.csv", scenario_rows)
    write_csv(out_dir / "real_query_inventory.csv", query_rows)
    write_csv(out_dir / "dataset_objective_inventory.csv", objective_rows)
    write_json(out_dir / "real_scenario_audit_summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
