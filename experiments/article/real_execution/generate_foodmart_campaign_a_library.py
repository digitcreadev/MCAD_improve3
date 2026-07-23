#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT_ROOT = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
OBJ_DIR = OUT_ROOT / "objectives"
SCEN_DIR = OUT_ROOT / "scenarios"
PLAN_DIR = OUT_ROOT / "plans"
AUDIT_DIR = OUT_ROOT / "audit"

for d in (OBJ_DIR, SCEN_DIR, PLAN_DIR, AUDIT_DIR):
    d.mkdir(parents=True, exist_ok=True)


TARGET_CATEGORIES = [
    "Beer and Wine",
    "Dairy",
    "Produce",
    "Snack Foods",
    "Canned Foods",
    "Frozen Foods",
]

TARGET_STATES = [
    "WA",
    "CA",
    "OR",
    "BC",
]

WRONG_CATEGORIES = [
    "Meat",
    "Eggs",
    "Seafood",
    "Breakfast Foods",
    "Baking Goods",
    "Jams and Jellies",
    "Starchy Foods",
    "Carousel",
]

WRONG_STATES = [
    "DF",
    "Jalisco",
    "Veracruz",
    "Zacatecas",
    "Guerrero",
    "Yucatan",
    "Sinaloa",
    "Campeche",
]

PROFILES = [
    {
        "id": "sales_profit_month",
        "label": "monthly sales and profit",
        "target_measures": ["Store Sales", "Profit"],
        "complexity_level": 1,
        "virtual_node_depth": 1,
        "superposition_width": 1,
    },
    {
        "id": "unit_sales_month",
        "label": "monthly unit sales and sales amount",
        "target_measures": ["Unit Sales", "Store Sales"],
        "complexity_level": 2,
        "virtual_node_depth": 2,
        "superposition_width": 1,
    },
    {
        "id": "category_state_profitability",
        "label": "category/state monthly profitability",
        "target_measures": ["Store Sales", "Profit", "Unit Sales"],
        "complexity_level": 3,
        "virtual_node_depth": 2,
        "superposition_width": 2,
    },
    {
        "id": "coverage_and_guard_mix",
        "label": "coverage, redundancy and guard mix",
        "target_measures": ["Store Sales", "Profit"],
        "complexity_level": 4,
        "virtual_node_depth": 3,
        "superposition_width": 2,
    },
]


def slug(s: str) -> str:
    return (
        s.lower()
        .replace("&", "and")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )


def mdx_measure(measure: str) -> str:
    return f"[Measures].[{measure}]"


def mdx_where(category: str | None = None, state: str | None = None) -> str:
    parts = []
    if category:
        parts.append(f"[Product].[Product Category].[{category}]")
    if state:
        parts.append(f"[Store].[Store State].[{state}]")
    if not parts:
        return ""
    return " WHERE (" + ", ".join(parts) + ")"


def mdx_single_measure(measure: str, rows: str, category: str | None, state: str | None) -> str:
    return f"SELECT {{{mdx_measure(measure)}}} ON COLUMNS, {rows} ON ROWS FROM [Sales]{mdx_where(category, state)}"


def mdx_multi_measure(measures: list[str], rows: str, category: str | None, state: str | None) -> str:
    cols = ", ".join(mdx_measure(m) for m in measures)
    return f"SELECT {{{cols}}} ON COLUMNS, {rows} ON ROWS FROM [Sales]{mdx_where(category, state)}"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def objective_id(profile_id: str, category: str, state: str) -> str:
    return f"O_FM_A_{slug(profile_id).upper()}_{slug(category).upper()}_{state.upper()}"


def scenario_id(profile_id: str, category: str, state: str) -> str:
    return f"fm_a_{slug(profile_id)}_{slug(category)}_{state.lower()}"


def make_objective(profile: dict[str, Any], category: str, state: str, wrong_category: str, wrong_state: str) -> dict[str, Any]:
    oid = objective_id(profile["id"], category, state)
    sid = scenario_id(profile["id"], category, state)

    constraints = []
    for i, measure in enumerate(profile["target_measures"], start=1):
        cid = f"C_FM_A_{slug(profile['id']).upper()}_{slug(category).upper()}_{state.upper()}_{i:02d}"
        nv_id = f"NV_FM_A_{slug(profile['id']).upper()}_{slug(category).upper()}_{state.upper()}_{slug(measure).upper()}_MONTH"
        constraints.append({
            "id": cid,
            "label": f"{measure} for {category}/{state} by month",
            "measure": measure,
            "metric": measure,
            "aggregator": "SUM",
            "unit": "CURRENCY" if measure in {"Store Sales", "Profit"} else "COUNT",
            "grain": ["Time.Month"],
            "slicers": {
                "Product.Product Category": category,
                "Store.Store State": state
            },
            "requirement_sets": [[nv_id]],
            "virtual_nodes": [{
                "id": nv_id,
                "fact": "Sales",
                "measure": measure,
                "aggregator": "SUM",
                "unit": "CURRENCY" if measure in {"Store Sales", "Profit"} else "COUNT",
                "grain": ["Time.Month"],
                "slicers": {
                    "Product.Product Category": category,
                    "Store.Store State": state
                },
                "complexity_level": profile["complexity_level"],
                "virtual_node_depth": profile["virtual_node_depth"],
                "superposition_width": profile["superposition_width"]
            }],
            "weight": round(1.0 / len(profile["target_measures"]), 4)
        })

    return {
        "id": oid,
        "objective_id": oid,
        "dataset_id": "foodmart",
        "dataset": "FoodMart",
        "dw_id": "foodmart",
        "compatible_dw_ids": ["foodmart", "foodmart_sql_direct"],
        "cube": "Sales",
        "title": f"FoodMart A / {profile['label']} / {category} / {state}",
        "description": (
            f"Campaign A FoodMart deep objective targeting {profile['label']} "
            f"for category={category}, state={state}, grain=Time.Month."
        ),
        "article_protocol": "campaign_A_foodmart_deep_v1",
        "campaign_id": "A_foodmart_deep",
        "scenario_id": sid,
        "business_domain": "Retail sales and profitability analysis",
        "target_category": category,
        "target_state": state,
        "negative_category": wrong_category,
        "negative_state": wrong_state,
        "grain": "month",
        "measures": profile["target_measures"],
        "dimensions": ["Product Category", "Store State", "Time Month"],
        "complexity_level": profile["complexity_level"],
        "virtual_node_depth": profile["virtual_node_depth"],
        "superposition_width": profile["superposition_width"],
        "constraints": constraints,
        "validation_status": "pending_physical_execution",
        "generation_note": "Generated as diversified Campaign A FoodMart scenario content, not as a renamed seed template."
    }


def query_row(
    sid: str,
    oid: str,
    idx: int,
    role: str,
    expected: str,
    mdx: str,
    profile: dict[str, Any],
    category: str,
    state: str,
    reason_class: str,
) -> dict[str, Any]:
    return {
        "id": f"Q{idx:02d}_{role}",
        "logical_query_id": f"{sid}_Q{idx:02d}_{role}",
        "label": f"Q{idx:02d} — {role.replace('_', ' ').title()}",
        "scenario_id": sid,
        "objective_id": oid,
        "dw_id": "foodmart",
        "query_type": "mdx",
        "expected_decision": expected,
        "expected_reason_class": reason_class,
        "mdx": mdx,
        "article_campaign": "A_foodmart_deep",
        "dataset_id": "foodmart",
        "cube": "Sales",
        "target_category": category,
        "target_state": state,
        "query_role": role,
        "complexity_level": profile["complexity_level"],
        "virtual_node_depth": profile["virtual_node_depth"],
        "superposition_width": profile["superposition_width"],
        "generation_status": "pending_physical_validation",
        "query_hash": stable_hash(mdx)
    }


def make_scenario(profile: dict[str, Any], category: str, state: str, wrong_category: str, wrong_state: str) -> list[dict[str, Any]]:
    oid = objective_id(profile["id"], category, state)
    sid = scenario_id(profile["id"], category, state)

    month_rows = "[Time].[Month].Members"
    year_rows = "[Time].[Year].Members"
    category_rows = "CrossJoin([Time].[Month].Members, [Product].[Product Category].Members)"
    state_rows = "CrossJoin([Time].[Month].Members, [Store].[Store State].Members)"

    m1 = profile["target_measures"][0]
    m2 = profile["target_measures"][1] if len(profile["target_measures"]) > 1 else profile["target_measures"][0]
    m_all = profile["target_measures"]

    q1 = mdx_single_measure(m1, month_rows, category, state)
    q2 = mdx_single_measure(m2, month_rows, category, state)
    q3 = mdx_multi_measure(m_all, month_rows, category, state)
    q4 = mdx_single_measure(m1, category_rows, None, state)
    q5 = mdx_single_measure(m2, state_rows, category, None)
    q6 = mdx_single_measure(m1, month_rows, wrong_category, state)
    q7 = mdx_single_measure(m1, month_rows, category, wrong_state)
    q8 = mdx_single_measure(m1, year_rows, category, state)
    q9 = q1
    q10 = mdx_single_measure("Unit Sales" if m1 != "Unit Sales" else "Store Sales", month_rows, wrong_category, wrong_state)
    q11 = mdx_multi_measure(["Store Sales", "Profit", "Unit Sales"], year_rows, category, state)
    q12 = mdx_single_measure("Store Cost", month_rows, category, state)

    return [
        query_row(sid, oid, 1, "ALLOW_TARGET_PRIMARY", "ALLOW", q1, profile, category, state, "ALLOW_NEW_TOTAL"),
        query_row(sid, oid, 2, "ALLOW_TARGET_COMPLEMENTARY", "ALLOW", q2, profile, category, state, "ALLOW_NEW_TOTAL"),
        query_row(sid, oid, 3, "ALLOW_SUPERPOSED_MEASURES", "ALLOW", q3, profile, category, state, "ALLOW_NEW_TOTAL_OR_PARTIAL"),
        query_row(sid, oid, 4, "ALLOW_CATEGORY_AXIS_COVERAGE", "ALLOW", q4, profile, category, state, "ALLOW_PARTIAL_OR_TOTAL"),
        query_row(sid, oid, 5, "ALLOW_STATE_AXIS_COVERAGE", "ALLOW", q5, profile, category, state, "ALLOW_PARTIAL_OR_TOTAL"),
        query_row(sid, oid, 6, "BLOCK_WRONG_CATEGORY", "BLOCK", q6, profile, category, state, "BLOCK_OUT_OF_OBJECTIVE_SCOPE"),
        query_row(sid, oid, 7, "BLOCK_WRONG_STATE", "BLOCK", q7, profile, category, state, "BLOCK_OUT_OF_OBJECTIVE_SCOPE"),
        query_row(sid, oid, 8, "BLOCK_BAD_GRAIN_YEAR", "BLOCK", q8, profile, category, state, "BLOCK_BAD_GRAIN"),
        query_row(sid, oid, 9, "BLOCK_REDUNDANT_PRIMARY", "BLOCK", q9, profile, category, state, "BLOCK_REDUNDANT"),
        query_row(sid, oid, 10, "BLOCK_WRONG_CATEGORY_AND_STATE", "BLOCK", q10, profile, category, state, "BLOCK_OUT_OF_OBJECTIVE_SCOPE"),
        query_row(sid, oid, 11, "BLOCK_SUPERPOSED_BAD_GRAIN", "BLOCK", q11, profile, category, state, "BLOCK_BAD_GRAIN_OR_OUT_OF_SCOPE"),
        query_row(sid, oid, 12, "BLOCK_NON_TARGET_MEASURE", "BLOCK", q12, profile, category, state, "BLOCK_NON_TARGET_MEASURE"),
    ]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def build_session_plan(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lengths = []
    for length in range(4, 13):
        if length == 8:
            lengths.extend([length] * 336)
        else:
            lengths.extend([length] * 333)

    assert len(lengths) == 3000
    assert sum(lengths) == 24000

    plan = []
    for i, length in enumerate(lengths, start=1):
        s = scenarios[(i - 1) % len(scenarios)]
        selected = [f"Q{j:02d}" for j in range(1, length + 1)]
        plan.append({
            "campaign_id": "A_foodmart_deep",
            "session_instance_id": f"A_FM_S{i:04d}",
            "session_template_id": s["scenario_id"],
            "objective_id": s["objective_id"],
            "dataset_id": "foodmart",
            "dw_id": "foodmart",
            "planned_backend_id": "sql_direct",
            "planned_length": length,
            "selected_query_prefix": "|".join(selected),
            "complexity_level": s["complexity_level"],
            "virtual_node_depth": s["virtual_node_depth"],
            "superposition_width": s["superposition_width"],
            "generation_status": "planned_not_executed"
        })

    return plan


def audit_library(scenario_files: list[Path]) -> dict[str, Any]:
    rows = []
    cross_scenario_hashes: dict[str, set[str]] = {}
    within_scenario_redundant_ok = 0

    for p in scenario_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        sid = data[0]["scenario_id"] if data else p.stem
        for q in data:
            h = q["query_hash"]
            cross_scenario_hashes.setdefault(h, set()).add(sid)
            rows.append({
                "scenario_id": sid,
                "query_id": q["id"],
                "query_role": q["query_role"],
                "expected_decision": q["expected_decision"],
                "query_hash": h,
                "mdx": q["mdx"]
            })

        hashes = {}
        for q in data:
            hashes.setdefault(q["query_hash"], []).append(q["query_role"])
        for roles in hashes.values():
            if len(roles) > 1 and any("REDUNDANT" in r for r in roles):
                within_scenario_redundant_ok += 1

    cross_duplicates = {
        h: sorted(sids)
        for h, sids in cross_scenario_hashes.items()
        if len(sids) > 1
    }

    summary = {
        "ok": len(cross_duplicates) == 0,
        "scenario_count": len(scenario_files),
        "candidate_query_count": len(rows),
        "unique_query_hash_count": len(cross_scenario_hashes),
        "cross_scenario_duplicate_hash_count": len(cross_duplicates),
        "within_scenario_redundant_duplicate_groups": within_scenario_redundant_ok,
        "diagnosis": (
            "FoodMart Campaign A library is diversified: no exact query text is reused across different scenario templates."
            if not cross_duplicates
            else "Cross-scenario exact duplicates remain and must be corrected."
        )
    }

    duplicate_rows = []
    for h, sids in cross_duplicates.items():
        for sid in sids:
            duplicate_rows.append({"query_hash": h, "scenario_id": sid})

    write_csv(AUDIT_DIR / "foodmart_campaign_a_query_inventory.csv", rows)
    write_csv(AUDIT_DIR / "foodmart_campaign_a_cross_scenario_duplicates.csv", duplicate_rows)
    write_json(AUDIT_DIR / "foodmart_campaign_a_library_audit.json", summary)

    return summary


def main() -> int:
    # Clean generated library only.
    for d in (OBJ_DIR, SCEN_DIR, PLAN_DIR, AUDIT_DIR):
        for p in d.glob("*"):
            if p.is_file():
                p.unlink()

    scenario_meta: list[dict[str, Any]] = []
    scenario_files: list[Path] = []

    k = 0
    for profile in PROFILES:
        for category in TARGET_CATEGORIES:
            for state in TARGET_STATES:
                wrong_category = WRONG_CATEGORIES[k % len(WRONG_CATEGORIES)]
                wrong_state = WRONG_STATES[k % len(WRONG_STATES)]
                k += 1

                oid = objective_id(profile["id"], category, state)
                sid = scenario_id(profile["id"], category, state)

                obj = make_objective(profile, category, state, wrong_category, wrong_state)
                queries = make_scenario(profile, category, state, wrong_category, wrong_state)

                obj_path = OBJ_DIR / f"objective_{sid}.json"
                scen_path = SCEN_DIR / f"{sid}.json"

                write_json(obj_path, obj)
                write_json(scen_path, queries)

                scenario_files.append(scen_path)
                scenario_meta.append({
                    "scenario_id": sid,
                    "objective_id": oid,
                    "dataset_id": "foodmart",
                    "dw_id": "foodmart",
                    "candidate_query_count": len(queries),
                    "profile_id": profile["id"],
                    "target_category": category,
                    "target_state": state,
                    "complexity_level": profile["complexity_level"],
                    "virtual_node_depth": profile["virtual_node_depth"],
                    "superposition_width": profile["superposition_width"],
                    "objective_file": str(obj_path.relative_to(ROOT)),
                    "scenario_file": str(scen_path.relative_to(ROOT)),
                    "validation_status": "pending_physical_execution"
                })

    plan = build_session_plan(scenario_meta)
    audit = audit_library(scenario_files)

    manifest = {
        "ok": audit["ok"],
        "contract_version": "mcad.campaign_a.foodmart_deep_library.v1",
        "campaign_id": "A_foodmart_deep",
        "dataset_id": "foodmart",
        "generation_policy": "diversified FoodMart scenario templates; no cross-scenario exact query clones",
        "scenario_count": len(scenario_meta),
        "objective_count": len(scenario_meta),
        "candidate_query_count": sum(s["candidate_query_count"] for s in scenario_meta),
        "planned_session_count": len(plan),
        "planned_query_decision_count": sum(int(r["planned_length"]) for r in plan),
        "planned_length_min": min(int(r["planned_length"]) for r in plan),
        "planned_length_max": max(int(r["planned_length"]) for r in plan),
        "planned_length_mean": sum(int(r["planned_length"]) for r in plan) / len(plan),
        "profiles": PROFILES,
        "target_categories": TARGET_CATEGORIES,
        "target_states": TARGET_STATES,
        "audit": audit,
        "outputs": {
            "objectives_dir": str(OBJ_DIR.relative_to(ROOT)),
            "scenarios_dir": str(SCEN_DIR.relative_to(ROOT)),
            "session_plan": str((PLAN_DIR / "campaign_a_session_plan.csv").relative_to(ROOT)),
            "scenario_inventory": str((PLAN_DIR / "campaign_a_scenario_inventory.csv").relative_to(ROOT)),
            "audit_summary": str((AUDIT_DIR / "foodmart_campaign_a_library_audit.json").relative_to(ROOT))
        },
        "validation_status": "generated_pending_runtime_validation"
    }

    write_csv(PLAN_DIR / "campaign_a_scenario_inventory.csv", scenario_meta)
    write_csv(PLAN_DIR / "campaign_a_session_plan.csv", plan)
    write_json(OUT_ROOT / "manifest.json", manifest)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
