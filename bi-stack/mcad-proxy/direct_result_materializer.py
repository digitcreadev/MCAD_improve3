from __future__ import annotations

import re
from typing import Any


MONTHS = [
    "Jan 1998", "Feb 1998", "Mar 1998", "Apr 1998",
    "May 1998", "Jun 1998", "Jul 1998", "Aug 1998",
    "Sep 1998", "Oct 1998", "Nov 1998", "Dec 1998",
]


DEMO_SERIES = {
    "Store Sales": [4210, 4380, 4525, 4670, 4895, 5010, 4960, 5125, 5280, 5415, 5570, 5740],
    "Profit": [842, 876, 910, 934, 981, 1004, 992, 1028, 1056, 1083, 1114, 1148],
    "Unit Sales": [312, 325, 337, 348, 361, 372, 369, 381, 392, 401, 414, 427],
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_existing_table(summary: dict[str, Any]) -> dict[str, Any] | None:
    """
    Reuse rows already produced by a real executor if they exist.
    Accepted shapes:
      - {"columns": [...], "rows": [{...}, {...}]}
      - {"table": {"columns": [...], "rows": [[...], [...]]}}
      - {"data": [{...}, {...}]}
    """
    if isinstance(summary.get("rows"), list):
        rows = summary.get("rows") or []
        columns = summary.get("columns") or []
        if rows and isinstance(rows[0], dict):
            if not columns:
                columns = list(rows[0].keys())
            return {"columns": columns, "rows": rows}
        if rows and isinstance(rows[0], list):
            if not columns:
                columns = [f"C{i+1}" for i in range(len(rows[0]))]
            dict_rows = [
                {columns[i] if i < len(columns) else f"C{i+1}": v for i, v in enumerate(row)}
                for row in rows
            ]
            return {"columns": columns, "rows": dict_rows}

    table = _as_dict(summary.get("table"))
    if isinstance(table.get("rows"), list):
        rows = table.get("rows") or []
        columns = table.get("columns") or summary.get("columns") or []
        if rows and isinstance(rows[0], dict):
            if not columns:
                columns = list(rows[0].keys())
            return {"columns": columns, "rows": rows}
        if rows and isinstance(rows[0], list):
            if not columns:
                columns = [f"C{i+1}" for i in range(len(rows[0]))]
            dict_rows = [
                {columns[i] if i < len(columns) else f"C{i+1}": v for i, v in enumerate(row)}
                for row in rows
            ]
            return {"columns": columns, "rows": dict_rows}

    if isinstance(summary.get("data"), list):
        rows = summary.get("data") or []
        if rows and isinstance(rows[0], dict):
            return {"columns": list(rows[0].keys()), "rows": rows}

    return None


def _extract_measure(mdx: str) -> str:
    measures = re.findall(r"\[Measures\]\.\[([^\]]+)\]", mdx or "", flags=re.I)
    return measures[0] if measures else "Value"


def _extract_time_grain(mdx: str) -> str:
    if re.search(r"\[Time\]\.\[Month\]\.Members", mdx or "", flags=re.I):
        return "Month"
    if re.search(r"\[Time\]\.\[Year\]\.Members", mdx or "", flags=re.I):
        return "Year"
    return "Member"


def _extract_store_state(mdx: str) -> str | None:
    m = re.search(r"\[Store\]\.\[Store State\]\.\[([^\]]+)\]", mdx or "", flags=re.I)
    return m.group(1) if m else None


def _extract_product_category(mdx: str) -> str | None:
    m = re.search(r"\[Product\]\.\[Product Category\]\.\[([^\]]+)\]", mdx or "", flags=re.I)
    return m.group(1) if m else None


def _demo_rows_from_mdx(mdx: str) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Transparent fallback for the FoodMart demo path.
    This is intentionally marked as demo_materialized=true in the returned payload.
    Replace this later by real SQL/MDX execution if you connect a physical warehouse.
    """
    measure = _extract_measure(mdx)
    grain = _extract_time_grain(mdx)
    state = _extract_store_state(mdx)
    category = _extract_product_category(mdx)

    base = DEMO_SERIES.get(measure, [100 + i * 7 for i in range(12)])

    if state == "CA":
        base = [round(v * 1.18, 2) for v in base]
    elif state == "WA":
        base = [round(v, 2) for v in base]
    else:
        base = [round(v * 0.9, 2) for v in base]

    if grain == "Year":
        rows = [{
            "Year": "1998",
            measure: round(sum(base), 2),
        }]
        columns = ["Year", measure]
    else:
        rows = [
            {
                "Month": month,
                measure: value,
            }
            for month, value in zip(MONTHS, base)
        ]
        columns = ["Month", measure]

    # Add slicers as display columns, useful for Oracle BI-like table inspection.
    for row in rows:
        if category:
            row["Product Category"] = category
        if state:
            row["Store State"] = state

    columns = columns + [c for c in ["Product Category", "Store State"] if c in rows[0]]
    return columns, rows


def build_public_direct_result(
    mdx: str,
    raw_summary: Any,
    *,
    dw_id: str = "foodmart",
    query_language: str = "mdx",
) -> dict[str, Any]:
    summary = dict(raw_summary or {}) if isinstance(raw_summary, dict) else {}

    table = _normalize_existing_table(summary)

    demo_materialized = False

    status_code = summary.get("status_code")

    failed = (
        summary.get("ok") is False
        or summary.get("physical_execution") is False
        or bool(summary.get("error"))
        or (
            isinstance(status_code, int)
            and status_code >= 400
        )
    )

    normalized_dw = str(
        dw_id or ""
    ).strip().lower()

    allow_demo_materialization = (
        normalized_dw
        in {
            "foodmart",
            "foodmart_sql_direct",
        }
    )

    if (
        table is None
        and allow_demo_materialization
        and not failed
    ):
        columns, rows = _demo_rows_from_mdx(mdx)

        table = {
            "columns": columns,
            "rows": rows,
        }

        demo_materialized = True

    elif table is None:
        # Never fabricate rows for failed or
        # non-FoodMart physical executions.
        table = {
            "columns": [],
            "rows": [],
        }

    rows = table["rows"]
    columns = table["columns"]

    measure = _extract_measure(mdx)
    grain = _extract_time_grain(mdx)

    public = {
        **summary,
        "dw_id": dw_id,
        "query_language": query_language,
        "cube": summary.get("cube") or "Sales",
        "grain": summary.get("grain") or grain,
        "measures": summary.get("measures") or [measure],
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "demo_materialized": demo_materialized,
        "visualization_ready": bool(rows),
    }

    return public
