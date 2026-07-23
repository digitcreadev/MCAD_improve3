#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = ROOT / "reports/article_experiments/scenario_semantic_uniqueness_audit"

INV = AUDIT_DIR / "scenario_query_hash_inventory.csv"
DUP = AUDIT_DIR / "duplicate_query_texts.csv"

OUT_SUMMARY = AUDIT_DIR / "compact_duplicate_summary.json"
OUT_GROUPS = AUDIT_DIR / "duplicate_groups_compact.csv"
OUT_SCENARIOS = AUDIT_DIR / "duplicate_by_scenario.csv"
OUT_CATEGORIES = AUDIT_DIR / "duplicate_by_category.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"[FAIL] Missing file: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def category(scenario_id: str, scenario_file: str) -> str:
    s = scenario_id or ""
    if s.startswith(("fm_", "aw_", "sw_")):
        return "generated_article_template"
    if s.startswith("demo_"):
        return "demo"
    if s in {
        "foodmart_q1_q6",
        "adventureworks_sales_margin_territory_q1_q6",
        "steelwheels_emea_classic_cars_q1_q6",
        "steelwheels_xmla_emea_classic_cars_q1_q6",
    }:
        return "seed_or_legacy"
    return "other"


inventory = read_csv(INV)
duplicates = read_csv(DUP)

for row in inventory:
    row["category"] = category(row.get("scenario_id", ""), row.get("scenario_file", ""))

for row in duplicates:
    row["category"] = category(row.get("scenario_id", ""), row.get("scenario_file", ""))

# Compact duplicate groups.
by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in duplicates:
    by_hash[row["query_hash"]].append(row)

group_rows: list[dict[str, object]] = []
for h, rows in by_hash.items():
    scenarios = sorted({r.get("scenario_id", "") for r in rows})
    files = sorted({r.get("scenario_file", "") for r in rows})
    cats = sorted({r.get("category", "") for r in rows})
    decisions = Counter(r.get("expected_decision", "") for r in rows)
    datasets = sorted({r.get("dataset_id", "") for r in rows})
    preview = next((r.get("query_text_preview", "") for r in rows if r.get("query_text_preview")), "")

    group_rows.append({
        "query_hash": h,
        "duplicate_rows": len(rows),
        "scenario_count": len(scenarios),
        "file_count": len(files),
        "datasets": "|".join(datasets),
        "categories": "|".join(cats),
        "expected_decisions": "|".join(f"{k}:{v}" for k, v in sorted(decisions.items())),
        "scenario_ids_short": "|".join(scenarios[:8]) + ("|..." if len(scenarios) > 8 else ""),
        "query_preview": preview[:160],
    })

group_rows.sort(key=lambda r: (-int(r["duplicate_rows"]), str(r["query_hash"])))

# Scenario-level summary.
by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
dup_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)

for row in inventory:
    by_scenario[row["scenario_id"]].append(row)

for row in duplicates:
    dup_by_scenario[row["scenario_id"]].append(row)

scenario_rows: list[dict[str, object]] = []
for sid, rows in sorted(by_scenario.items()):
    dup_rows = dup_by_scenario.get(sid, [])
    cat = category(sid, rows[0].get("scenario_file", ""))
    query_count = len(rows)
    duplicate_query_rows = len(dup_rows)
    scenario_rows.append({
        "scenario_id": sid,
        "category": cat,
        "dataset_id": rows[0].get("dataset_id", ""),
        "objective_id": rows[0].get("objective_id", ""),
        "query_count": query_count,
        "unique_hashes": len({r["query_hash"] for r in rows}),
        "duplicate_query_rows": duplicate_query_rows,
        "duplicate_ratio": round(duplicate_query_rows / query_count, 4) if query_count else 0,
    })

# Category-level summary.
by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
dup_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)

for row in inventory:
    by_category[row["category"]].append(row)

for row in duplicates:
    dup_by_category[row["category"]].append(row)

category_rows: list[dict[str, object]] = []
for cat, rows in sorted(by_category.items()):
    dup_rows = dup_by_category.get(cat, [])
    category_rows.append({
        "category": cat,
        "scenario_count": len({r["scenario_id"] for r in rows}),
        "query_count": len(rows),
        "unique_hashes": len({r["query_hash"] for r in rows}),
        "duplicate_query_rows": len(dup_rows),
        "duplicate_ratio": round(len(dup_rows) / len(rows), 4) if rows else 0,
    })

summary = {
    "ok_for_final_article_scenarios": False,
    "inventory_file": str(INV.relative_to(ROOT)),
    "duplicate_file": str(DUP.relative_to(ROOT)),
    "scenario_count": len({r["scenario_id"] for r in inventory}),
    "query_count": len(inventory),
    "unique_hash_count": len({r["query_hash"] for r in inventory}),
    "duplicate_group_count": len(group_rows),
    "duplicate_query_rows": len(duplicates),
    "categories": category_rows,
    "diagnosis": (
        "The UI/reporting pipeline is valid, but the current scenario library contains many exact query clones. "
        "Generated article templates must be diversified before use in the final experimental campaign."
    ),
    "recommended_policy": {
        "campaign_A": "Do not use current fm_*/aw_*/sw_* templates as final deep campaign content.",
        "campaign_B": "Use UI reports only after dataset-specific scenarios are diversified or explicitly marked as targeted demos.",
        "campaign_C": "Exact SQL/XMLA paired logical sessions are acceptable when the purpose is backend portability."
    }
}

OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
write_csv(OUT_GROUPS, group_rows)
write_csv(OUT_SCENARIOS, scenario_rows)
write_csv(OUT_CATEGORIES, category_rows)

print(json.dumps(summary, indent=2, ensure_ascii=False))

print("\n=== Top duplicate groups ===")
for row in group_rows[:12]:
    print(
        f"- rows={row['duplicate_rows']} scenarios={row['scenario_count']} "
        f"categories={row['categories']} decisions={row['expected_decisions']}"
    )
    print(f"  {row['query_preview'][:140]}")

print("\n=== By category ===")
for row in category_rows:
    print(row)
