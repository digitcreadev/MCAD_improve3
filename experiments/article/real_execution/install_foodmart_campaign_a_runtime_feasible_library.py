#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library_runtime_feasible"
INV = LIB / "plans/campaign_a_runtime_feasible_scenario_inventory.csv"

BI_OBJECTIVES = ROOT / "bi-stack/objectives"
BI_SCENARIOS = ROOT / "bi-stack/direct-scenarios"

OUT = ROOT / "reports/article_experiments/foodmart_campaign_a_runtime_feasible_install"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    rows = read_csv(INV)
    installed = []

    for r in rows:
        src_obj = ROOT / r["objective_file"]
        src_scen = ROOT / r["scenario_file"]

        dst_obj = BI_OBJECTIVES / src_obj.name
        dst_scen = BI_SCENARIOS / src_scen.name

        shutil.copy2(src_obj, dst_obj)
        shutil.copy2(src_scen, dst_scen)

        installed.append({
            "scenario_id": r["scenario_id"],
            "objective_id": r["objective_id"],
            "state": r["state"],
            "profile": r["profile"],
            "category": r["category"],
            "installed_objective": str(dst_obj.relative_to(ROOT)),
            "installed_scenario": str(dst_scen.relative_to(ROOT)),
        })

    report = {
        "ok": True,
        "campaign_id": "A_foodmart_deep_runtime_feasible",
        "installed_scenario_count": len(installed),
        "installed_objective_count": len(installed),
        "installed": installed,
    }

    out = OUT / "installed_foodmart_campaign_a_runtime_feasible_library.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
