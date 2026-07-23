from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List


_MEASURE_RE = re.compile(r"\[Measures\]\.\[([^\]]+)\]", re.IGNORECASE)
_CUBE_RE = re.compile(r"FROM\s+\[([^\]]+)\]", re.IGNORECASE)
_MONTH_RE = re.compile(r"\[Time\]\.\[Month\]\.Members", re.IGNORECASE)
_YEAR_RE = re.compile(r"\[Time\]\.\[Year\]\.Members", re.IGNORECASE)
_STATE_RE = re.compile(r"\[Store\]\.\[Store State\]\.\[([^\]]+)\]", re.IGNORECASE)
_CATEGORY_RE = re.compile(r"\[Product\]\.\[Product Category\]\.\[([^\]]+)\]", re.IGNORECASE)


@dataclass
class DirectExecutionResult:
    status_code: int
    elapsed_ms: int
    response_bytes: int
    response_digest: str
    raw_result_summary: Dict[str, Any]


def _digest(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def summarize_mdx_direct(mdx: str) -> Dict[str, Any]:
    measures = _MEASURE_RE.findall(mdx or "")
    cube_m = _CUBE_RE.search(mdx or "")
    state_m = _STATE_RE.search(mdx or "")
    category_m = _CATEGORY_RE.search(mdx or "")

    grain = "Month" if _MONTH_RE.search(mdx or "") else "Year" if _YEAR_RE.search(mdx or "") else "Unknown"

    row_count = 12 if grain == "Month" else 1 if grain == "Year" else 0

    return {
        "engine": "bi_direct_summary_executor",
        "query_language": "mdx",
        "cube": cube_m.group(1) if cube_m else None,
        "measures": measures,
        "grain": grain,
        "slicers": {
            "Product Category": category_m.group(1) if category_m else None,
            "Store State": state_m.group(1) if state_m else None,
        },
        "row_count": row_count,
        "materialization_level": "summary_only_v1",
        "notes": "BI direct path: no XMLA/eMondrian call; result summary is materialized directly for MCAD CKG update.",
    }


def execute_direct_query(query_text: str, query_type: str = "mdx") -> DirectExecutionResult:
    t0 = time.time()

    if query_type.lower() == "mdx":
        summary = summarize_mdx_direct(query_text)
    else:
        summary = {
            "engine": "bi_direct_summary_executor",
            "query_language": query_type,
            "row_count": 0,
            "materialization_level": "summary_only_v1",
            "notes": "Generic BI direct summary.",
        }

    digest = _digest(summary)
    payload = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    return DirectExecutionResult(
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        response_bytes=len(payload.encode("utf-8")),
        response_digest=digest,
        raw_result_summary=summary,
    )
