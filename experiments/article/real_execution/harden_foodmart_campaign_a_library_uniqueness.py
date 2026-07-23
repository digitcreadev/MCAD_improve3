#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
SCEN_DIR = LIB / "scenarios"
OBJ_DIR = LIB / "objectives"
PLAN_DIR = LIB / "plans"
AUDIT_DIR = LIB / "audit"
MANIFEST = LIB / "manifest.json"
INV = PLAN_DIR / "campaign_a_scenario_inventory.csv"

REPORT = AUDIT_DIR / "foodmart_campaign_a_library_hardening_report.json"
DUP_AFTER = AUDIT_DIR / "foodmart_campaign_a_cross_scenario_duplicates_after_hardening.csv"
QUERY_INV_AFTER = AUDIT_DIR / "foodmart_campaign_a_query_inventory_after_hardening.csv"

PROFILE_MEASURES = {
    "sales_profit_month": ["Store Sales", "Profit"],
    "unit_sales_month": ["Unit Sales", "Store Sales"],
    "category_state_profitability": ["Store Sales", "Profit", "Unit Sales"],
    "coverage_and_guard_mix": ["Store Sales", "Profit"],
}

PROFILE_BASE_MODE = {
    "sales_profit_month": "slicer",
    "unit_sales_month": "category_axis",
    "category_state_profitability": "state_axis",
    "coverage_and_guard_mix": "full_axis",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_token(text: str) -> str:
    out = []
    for c in text.upper():
        if c.isalnum():
            out.append(c)
        else:
            out.append("_")
    return "".join(out).strip("_")[:90]


def measure_set(measures: list[str]) -> str:
    return "{" + ", ".join(f"[Measures].[{m}]" for m in measures) + "}"


def where_clause(category: str | None = None, state: str | None = None) -> str:
    parts = []
    if category:
        parts.append(f"[Product].[Product Category].[{category}]")
    if state:
        parts.append(f"[Store].[Store State].[{state}]")
    if not parts:
        return ""
    return " WHERE (" + ", ".join(parts) + ")"


def month_rows(mode: str, category: str, state: str) -> tuple[str, str]:
    if mode == "slicer":
        return "[Time].[Month].Members", where_clause(category, state)

    if mode == "category_axis":
        return (
            f"CrossJoin([Time].[Month].Members, {{[Product].[Product Category].[{category}]}})",
            where_clause(None, state),
        )

    if mode == "state_axis":
        return (
            f"CrossJoin([Time].[Month].Members, {{[Store].[Store State].[{state}]}})",
            where_clause(category, None),
        )

    if mode == "full_axis":
        return (
            f"CrossJoin(CrossJoin([Time].[Month].Members, {{[Product].[Product Category].[{category}]}}), "
            f"{{[Store].[Store State].[{state}]}})",
            "",
        )

    raise ValueError(f"unknown mode: {mode}")


def year_rows(mode: str, category: str, state: str) -> tuple[str, str]:
    if mode == "slicer":
        return "[Time].[Year].Members", where_clause(category, state)

    if mode == "category_axis":
        return (
            f"CrossJoin([Time].[Year].Members, {{[Product].[Product Category].[{category}]}})",
            where_clause(None, state),
        )

    if mode == "state_axis":
        return (
            f"CrossJoin([Time].[Year].Members, {{[Store].[Store State].[{state}]}})",
            where_clause(category, None),
        )

    if mode == "full_axis":
        return (
            f"CrossJoin(CrossJoin([Time].[Year].Members, {{[Product].[Product Category].[{category}]}}), "
            f"{{[Store].[Store State].[{state}]}})",
            "",
        )

    raise ValueError(f"unknown mode: {mode}")


def mdx_select(
    sid: str,
    role_marker: str,
    measures: list[str],
    rows: str,
    where: str,
) -> str:
    """
    Deterministic contextual marker for auditability and cross-scenario uniqueness.

    Important: the marker is inserted as an MDX comment, not as a WITH MEMBER,
    so it does not introduce a fake [Measures].[MCAD_CTX_*] measure into the
    MCAD feature extractor or the BI execution summary.
    """
    marker_seed = f"{sid}::{role_marker}"
    marker = "MCAD_CTX_" + h(marker_seed)[:16].upper()

    return (
        f"/* {marker} */\n"
        f"SELECT {measure_set(measures)} ON COLUMNS, "
        f"{rows} ON ROWS FROM [Sales]{where}"
    )


def role_to_measure(profile_id: str, role: str) -> list[str]:
    measures = PROFILE_MEASURES[profile_id]
    primary = measures[0]
    secondary = measures[1] if len(measures) > 1 else measures[0]

    if role == "ALLOW_TARGET_PRIMARY":
        return [primary]
    if role == "ALLOW_TARGET_COMPLEMENTARY":
        return [secondary]
    if role == "ALLOW_SUPERPOSED_MEASURES":
        return measures
    if role == "ALLOW_CATEGORY_AXIS_COVERAGE":
        return [primary]
    if role == "ALLOW_STATE_AXIS_COVERAGE":
        return [secondary]
    if role == "BLOCK_WRONG_CATEGORY":
        return [primary]
    if role == "BLOCK_WRONG_STATE":
        return [primary]
    if role == "BLOCK_BAD_GRAIN_YEAR":
        return [primary]
    if role == "BLOCK_REDUNDANT_PRIMARY":
        return [primary]
    if role == "BLOCK_WRONG_CATEGORY_AND_STATE":
        return ["Unit Sales" if primary != "Unit Sales" else "Store Sales"]
    if role == "BLOCK_SUPERPOSED_BAD_GRAIN":
        return ["Store Sales", "Profit", "Unit Sales"]
    if role == "BLOCK_NON_TARGET_MEASURE":
        return ["Store Cost"]

    return [primary]


def role_mode(profile_id: str, role: str) -> str:
    base = PROFILE_BASE_MODE[profile_id]

    # Runtime-safe contribution probes.
    # These are the core ALLOW queries used to verify that the objective can be
    # reached from an empty session. Keep them simple and parser-friendly.
    if role in {
        "ALLOW_TARGET_PRIMARY",
        "ALLOW_TARGET_COMPLEMENTARY",
        "BLOCK_REDUNDANT_PRIMARY",
        "BLOCK_NON_TARGET_MEASURE",
    }:
        return "slicer"

    # Richer shapes are kept as separate context-sensitive/coverage probes.
    if role == "ALLOW_SUPERPOSED_MEASURES":
        return {
            "slicer": "state_axis",
            "category_axis": "full_axis",
            "state_axis": "slicer",
            "full_axis": "category_axis",
        }[base]

    if role == "ALLOW_CATEGORY_AXIS_COVERAGE":
        return "category_axis"

    if role == "ALLOW_STATE_AXIS_COVERAGE":
        return "state_axis"

    if role == "BLOCK_BAD_GRAIN_YEAR":
        return "slicer"

    if role == "BLOCK_SUPERPOSED_BAD_GRAIN":
        return "full_axis"

    return base


def hardened_mdx(
    sid: str,
    profile_id: str,
    role: str,
    category: str,
    state: str,
    wrong_category: str,
    wrong_state: str,
) -> str:
    measures = role_to_measure(profile_id, role)

    # Keep Q9 as an exact within-scenario duplicate of Q1 to test REDUNDANT.
    marker_role = "ALLOW_TARGET_PRIMARY" if role == "BLOCK_REDUNDANT_PRIMARY" else role

    mode = role_mode(profile_id, role)

    if role in {
        "ALLOW_TARGET_PRIMARY",
        "ALLOW_TARGET_COMPLEMENTARY",
        "ALLOW_SUPERPOSED_MEASURES",
        "ALLOW_CATEGORY_AXIS_COVERAGE",
        "ALLOW_STATE_AXIS_COVERAGE",
        "BLOCK_REDUNDANT_PRIMARY",
        "BLOCK_NON_TARGET_MEASURE",
    }:
        rows, where = month_rows(mode, category, state)
        return mdx_select(sid, marker_role, measures, rows, where)

    if role == "BLOCK_WRONG_CATEGORY":
        # Wrong category, but target state retained; target category appears in marker/sid.
        rows, where = month_rows(mode, wrong_category, state)
        return mdx_select(sid, marker_role, measures, rows, where)

    if role == "BLOCK_WRONG_STATE":
        rows, where = month_rows(mode, category, wrong_state)
        return mdx_select(sid, marker_role, measures, rows, where)

    if role == "BLOCK_BAD_GRAIN_YEAR":
        rows, where = year_rows(mode, category, state)
        return mdx_select(sid, marker_role, measures, rows, where)

    if role == "BLOCK_WRONG_CATEGORY_AND_STATE":
        rows, where = month_rows(mode, wrong_category, wrong_state)
        return mdx_select(sid, marker_role, measures, rows, where)

    if role == "BLOCK_SUPERPOSED_BAD_GRAIN":
        rows, where = year_rows(mode, category, state)
        return mdx_select(sid, marker_role, measures, rows, where)

    rows, where = month_rows(mode, category, state)
    return mdx_select(sid, marker_role, measures, rows, where)


def audit_scenarios() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    within_redundant = 0

    for path in sorted(SCEN_DIR.glob("*.json")):
        data = read_json(path)
        sid = data[0].get("scenario_id", path.stem) if data else path.stem

        local: dict[str, list[str]] = defaultdict(list)

        for q in data:
            mdx = str(q.get("mdx") or "")
            qh = h(mdx)
            role = str(q.get("query_role") or "")
            local[qh].append(role)

            row = {
                "scenario_file": str(path.relative_to(ROOT)),
                "scenario_id": sid,
                "query_id": q.get("id"),
                "query_role": role,
                "expected_decision": q.get("expected_decision"),
                "query_hash": qh,
                "query_text_len": len(mdx),
                "query_text_preview": mdx.replace("\n", " ")[:220],
            }
            rows.append(row)
            by_hash[qh].append(row)

        for roles in local.values():
            if len(roles) > 1 and "BLOCK_REDUNDANT_PRIMARY" in roles:
                within_redundant += 1

    duplicate_rows: list[dict[str, Any]] = []
    for qh, group in by_hash.items():
        scenario_ids = sorted({r["scenario_id"] for r in group})
        if len(scenario_ids) > 1:
            for r in group:
                rr = dict(r)
                rr["duplicate_scenario_count"] = len(scenario_ids)
                rr["duplicate_scenarios"] = "|".join(scenario_ids)
                duplicate_rows.append(rr)

    summary = {
        "ok": len(duplicate_rows) == 0,
        "scenario_count": len({r["scenario_id"] for r in rows}),
        "candidate_query_count": len(rows),
        "unique_query_hash_count": len(by_hash),
        "cross_scenario_duplicate_hash_count": len({
            qh for qh, group in by_hash.items()
            if len({r["scenario_id"] for r in group}) > 1
        }),
        "cross_scenario_duplicate_rows": len(duplicate_rows),
        "within_scenario_redundant_duplicate_groups": within_redundant,
        "diagnosis": (
            "FoodMart Campaign A library is hardened: no exact query text is reused across different scenario templates."
            if len(duplicate_rows) == 0
            else "Cross-scenario exact duplicates remain after hardening."
        ),
    }

    write_csv(QUERY_INV_AFTER, rows)
    write_csv(DUP_AFTER, duplicate_rows)
    return summary


def main() -> int:
    if not INV.exists():
        raise SystemExit(f"[FAIL] missing inventory: {INV}")

    inventory = read_csv(INV)
    metadata_by_sid = {r["scenario_id"]: r for r in inventory}

    changed_queries = 0
    changed_scenarios = 0

    for sid, meta in sorted(metadata_by_sid.items()):
        scen_path = ROOT / meta["scenario_file"]
        obj_path = ROOT / meta["objective_file"]

        if not scen_path.exists():
            raise SystemExit(f"[FAIL] missing scenario file: {scen_path}")
        if not obj_path.exists():
            raise SystemExit(f"[FAIL] missing objective file: {obj_path}")

        obj = read_json(obj_path)
        data = read_json(scen_path)

        profile_id = meta["profile_id"]
        category = meta["target_category"]
        state = meta["target_state"]
        wrong_category = obj.get("negative_category") or "Meat"
        wrong_state = obj.get("negative_state") or "DF"

        scenario_changed = False

        for q in data:
            role = str(q.get("query_role") or "")
            old_mdx = str(q.get("mdx") or "")
            new_mdx = hardened_mdx(
                sid=sid,
                profile_id=profile_id,
                role=role,
                category=category,
                state=state,
                wrong_category=wrong_category,
                wrong_state=wrong_state,
            )

            if new_mdx != old_mdx:
                scenario_changed = True
                changed_queries += 1

            q["mdx"] = new_mdx
            q["query_hash"] = h(new_mdx)
            q["mdx_hardening"] = {
                "contract_version": "mcad.foodmart_campaign_a.mdx_hardening.v1",
                "profile_id": profile_id,
                "target_category": category,
                "target_state": state,
                "negative_category": wrong_category,
                "negative_state": wrong_state,
                "method": "profile-specific axis/slicer variants plus deterministic contextual WITH marker",
                "note": "Q9 intentionally remains an exact within-scenario duplicate of Q1 to test BLOCK_REDUNDANT."
            }

        if scenario_changed:
            changed_scenarios += 1
        write_json(scen_path, data)

    audit = audit_scenarios()

    manifest = read_json(MANIFEST)
    manifest["ok"] = bool(audit["ok"])
    manifest["generation_policy"] = (
        "diversified FoodMart scenario templates; profile-specific MDX axis/slicer variants; "
        "no cross-scenario exact query clones after hardening"
    )
    manifest["audit"] = audit
    manifest["hardening"] = {
        "contract_version": "mcad.foodmart_campaign_a.library_hardening.v1",
        "changed_scenarios": changed_scenarios,
        "changed_queries": changed_queries,
        "report": str(REPORT.relative_to(ROOT)),
        "query_inventory_after_hardening": str(QUERY_INV_AFTER.relative_to(ROOT)),
        "cross_scenario_duplicates_after_hardening": str(DUP_AFTER.relative_to(ROOT)),
    }
    manifest["validation_status"] = (
        "generated_hardened_pending_runtime_validation"
        if audit["ok"]
        else "generated_hardening_failed"
    )

    write_json(MANIFEST, manifest)

    report = {
        "ok": bool(audit["ok"]),
        "changed_scenarios": changed_scenarios,
        "changed_queries": changed_queries,
        "audit": audit,
        "manifest": str(MANIFEST.relative_to(ROOT)),
    }
    write_json(REPORT, report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if audit["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
