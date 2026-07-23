#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SRC = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
DST = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library_runtime_feasible"

SRC_INV = SRC / "plans/campaign_a_scenario_inventory.csv"
SRC_SCEN = SRC / "scenarios"
SRC_OBJ = SRC / "objectives"

DST_SCEN = DST / "scenarios"
DST_OBJ = DST / "objectives"
DST_PLANS = DST / "plans"
DST_AUDIT = DST / "audit"

POSITIVE_STATES = {"WA", "CA", "OR"}
EXCLUDED_POSITIVE_STATES = {"BC"}

SESSION_COUNT = 3000
LENGTHS = list(range(4, 13))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def infer_state(scenario_id: str) -> str:
    for suffix in ["_wa", "_ca", "_or", "_bc"]:
        if scenario_id.endswith(suffix):
            return suffix[1:].upper()
    return "UNKNOWN"


def infer_profile(scenario_id: str) -> str:
    if scenario_id.startswith("fm_a_sales_profit_month_"):
        return "sales_profit_month"
    if scenario_id.startswith("fm_a_unit_sales_month_"):
        return "unit_sales_month"
    if scenario_id.startswith("fm_a_category_state_profitability_"):
        return "category_state_profitability"
    if scenario_id.startswith("fm_a_coverage_and_guard_mix_"):
        return "coverage_and_guard_mix"
    return "UNKNOWN"


def infer_category(scenario_id: str) -> str:
    x = scenario_id
    for prefix in [
        "fm_a_sales_profit_month_",
        "fm_a_unit_sales_month_",
        "fm_a_category_state_profitability_",
        "fm_a_coverage_and_guard_mix_",
    ]:
        if x.startswith(prefix):
            x = x[len(prefix):]
            break

    for suffix in ["_wa", "_ca", "_or", "_bc"]:
        if x.endswith(suffix):
            x = x[:-len(suffix)]
            break

    return x


def stable_query_hash(q: dict) -> str:
    import hashlib
    mdx = str(q.get("mdx") or "").strip()
    return hashlib.sha256(mdx.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    if DST.exists():
        shutil.rmtree(DST)

    DST_SCEN.mkdir(parents=True, exist_ok=True)
    DST_OBJ.mkdir(parents=True, exist_ok=True)
    DST_PLANS.mkdir(parents=True, exist_ok=True)
    DST_AUDIT.mkdir(parents=True, exist_ok=True)

    src_rows = read_csv(SRC_INV)

    kept = []
    excluded = []

    for r in src_rows:
        scenario_id = r["scenario_id"]
        state = infer_state(scenario_id)

        if state in POSITIVE_STATES:
            src_scen = ROOT / r["scenario_file"]
            src_obj = ROOT / r["objective_file"]

            dst_scen = DST_SCEN / src_scen.name
            dst_obj = DST_OBJ / src_obj.name

            shutil.copy2(src_scen, dst_scen)
            shutil.copy2(src_obj, dst_obj)

            kept.append({
                **r,
                "state": state,
                "category": infer_category(scenario_id),
                "profile": infer_profile(scenario_id),
                "scenario_file": str(dst_scen.relative_to(ROOT)),
                "objective_file": str(dst_obj.relative_to(ROOT)),
                "runtime_feasible_status": "kept_positive_target_state",
            })
        else:
            excluded.append({
                **r,
                "state": state,
                "category": infer_category(scenario_id),
                "profile": infer_profile(scenario_id),
                "runtime_feasible_status": "excluded_positive_target_state",
                "exclusion_reason": "BC is not runtime-feasible as a positive FoodMart target state",
            })

    if len(kept) != 72:
        raise SystemExit(f"[FAIL] Expected 72 kept scenarios, got {len(kept)}")

    # Build balanced 3000-session plan over 72 runtime-feasible scenarios.
    session_plan = []
    length_counts = Counter()

    for i in range(SESSION_COUNT):
        scenario = kept[i % len(kept)]
        length = LENGTHS[i % len(LENGTHS)]

        session_plan.append({
            "campaign_id": "A_foodmart_deep_runtime_feasible",
            "planned_session_index": i,
            "planned_session_id": f"A_FM_RF_{i+1:04d}",
            "scenario_id": scenario["scenario_id"],
            "objective_id": scenario["objective_id"],
            "profile": scenario["profile"],
            "category": scenario["category"],
            "state": scenario["state"],
            "planned_length": length,
            "scenario_file": scenario["scenario_file"],
            "objective_file": scenario["objective_file"],
        })

        length_counts[length] += 1

    # Audit query hashes.
    all_query_hashes = []
    within_redundant_groups = 0

    for r in kept:
        scenario_path = ROOT / r["scenario_file"]
        queries = json.loads(scenario_path.read_text(encoding="utf-8"))

        hashes = [stable_query_hash(q) for q in queries]
        local_counts = Counter(hashes)

        within_redundant_groups += sum(1 for c in local_counts.values() if c > 1)

        for h in hashes:
            all_query_hashes.append({
                "scenario_id": r["scenario_id"],
                "query_hash": h,
            })

    by_hash = Counter(x["query_hash"] for x in all_query_hashes)
    cross_duplicate_hash_count = sum(1 for _, c in by_hash.items() if c > 1)

    manifest = {
        "ok": True,
        "campaign_id": "A_foodmart_deep_runtime_feasible",
        "source_campaign_id": "A_foodmart_deep",
        "dataset_id": "foodmart",
        "positive_target_states": sorted(POSITIVE_STATES),
        "excluded_positive_target_states": sorted(EXCLUDED_POSITIVE_STATES),
        "scenario_count": len(kept),
        "objective_count": len(kept),
        "candidate_query_count": len(kept) * 12,
        "planned_session_count": len(session_plan),
        "planned_query_decision_count": sum(int(r["planned_length"]) for r in session_plan),
        "planned_length_min": min(length_counts),
        "planned_length_max": max(length_counts),
        "planned_length_mean": sum(k * v for k, v in length_counts.items()) / sum(length_counts.values()),
        "planned_length_distribution": dict(sorted(length_counts.items())),
        "excluded_scenario_count": len(excluded),
        "excluded_scenarios_by_state": dict(Counter(r["state"] for r in excluded)),
        "kept_scenarios_by_state": dict(Counter(r["state"] for r in kept)),
        "kept_scenarios_by_profile": dict(Counter(r["profile"] for r in kept)),
        "audit": {
            "cross_scenario_duplicate_hash_count_raw": cross_duplicate_hash_count,
            "within_scenario_redundant_duplicate_groups": within_redundant_groups,
            "note": "Cross-hash count is raw over copied hardened MDX; within-scenario redundancy probes are expected.",
        },
        "validation_status": "runtime_feasible_filtered_pending_batch_validation",
    }

    write_csv(DST_PLANS / "campaign_a_runtime_feasible_scenario_inventory.csv", kept)
    write_csv(DST_PLANS / "campaign_a_runtime_feasible_excluded_scenarios.csv", excluded)
    write_csv(DST_PLANS / "campaign_a_runtime_feasible_session_plan.csv", session_plan)
    write_json(DST / "manifest.json", manifest)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
