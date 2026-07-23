#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
INV = LIB / "plans/campaign_a_scenario_inventory.csv"

BI_OBJECTIVES = ROOT / "bi-stack/objectives"
BI_SCENARIOS = ROOT / "bi-stack/direct-scenarios"

OUT = ROOT / "reports/article_experiments/foodmart_campaign_a_full_install"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    rows = read_csv(INV)
    installed = []

    for r in rows:
        src_obj = ROOT / r["objective_file"]
        src_scen = ROOT / r["scenario_file"]

        dst_obj = BI_OBJECTIVES / src_obj.name
        dst_scen = BI_SCENARIOS / src_scen.name

        if not src_obj.exists():
            raise SystemExit(f"[FAIL] missing objective: {src_obj}")
        if not src_scen.exists():
            raise SystemExit(f"[FAIL] missing scenario: {src_scen}")

        shutil.copy2(src_obj, dst_obj)
        shutil.copy2(src_scen, dst_scen)

        installed.append({
            "scenario_id": r["scenario_id"],
            "objective_id": r["objective_id"],
            "installed_objective": str(dst_obj.relative_to(ROOT)),
            "installed_scenario": str(dst_scen.relative_to(ROOT)),
        })

    summary = {
        "ok": True,
        "campaign_id": "A_foodmart_deep",
        "installed_scenario_count": len(installed),
        "installed_objective_count": len(installed),
        "installed": installed,
    }

    write_json(OUT / "installed_foodmart_campaign_a_full_library.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
