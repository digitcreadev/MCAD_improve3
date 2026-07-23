#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
PLAN = LIB / "plans/campaign_a_scenario_inventory.csv"

BI_OBJECTIVES = ROOT / "bi-stack/objectives"
BI_SCENARIOS = ROOT / "bi-stack/direct-scenarios"

OUT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample"
OUT.mkdir(parents=True, exist_ok=True)

SAMPLE_SCENARIOS = [
    "fm_a_sales_profit_month_beer_and_wine_wa",
    "fm_a_unit_sales_month_frozen_foods_ca",
    "fm_a_category_state_profitability_produce_or",
    "fm_a_coverage_and_guard_mix_beer_and_wine_wa",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    keys = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    inventory = read_csv(PLAN)
    by_sid = {r["scenario_id"]: r for r in inventory}

    missing = [sid for sid in SAMPLE_SCENARIOS if sid not in by_sid]
    if missing:
        raise SystemExit(f"[FAIL] missing sample scenarios in inventory: {missing}")

    installed = []

    for sid in SAMPLE_SCENARIOS:
        row = by_sid[sid]

        src_obj = ROOT / row["objective_file"]
        src_scen = ROOT / row["scenario_file"]

        dst_obj = BI_OBJECTIVES / src_obj.name
        dst_scen = BI_SCENARIOS / src_scen.name

        if not src_obj.exists():
            raise SystemExit(f"[FAIL] missing objective: {src_obj}")
        if not src_scen.exists():
            raise SystemExit(f"[FAIL] missing scenario: {src_scen}")

        shutil.copy2(src_obj, dst_obj)
        shutil.copy2(src_scen, dst_scen)

        installed.append({
            "scenario_id": sid,
            "objective_id": row["objective_id"],
            "complexity_level": row["complexity_level"],
            "virtual_node_depth": row["virtual_node_depth"],
            "superposition_width": row["superposition_width"],
            "target_category": row["target_category"],
            "target_state": row["target_state"],
            "installed_objective": str(dst_obj.relative_to(ROOT)),
            "installed_scenario": str(dst_scen.relative_to(ROOT)),
        })

    summary = {
        "ok": True,
        "campaign_id": "A_foodmart_deep",
        "sample_type": "runtime_smoke_sample",
        "sample_scenario_count": len(installed),
        "sample_query_count": len(installed) * 12,
        "installed": installed,
        "next_step": "Rebuild/restart mcad-api and mcad-proxy, then run runtime smoke validation."
    }

    (OUT / "installed_smoke_sample.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    write_csv(OUT / "installed_smoke_sample.csv", installed)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
