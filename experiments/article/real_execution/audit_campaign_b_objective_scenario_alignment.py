#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(x: Any) -> list:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def find_value(obj: Any, key_names: set[str]) -> list[Any]:
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in key_names:
                found.append(v)
            found.extend(find_value(v, key_names))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(find_value(v, key_names))
    return found


def objective_id_from_obj(obj: Any) -> str:
    if isinstance(obj, dict):
        for k in ("id", "objective_id", "objectiveId"):
            if obj.get(k):
                return str(obj[k])
    return ""


def scenario_id_from_obj(obj: Any, fallback: Path) -> str:
    if isinstance(obj, dict):
        for k in ("id", "scenario_id", "scenarioId", "name"):
            if obj.get(k):
                return str(obj[k])
    return fallback.stem


def extract_scenario_objective_ids(obj: Any) -> list[str]:
    vals = find_value(obj, {"objective_id", "objectiveId"})
    out = []
    for v in vals:
        if isinstance(v, str) and v:
            out.append(v)
    return sorted(set(out))


def extract_expected_decisions(obj: Any) -> dict[str, int]:
    vals = find_value(obj, {"expected_decision", "expectedDecision"})
    out = {"ALLOW": 0, "BLOCK": 0, "OTHER": 0}
    for v in vals:
        s = str(v or "").upper()
        if s in out:
            out[s] += 1
        else:
            out["OTHER"] += 1
    return out


def dataset_from_path_or_text(path: Path, obj: Any) -> str:
    s = (str(path) + " " + json.dumps(obj, ensure_ascii=False)).lower()
    if "adventure" in s or "aw_" in s:
        return "adventureworks"
    if "steel" in s or "sw_" in s:
        return "steelwheels"
    if "foodmart" in s or "food mart" in s or "fm_" in s:
        return "foodmart"
    return "unknown"


def main() -> int:
    run_id = f"campaign_b_alignment_{stamp()}"
    out_dir = ROOT / "reports" / "article_experiments" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    registry_path = ROOT / "experiments/article/real_execution/real_scenario_registry.json"
    catalog_path = ROOT / "experiments/article/real_execution/dataset_experimental_catalog.json"
    objectives_dir = ROOT / "bi-stack/objectives"

    registry = read_json(registry_path)
    catalog = read_json(catalog_path)

    objective_files = sorted(objectives_dir.glob("*.json"))
    objectives_by_id: dict[str, dict[str, Any]] = {}
    objective_inventory = []

    for p in objective_files:
        try:
            obj = read_json(p)
            oid = objective_id_from_obj(obj)
            ds = dataset_from_path_or_text(p, obj)
            objective_inventory.append({
                "dataset_inferred": ds,
                "objective_id": oid,
                "objective_file": str(p.relative_to(ROOT)),
                "ok": bool(oid),
            })
            if oid:
                objectives_by_id[oid] = {
                    "path": p,
                    "dataset": ds,
                    "object": obj,
                }
        except Exception as e:
            objective_inventory.append({
                "dataset_inferred": "unknown",
                "objective_id": "",
                "objective_file": str(p.relative_to(ROOT)),
                "ok": False,
                "error": repr(e),
            })

    scenario_rows = []
    missing_objectives = []
    dataset_backend_counts: dict[str, dict[str, int]] = {}

    for dataset, backends in registry.items():
        dataset_backend_counts.setdefault(dataset, {})
        if not isinstance(backends, dict):
            continue
        for backend, paths in backends.items():
            dataset_backend_counts[dataset].setdefault(backend, 0)
            for rel in as_list(paths):
                sp = ROOT / rel
                row_base = {
                    "dataset": dataset,
                    "backend": backend,
                    "scenario_file": str(sp.relative_to(ROOT)),
                    "scenario_file_exists": sp.exists(),
                }
                if not sp.exists():
                    scenario_rows.append({
                        **row_base,
                        "scenario_id": "",
                        "objective_ids_in_scenario": "",
                        "objective_id_matched": "",
                        "objective_file_matched": "",
                        "expected_allow_count": 0,
                        "expected_block_count": 0,
                        "status": "MISSING_SCENARIO_FILE",
                    })
                    continue

                try:
                    sobj = read_json(sp)
                    sid = scenario_id_from_obj(sobj, sp)
                    oids = extract_scenario_objective_ids(sobj)
                    dec = extract_expected_decisions(sobj)
                    dataset_backend_counts[dataset][backend] += 1

                    matched = [oid for oid in oids if oid in objectives_by_id]
                    if matched:
                        status = "OK_OBJECTIVE_MATCH"
                        oid0 = matched[0]
                        ofile = objectives_by_id[oid0]["path"]
                    else:
                        status = "NO_MATCHING_OBJECTIVE_ID"
                        oid0 = ""
                        ofile = ""

                    scenario_rows.append({
                        **row_base,
                        "scenario_id": sid,
                        "objective_ids_in_scenario": "|".join(oids),
                        "objective_id_matched": oid0,
                        "objective_file_matched": str(ofile.relative_to(ROOT)) if ofile else "",
                        "expected_allow_count": dec["ALLOW"],
                        "expected_block_count": dec["BLOCK"],
                        "status": status,
                    })

                    if not matched:
                        missing_objectives.append({
                            "dataset": dataset,
                            "backend": backend,
                            "scenario_id": sid,
                            "scenario_file": str(sp.relative_to(ROOT)),
                            "objective_ids_in_scenario": "|".join(oids),
                        })

                except Exception as e:
                    scenario_rows.append({
                        **row_base,
                        "scenario_id": "",
                        "objective_ids_in_scenario": "",
                        "objective_id_matched": "",
                        "objective_file_matched": "",
                        "expected_allow_count": 0,
                        "expected_block_count": 0,
                        "status": f"LOAD_ERROR: {e!r}",
                    })

    catalog_datasets = sorted((catalog.get("datasets") or {}).keys()) if isinstance(catalog, dict) else []

    def write_csv(name: str, rows: list[dict]) -> str:
        path = out_dir / name
        keys = sorted({k for r in rows for k in r.keys()})
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        return str(path.relative_to(ROOT))

    objective_csv = write_csv("objective_inventory.csv", objective_inventory)
    scenario_csv = write_csv("scenario_objective_alignment.csv", scenario_rows)
    missing_csv = write_csv("missing_objective_mappings.csv", missing_objectives)

    matched_count = sum(1 for r in scenario_rows if r.get("status") == "OK_OBJECTIVE_MATCH")
    scenario_count = len(scenario_rows)
    datasets_with_scenario = sorted(set(r["dataset"] for r in scenario_rows if r.get("scenario_file_exists")))

    summary = {
        "ok": scenario_count > 0 and matched_count == scenario_count and set(["foodmart", "adventureworks", "steelwheels"]).issubset(set(datasets_with_scenario)),
        "run_id": run_id,
        "registry": str(registry_path.relative_to(ROOT)),
        "catalog": str(catalog_path.relative_to(ROOT)),
        "catalog_datasets": catalog_datasets,
        "objective_file_count": len(objective_files),
        "objective_id_count": len(objectives_by_id),
        "scenario_count": scenario_count,
        "matched_scenario_objective_count": matched_count,
        "missing_objective_mapping_count": len(missing_objectives),
        "datasets_with_scenario": datasets_with_scenario,
        "dataset_backend_counts": dataset_backend_counts,
        "output_dir": str(out_dir.relative_to(ROOT)),
        "outputs": {
            "objective_inventory_csv": objective_csv,
            "scenario_objective_alignment_csv": scenario_csv,
            "missing_objective_mappings_csv": missing_csv,
            "summary_json": str((out_dir / "campaign_b_alignment_summary.json").relative_to(ROOT)),
        },
        "interpretation": (
            "This is a static B-campaign readiness audit. It does not execute queries. "
            "B should not be executed as final evidence until each selected scenario has a matching imported objective."
        ),
    }

    (out_dir / "campaign_b_alignment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
