#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "experiments/article/real_execution/article_scenario_registry.json"
SCENARIO_DIR = ROOT / "bi-stack/direct-scenarios"
OBJECTIVE_DIR = ROOT / "bi-stack/objectives"


DATASET_INFO = {
    "foodmart": {
        "domain": "Retail decision analysis",
        "cube": "Sales",
        "measures": ["Store Sales", "Store Cost", "Unit Sales", "Profit"],
        "dimensions": ["Product", "Store", "Time", "Promotion"],
        "seed": "bi-stack/direct-scenarios/foodmart_q1_q6.json"
    },
    "adventureworks": {
        "domain": "Manufacturing and sales territory analysis",
        "cube": "AdventureWorksDW",
        "measures": ["Sales Amount", "Total Product Cost", "Gross Margin", "Order Quantity"],
        "dimensions": ["Product Category", "Sales Territory", "Time", "Channel"],
        "seed": "bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"
    },
    "steelwheels": {
        "domain": "Orders, product lines and customer-country sales analysis",
        "cube": "SteelWheelsSales",
        "measures": ["Sales", "Quantity Ordered", "Orders"],
        "dimensions": ["Product Line", "Customer Country", "Office", "Time"],
        "seed": "bi-stack/direct-scenarios/steelwheels_emea_classic_cars_q1_q6.json"
    }
}


SCENARIO_META = {
    "fm_beer_wa_month_sales_profit": {
        "title": "Beer and wine monthly sales/profit in Washington",
        "grain": "month",
        "measures": ["Store Sales", "Profit"],
        "dimensions": ["Product Category", "Store State", "Time Month"],
        "allow_theme": "Beer/Wine Washington monthly sales and profit",
        "block_theme": "wrong state/category, bad grain, non-target measures"
    },
    "fm_dairy_ca_month_margin": {
        "title": "Dairy monthly margin in California",
        "grain": "month",
        "measures": ["Store Sales", "Store Cost", "Profit"],
        "dimensions": ["Product Category", "Store State", "Time Month"],
        "allow_theme": "Dairy California monthly margin",
        "block_theme": "private attributes, wrong category, yearly grain"
    },
    "fm_store_region_promotion_units": {
        "title": "Store-region promotion unit sales and cost",
        "grain": "month",
        "measures": ["Unit Sales", "Store Cost"],
        "dimensions": ["Store Region", "Promotion", "Time Month"],
        "allow_theme": "promotion and region unit-sales analysis",
        "block_theme": "customer private attributes and non-retail measures"
    },
    "fm_category_state_profitability": {
        "title": "Category/state profitability comparison",
        "grain": "category-state",
        "measures": ["Store Sales", "Store Cost", "Profit"],
        "dimensions": ["Product Category", "Store State"],
        "allow_theme": "category profitability by state",
        "block_theme": "supplier/private cost and wrong time grain"
    },
    "fm_inventory_risk_state_category": {
        "title": "Inventory-risk proxy by state and category",
        "grain": "category-state-month",
        "measures": ["Unit Sales", "Store Cost", "Profit"],
        "dimensions": ["Product Category", "Store State", "Time Month"],
        "allow_theme": "inventory-risk proxy through unit sales and cost",
        "block_theme": "marketing/private attributes and unrelated measures"
    },

    "aw_europe_bikes_month_margin": {
        "title": "Europe Bikes monthly margin",
        "grain": "month",
        "measures": ["Sales Amount", "Total Product Cost", "Gross Margin"],
        "dimensions": ["Sales Territory", "Product Category", "Time Month"],
        "allow_theme": "Europe Bikes monthly sales/cost/margin",
        "block_theme": "wrong category, wrong territory, yearly grain"
    },
    "aw_na_accessories_month_sales_quantity": {
        "title": "North America Accessories monthly sales and quantity",
        "grain": "month",
        "measures": ["Sales Amount", "Order Quantity"],
        "dimensions": ["Sales Territory", "Product Category", "Time Month"],
        "allow_theme": "North America Accessories monthly sales/quantity",
        "block_theme": "Bikes instead of Accessories, customer phone, wrong grain"
    },
    "aw_bikes_quarter_quantity_revenue": {
        "title": "Bikes quarterly quantity and revenue",
        "grain": "quarter",
        "measures": ["Order Quantity", "Sales Amount"],
        "dimensions": ["Product Category", "Sales Territory", "Time Quarter"],
        "allow_theme": "Bikes quarterly order quantity/revenue",
        "block_theme": "daily grain, employee pay rate, reseller credit limit"
    },
    "aw_channel_product_cost_month": {
        "title": "Channel/category monthly product cost",
        "grain": "month",
        "measures": ["Total Product Cost", "Sales Amount"],
        "dimensions": ["Sales Channel", "Product Category", "Time Month"],
        "allow_theme": "channel and category monthly product cost",
        "block_theme": "customer contact and reseller financial attributes"
    },
    "aw_territory_margin_variance_month": {
        "title": "Territory monthly margin variance",
        "grain": "month",
        "measures": ["Sales Amount", "Total Product Cost", "Gross Margin"],
        "dimensions": ["Sales Territory", "Time Month"],
        "allow_theme": "territory monthly margin variance",
        "block_theme": "tax detail, personal/contact attributes, wrong grain"
    },

    "sw_emea_classic_cars_month_sales_quantity": {
        "title": "EMEA Classic Cars monthly sales and quantity",
        "grain": "month",
        "measures": ["Sales", "Quantity Ordered"],
        "dimensions": ["Product Line", "Customer Country", "Time Month"],
        "allow_theme": "EMEA Classic Cars monthly sales/quantity",
        "block_theme": "wrong territory, wrong product line, bad grain"
    },
    "sw_apac_vintage_cars_2004_sales": {
        "title": "APAC Vintage Cars 2004 sales",
        "grain": "month",
        "measures": ["Sales", "Quantity Ordered"],
        "dimensions": ["Product Line", "Customer Country", "Time Month"],
        "allow_theme": "APAC Vintage Cars 2004 monthly sales",
        "block_theme": "Motorcycles, wrong region, payment check number"
    },
    "sw_na_motorcycles_2004_orders": {
        "title": "North America Motorcycles 2004 orders",
        "grain": "month",
        "measures": ["Sales", "Orders", "Quantity Ordered"],
        "dimensions": ["Product Line", "Customer Country", "Time Month"],
        "allow_theme": "NA Motorcycles 2004 order and sales volume",
        "block_theme": "Classic Cars, employee extension, customer credit limit"
    },
    "sw_office_quarter_sales_orders": {
        "title": "Office quarterly sales and orders",
        "grain": "quarter",
        "measures": ["Sales", "Orders", "Quantity Ordered"],
        "dimensions": ["Office", "Territory", "Time Quarter"],
        "allow_theme": "office-level quarterly sales/orders",
        "block_theme": "payment check number and employee extension"
    },
    "sw_customer_country_productline_mix": {
        "title": "Customer-country product-line mix",
        "grain": "country-product-line",
        "measures": ["Sales", "Orders", "Quantity Ordered"],
        "dimensions": ["Product Line", "Customer Country"],
        "allow_theme": "product-line mix by customer country",
        "block_theme": "payment identifiers, customer credit limit, wrong daily grain"
    }
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def query_list(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("queries", "items", "steps"):
            if isinstance(obj.get(key), list):
                return [x for x in obj[key] if isinstance(x, dict)]
    return []


def query_text(q: dict[str, Any]) -> str:
    return str(q.get("mdx") or q.get("query") or q.get("sql") or q.get("query_text") or "")


def expected_decision(q: dict[str, Any]) -> str:
    return str(q.get("expected_decision") or q.get("expected") or q.get("decision") or "").upper()


def normalize_queries(seed_queries: list[dict[str, Any]], scenario_id: str, objective_id: str) -> list[dict[str, Any]]:
    out = []
    for idx, src in enumerate(seed_queries, start=1):
        q = deepcopy(src)
        expected = expected_decision(q) or ("ALLOW if idx <= 2 else BLOCK")
        source_id = str(q.get("id") or q.get("query_id") or f"Q{idx}")
        logical_id = f"Q{idx:02d}_{source_id}"
        text = query_text(q)

        q.pop("dw_id", None)
        q.pop("backend_id", None)
        q["id"] = f"{scenario_id}_{logical_id}"
        q["query_id"] = f"{scenario_id}_{logical_id}"
        q["logical_query_id"] = logical_id
        q["objective_id"] = objective_id
        q["expected_decision"] = expected
        q["decision"] = expected
        q["query_type"] = str(q.get("query_type") or q.get("language") or "mdx")
        q["purpose"] = q.get("purpose") or q.get("label") or source_id
        q["backend_neutral"] = True

        if text:
            q["mdx"] = text
            q["query"] = text

        out.append(q)

    return out


def make_objective(dataset_id: str, scenario_id: str, objective_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    info = DATASET_INFO[dataset_id]
    return {
        "id": objective_id,
        "objective_id": objective_id,
        "dataset_id": dataset_id,
        "title": meta["title"],
        "description": f"Article full-real V2 objective for {meta['title']}.",
        "business_domain": info["domain"],
        "grain": meta["grain"],
        "measures": meta["measures"],
        "dimensions": meta["dimensions"],
        "allow_theme": meta["allow_theme"],
        "block_theme": meta["block_theme"],
        "article_protocol": "full_real_v2",
        "scenario_id": scenario_id,
        "backend_neutral": True,
        "validation_status": "pending_physical_execution"
    }


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    created_scenarios = []
    created_objectives = []

    for item in registry["logical_scenarios"]:
        dataset_id = item["dataset_id"]
        scenario_id = item["scenario_id"]
        objective_id = item["objective_id"]
        scenario_path = ROOT / item["scenario_path"]
        meta = SCENARIO_META[scenario_id]
        info = DATASET_INFO[dataset_id]

        seed_path = ROOT / info["seed"]
        if not seed_path.exists():
            raise SystemExit(f"[FAIL] missing seed scenario for {dataset_id}: {seed_path}")

        seed_obj = load_json(seed_path)
        seed_queries = query_list(seed_obj)
        if not seed_queries:
            raise SystemExit(f"[FAIL] seed scenario has no queries: {seed_path}")

        queries = normalize_queries(seed_queries, scenario_id, objective_id)

        scenario = {
            "id": scenario_id,
            "scenario_id": scenario_id,
            "dataset_id": dataset_id,
            "objective_id": objective_id,
            "title": meta["title"],
            "description": f"Backend-neutral article scenario: {meta['title']}. The same scenario must be executed through sql_direct and xmla_emondrian.",
            "business_domain": info["domain"],
            "cube": info["cube"],
            "grain": meta["grain"],
            "measures": meta["measures"],
            "dimensions": meta["dimensions"],
            "allow_theme": meta["allow_theme"],
            "block_theme": meta["block_theme"],
            "backend_neutral": True,
            "required_backends": ["sql_direct", "xmla_emondrian"],
            "source_seed_scenario": str(seed_path.relative_to(ROOT)),
            "validation_status": "pending_physical_execution",
            "queries": queries
        }

        objective = make_objective(dataset_id, scenario_id, objective_id, meta)

        write_json(scenario_path, scenario)
        obj_file = OBJECTIVE_DIR / f"objective_{scenario_id}.json"
        write_json(obj_file, objective)

        created_scenarios.append(str(scenario_path.relative_to(ROOT)))
        created_objectives.append(str(obj_file.relative_to(ROOT)))

    print(json.dumps({
        "created_scenarios": created_scenarios,
        "created_objectives": created_objectives,
        "scenario_count": len(created_scenarios),
        "objective_count": len(created_objectives),
        "note": "These files are backend-neutral definitions. They are not validated until executed on both sql_direct and xmla_emondrian."
    }, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
