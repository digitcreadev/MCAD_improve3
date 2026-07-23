#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = os.environ.get("MCAD_BASE_URL", "http://localhost:9000").rstrip("/")
DW_ID = os.environ.get("MCAD_SMOKE_DW_ID", "foodmart")

INSTALLED = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample/installed_smoke_sample.json"

RUN_ID = datetime.now(timezone.utc).strftime("foodmart_campaign_a_smoke_v2_%Y%m%dT%H%M%SZ")
OUT_DIR = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_runtime" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Session-safe smoke roles:
# Q01/Q02 validate positive contribution.
# Q06/Q07/Q08/Q09/Q12 validate guarded blocking.
SELECTED_ROLES = {
    "ALLOW_TARGET_PRIMARY",
    "ALLOW_TARGET_COMPLEMENTARY",
    "BLOCK_WRONG_CATEGORY",
    "BLOCK_WRONG_STATE",
    "BLOCK_BAD_GRAIN_YEAR",
    "BLOCK_REDUNDANT_PRIMARY",
    "BLOCK_NON_TARGET_MEASURE",
}


def http_json(method: str, path: str, payload: Any | None = None, timeout: int = 240) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", errors="replace")
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(txt)
        except Exception:
            body = {"raw": txt[:2000]}
        return {"ok": False, "http_error": e.code, "body": body}


def find_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
        for v in obj.values():
            found = find_key(v, key)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found not in (None, ""):
                return found
    return None


def norm_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def extract_fields(resp: dict) -> dict[str, Any]:
    d = resp.get("decision") if isinstance(resp.get("decision"), dict) else {}

    decision = str(
        d.get("decision")
        or find_key(resp, "decision")
        or ""
    ).upper()

    reason = (
        d.get("decision_reason_code")
        or d.get("reason_code")
        or d.get("reason")
        or find_key(resp, "reason_code")
        or find_key(resp, "reason")
        or ""
    )

    status_code = find_key(resp, "status_code")
    execution_path = find_key(resp, "execution_path")
    adapter_id = find_key(resp, "adapter_id")
    response_digest = find_key(resp, "response_digest") or find_key(resp, "result_digest")

    physical = norm_bool(find_key(resp, "physical_execution"))
    if physical is None:
        physical = bool(
            decision == "ALLOW"
            and str(status_code) == "200"
            and (execution_path or adapter_id or response_digest)
        )

    blocked_before = norm_bool(find_key(resp, "blocked_before_execution"))
    if blocked_before is None:
        blocked_before = bool(decision == "BLOCK" and physical is False)

    return {
        "decision": decision,
        "reason": reason,
        "phi": d.get("phi"),
        "sat": d.get("sat"),
        "real": d.get("real"),
        "ceval": d.get("ceval"),
        "physical_execution": physical,
        "blocked_before_execution": blocked_before,
        "execution_path": execution_path,
        "adapter_id": adapter_id,
        "status_code": status_code,
        "elapsed_ms": find_key(resp, "elapsed_ms"),
        "response_digest": response_digest,
    }


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    installed = json.loads(INSTALLED.read_text(encoding="utf-8"))

    rows = []
    mismatches = []

    for sample in installed["installed"]:
        scenario_id = sample["scenario_id"]
        objective_id = sample["objective_id"]
        scenario_path = ROOT / sample["installed_scenario"]

        queries = json.loads(scenario_path.read_text(encoding="utf-8"))
        selected = [q for q in queries if q.get("query_role") in SELECTED_ROLES]

        session = http_json(
            "POST",
            "/mcad/session/new",
            {"objective_id": objective_id, "dw_id": DW_ID},
            timeout=90,
        )

        session_id = (
            session.get("active", {}).get("session_id")
            or session.get("session", {}).get("session_id")
            or session.get("session_id")
            or ""
        )

        for q in selected:
            query_id = q.get("logical_query_id") or q.get("id")
            expected = str(q.get("expected_decision") or "").upper()

            payload = {
                "mdx": q.get("mdx"),
                "query_type": "mdx",
                "query_id": query_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "dw_id": DW_ID,
                "scenario_id": scenario_id,
                "source_scenario_id": scenario_id,
                "scenario_query_id": query_id,
                "scenario_query_index": q.get("id"),
                "scenario_source": "campaign_a_smoke_runtime_v2",
                "execution_mode": "campaign_a_smoke_runtime_v2",
                "allow_fallback": False,
            }

            t0 = time.time()
            resp = http_json("POST", "/bi/execute", payload, timeout=300)
            client_elapsed_ms = int((time.time() - t0) * 1000)

            fields = extract_fields(resp)
            decision = fields["decision"]
            reason = str(fields["reason"] or "")

            strict_match = expected == decision

            # Session-aware acceptance:
            # An ALLOW candidate can become BLOCK_REDUNDANT after prior coverage.
            session_context_match = strict_match or (
                expected == "ALLOW"
                and decision == "BLOCK"
                and reason.startswith("BLOCK_REDUNDANT")
            )

            row = {
                "run_id": RUN_ID,
                "campaign_id": "A_foodmart_deep",
                "scenario_id": scenario_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "dw_id": DW_ID,
                "query_id": query_id,
                "query_role": q.get("query_role"),
                "expected_decision": expected,
                "decision": decision,
                "strict_match": strict_match,
                "session_context_match": session_context_match,
                "reason": reason,
                "physical_execution": fields["physical_execution"],
                "blocked_before_execution": fields["blocked_before_execution"],
                "execution_path": fields["execution_path"],
                "adapter_id": fields["adapter_id"],
                "status_code": fields["status_code"],
                "elapsed_ms": fields["elapsed_ms"],
                "client_elapsed_ms": client_elapsed_ms,
                "response_digest": fields["response_digest"],
                "phi": fields["phi"],
                "sat": fields["sat"],
                "real": fields["real"],
                "ceval": fields["ceval"],
                "http_error": resp.get("http_error"),
            }

            rows.append(row)

            raw = OUT_DIR / "raw" / f"{scenario_id}_{q.get('id')}.json"
            write_json(raw, resp)

            if not session_context_match:
                mismatches.append(row)

            print(
                f"{scenario_id} {q.get('id')} expected={expected} "
                f"decision={decision} strict={strict_match} "
                f"context={session_context_match} reason={reason}"
            )

    total = len(rows)
    strict = sum(1 for r in rows if r["strict_match"])
    contextual = sum(1 for r in rows if r["session_context_match"])

    summary = {
        "ok": total > 0 and contextual == total and sum(1 for r in rows if r.get("http_error")) == 0,
        "run_id": RUN_ID,
        "campaign_id": "A_foodmart_deep",
        "dw_id": DW_ID,
        "sample_scenario_count": len(installed["installed"]),
        "executed_query_count": total,
        "strict_match_count": strict,
        "strict_match_rate": strict / total if total else 0.0,
        "session_context_match_count": contextual,
        "session_context_match_rate": contextual / total if total else 0.0,
        "allow_count": sum(1 for r in rows if r["decision"] == "ALLOW"),
        "block_count": sum(1 for r in rows if r["decision"] == "BLOCK"),
        "physical_execution_count": sum(1 for r in rows if r["physical_execution"] is True),
        "blocked_before_execution_count": sum(1 for r in rows if r["blocked_before_execution"] is True),
        "http_error_count": sum(1 for r in rows if r.get("http_error")),
        "mismatch_count": len(mismatches),
        "output_dir": str(OUT_DIR.relative_to(ROOT)),
    }

    write_csv(OUT_DIR / "foodmart_campaign_a_smoke_v2_by_query.csv", rows)
    write_csv(OUT_DIR / "foodmart_campaign_a_smoke_v2_mismatches.csv", mismatches)
    write_json(OUT_DIR / "foodmart_campaign_a_smoke_v2_summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
